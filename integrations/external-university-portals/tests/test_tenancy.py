"""No organisation sees another's exchanges (module standard: cross-tenant leak test)."""

from eos_testing import assert_no_cross_tenant_leak
from eup_support import PREFIX, export, put


def test_no_cross_tenant_leak(client, adapter, docs, org, other_org):
    for o in (org, other_org):
        export(adapter, o, "csv")
        export(adapter, o, "elmo_xml")
        adapter.import_records(
            o.ctx(),
            exchange_key="in",
            partner_id="uni-oslo",
            format="csv",
            document_id=put(docs, o.id, b"course_code,title,credits,status\nC,T,1,passed\n"),
        )
    assert_no_cross_tenant_leak(client, f"{PREFIX}/exchanges", org.token("admin"), other_org.token("admin"))


def test_another_organisations_exchange_is_not_found(client, adapter, org, other_org):
    ex = export(adapter, org, "csv").output["exchange_id"]
    assert client.get(f"{PREFIX}/exchanges/{ex}", headers=org.admin).status_code == 200
    assert client.get(f"{PREFIX}/exchanges/{ex}", headers=other_org.admin).status_code == 404
    assert adapter.send_records(other_org.ctx(), exchange_id=ex).error.code == "not_found"
    r = adapter.record_manual_delivery(
        other_org.ctx(),
        exchange_id=ex,
        delivered_on="2026-11-05",
        delivered_by=other_org.admin_id,
        partner_reference="R",
    )
    assert r.error.code == "not_found"


def test_the_same_key_in_two_organisations_is_two_exchanges(adapter, org, other_org):
    a = export(adapter, org, "csv", key="shared").output["exchange_id"]
    b = export(adapter, other_org, "csv", key="shared").output["exchange_id"]
    assert a != b


def test_another_organisations_document_cannot_be_imported(adapter, docs, org, other_org):
    theirs = put(docs, other_org.id, b"course_code,title,credits,status\nC,T,1,passed\n")
    r = adapter.import_records(org.ctx(), exchange_key="x", partner_id="uni-oslo", format="csv", document_id=theirs)
    assert r.error.code == "invalid_request"
