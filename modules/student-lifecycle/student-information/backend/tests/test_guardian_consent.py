"""The guardian's consent for a minor (DPDP gap D7): the institution obtains it offline, the platform records it.

- `minor` derived from the date of birth: under 18 today, exactly 18 today, unknown, a 29 February today
- recording (default today, a past date, recorded_by the caller) and withdrawing, each in the append-only history
  and announced by `person.guardian-consent-changed` without the note
- the future-date refusal and the other rule errors
- `GET /people?minor=true&guardian_consent=false` lists the minors whose consent is missing
- permissions: person:write records, person:read reads, nothing else; cross-tenant reads and writes are 404
"""

from __future__ import annotations

from datetime import date, timedelta

from conftest import ADMISSIONS, NO_ACCESS, READ_ONLY, REGISTRAR, make_auth_headers
from eos_core.db import SessionLocal, new_id
from eos_core.events import OutboxEvent
from eos_student_information.api import schemas as s
from eos_student_information.domain.rules import (
    RuleViolationError,
    adult_cutoff,
    is_minor,
    validate_consent_date,
)
from sqlalchemy import select

BASE = "/api/v1/student-information"
TODAY = date.today()
CONSENT_EVENT = "student-information.person.guardian-consent-changed"


def _years_ago(years: int, today: date = TODAY) -> date:
    try:
        return today.replace(year=today.year - years)
    except ValueError:
        return today.replace(year=today.year - years, day=28)


def _org() -> str:
    return f"org-gc-{new_id()[:8]}"


def _headers(org: str, role: str = REGISTRAR, user: str = "user-registrar-1") -> dict[str, str]:
    return make_auth_headers(user_id=user, organisation_id=org, roles=[role])


def _person(client, headers, dob: date | None, name: str = "Asha") -> dict:
    body = {"first_name": name, "last_name": "Rao"}
    if dob is not None:
        body["date_of_birth"] = dob.isoformat()
    res = client.post(f"{BASE}/people", json=body, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _consent(client, headers, person_id: str, **body):
    return client.put(f"{BASE}/people/{person_id}/guardian-consent", json=body, headers=headers)


def _events(org: str) -> list[dict]:
    with SessionLocal() as db:
        rows = db.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.organisation_id == org, OutboxEvent.name == CONSENT_EVENT)
            .order_by(OutboxEvent.occurred_at.asc())
        ).all()
        return [r.payload for r in rows]


# ---------------------------------------------------------------- minor derivation (domain)


def test_minor_under_18_exactly_18_and_unknown():
    today = date(2026, 11, 20)
    assert is_minor(date(2008, 11, 21), today) is True  # 18 tomorrow
    assert is_minor(date(2008, 11, 20), today) is False  # 18 today
    assert is_minor(date(2000, 1, 1), today) is False
    assert is_minor(date(2026, 1, 1), today) is True
    assert is_minor(None, today) is None


def test_minor_on_29_february():
    """18 years before 29 February 2028 has no 29 February: born 28 February 2010 is 18, 1 March 2010 is 17."""
    today = date(2028, 2, 29)
    assert adult_cutoff(today) == date(2010, 2, 28)
    assert is_minor(date(2010, 2, 28), today) is False
    assert is_minor(date(2010, 3, 1), today) is True


def test_consent_date_today_or_past_is_accepted_and_future_refused():
    today = date(2026, 11, 20)
    validate_consent_date(today, today)
    validate_consent_date(date(2026, 6, 1), today)
    try:
        validate_consent_date(date(2026, 11, 21), today)
    except RuleViolationError as exc:
        assert exc.code == "consent_date_in_future"
    else:
        raise AssertionError("a future consent date was accepted")


# ---------------------------------------------------------------- the person carries minor and guardian_consent


def test_person_reports_minor_and_no_consent_by_default(client):
    h = _headers(_org())
    child = _person(client, h, _years_ago(17))
    adult = _person(client, h, _years_ago(18))
    unknown = _person(client, h, None)

    assert child["minor"] is True
    assert adult["minor"] is False  # exactly 18 today
    assert unknown["minor"] is None
    for p in (child, adult, unknown):
        assert p["guardian_consent"] == {"obtained": False, "obtained_on": None, "recorded_by": None, "note": None}
        s.Person.model_validate(p)

    fetched = client.get(f"{BASE}/people/{child['id']}", headers=h).json()
    assert fetched["minor"] is True


