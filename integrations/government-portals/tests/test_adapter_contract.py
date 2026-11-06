"""The Adapter contract and the port as the contract files state them: the adapter registers itself, answers every
operation, never raises on bad input, and holds no credentials."""

import re
import uuid
from pathlib import Path

import pytest
import yaml
from eos_government_portals.application import service
from eos_government_portals.application.adapter import GovernmentPortalsAdapter, get_adapter
from eos_government_portals.domain.port import ERROR_CODES, Context, PortError, Result
from gp_support import load_case

ROOT = Path(__file__).resolve().parents[1]
PORTS = ROOT / "contracts" / "ports"


def _yaml(name):
    return yaml.safe_load((PORTS / name).read_text())


def test_describe_matches_the_manifest_and_the_contract(adapter):
    d = adapter.describe()
    manifest = yaml.safe_load((ROOT / "module.yaml").read_text())
    port = _yaml("regulatory-submission.yaml")
    assert d["adapter"] == manifest["name"] == "government-portals"
    assert d["version"] == manifest["version"]
    assert d["ports"] == [{"port": port["id"], "version": port["version"]}]
    fields = set(_yaml("adapter.yaml")["registration"]["provider_fields"])
    assert {p["provider"] for p in d["providers"]} == {"aishe", "nirf", "naac"}
    for p in d["providers"]:
        assert set(p) == fields
        assert p["auth"] == "none" and p["credential_names"] == [] and p["platform_credential_names"] == []
        assert p["modes"] == ["mock", "sandbox", "live"] and p["inbound"] == []
        assert p["ports"] == ["regulatory-submission"]


def test_the_entry_point_is_declared_for_the_hub():
    text = (ROOT / "pyproject.toml").read_text()
    assert '[project.entry-points."eos.integration_adapters"]' in text
    assert 'government-portals = "eos_government_portals.application.adapter:get_adapter"' in text
    target = re.search(r'government-portals = "([^:]+):([^"]+)"', text)
    module = __import__(target.group(1), fromlist=[target.group(2)])
    assert isinstance(getattr(module, target.group(2))(), GovernmentPortalsAdapter)
    assert get_adapter() is get_adapter()


def test_every_operation_of_the_contract_is_implemented(adapter):
    ops = {o["name"] for o in _yaml("adapter.yaml")["operations"]}
    ops |= {o["name"] for o in _yaml("regulatory-submission.yaml")["operations"]}
    assert not [o for o in ops if not callable(getattr(adapter, o, None))]


def test_the_contract_copies_are_what_the_manifest_lists():
    manifest = yaml.safe_load((ROOT / "module.yaml").read_text())
    assert manifest["exposes"]["ports"] == [
        "contracts/ports/adapter.yaml",
        "contracts/ports/regulatory-submission.yaml",
    ]
    assert _yaml("adapter.yaml")["error_codes"].keys() == ERROR_CODES.keys()
    for code, spec in _yaml("adapter.yaml")["error_codes"].items():
        assert ERROR_CODES[code] is spec["retryable"]


def test_the_port_error_codes_are_all_in_the_vocabulary():
    port = _yaml("regulatory-submission.yaml")
    for op in port["operations"]:
        assert set(op["errors"]) <= set(ERROR_CODES)


def test_a_result_is_exactly_output_or_error():
    with pytest.raises(ValueError):
        Result()
    with pytest.raises(ValueError):
        Result(output={}, error=PortError("not_found", "x"))
    with pytest.raises(ValueError):
        PortError("a provider's own words", "x")


def test_capabilities_and_list_forms_agree_with_the_port(adapter, org):
    caps = adapter.capabilities(org.ctx("nirf")).output
    assert caps["port"] == "regulatory-submission"
    forms = adapter.list_forms(org.ctx("nirf")).output["items"]
    assert {f["form_code"] for f in forms} == {
        f"nirf.dcs.{c}"
        for c in __import__("eos_government_portals.application.catalogue", fromlist=["x"]).NIRF_CATEGORIES
    }
    listed = {
        (f["form_code"], f["channel"], f["format_version"])
        for f in service.list_forms(
            __import__("eos_government_portals.infrastructure.config", fromlist=["x"]).Settings.from_env()
        ).output["items"]
    }
    assert {
        (c["form_code"], c["channel"], c["format_version"])
        for c in service.capabilities(
            __import__("eos_government_portals.infrastructure.config", fromlist=["x"]).Settings.from_env()
        )["forms"]
    } == listed
    for f in forms:
        assert set(f) >= {
            "form_code",
            "authority",
            "title",
            "channel",
            "format_version",
            "period_kind",
            "data_schema",
            "evidence",
            "portal_url",
        }


