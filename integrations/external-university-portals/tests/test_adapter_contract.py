"""The Adapter contract and the port as the contract files state them: the adapter registers itself, answers every
operation, never raises on bad input, and takes its partner from the connection's settings."""

import re
import uuid
from pathlib import Path

import pytest
import yaml
from eos_external_university_portals.application.adapter import ExternalUniversityPortalsAdapter, get_adapter
from eos_external_university_portals.domain.port import ERROR_CODES, Context, PortError, Result
from eup_support import export, partner, transcript

ROOT = Path(__file__).resolve().parents[1]
PORTS = ROOT / "contracts" / "ports"


def _yaml(name):
    return yaml.safe_load((PORTS / name).read_text())


def test_describe_matches_the_manifest_and_the_contract(adapter):
    d = adapter.describe()
    manifest = yaml.safe_load((ROOT / "module.yaml").read_text())
    port = _yaml("inter-institution-records.yaml")
    assert d["adapter"] == manifest["name"] == "external-university-portals"
    assert d["version"] == manifest["version"]
    assert d["ports"] == [{"port": port["id"], "version": port["version"]}]
    fields = set(_yaml("adapter.yaml")["registration"]["provider_fields"])
    assert {p["provider"] for p in d["providers"]} == {"file", "elmo", "edc"}  # the provider ids of the PRD
    for p in d["providers"]:
        assert set(p) == fields and p["ports"] == ["inter-institution-records"]
        assert p["modes"] == ["mock", "sandbox", "live"] and p["inbound"] == [] and p["auth"] == "none"
        assert p["settings_schema"]["required"] == ["partner_id", "country", "channel"]


def test_the_entry_point_is_declared_for_the_hub():
    text = (ROOT / "pyproject.toml").read_text()
    assert '[project.entry-points."eos.integration_adapters"]' in text
    target = re.search(r'external-university-portals = "([^:]+):([^"]+)"', text)
    module = __import__(target.group(1), fromlist=[target.group(2)])
    assert isinstance(getattr(module, target.group(2))(), ExternalUniversityPortalsAdapter)
    assert get_adapter() is get_adapter()


def test_every_operation_of_the_contract_is_implemented(adapter):
    ops = {o["name"] for o in _yaml("adapter.yaml")["operations"]} | {
        o["name"] for o in _yaml("inter-institution-records.yaml")["operations"]
    }
    assert not [o for o in ops if not callable(getattr(adapter, o, None))]


def test_the_contract_copies_and_error_codes_match():
    manifest = yaml.safe_load((ROOT / "module.yaml").read_text())
    assert manifest["exposes"]["ports"] == [
        "contracts/ports/adapter.yaml",
        "contracts/ports/inter-institution-records.yaml",
    ]
    codes = _yaml("adapter.yaml")["error_codes"]
    assert codes.keys() == ERROR_CODES.keys() and all(ERROR_CODES[c] is s["retryable"] for c, s in codes.items())
    for op in _yaml("inter-institution-records.yaml")["operations"]:
        assert set(op["errors"]) <= set(ERROR_CODES)
    vocab = _yaml("inter-institution-records.yaml")["vocabulary"]
    from eos_external_university_portals.application.transcript import FORMATS
    from eos_external_university_portals.domain.models import STATUSES

    assert tuple(vocab["exchange_status"]) == STATUSES and vocab["format"] == FORMATS


def test_a_result_is_exactly_output_or_error():
    for bad in (
        lambda: Result(),
        lambda: Result(output={}, error=PortError("not_found", "x")),
        lambda: PortError("provider words", "x"),
    ):
        with pytest.raises(ValueError):
            bad()


def test_capabilities_per_provider(adapter, org):
    f = adapter.capabilities(org.ctx("file")).output
    assert f["port"] == "inter-institution-records"
    assert f["capabilities"] == {
        "formats_out": ["pdf", "csv"],
        "formats_in": ["csv"],
        "channels": ["download", "email", "partner_portal"],
        "signed_exports": False,
    }
    assert adapter.capabilities(org.ctx("elmo")).output["capabilities"]["formats_out"] == ["elmo_xml"]
    assert adapter.capabilities(org.ctx("edc")).output["capabilities"]["formats_in"] == ["edc_jsonld"]


def test_list_partners_reflects_the_connection(adapter, org):
    s = partner(
        formats_out=["csv"],
        formats_in=["csv"],
        grade_conversion={"A": 10},
        channel="email",
        email="admissions@uio.example",
    )
    (item,) = adapter.list_partners(org.ctx("file", settings=s)).output["items"]
    assert item == {
        "partner_id": "uni-oslo",
        "name": "University of Oslo",
        "country": "NO",
        "formats": {"out": ["csv"], "in": ["csv"]},
        "channels": ["email"],
        "grade_conversion": {"A": 10},
    }


