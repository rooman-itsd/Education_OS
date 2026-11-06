"""The adapter against the draft contracts it was built from: describe() is the registry row, the operations are the port's,
the capability fields are the port's, the entry point is declared, the manifest agrees, and the port files are the hub's."""

from __future__ import annotations

import tomllib
from pathlib import Path

import yaml
from eos_video_conferencing import __version__
from eos_video_conferencing.application.adapter import CAPABILITIES

MODULE = Path(__file__).resolve().parents[1]
PORT = yaml.safe_load((MODULE / "contracts/ports/meetings.yaml").read_text())
ADAPTER = yaml.safe_load((MODULE / "contracts/ports/adapter.yaml").read_text())


def test_describe_is_the_registry_row(adapter):
    d = adapter.describe()
    assert d["adapter"] == "video-conferencing" == MODULE.name
    assert d["version"] == __version__ == yaml.safe_load((MODULE / "module.yaml").read_text())["version"]
    assert d["ports"] == [{"port": "meetings", "version": PORT["version"]}]
    assert [p["provider"] for p in d["providers"]] == ["zoom", "teams", "webex", "jitsi"]
    fields = set(ADAPTER["registration"]["provider_fields"]) | {
        "settings_schema",
        "credential_names",
        "platform_credential_names",
    }
    for p in d["providers"]:
        assert set(p) == fields
        assert p["ports"] == ["meetings"] and p["modes"] == ["mock", "sandbox", "live"]
        assert p["auth"] in ADAPTER["registration"]["provider_fields"]["auth"].split("#")[0].split() + [
            "none",
            "api_key",
            "oauth2_client_credentials",
            "oauth2_authorization_code",
            "jwt_shared_secret",
            "hmac_shared_secret",
        ]
        assert p["link_scope"] == "organisation" and p["settings_schema"]["type"] == "object"
    by = {p["provider"]: p for p in d["providers"]}
    assert (
        by["zoom"]["auth"] == "oauth2_authorization_code"
        and by["teams"]["auth"] == "oauth2_client_credentials"
        and by["jitsi"]["auth"] == "jwt_shared_secret"
    )
    assert (
        by["jitsi"]["inbound"] == []
        and by["zoom"]["inbound"] == ["webhook"]
        and by["jitsi"]["credential_names"] == ["app_secret"]
    )
    assert (
        "VIDEO_CONFERENCING_ZOOM_WEBHOOK_SECRET_TOKEN" in by["zoom"]["platform_credential_names"]
        and by["jitsi"]["platform_credential_names"] == []
    )


def test_every_port_and_adapter_operation_is_implemented(adapter):
    ops = [o["name"] for o in PORT["operations"]] + [
        o["name"]
        for o in ADAPTER["operations"]
        if o["name"]
        != "handle_provider_request"  # DigiLocker's synchronous pull; no meeting provider calls us and waits
    ]
    missing = [o for o in ops if not callable(getattr(adapter, o, None))]
    assert not missing


def test_capabilities_are_the_ports_fields_for_every_provider(adapter, org):
    for provider in CAPABILITIES:
        out = adapter.capabilities(org.ctx(provider)).output
        assert out["port"] == "meetings" and set(out["capabilities"]) == set(PORT["capabilities"])
    assert adapter.capabilities(org.ctx("jitsi")).output["capabilities"]["scheduled_meetings"] is False
    assert adapter.capabilities(org.ctx("jitsi")).output["capabilities"]["attendance_report"] is False
    assert adapter.capabilities(org.ctx("zoom")).output["capabilities"]["attendance_report"] is True


def test_the_notifications_the_adapter_emits_are_the_ports_kinds():
    import re

    src = (MODULE / "src/eos_video_conferencing/application/adapter.py").read_text()
    kinds = {k["kind"] for k in PORT["inbound"]}
    assert set(re.findall(r'_note\("(\w+)"', src)) <= kinds


def test_the_entry_point_is_declared_and_resolves():
    cfg = tomllib.loads((MODULE / "pyproject.toml").read_text())
    group = cfg["project"]["entry-points"][ADAPTER["registration"]["entry_point_group"]]
    assert list(group) == ["video-conferencing"]
    module, _, attr = group["video-conferencing"].partition(":")
    import importlib

    adapter = getattr(importlib.import_module(module), attr)()
    assert adapter.describe()["adapter"] == "video-conferencing"


def test_the_port_copies_are_what_the_manifest_exposes():
    manifest = yaml.safe_load((MODULE / "module.yaml").read_text())
    assert manifest["exposes"]["ports"] == ["contracts/ports/adapter.yaml", "contracts/ports/meetings.yaml"]
    assert all((MODULE / p).is_file() for p in manifest["exposes"]["ports"])
    assert manifest["depends_on"]["platform"] == ["identity", "audit", "integration-hub", "documents"]


def test_every_env_key_the_code_reads_is_in_env_example():
    import re

    env = (MODULE / "config/env.example").read_text()
    documented = set(re.findall(r"^#?\s*(VIDEO_CONFERENCING_[A-Z0-9_]+)=", env, re.M))
    code = (MODULE / "src/eos_video_conferencing/infrastructure/config.py").read_text()
    read = {"VIDEO_CONFERENCING_" + k for k in re.findall(r'_(?:env|int)\("([A-Z0-9_]+)"', code)}
    assert read <= documented, sorted(read - documented)