def test_the_catalogue_has_every_form_the_draft_lists(adapter, org):
    codes = {f["form_code"] for p in ("aishe", "nirf", "naac") for f in adapter.list_forms(org.ctx(p)).output["items"]}
    assert {
        "aishe.dcf-i",
        "aishe.dcf-ii",
        "aishe.dcf-iii",
        "naac.iiqa",
        "naac.ssr",
        "naac.aqar",
        "naac.dvv-response",
    } <= codes
    assert len([c for c in codes if c.startswith("nirf.dcs.")]) == 17


def test_healthcheck_is_always_healthy_and_needs_no_secret(adapter, org):
    for provider in ("aishe", "nirf", "naac"):
        for mode in ("mock", "sandbox", "live"):
            assert adapter.healthcheck(org.ctx(provider, mode)).output["status"] == "healthy"


def test_there_is_no_authorisation_and_no_inbound(adapter, org):
    ctx = org.ctx("aishe")
    for op in ("begin_authorisation", "complete_authorisation", "refresh_authorisation", "revoke_authorisation"):
        assert getattr(adapter, op)(ctx).error.code == "unsupported"
    assert adapter.verify_inbound(ctx, method="POST", raw_body=b"{}").output["verdict"] == "reject"
    assert adapter.parse_inbound(ctx).output == {"notifications": []}
    assert adapter.handle_provider_request(ctx).output["status"] == 404


def test_secrets_in_the_context_are_never_used_or_echoed(adapter, docs, org):
    ctx = org.ctx("aishe", secrets={"password": "hunter2-hunter2"})
    assert "hunter2" not in repr(ctx)
    case = load_case("aishe-dcf-i")
    r = adapter.prepare_package(
        ctx, package_key="k1", form_code=case["form_code"], period=case["period"], data=case["data"]
    )
    assert "hunter2" not in repr(r)
    for f in r.output["files"]:
        assert b"hunter2" not in docs.get(org.id, f["document_id"]).content


def test_unknown_forms_and_cycles_are_unsupported(adapter, docs, org, monkeypatch):
    case = load_case("aishe-dcf-i")
    ctx = org.ctx("aishe")
    r = adapter.prepare_package(ctx, package_key="k", form_code="aishe.dcf-iv", period="2025-26", data={})
    assert r.error.code == "unsupported"
    r = adapter.prepare_package(ctx, package_key="k", form_code=case["form_code"], period="2024-25", data=case["data"])
    assert r.error.code == "unsupported"  # last year's format is never reused
    monkeypatch.setenv("GOVERNMENT_PORTALS_AISHE_FORMAT", "2026-27")
    r = adapter.prepare_package(ctx, package_key="k", form_code=case["form_code"], period="2026-27", data=case["data"])
    assert r.error.code == "unsupported"  # a format this release does not have
    assert adapter.validate(ctx, form_code="aishe.dcf-i", period="2026-27", data={}).error.code == "unsupported"


def test_a_connection_only_serves_its_own_authority(adapter, docs, org):
    case = load_case("nirf-dcs-overall")
    r = adapter.prepare_package(
        org.ctx("aishe"), package_key="k", form_code=case["form_code"], period=case["period"], data=case["data"]
    )
    assert r.error.code == "unsupported"


