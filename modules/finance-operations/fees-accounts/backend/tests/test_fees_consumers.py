"""Consumed events: online payments, admissions, hostel, transport and library (X1-X4, X6). Every handler is idempotent."""

from eos_core.db import SessionLocal
from eos_fees_accounts.application import consumers
from fees_support import BASE, adhoc, head, invoice, outbox, published


def handle(name: str, payload: dict) -> dict:
    with SessionLocal() as db:
        return consumers.handle(db, name, payload)


def succeeded(org, inv, reference="EOS1", amount=None, module="fees-accounts") -> dict:
    return {
        "organisation_id": org.id,
        "reference": reference,
        "purpose": "fee",
        "source_module": module,
        "source_reference": inv["id"],
        "amount": amount or inv["balance"],
        "currency": "INR",
        "completed_at": "2026-10-22T09:00:00+00:00",
    }


def test_online_payment_is_applied_exactly_once(client, org):
    inv = adhoc(client, org, "1200.00")
    first = handle(consumers.PAYMENT_SUCCEEDED, succeeded(org, inv))
    assert first["result"] == "applied" and first["invoice_status"] == "paid"
    assert handle(consumers.PAYMENT_SUCCEEDED, succeeded(org, inv))["result"] == "ignored"
    after = client.get(f"{BASE}/invoices/{inv['id']}", headers=org.staff).json()
    assert len(after["payments"]) == 1 and after["payments"][0]["mode"] == "online"
    assert after["payments"][0]["gateway_reference"] == "EOS1" and after["payments"][0]["receipt_id"]
    assert len([e for e in outbox("fees-accounts.invoice.paid", org.id) if e["invoice_id"] == inv["id"]]) == 1


def test_payment_events_of_other_modules_are_ignored(client, org):
    inv = adhoc(client, org, "10.00")
    assert handle(consumers.PAYMENT_SUCCEEDED, succeeded(org, inv, module="billing"))["result"] == "ignored"
    assert handle(consumers.PAYMENT_FAILED, succeeded(org, inv))["result"] == "ignored"
    assert handle("someone.else.happened", {"organisation_id": org.id})["result"] == "ignored"
    assert handle(consumers.PAYMENT_SUCCEEDED, {**succeeded(org, inv), "organisation_id": None})["result"] == "ignored"


def test_hostel_allocation_invoices_the_room_type_fee(client, org):
    h = head(client, org, "HOSTEL1", "hostel")
    s = published(client, org, [h], name="Hostel double", room_type="double")
    payload = {
        "organisation_id": org.id,
        "allocation_id": "ALLOC-1",
        "person_id": "p-hostel",
        "room_type": "double",
        "academic_year": "2026-27",
    }
    r = handle(consumers.ALLOCATION_CONFIRMED, payload)
    assert r["result"] == "invoiced" and len(r["invoices"]) == 2  # one per instalment
    assert handle(consumers.ALLOCATION_CONFIRMED, payload)["result"] == "ignored"
    items = client.get(f"{BASE}/invoices?person_id=p-hostel", headers=org.staff).json()["items"]
    assert {i["source"]["reference"] for i in items} == {"ALLOC-1"} and {i["fee_structure_id"] for i in items} == {
        s["id"]
    }
    single = handle(consumers.ALLOCATION_CONFIRMED, {**payload, "allocation_id": "ALLOC-2", "room_type": "single"})
    assert single["result"] == "ignored"  # no structure prices a single room
    cancelled = handle(
        consumers.ALLOCATION_CANCELLED, {"organisation_id": org.id, "allocation_id": "ALLOC-1", "reason": "left"}
    )
    assert cancelled["result"] == "cancelled" and len(cancelled["invoices"]) == 2
    assert all(
        i["status"] == "cancelled"
        for i in client.get(f"{BASE}/invoices?person_id=p-hostel", headers=org.staff).json()["items"]
    )


