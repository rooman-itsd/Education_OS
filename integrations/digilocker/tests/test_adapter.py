"""The Adapter contract (contracts/ports/adapter.yaml): registration, describe, capabilities, healthcheck, error
vocabulary, modes, and secrets that never leak."""

import importlib
import json
import logging
import tomllib
from datetime import timedelta
from pathlib import Path

import yaml
from dgl_support import ctx, err, issue_input, link_ctx, ok
from eos_digilocker import __version__
from eos_digilocker.domain.errors import RETRYABLE

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = yaml.safe_load((ROOT / "contracts/ports/adapter.yaml").read_text())
PORT = yaml.safe_load((ROOT / "contracts/ports/certificate-issuance.yaml").read_text())


def test_the_entry_point_names_the_adapter_and_loads():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    group = CONTRACT["registration"]["entry_point_group"]
    target = pyproject["project"]["entry-points"][group]["digilocker"]
    module, func = target.split(":")
    adapter = getattr(importlib.import_module(module), func)()
    assert adapter.describe()["adapter"] == "digilocker"  # the entry point name is the folder name


def test_describe_follows_the_contract():
    d = importlib.import_module("eos_digilocker.application.adapter").get_adapter().describe()
    assert set(d) == set(CONTRACT["registration"]["describe"]["output"])
    manifest = yaml.safe_load((ROOT / "module.yaml").read_text())
    assert d["version"] == manifest["version"] == __version__
    assert d["ports"] == [{"port": PORT["id"], "version": PORT["version"]}]
    [p] = d["providers"]
    assert set(p) == set(CONTRACT["registration"]["provider_fields"])
    assert p["provider"] == "digilocker" and p["ports"] == [PORT["id"]] and p["inbound"] == ["provider_request"]
    assert set(p["modes"]) == {"mock", "sandbox", "live"} and p["link_scope"] == "person"
    assert p["auth"] in ("oauth2_authorization_code",)
    json.dumps(p["settings_schema"])  # a JSON Schema the hub can store


def test_the_error_codes_are_the_contracts_with_the_same_retryability():
    assert RETRYABLE == {k: v["retryable"] for k, v in CONTRACT["error_codes"].items()}


def test_every_operation_the_port_and_contract_name_is_implemented(adapter, org):
    names = [o["name"] for o in PORT["operations"]] + [o["name"] for o in CONTRACT["operations"]]
    for name in names:
        r = adapter.invoke(name, ctx(org), {})
        assert "output" in r or r["error"]["code"] != "unsupported", name


def test_an_unknown_operation_is_unsupported(adapter, org):
    assert err(adapter.invoke("teleport", ctx(org), {}))["code"] == "unsupported"


def test_a_malformed_context_is_invalid_request(adapter):
    assert err(adapter.invoke("capabilities", {"organisation_id": "nope"}, {}))["code"] == "invalid_request"
    assert err(adapter.invoke("capabilities", {}, {}))["code"] == "invalid_request"


def test_capabilities_follow_the_connection_without_calling_the_provider(adapter, mock, org):
    out = ok(adapter.invoke("capabilities", ctx(org), {}))
    assert out["port"] == "certificate-issuance"
    caps = out["capabilities"]
    assert set(caps) == set(PORT["capabilities"])
    assert caps["push_to_holder"] is False and caps["pull_on_demand"] and caps["holder_consent_fetch"]
    assert {d["provider_doc_type"] for d in caps["doc_types"]} == {"DGCER", "MKSHT"} and caps[
        "max_document_bytes"
    ] == 5242880
    s = ctx(org)["settings"] | {"push_enabled": True}
    assert ok(adapter.invoke("capabilities", ctx(org, settings=s), {}))["capabilities"]["push_to_holder"] is True
    assert mock.requests == []


def test_healthcheck_by_mode(adapter, org, monkeypatch):
    assert ok(adapter.invoke("healthcheck", ctx(org), {}))["status"] == "healthy"
    # sandbox with the deployment's URL but no issuer key: the credentials are missing
    assert ok(adapter.invoke("healthcheck", ctx(org, mode="sandbox", secrets={}), {}))["status"] == "auth_failed"
    monkeypatch.delenv("DIGILOCKER_SANDBOX_BASE_URL")
    assert ok(adapter.invoke("healthcheck", ctx(org, mode="sandbox"), {}))["status"] == "auth_failed"


