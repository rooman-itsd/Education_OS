"""The merged adapters plug into the hub. Each is found through the hub's own registry (the
`eos.integration_adapters` entry point and describe()), and one mock-mode operation of its port runs through
`invoke`, the path every module uses, on a connection made through the hub's API.

An adapter that is installed is used as installed. One that is not (this suite runs in the hub's own environment) is
registered from the repository for the test: its src/ goes on sys.path and its entry point is declared in a
dist-info of its own, so discovery goes through the registry unchanged. An adapter that cannot be imported here is
skipped."""

from __future__ import annotations

import importlib
import importlib.metadata as metadata
import sys
import tomllib
import uuid
from pathlib import Path

import pytest
from hub_support import BASE, put_credential

REPO = Path(__file__).resolve().parents[4]
GROUP = "eos.integration_adapters"

PERSON = "5b0e4a7e-58d4-4c39-8a1b-4f4b8b1f2c01"

# adapter -> (provider, port, operation, input): one mock-mode operation per port, through invoke
CASES = {
    "digilocker": ("digilocker", "certificate-issuance", "get_issuance", {"issuance_key": "compat-1"}),
    "nad": (
        "nad",
        "academic-records",
        "verify_learner_id",
        {
            "learner": {
                "person_id": PERSON,
                "apaar_id": "123456789012",
                "name": "Riya Sharma",
                "date_of_birth": "2004-05-06",
            }
        },
    ),
    "government-portals": ("aishe", "regulatory-submission", "list_forms", {}),
    "external-university-portals": ("file", "inter-institution-records", "list_partners", {}),
    "video-conferencing": (
        "jitsi",
        "meetings",
        "create_meeting",
        {
            "meeting_key": "compat-class-1",
            "title": "Compatibility check",
            "starts_at": "2026-11-10T09:00:00+00:00",
            "duration_minutes": 30,
            "host": {"person_id": PERSON, "display_name": "Host", "email": "host@example.com"},
        },
    ),
    "wearables": ("strava", "wearable-data", "link_status", {"person_ids": [PERSON]}),
}
# The connection settings each provider's settings_schema requires.
SETTINGS = {
    "digilocker": {"issuer_id": "in.example.compat"},
    "external-university-portals": {"partner_id": "compat-partner", "country": "GB", "channel": "download"},
    "video-conferencing": {"base_url": "https://meet.example.test", "app_id": "compat-app"},
}
# get_issuance of a key nothing was issued under: DigiLocker's mock answers not_found. That shows the call reached the
# adapter (through its operation-first invoke dispatcher, which validates the context with pydantic) and came back
# in the contract's vocabulary.
EXPECTED_ERROR = {"digilocker": "not_found"}
# Adapters that refused any context but their own class. Each is fixed in its own PR; with the fix they pass here.
NEEDS_FIX = {"government-portals": "#585", "external-university-portals": "#586"}


def _entry_point(adapter: str) -> str | None:
    pyproject = REPO / "integrations" / adapter / "pyproject.toml"
    if not pyproject.is_file():
        return None
    project = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
    return project.get("entry-points", {}).get(GROUP, {}).get(adapter)


@pytest.fixture(scope="module")
def adapters(tmp_path_factory):
    """{adapter: entry point value} for every adapter importable here, each findable on the entry point group."""
    installed = {ep.name for ep in metadata.entry_points(group=GROUP)}
    dist_root = tmp_path_factory.mktemp("adapter-dists")
    found: dict[str, str] = {}
    added: list[str] = []
    for adapter in CASES:
        value = _entry_point(adapter)
        if value is None:
            continue
        if adapter not in installed:
            src = REPO / "integrations" / adapter / "src"
            if str(src) not in sys.path:
                sys.path.insert(0, str(src))
                added.append(str(src))
            dist = dist_root / f"eos_compat_{adapter.replace('-', '_')}-0.0.0.dist-info"
            dist.mkdir()
            (dist / "METADATA").write_text(f"Metadata-Version: 2.1\nName: eos-compat-{adapter}\nVersion: 0.0.0\n")
            (dist / "entry_points.txt").write_text(f"[{GROUP}]\n{adapter} = {value}\n")
        try:
            importlib.import_module(value.split(":")[0])
        except Exception:  # noqa: BLE001 - not importable in this environment: that adapter is skipped
            continue
        found[adapter] = value
    sys.path.insert(0, str(dist_root))
    importlib.invalidate_caches()
    # the adapters' own tables (several keep state of their own), next to the hub's in the test database
    from eos_core.db import Base, engine

    Base.metadata.create_all(engine)
    yield found
    sys.path.remove(str(dist_root))
    for path in added:
        sys.path.remove(path)
    importlib.invalidate_caches()


@pytest.fixture
def registry_of(adapters, monkeypatch):
    from eos_integration_hub.infrastructure import registry

    monkeypatch.setenv("INTEGRATION_HUB_ADAPTERS", ",".join(adapters))
    registry.reset_cache()
    yield registry.get_registry()
    registry.reset_cache()


