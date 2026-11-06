"""The adapter against the draft contracts it was built from: describe() is the registry row, the operations are the port's,
the capability fields are the port's, the entry points are declared, the manifest agrees, and the env keys are documented."""

from __future__ import annotations

import importlib
import re
import tomllib
from pathlib import Path

import yaml
from eos_wearables import __version__

MODULE = Path(__file__).resolve().parents[1]
PORT = yaml.safe_load((MODULE / "contracts/ports/wearable-data.yaml").read_text())
ADAPTER = yaml.safe_load((MODULE / "contracts/ports/adapter.yaml").read_text())
AUTHS = [
    "none",
    "api_key",
    "oauth2_client_credentials",
    "oauth2_authorization_code",
    "jwt_shared_secret",
    "hmac_shared_secret",
]


def test_describe_is_the_registry_row(adapter):
    d = adapter.describe()
    assert d["adapter"] == "wearables" == MODULE.name
    assert d["version"] == __version__ == yaml.safe_load((MODULE / "module.yaml").read_text())["version"]
    assert d["ports"] == [{"port": "wearable-data", "version": PORT["version"]}]
    assert [p["provider"] for p in d["providers"]] == ["garmin", "polar", "google-health", "strava"]
    fields = set(ADAPTER["registration"]["provider_fields"]) | {
        "settings_schema",
        "credential_names",
        "platform_credential_names",
    }
    for p in d["providers"]:
        assert set(p) == fields and p["ports"] == ["wearable-data"] and p["modes"] == ["mock", "sandbox", "live"]
        assert (
            p["auth"] in AUTHS
            and p["link_scope"] == "person"
            and p["inbound"] == ["webhook"]
            and p["settings_schema"]["type"] == "object"
        )
        assert p["credential_names"] == ["access_token", "refresh_token"]
    by = {p["provider"]: p for p in d["providers"]}
    assert by["strava"]["platform_credential_names"] == [
        "WEARABLES_STRAVA_CLIENT_ID",
        "WEARABLES_STRAVA_CLIENT_SECRET",
        "WEARABLES_STRAVA_VERIFY_TOKEN",
        "WEARABLES_STRAVA_SUBSCRIPTION_ID",
    ]


def test_every_port_and_adapter_operation_is_implemented(adapter):
    skipped = {
        "handle_provider_request"
    }  # DigiLocker's synchronous pull: no device maker calls us and waits for an answer
    ops = [o["name"] for o in PORT["operations"]] + [
        o["name"] for o in ADAPTER["operations"] if o["name"] not in skipped
    ]
    assert not [o for o in ops if not callable(getattr(adapter, o, None))]


def test_capabilities_are_the_ports_fields_for_every_provider(adapter, org):
    for provider in ("garmin", "polar", "google-health", "strava"):
        out = adapter.capabilities(org.ctx(provider)).output
        assert out["port"] == "wearable-data" and set(out["capabilities"]) == set(PORT["capabilities"])
        assert set(out["capabilities"]["data_types"]) <= set(PORT["vocabulary"]["data_type"])
        assert out["capabilities"]["requires_mobile_app"] is False
    assert adapter.capabilities(org.ctx("strava")).output["capabilities"]["data_types"] == ["activity"]


def test_every_normalised_record_has_exactly_the_ports_fields(adapter, transport, org):
    from wear_support import make_link, records

    ids = make_link(org, "garmin")
    from wear_support import fixture, request

    adapter.parse_inbound(None, request(fixture("garmin/push_health.json"), query={"provider": "garmin"}))
    adapter.parse_inbound(None, request(fixture("garmin/push_activities.json"), query={"provider": "garmin"}))
    want = {
        "daily_summary": "daily_summary",
        "activity": "activity",
        "sleep": "sleep",
        "heart_rate_variability": "heart_rate_variability",
        "body_composition": "body_composition",
    }
    for r in records(ids["link"]):
        assert set(r.fields) == set(PORT["records"][want[r.data_type]]), r.data_type


def test_the_notifications_the_adapter_emits_are_the_ports_kinds():
    src = (MODULE / "src/eos_wearables/application/adapter.py").read_text()
    assert set(re.findall(r'_note\("(\w+)"', src)) <= {k["kind"] for k in PORT["inbound"]}


def test_the_entry_points_are_declared_and_resolve():
    cfg = tomllib.loads((MODULE / "pyproject.toml").read_text())
    group = cfg["project"]["entry-points"][ADAPTER["registration"]["entry_point_group"]]
    assert list(group) == ["wearables"]
    module, _, attr = group["wearables"].partition(":")
    assert getattr(importlib.import_module(module), attr)().describe()["adapter"] == "wearables"
    consumers = cfg["project"]["entry-points"]["eos.event_consumers"]["wearables"]
    module, _, attr = consumers.partition(":")
    assert list(getattr(importlib.import_module(module), attr)) == ["integration-hub.account-link.revoked"]
    manifest = yaml.safe_load((MODULE / "module.yaml").read_text())
    assert manifest["consumes_events"] == ["integration-hub.account-link.revoked"]


def test_the_port_copies_are_what_the_manifest_exposes():
    manifest = yaml.safe_load((MODULE / "module.yaml").read_text())
    assert manifest["exposes"]["ports"] == ["contracts/ports/adapter.yaml", "contracts/ports/wearable-data.yaml"]
    assert all((MODULE / p).is_file() for p in manifest["exposes"]["ports"])


def test_every_env_key_the_code_reads_is_in_env_example():
    env = (MODULE / "config/env.example").read_text()
    documented = set(re.findall(r"^#?\s*(WEARABLES_[A-Z0-9_]+)=", env, re.M))
    code = (MODULE / "src/eos_wearables/infrastructure/config.py").read_text() + (
        MODULE / "src/eos_wearables/application/adapter.py"
    ).read_text()
    read = {"WEARABLES_" + k for k in re.findall(r'_(?:env|int)\("([A-Z0-9_]+)"', code)} | {"WEARABLES_PROVIDERS"}
    assert read <= documented, sorted(read - documented)


def test_the_permission_catalogue_matches_the_contract():
    cat = yaml.safe_load((MODULE / "contracts/permissions.yaml").read_text())
    assert [p["key"] for p in cat["permissions"]] == ["wearables:alert:read"] and {r["name"] for r in cat["roles"]} == {
        "coach",
        "org-admin",
    }