def test_inbound_is_by_provider_request_only(adapter, org):
    v = ok(adapter.invoke("verify_inbound", ctx(org), {"method": "POST", "path_suffix": "x", "raw_body": b""}))
    assert v["verdict"] == "reject" and v["reject_status"] == 401
    assert ok(adapter.invoke("parse_inbound", ctx(org), {"headers": {}, "raw_body": b""})) == {"notifications": []}


def test_mock_mode_is_refused_outside_development(adapter, documents, org, monkeypatch):
    import eos_digilocker.infrastructure.config as config

    monkeypatch.setattr(config, "core_settings", type("S", (), {"dev_mode": False})())
    assert err(adapter.invoke("issue", ctx(org), issue_input(documents, org)))["code"] == "not_configured"


def test_sandbox_and_live_refuse_to_start_without_their_endpoint_and_credentials(adapter, documents, org, monkeypatch):
    monkeypatch.delenv("DIGILOCKER_SANDBOX_BASE_URL")
    body = issue_input(documents, org)
    assert err(adapter.invoke("issue", ctx(org, mode="sandbox"), body))["code"] == "not_configured"
    monkeypatch.delenv("DIGILOCKER_SEARCH_KEY_PEPPER")
    monkeypatch.setenv("DIGILOCKER_LIVE_BASE_URL", "https://api.example.invalid/public")
    e = err(adapter.invoke("issue", ctx(org, mode="live"), body))
    assert e["code"] == "not_configured" and "PEPPER" in e["detail"]
    monkeypatch.delenv("DIGILOCKER_REQUESTER_CLIENT_ID")
    inp = {"state": "state-abcdef", "code_challenge": "a" * 43, "redirect_uri": "https://x.example/cb"}
    assert err(adapter.invoke("begin_authorisation", ctx(org, mode="live"), inp))["code"] == "not_configured"


def test_a_passed_deadline_is_transport_unavailable(adapter, org, now):
    c = link_ctx(org, deadline=(now - timedelta(seconds=1)).isoformat())
    r = adapter.invoke("list_holder_documents", c, {"account_link_id": c["account_link"]["id"]})
    assert err(r)["code"] == "transport_unavailable" and err(r)["retryable"]


def test_secrets_never_appear_in_results_logs_or_the_database(adapter, mock, documents, org, caplog):
    caplog.set_level(logging.DEBUG)
    secrets_in = {
        "issuer_api_key": "SECRET-ISSUER-KEY",
        "push_client_id": "PUSH-APP-001",
        "push_client_secret": "push-secret-fixture",
    }
    body = issue_input(documents, org)
    body["holder"]["wallet_account_id"] = "dl-holder-0001"
    s = ctx(org)["settings"] | {"push_enabled": True}
    results = [
        adapter.invoke("issue", ctx(org, settings=s, secrets=secrets_in), body),
        adapter.invoke("issue", ctx(org, settings=s, secrets=secrets_in | {"push_client_secret": "wrong-one"}), body),
    ]
    blob = json.dumps(results, default=str) + caplog.text
    from dgl_support import rows
    from eos_digilocker.domain.models import IssuanceHistory, IssuedDocument

    blob += repr([vars(r) for r in rows(IssuedDocument, org.id) + rows(IssuanceHistory, org.id)])
    for secret in ("SECRET-ISSUER-KEY", "push-secret-fixture", "wrong-one"):
        assert secret not in blob
    from eos_digilocker.application.schemas import Context

    assert "SECRET-ISSUER-KEY" not in repr(Context.model_validate(ctx(org, secrets=secrets_in)))


def test_an_unexpected_bug_becomes_a_retryable_provider_error_not_an_exception(adapter, documents, org, monkeypatch):
    monkeypatch.setattr(adapter.runtime, "session_factory", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    r = adapter.invoke("get_issuance", ctx(org), {"issuance_key": "k"})
    assert err(r)["code"] == "provider_error" and err(r)["retryable"] and "db down" not in err(r)["detail"]


def test_the_package_imports_only_what_an_integration_may():
    banned = ("eos_identity", "eos_audit", "eos_notification", "modules.", "eos_integration_hub")
    for path in (ROOT / "src").rglob("*.py"):
        imports = [ln for ln in path.read_text().splitlines() if ln.startswith(("import ", "from "))]
        assert not any(b in ln for ln in imports for b in banned), path
