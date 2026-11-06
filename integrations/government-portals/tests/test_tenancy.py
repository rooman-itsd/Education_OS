"""No organisation sees another's packages (module standard: cross-tenant leak test)."""

from eos_testing import assert_no_cross_tenant_leak
from gp_support import PREFIX, load_case, prepare


def test_no_cross_tenant_leak(client, adapter, docs, org, other_org):
    for o in (org, other_org):
        prepare(adapter, o, docs, load_case("aishe-dcf-ii"))
        prepare(adapter, o, docs, load_case("nirf-dcs-overall"))
    assert_no_cross_tenant_leak(client, f"{PREFIX}/packages", org.token("admin"), other_org.token("admin"))


def test_another_organisations_package_is_not_found(client, adapter, docs, org, other_org):
    pid = prepare(adapter, org, docs, load_case("aishe-dcf-ii")).output["package_id"]
    assert client.get(f"{PREFIX}/packages/{pid}", headers=org.admin).status_code == 200
    assert client.get(f"{PREFIX}/packages/{pid}", headers=other_org.admin).status_code == 404
    assert adapter.get_package(other_org.ctx("aishe"), package_id=pid).error.code == "not_found"
    assert adapter.submit(other_org.ctx("aishe"), package_id=pid).error.code == "not_found"
    r = adapter.record_manual_submission(
        other_org.ctx("aishe"),
        package_id=pid,
        submitted_on="2026-01-01",
        submitted_by=other_org.admin_id,
        portal_reference="R",
    )
    assert r.error.code == "not_found"
    assert adapter.get_package(org.ctx("aishe"), package_id=pid).output["status"] == "prepared"


def test_the_same_key_in_two_organisations_is_two_packages(adapter, docs, org, other_org):
    a = prepare(adapter, org, docs, load_case("aishe-dcf-ii"), key="shared-key").output["package_id"]
    b = prepare(adapter, other_org, docs, load_case("aishe-dcf-ii"), key="shared-key").output["package_id"]
    assert a != b
    assert adapter.get_package(org.ctx("aishe"), package_id=a).output["status"] == "prepared"  # not superseded by b


def test_events_carry_their_organisation(adapter, docs, org, other_org):
    from gp_support import outbox

    prepare(adapter, org, docs, load_case("aishe-dcf-ii"))
    assert len(outbox(org.id, "government-portals.package.prepared")) == 1
    assert outbox(other_org.id, "government-portals.package.prepared") == []