def test_consent_is_not_set_through_create_or_update(client):
    h = _headers(_org())
    res = client.post(
        f"{BASE}/people",
        json={"first_name": "A", "last_name": "B", "guardian_consent": {"obtained": True}},
        headers=h,
    )
    assert res.status_code == 422
    p = _person(client, h, _years_ago(15))
    res = client.patch(f"{BASE}/people/{p['id']}", json={"guardian_consent": {"obtained": True}}, headers=h)
    assert res.status_code == 422


# ---------------------------------------------------------------- recording and withdrawing, audited


def test_record_defaults_to_today_and_the_caller(client):
    org = _org()
    h = _headers(org, user="user-registrar-7")
    p = _person(client, h, _years_ago(16))

    res = _consent(client, h, p["id"], obtained=True, note="Signed form GC-12 on file")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["guardian_consent"] == {
        "obtained": True,
        "obtained_on": TODAY.isoformat(),
        "recorded_by": "user-registrar-7",
        "note": "Signed form GC-12 on file",
    }
    s.Person.model_validate(body)

    history = client.get(f"{BASE}/people/{p['id']}/guardian-consent", headers=h)
    assert history.status_code == 200
    [entry] = history.json()
    s.GuardianConsentEntry.model_validate(entry)
    assert entry["action"] == "recorded"
    assert entry["obtained_on"] == TODAY.isoformat()
    assert entry["changed_by"] == "user-registrar-7"
    assert entry["note"] == "Signed form GC-12 on file"

    # The event says whether consent is on file; never the note or anything about the guardian
    assert _events(org) == [
        {
            "organisation_id": org,
            "person_id": p["id"],
            "guardian_consent_obtained": True,
            "obtained_on": TODAY.isoformat(),
        }
    ]


def test_record_with_a_past_date_then_withdraw(client):
    org = _org()
    h = _headers(org)
    p = _person(client, h, _years_ago(12))
    past = TODAY - timedelta(days=30)

    res = _consent(client, h, p["id"], obtained=True, obtained_on=past.isoformat())
    assert res.status_code == 200, res.text
    assert res.json()["guardian_consent"]["obtained_on"] == past.isoformat()

    withdrawer = _headers(org, user="user-registrar-2")
    res = _consent(client, withdrawer, p["id"], obtained=False, note="Parent withdrew by letter")
    assert res.status_code == 200, res.text
    assert res.json()["guardian_consent"] == {"obtained": False, "obtained_on": None, "recorded_by": None, "note": None}

    entries = client.get(f"{BASE}/people/{p['id']}/guardian-consent", headers=h).json()
    by_action = {e["action"]: e for e in entries}
    assert set(by_action) == {"recorded", "withdrawn"}
    assert by_action["recorded"]["obtained_on"] == past.isoformat()
    assert by_action["withdrawn"]["changed_by"] == "user-registrar-2"
    assert by_action["withdrawn"]["note"] == "Parent withdrew by letter"
    assert by_action["withdrawn"]["obtained_on"] is None

    published = _events(org)
    assert [e["guardian_consent_obtained"] for e in published] == [True, False]
    assert published[1]["obtained_on"] is None
    assert all("note" not in e for e in published)


def test_recording_again_corrects_the_date(client):
    h = _headers(_org())
    p = _person(client, h, _years_ago(10))
    _consent(client, h, p["id"], obtained=True, obtained_on=(TODAY - timedelta(days=3)).isoformat())
    res = _consent(client, h, p["id"], obtained=True, obtained_on=(TODAY - timedelta(days=5)).isoformat())
    assert res.status_code == 200
    assert res.json()["guardian_consent"]["obtained_on"] == (TODAY - timedelta(days=5)).isoformat()
    assert len(client.get(f"{BASE}/people/{p['id']}/guardian-consent", headers=h).json()) == 2


def test_future_date_is_refused_and_nothing_is_recorded(client):
    org = _org()
    h = _headers(org)
    p = _person(client, h, _years_ago(14))
    res = _consent(client, h, p["id"], obtained=True, obtained_on=(TODAY + timedelta(days=1)).isoformat())
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "consent_date_in_future"
    assert client.get(f"{BASE}/people/{p['id']}", headers=h).json()["guardian_consent"]["obtained"] is False
    assert client.get(f"{BASE}/people/{p['id']}/guardian-consent", headers=h).json() == []
    assert _events(org) == []