def test_bad_context_never_raises(adapter, org):
    assert adapter.list_forms(None).error.code == "invalid_request"
    assert adapter.list_forms(Context(organisation_id="not-a-uuid")).error.code == "invalid_request"
    assert adapter.list_forms(org.ctx("aishe", mode="production")).error.code == "invalid_request"
    assert adapter.list_forms(org.ctx("irs")).error.code == "not_configured"
    assert adapter.list_forms(org.ctx("aishe", settings={"aishe_code": "nope"})).error.code == "not_configured"
    assert adapter.list_forms(org.ctx("aishe", settings={"unknown": 1})).error.code == "not_configured"
    assert adapter.list_forms(org.ctx("aishe", settings={"aishe_code": "C-12345", "institution_type": "college"})).ok


def test_live_and_sandbox_need_the_hubs_documents_client():
    bare = GovernmentPortalsAdapter()  # nothing injected: only mock runs, on the in-memory store
    org_id = str(uuid.uuid4())
    case = load_case("aishe-dcf-i")
    args = {"package_key": "k", "form_code": case["form_code"], "period": case["period"], "data": case["data"]}
    for mode in ("sandbox", "live"):
        r = bare.prepare_package(Context(organisation_id=org_id, provider="aishe", mode=mode), **args)
        assert r.error.code == "not_configured"
    assert bare.prepare_package(Context(organisation_id=org_id, provider="aishe", mode="mock"), **args).ok


HOSTILE = [
    None,
    1,
    1.5,
    True,
    [],
    {},
    "",
    "x" * 100_000,
    float("nan"),
    float("inf"),
    {"a": {"b": [None]}},
    b"bytes",
    "\x00",
    "../../etc/passwd",
]


@pytest.mark.parametrize("bad", HOSTILE, ids=[repr(h)[:20] for h in HOSTILE])
def test_no_operation_raises_on_hostile_input(adapter, org, bad):
    ctx = org.ctx("aishe")
    for result in (
        adapter.validate(ctx, form_code=bad, period=bad, data=bad),
        adapter.validate(ctx, form_code="aishe.dcf-i", period="2025-26", data=bad),
        adapter.prepare_package(ctx, package_key=bad, form_code=bad, period=bad, data=bad, evidence=bad),
        adapter.prepare_package(
            ctx, package_key="k", form_code="aishe.dcf-i", period="2025-26", data=bad, evidence=bad
        ),
        adapter.prepare_package(ctx, package_key="k", form_code="aishe.dcf-i", period="2025-26", data={}, evidence=bad),
        adapter.submit(ctx, package_id=bad),
        adapter.get_package(ctx, package_id=bad),
        adapter.record_manual_submission(
            ctx,
            package_id=bad,
            submitted_on=bad,
            submitted_by=bad,
            portal_reference=bad,
            acknowledgement_document_id=bad,
        ),
    ):
        assert isinstance(result, Result)


def test_empty_and_wrong_shaped_data_is_a_list_of_issues(adapter, docs, org):
    r = adapter.prepare_package(org.ctx("aishe"), package_key="k", form_code="aishe.dcf-i", period="2025-26", data={})
    assert r.output["status"] == "invalid"
    assert {i["code"] for i in r.output["issues"]} == {"required"}
    r = adapter.prepare_package(org.ctx("aishe"), package_key="k", form_code="aishe.dcf-i", period="2025-26", data=[])
    assert r.error.code == "invalid_request"


def test_a_deeply_nested_or_huge_payload_is_bounded(adapter, org):
    data = load_case("aishe-dcf-i")["data"]
    data["programmes"] = data["programmes"][:1] * 5000
    r = adapter.validate(org.ctx("aishe"), form_code="aishe.dcf-i", period="2025-26", data=data)
    assert r.output["valid"] is False and len(r.output["issues"]) <= 500
    nested = {}
    for _ in range(3000):
        nested = {"a": nested}
    assert (
        adapter.validate(org.ctx("aishe"), form_code="aishe.dcf-i", period="2025-26", data=nested).output["valid"]
        is False
    )


def test_the_adapter_stores_no_credentials_anywhere():
    """Docs and config keys: nothing here asks for a portal login."""
    env = (ROOT / "config" / "env.example").read_text().lower()
    for word in ("password", "token", "secret", "api_key"):
        assert not re.search(rf"^[^#\n]*{word}[^#\n]*=", env, re.M), word