def test_cancelling_keeps_invoices_that_have_payments(client, org):
    inv = adhoc(client, org, "100.00", source={"module": "hostel", "reference": "ALLOC-9"})
    client.post(
        f"{BASE}/invoices/{inv['id']}/payments",
        json={"amount": "10", "mode": "cash", "paid_on": "2026-10-22"},
        headers=org.staff,
    )
    r = handle(consumers.ALLOCATION_CANCELLED, {"organisation_id": org.id, "allocation_id": "ALLOC-9"})
    assert r["kept_with_payments"] == [inv["number"]] and r["invoices"] == []


def test_transport_pass_and_the_staff_setting(client, org):
    h = head(client, org, "BUS1", "transport")
    published(client, org, [h], name="Route 7", route_id="route-7")
    student = {
        "organisation_id": org.id,
        "pass_id": "PASS-1",
        "person_id": "p-bus",
        "rider_type": "student",
        "route_id": "route-7",
    }
    assert handle(consumers.PASS_ISSUED, student)["result"] == "invoiced"
    staff = {**student, "pass_id": "PASS-2", "person_id": "p-staff", "rider_type": "staff"}
    assert handle(consumers.PASS_ISSUED, staff)["result"] == "ignored"
    client.put(f"{BASE}/settings", json={"invoice_staff_transport": True}, headers=org.staff)
    assert handle(consumers.PASS_ISSUED, staff)["result"] == "invoiced"
    assert handle(consumers.PASS_ISSUED, {**student, "pass_id": "PASS-3", "route_id": "nowhere"})["result"] == "ignored"
    assert handle(consumers.PASS_CANCELLED, {"organisation_id": org.id, "pass_id": "PASS-1"})["result"] == "cancelled"


def test_library_fines_follow_the_setting(client, org):
    fine = {
        "organisation_id": org.id,
        "fine_id": "FINE-1",
        "person_id": "p-lib",
        "loan_id": "L1",
        "reason": "late return",
        "amount": "45.00",
    }
    assert handle(consumers.FINE_RAISED, fine)["result"] == "ignored"  # desk only by default
    client.put(f"{BASE}/settings", json={"invoice_library_fines": True}, headers=org.staff)
    assert handle(consumers.FINE_RAISED, fine)["reason"].startswith("no active fee head")
    head(client, org, "LIBFINE", "library")
    r = handle(consumers.FINE_RAISED, fine)
    assert r["result"] == "invoiced"
    [inv] = client.get(f"{BASE}/invoices?person_id=p-lib", headers=org.staff).json()["items"]
    assert (
        inv["total"] == "45.00"
        and inv["due_date"] == "2026-11-06"
        and inv["source"] == {"module": "library", "reference": "FINE-1"}
    )
    assert handle(consumers.FINE_RAISED, fine)["result"] == "ignored"
    assert handle(consumers.FINE_WAIVED, {"organisation_id": org.id, "fine_id": "FINE-1"})["result"] == "cancelled"


def test_admission_accepted_needs_a_person_id(client, org):
    h = head(client, org, "ADM1", "admission")
    published(
        client,
        org,
        [h],
        name="Confirmation fee",
        applies_to="applicant",
        instalments=[{"label": "Confirmation", "percent": 100, "due_date": "2026-11-01"}],
    )
    event = {"organisation_id": org.id, "application_id": "APP-1", "academic_year": "2026-27", "programme_id": "prog-x"}
    assert "person id" in handle(consumers.APPLICATION_ACCEPTED, event)["reason"]
    r = handle(consumers.APPLICATION_ACCEPTED, {**event, "user_id": "applicant-1"})
    assert r["result"] == "invoiced"
    assert handle(consumers.APPLICATION_ACCEPTED, {**event, "user_id": "applicant-1"})["result"] == "ignored"
    [inv] = client.get(f"{BASE}/invoices?person_id=applicant-1", headers=org.staff).json()["items"]
    assert inv["lines"][0]["fee_head_name"] == "Adm1" and inv["source"]["module"] == "admissions"


def test_events_act_only_in_their_own_organisation(client, org, other_org):
    inv = invoice(client, org)
    r = handle(consumers.PAYMENT_SUCCEEDED, {**succeeded(org, inv), "organisation_id": other_org.id})
    assert r == {"result": "ignored", "reason": "invoice not found"}