def test_healthcheck_is_healthy_in_every_mode(adapter, org):
    for provider in ("file", "elmo", "edc"):
        for mode in ("mock", "sandbox", "live"):
            assert adapter.healthcheck(org.ctx(provider, mode)).output["status"] == "healthy"


def test_there_is_no_authorisation_and_no_inbound_in_v1(adapter, org):
    ctx = org.ctx()
    for op in ("begin_authorisation", "complete_authorisation", "refresh_authorisation", "revoke_authorisation"):
        assert getattr(adapter, op)(ctx).error.code == "unsupported"
    assert adapter.verify_inbound(ctx, method="POST", raw_body=b"{}").output["verdict"] == "reject"
    assert adapter.parse_inbound(ctx).output == {"notifications": []}
    assert adapter.handle_provider_request(ctx).output["status"] == 404


def test_formats_follow_the_provider_and_the_partner(adapter, org):
    # a provider only writes its own formats
    assert (
        adapter.export_records(
            org.ctx("file"), exchange_key="a", partner_id="uni-oslo", format="elmo_xml", transcript=transcript()
        ).error.code
        == "unsupported"
    )
    assert export(adapter, org, "edc_jsonld", key="b").ok
    wrong = adapter.export_records(
        org.ctx("elmo"), exchange_key="c", partner_id="uni-oslo", format="edc_jsonld", transcript=transcript()
    )
    assert wrong.error.code == "unsupported"
    # a partner that accepts only CSV is not sent ELMO
    only_csv = partner(formats_out=["csv"])
    assert export(adapter, org, "elmo_xml", key="d", settings=only_csv).error.code == "unsupported"
    assert export(adapter, org, "csv", key="e", settings=only_csv).ok
    assert export(adapter, org, "pdf", key="f", settings=only_csv).error.code == "unsupported"


def test_bad_context_and_settings_never_raise(adapter, org):
    assert adapter.list_partners(None).error.code == "invalid_request"
    assert adapter.list_partners(Context(organisation_id="nope")).error.code == "invalid_request"
    assert adapter.list_partners(org.ctx(mode="production")).error.code == "invalid_request"
    assert adapter.list_partners(org.ctx("emrex")).error.code == "not_configured"
    assert (
        adapter.list_partners(Context(organisation_id=org.id, provider="file", settings=None)).error.code
        == "not_configured"
    )
    bad = [
        {},
        {"partner_id": "x"},
        partner(country="norway"),
        partner(channel="carrier-pigeon"),
        partner(email="nope"),
        partner(portal_url="javascript:alert(1)"),
        partner(formats_out=["docx"]),
        partner(unknown=1),
        partner(csv_mapping={"nope": "x"}),
        partner(csv_mapping={"title": ""}),
        partner(csv_mapping={"title": 5}),
        partner(grade_conversion={"A": [1]}),
        partner(credit_conversion={f"k{i}": 1 for i in range(201)}),
        partner(partner_id="a b"),
    ]
    for s in bad:
        assert adapter.list_partners(org.ctx(settings=s)).error.code == "not_configured", s
    assert adapter.list_partners(
        org.ctx(
            settings=partner(
                channel="email",
                email="a@b.example",
                portal_url="https://portal.example/x",
                csv_mapping={"title": "Name"},
                credit_conversion={"ects": 2},
            )
        )
    ).ok


def test_sandbox_and_live_need_the_hubs_documents_client(docs):
    bare = ExternalUniversityPortalsAdapter()
    org_id = str(uuid.uuid4())
    args = {"exchange_key": "k", "partner_id": "uni-oslo", "format": "csv", "transcript": transcript()}
    for mode in ("sandbox", "live"):
        assert (
            bare.export_records(
                Context(organisation_id=org_id, provider="file", mode=mode, settings=partner()), **args
            ).error.code
            == "not_configured"
        )
    assert bare.export_records(
        Context(organisation_id=org_id, provider="file", mode="mock", settings=partner()), **args
    ).ok


