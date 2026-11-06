"""Edge inputs answer 422 or 409, never a 500: cursors, limits, enums, ids and filters."""

import base64

import pytest
from eos_core.db import new_id


def cursor(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode()


@pytest.mark.parametrize("path", ["/me/grievances", "/grievances"])
def test_limits_cursors_and_filters_are_bounded(campus, path):
    c = campus
    c.file()
    who = c.complainant if path.startswith("/me") else c.member()
    assert c.get(f"{path}?limit=0", who).status_code == 422
    assert c.get(f"{path}?limit=101", who).status_code == 422
    assert c.get(f"{path}?limit=100000000000000000000", who).status_code == 422
    assert c.get(f"{path}?limit=abc", who).status_code == 422
    assert c.get(f"{path}?limit=100", who).status_code == 200
    for bad in (
        "nope!",
        "%C3%A9",
        cursor(b"-5"),
        cursor(b"1.5"),
        cursor(b"99999999999999999999"),
        cursor(b"9223372036854775808"),
        cursor("١٢٣".encode()),  # Arabic-Indic digits are not ASCII digits
        cursor(b"1" * 40),
        "A" * 65,
    ):
        r = c.get(f"{path}?cursor={bad}", who)
        assert (r.status_code, r.json()["detail"]["code"]) == (422, "invalid_cursor"), bad
    assert c.get(f"{path}?cursor={cursor(b'0')}", who).status_code == 200
    past_the_end = c.get(f"{path}?cursor={cursor(b'1000')}", who)
    assert past_the_end.status_code == 200 and past_the_end.json()["items"] == []
    for q in ("status=nonsense", "status=submitted,nonsense", "status=%20,"):
        r = c.get(f"{path}?{q}", who)
        assert r.status_code in (200, 422), q
    assert c.get(f"{path}?status=nonsense", who).status_code == 422
    assert c.get(f"{path}?status=" + "a" * 5000, who).status_code == 422


def test_committee_list_filters_are_validated(campus):
    c = campus
    for q in (
        "track=bullying",
        "overdue=maybe",
        f"committee_id={new_id()},{new_id()}",
        "committee_id=me",
        "committee_id=",
    ):
        r = c.get(f"/grievances?{q}", c.member())
        assert r.status_code == 422, q
    assert c.get("/grievances?committee_id=" + new_id(), c.member()).status_code == 200


def test_ids_that_are_not_uuids_are_not_found(campus):
    c = campus
    for bad in ("1", "me", "../etc", "x" * 300, "%27%3B--"):
        assert c.get(f"/grievances/{bad}", c.member()).status_code == 404, bad
        assert c.get(f"/me/grievances/{bad}", c.complainant).status_code == 404, bad
        assert c.post(f"/grievances/{bad}/status", {"status": "acknowledged"}, c.member()).status_code == 404, bad
        assert c.patch(f"/committees/{bad}", {"name": "x"}).status_code == 404, bad


def test_oversized_and_unicode_text_is_stored_or_refused_cleanly(campus):
    c = campus
    emoji = "Ünïcödé 😀 complaint " * 5
    case = c.file(category="Café 😀", description=emoji)
    assert c.ok(c.get(f"/grievances/{case['id']}", c.member()))["description"] == emoji
    assert (
        c.post(
            "/me/grievances", {"track": "ragging", "category": "x", "description": "y" * 20_000}, c.complainant
        ).status_code
        == 201
    )
    assert (
        c.post(
            "/me/grievances", {"track": "ragging", "category": "x", "description": "y" * 20_001}, c.complainant
        ).status_code
        == 422
    )
    # not JSON at all, or the wrong shape
    assert (
        c.client.post(
            "/api/v1/grievance/me/grievances",
            content=b"{",
            headers={**c.complainant, "content-type": "application/json"},
        ).status_code
        == 422
    )
    assert c.post("/me/grievances", [1, 2], c.complainant).status_code == 422
    assert c.post(f"/me/grievances/{case['id']}/withdraw", {"reason": "r" * 2001}, c.complainant).status_code == 422
    assert c.post(f"/me/grievances/{case['id']}/withdraw", {"unknown": 1}, c.complainant).status_code == 422


def test_a_duplicate_that_slips_past_the_check_is_a_conflict(campus, monkeypatch):
    """Two requests at once both pass the lookup; the unique constraint catches the second one."""
    from eos_grievance.infrastructure import repository

    c = campus
    monkeypatch.setattr(repository, "committee_by_name", lambda db, name: None)
    r = c.post("/committees", {"name": "sgrc committee", "kind": "sgrc"})
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "name_used")
    r = c.patch(f"/committees/{c.committees['icc']['id']}", {"name": "sgrc committee"})
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "name_used")
    # the organisation is still usable after the refused writes
    assert c.post("/committees", {"name": "Fresh", "kind": "sgrc"}).status_code == 201


def test_a_case_number_taken_at_the_same_moment_is_a_conflict_not_a_500(campus, monkeypatch):
    from eos_grievance.infrastructure import repository

    c = campus
    c.file()
    monkeypatch.setattr(repository, "next_sequence", lambda db: 1)
    body = {"track": "student_grievance", "category": "x", "description": "d" * 12}
    r = c.post("/me/grievances", body, c.complainant)
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "number_taken")
