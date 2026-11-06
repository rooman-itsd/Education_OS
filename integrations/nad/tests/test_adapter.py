"""The Adapter contract (contracts/ports/adapter.yaml): registration, describe, capabilities, healthcheck, error
vocabulary, modes."""

import importlib
import json
import logging
import tomllib
from pathlib import Path

import yaml
from eos_nad import __version__
from eos_nad.domain.errors import RETRYABLE
from nad_support import awards_batch, ctx, err, ok, settings

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = yaml.safe_load((ROOT / "contracts/ports/adapter.yaml").read_text())
PORT = yaml.safe_load((ROOT / "contracts/ports/academic-records.yaml").read_text())


def test_the_entry_point_names_the_adapter_and_loads():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    target = pyproject["project"]["entry-points"][CONTRACT["registration"]["entry_point_group"]]["nad"]
    module, func = target.split(":")
    assert getattr(importlib.import_module(module), func)().describe()["adapter"] == "nad"


def test_describe_follows_the_contract():
    d = importlib.import_module("eos_nad.application.adapter").get_adapter().describe()
    assert set(d) == set(CONTRACT["registration"]["describe"]["output"])
    manifest = yaml.safe_load((ROOT / "module.yaml").read_text())
    assert d["version"] == manifest["version"] == __version__
    assert d["ports"] == [{"port": PORT["id"], "version": PORT["version"]}]
    [p] = d["providers"]
    assert set(p) == set(CONTRACT["registration"]["provider_fields"])
    assert p["ports"] == [PORT["id"]] and p["inbound"] == [] and p["link_scope"] == "organisation"
    assert set(p["modes"]) == {"mock", "sandbox", "live"}
    json.dumps(p["settings_schema"])


def test_the_error_codes_are_the_contracts_with_the_same_retryability():
    assert RETRYABLE == {k: v["retryable"] for k, v in CONTRACT["error_codes"].items()}


def test_every_operation_the_port_names_is_implemented(adapter, org):
    for name in [o["name"] for o in PORT["operations"]] + [
        "capabilities",
        "healthcheck",
        "verify_inbound",
        "parse_inbound",
    ]:
        r = adapter.invoke(name, ctx(org), {})
        assert "output" in r or r["error"]["code"] != "unsupported", name


def test_operations_that_do_not_apply_are_unsupported(adapter, org):
    for name in (
        "begin_authorisation",
        "complete_authorisation",
        "refresh_authorisation",
        "revoke_authorisation",
        "handle_provider_request",
        "teleport",
    ):
        assert err(adapter.invoke(name, ctx(org), {}))["code"] == "unsupported", name


def test_a_malformed_context_is_invalid_request(adapter):
    assert err(adapter.invoke("capabilities", {"organisation_id": "nope"}, {}))["code"] == "invalid_request"
    assert err(adapter.invoke("capabilities", {}, {}))["code"] == "invalid_request"


def test_capabilities_say_the_manual_channel_is_all_there_is(adapter, org):
    out = ok(adapter.invoke("capabilities", ctx(org), {}))
    assert out["port"] == "academic-records"
    caps = out["capabilities"]
    assert set(PORT["capabilities"]) <= set(caps)
    assert (caps["awards_api"], caps["credits_api"], caps["learner_id_verification"], caps["status_polling"]) == (
        False,
    ) * 4
    assert caps["max_rows_per_batch"] == 20000 and caps["max_rows_per_file"] == 5000


def test_healthcheck(adapter, org, monkeypatch):
    assert ok(adapter.invoke("healthcheck", ctx(org), {}))["status"] == "healthy"
    assert ok(adapter.invoke("healthcheck", ctx(org, mode="live"), {}))["status"] == "healthy"
    assert (
        ok(
            adapter.invoke(
                "healthcheck",
                ctx(org, mode="live", settings=settings(nad_institution_id=None, abc_institution_id=None)),
                {},
            )
        )["status"]
        == "degraded"
    )
    assert ok(adapter.invoke("healthcheck", ctx(org, settings={"award_templates": 1}), {}))["status"] == "degraded"
    monkeypatch.setenv("NAD_AWARDS_CSV_TEMPLATE_VERSION", "7")
    assert ok(adapter.invoke("healthcheck", ctx(org), {}))["status"] == "degraded"


def test_nothing_is_ever_called_by_a_depository(adapter, org):
    v = ok(adapter.invoke("verify_inbound", ctx(org), {"method": "POST", "path_suffix": "x", "raw_body": b""}))
    assert v["verdict"] == "reject" and v["reject_status"] == 401
    assert ok(adapter.invoke("parse_inbound", ctx(org), {"headers": {}, "raw_body": b""})) == {"notifications": []}


def test_mock_mode_is_refused_outside_development(adapter, org, monkeypatch):
    import eos_nad.infrastructure.config as config

    monkeypatch.setattr(config, "core_settings", type("S", (), {"dev_mode": False})())
    assert err(adapter.invoke("publish_awards", ctx(org), awards_batch()))["code"] == "not_configured"
    assert (
        ok(adapter.invoke("publish_awards", ctx(org, mode="sandbox"), awards_batch()))["status"]
        == "manual_action_required"
    )


def test_an_unexpected_bug_becomes_a_retryable_provider_error_not_an_exception(adapter, org, monkeypatch):
    monkeypatch.setattr(adapter.runtime, "session_factory", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    r = adapter.invoke("get_submission", ctx(org), {"submission_id": "0b1b8f38-4a7e-4a54-9f0e-4f5b1c7a0001"})
    assert err(r)["code"] == "provider_error" and err(r)["retryable"] and "db down" not in err(r)["detail"]


def test_no_learner_data_in_logs_or_error_details(adapter, org, caplog):
    caplog.set_level(logging.DEBUG)
    bad = awards_batch()
    bad["records"][0]["learner"]["apaar_id"] = "x"
    out = ok(adapter.invoke("publish_awards", ctx(org), bad))
    blob = caplog.text + json.dumps(out)
    for private in ("Asha", "Rao", "123456789012", "2004-01-01", "EN-2023-0001", "Sunita"):
        assert private not in blob


def test_the_package_imports_only_what_an_integration_may():
    banned = (
        "eos_identity",
        "eos_audit",
        "eos_notification",
        "modules.",
        "eos_integration_hub",
        "eos_digilocker",
        "httpx",
    )
    for path in (ROOT / "src").rglob("*.py"):
        imports = [ln for ln in path.read_text().splitlines() if ln.startswith(("import ", "from "))]
        assert not any(b in ln for ln in imports for b in banned), path