def test_signing_is_refused_not_silently_skipped(adapter, org):
    ctx = org.ctx("elmo", secrets={"signing_key": "-----BEGIN PRIVATE KEY-----", "signing_certificate": "x"})
    r = adapter.export_records(ctx, exchange_key="s", partner_id="uni-oslo", format="elmo_xml", transcript=transcript())
    assert r.error.code == "unsupported" and "BEGIN" not in repr(r) and "BEGIN" not in repr(ctx)


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
    ctx = org.ctx()
    for result in (
        adapter.export_records(ctx, exchange_key=bad, partner_id=bad, format=bad, transcript=bad, document_id=bad),
        adapter.export_records(ctx, exchange_key="k", partner_id="uni-oslo", format="csv", transcript=bad),
        adapter.export_records(
            ctx, exchange_key="k", partner_id="uni-oslo", format="pdf", transcript=transcript(), document_id=bad
        ),
        adapter.send_records(ctx, exchange_id=bad, message=bad),
        adapter.record_manual_delivery(ctx, exchange_id=bad, delivered_on=bad, delivered_by=bad, partner_reference=bad),
        adapter.import_records(ctx, exchange_key=bad, partner_id=bad, format=bad, document_id=bad),
    ):
        assert isinstance(result, Result) and result.error is not None


def test_transcript_validation_names_fields_never_values(adapter, org):
    secret = "Secret Student " + "x" * 300
    t = transcript()
    t["learner"]["name"] = secret
    r = export(adapter, org, "csv", transcript=t)
    assert r.error.code == "invalid_request" and "Secret Student" not in repr(r) and "learner.name" in r.error.detail


BROKEN = [
    (lambda t: t.pop("entries"), "entries", "required"),
    (lambda t: t.update(entries=[]), "entries", "items_count"),
    (lambda t: t["entries"][0].update(credits=-1), "entries[0].credits", "minimum"),
    (lambda t: t["entries"][0].update(credits=float("nan")), "entries[0].credits", "not_finite"),
    (lambda t: t["entries"][0].update(credits=float("inf")), "entries[0].credits", "not_finite"),
    (lambda t: t["entries"][0].update(credits=True), "entries[0].credits", "type"),
    (lambda t: t["entries"][0].update(status="done"), "entries[0].status", "enum"),
    (lambda t: t["entries"][0].update(credit_system="gold"), "entries[0].credit_system", "enum"),
    (lambda t: t["entries"][0].update(completed_on="2024-02-30"), "entries[0].completed_on", "date"),
    (
        lambda t: t["entries"][0].update(completed_on="2024-01-01", started_on="2024-06-01"),
        "entries[0].completed_on",
        "before_start",
    ),
    (lambda t: t["learner"].update(date_of_birth="12/04/2003"), "learner.date_of_birth", "pattern"),
    (lambda t: t["learner"].update(date_of_birth="2030-01-01"), "learner.date_of_birth", "after_issue"),
    (lambda t: t["learner"].update(email="not an email"), "learner.email", "pattern"),
    (lambda t: t["learner"].update(person_id="nope"), "learner.person_id", "pattern"),
    (lambda t: t["issuer"].update(country="IND"), "issuer.country", "length"),
    (lambda t: t["programme"].update(eqf_level=9), "programme.eqf_level", "maximum"),
    (lambda t: t["totals"].update(credits_earned=99), "totals.credits_earned", "total_mismatch"),
    (lambda t: t.update(entries=t["entries"] * 200), "entries", "items_count"),
    (lambda t: t.update(invented=1), "invented", "unknown_field"),
    (lambda t: t["entries"][0].update(title="t" * 301), "entries[0].title", "length"),
]


@pytest.mark.parametrize(("mutate", "path", "code"), BROKEN, ids=[f"{b[2]}:{b[1]}" for b in BROKEN])
def test_every_transcript_rule_has_a_failing_fixture(adapter, org, mutate, path, code):
    t = transcript()
    mutate(t)
    r = export(adapter, org, "csv", transcript=t)
    assert r.error and r.error.code == "invalid_request" and f"{path} ({code})" in r.error.detail


def test_format_specific_requirements_are_reported(adapter, org):
    t = transcript()
    t["issuer"].pop("url")
    assert "issuer.url (required)" in export(adapter, org, "elmo_xml", transcript=t).error.detail
    assert export(adapter, org, "csv", transcript=t).ok  # CSV does not need it
    t = transcript()
    t["issuer"]["country"] = "ZZ"
    assert "issuer.country (unknown_country)" in export(adapter, org, "edc_jsonld", transcript=t).error.detail
    t = transcript()
    for e in t["entries"]:
        e["status"] = "in_progress"
    t["totals"] = {}
    assert "entries (no_passed_entries)" in export(adapter, org, "edc_jsonld", transcript=t).error.detail