def test_withdrawing_needs_a_recorded_consent_and_takes_no_date(client):
    h = _headers(_org())
    p = _person(client, h, _years_ago(14))
    res = _consent(client, h, p["id"], obtained=False)
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "consent_not_recorded"

    _consent(client, h, p["id"], obtained=True)
    res = _consent(client, h, p["id"], obtained=False, obtained_on=TODAY.isoformat())
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "consent_date_not_allowed"


def test_consent_can_be_recorded_for_an_adult_and_an_unknown_age(client):
    """The platform records; it never refuses on age (no hard block)."""
    h = _headers(_org())
    for dob in (_years_ago(30), None):
        p = _person(client, h, dob)
        assert _consent(client, h, p["id"], obtained=True).status_code == 200


# ---------------------------------------------------------------- the list filter


def test_list_minors_missing_consent(client):
    h = _headers(_org())
    missing = _person(client, h, _years_ago(16), name="Missing")
    on_file = _person(client, h, _years_ago(15), name="OnFile")
    withdrawn = _person(client, h, _years_ago(13), name="Withdrawn")
    adult = _person(client, h, _years_ago(18), name="Adult")
    unknown = _person(client, h, None, name="Unknown")
    _consent(client, h, on_file["id"], obtained=True)
    _consent(client, h, withdrawn["id"], obtained=True)
    _consent(client, h, withdrawn["id"], obtained=False)

    def ids(query: str) -> set[str]:
        res = client.get(f"{BASE}/people?{query}", headers=h)
        assert res.status_code == 200, res.text
        page = res.json()
        assert page["total"] == len(page["items"])
        return {p["id"] for p in page["items"]}

    assert ids("minor=true&guardian_consent=false") == {missing["id"], withdrawn["id"]}
    assert ids("minor=true&guardian_consent=true") == {on_file["id"]}
    assert ids("minor=true") == {missing["id"], on_file["id"], withdrawn["id"]}
    assert ids("minor=false") == {adult["id"]}
    assert ids("guardian_consent=false") == {missing["id"], withdrawn["id"], adult["id"], unknown["id"]}
    assert client.get(f"{BASE}/people?minor=maybe", headers=h).status_code == 422


# ---------------------------------------------------------------- permissions and tenants


def test_permissions(client):
    org = _org()
    h = _headers(org)
    p = _person(client, h, _years_ago(16))

    # person:write records: registrar (above) and admissions staff, who collect it with the application
    assert _consent(client, _headers(org, ADMISSIONS), p["id"], obtained=True).status_code == 200

    # read-only management can see the history but not record or withdraw
    read_only = _headers(org, READ_ONLY)
    assert _consent(client, read_only, p["id"], obtained=False).status_code == 403
    assert client.get(f"{BASE}/people/{p['id']}/guardian-consent", headers=read_only).status_code == 200

    no_access = _headers(org, NO_ACCESS)
    assert _consent(client, no_access, p["id"], obtained=True).status_code == 403
    assert client.get(f"{BASE}/people/{p['id']}/guardian-consent", headers=no_access).status_code == 403
    assert client.get(f"{BASE}/people?minor=true", headers=no_access).status_code == 403

    assert client.put(f"{BASE}/people/{p['id']}/guardian-consent", json={"obtained": True}).status_code == 401


def test_cross_tenant_reads_and_writes_are_404(client):
    org_a, org_b = _org(), _org()
    ha, hb = _headers(org_a), _headers(org_b)
    p = _person(client, ha, _years_ago(16))
    _person(client, hb, _years_ago(16), name="OtherOrgChild")

    assert _consent(client, hb, p["id"], obtained=True).status_code == 404
    assert client.get(f"{BASE}/people/{p['id']}/guardian-consent", headers=hb).status_code == 404
    assert client.get(f"{BASE}/people/{p['id']}", headers=ha).json()["guardian_consent"]["obtained"] is False
    assert _events(org_b) == []

    listed_b = client.get(f"{BASE}/people?minor=true&guardian_consent=false", headers=hb).json()
    assert p["id"] not in {x["id"] for x in listed_b["items"]}
    assert listed_b["total"] == 1

    _consent(client, ha, p["id"], obtained=True)
    assert client.get(f"{BASE}/people?guardian_consent=true", headers=hb).json()["total"] == 0