def _need(adapters, adapter):
    if adapter not in adapters:
        pytest.skip(f"{adapter} is not importable here")


@pytest.mark.parametrize("adapter", sorted(CASES))
def test_the_hub_registry_loads_the_adapter_from_its_describe(adapters, registry_of, adapter, client, super_admin):
    _need(adapters, adapter)
    info = registry_of.get(adapter)
    assert info is not None and adapter not in registry_of.skipped, registry_of.skipped
    provider, port, _op, _input = CASES[adapter]
    assert port in [p for p, _v in info.ports]
    assert info.provider(provider) is not None and port in info.provider(provider).ports
    assert "mock" in info.provider(provider).modes
    listed = client.get(f"{BASE}/adapters", headers=super_admin.headers).json()["items"]
    assert adapter in {a["adapter"] for a in listed}


@pytest.mark.parametrize("adapter", sorted(CASES))
def test_one_mock_operation_per_port_runs_through_invoke(adapters, registry_of, adapter, client, org):
    from eos_integration_hub.application.invoke import invoke

    _need(adapters, adapter)
    provider, port, operation, payload = CASES[adapter]
    info = registry_of.get(adapter).provider(provider)
    r = client.post(
        f"{BASE}/connections",
        json={
            "adapter": adapter,
            "provider": provider,
            "port": port,
            "mode": "mock",
            "settings": SETTINGS.get(adapter, {}),
        },
        headers=org.admin,
    )
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for name in info.credential_names:
        put_credential(client, org, cid, name, f"compat-{name}-{uuid.uuid4().hex[:6]}")
    r = client.post(f"{BASE}/connections/{cid}/enable", headers=org.admin)
    assert r.status_code == 200, r.text
    out = invoke(
        port=port,
        operation=operation,
        input=payload,
        idempotency_key=f"compat:{adapter}",
        caller_module="integration-hub",
        organisation_id=org.id,
    )
    error = out["error"] or {}
    if adapter in NEEDS_FIX and error.get("detail") == "missing context":
        pytest.xfail(f"{adapter} refuses the hub's context until {NEEDS_FIX[adapter]} merges")
    expected = EXPECTED_ERROR.get(adapter)
    if expected:  # the adapter ran and gave the contract's answer for this input
        assert out["status"] == "failed" and error["code"] == expected, out
    else:
        assert out["status"] == "succeeded" and out["error"] is None, out


# ------------------------------------------------------------------ the calling shapes the merged adapters use


def test_the_hub_calls_each_shape_the_adapters_use():
    """Methods that take the input as one argument or as keyword arguments, and an operation-first dispatcher for
    whatever has no method. The context is a real mapping, so a pydantic model validates it as a dict."""
    from eos_integration_hub.infrastructure.registry import AdapterContext, call, describe_adapter
    from pydantic import BaseModel

    class Ctx(BaseModel):
        organisation_id: str
        mode: str

    class Shapes:
        def describe(self):
            return {"adapter": "shapes", "ports": [{"port": "regulatory-submission", "version": 1}], "providers": []}

        def validate(self, ctx, *, form_code, period, data=None):  # keyword arguments
            return {"output": {"form_code": form_code, "period": period, "org": ctx.organisation_id}}

        def list_forms(self, ctx):  # no input
            return {"output": {"items": []}}

        def invoke(self, operation, context, input=None):  # noqa: A002 - operation first, for everything else
            return {"output": {"op": operation, "mode": Ctx.model_validate(context).mode, "input": input}}

    info = describe_adapter("shapes", Shapes())
    ctx = AdapterContext(organisation_id="o-1", connection_id="c-1", provider="p", mode="mock")
    assert dict(ctx)["organisation_id"] == "o-1" and ctx["mode"] == "mock" and len(ctx) == len(dict(ctx))
    got = call(info, "validate", ctx, {"form_code": "F", "period": "2025"}, timeout_s=5, port_operation=True)
    assert got.output == {"form_code": "F", "period": "2025", "org": "o-1"}
    assert call(info, "validate", ctx, {"form_code": "F"}, timeout_s=5).error_code == "invalid_request"  # missing
    extra = call(info, "validate", ctx, {"form_code": "F", "period": "p", "x": 1}, timeout_s=5)
    assert extra.error_code == "invalid_request"  # a field the operation does not take
    assert call(info, "list_forms", ctx, {}, timeout_s=5).output == {"items": []}
    got = call(info, "healthcheck", ctx, None, timeout_s=5)  # an adapter.yaml operation, through the dispatcher
    assert got.output == {"op": "healthcheck", "mode": "mock", "input": {}}
    got = call(info, "submit", ctx, {"package_id": "k"}, timeout_s=5, port_operation=True)
    assert got.output["op"] == "submit" and got.output["input"] == {"package_id": "k"}
