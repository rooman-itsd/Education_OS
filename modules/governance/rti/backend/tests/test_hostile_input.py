"""Input that is not what the contract describes is a 4xx, never a 500 (reviewers on this team try exactly these)."""

import json

import pytest
from conftest import BASE, days

BODY_ROUTES = [
    ("post", "/requests"),
    ("patch", "/requests/{id}"),
    ("post", "/requests/{id}/assign"),
    ("post", "/requests/{id}/referrals"),
    ("post", "/requests/{id}/respond"),
    ("post", "/requests/{id}/transfer"),
    ("post", "/requests/{id}/appeal"),
    ("post", "/requests/{id}/appeal-decision"),
    ("post", "/referrals/{id}/reply"),
]
RAW_BODIES = [
    '{"subject": NaN}',
    '{"subject": Infinity}',
    '{"subject": -Infinity}',
    '{"subject": 1e999}',
    '{"fee": {"status": "paid", "amount": {"amount": 1e999}}}',
    '{"subject": ',
    "",
    "null",
    "[]",
    '"text"',
    "[" * 200 + "]" * 200,
    "[" * 100_000,
    '{"a":' * 50_000,
    '{"received_on": "2026-02-30"}',
    '{"received_on": "2026-11-05T10:00:00"}',
    '{"received_on": 20261105}',
    '{"received_on": "٢٠٢٦-١١-٠٥"}',
    '{"subject": "\\ud800\\udc00\\ud800"}',
    '{"subject": "ab\\u0000"}',
    '{"fee": {"status": "paid", "amount": {"amount": "1' + "0" * 5000 + '"}}}',
    '{"limit": ' + "9" * 5000 + "}",
]


@pytest.fixture
def probe(desk):
    r = desk.assigned()

    def send(method: str, path: str, raw: str, headers: dict):
        url = BASE + path.replace("{id}", r["id"])
        return desk.client.request(
            method.upper(), url, content=raw, headers={**headers, "content-type": "application/json"}
        )

    return send, r


@pytest.mark.parametrize("raw", RAW_BODIES)
@pytest.mark.parametrize(("method", "path"), BODY_ROUTES, ids=[f"{m} {p}" for m, p in BODY_ROUTES])
def test_a_hostile_body_is_a_4xx(desk, probe, method, path, raw):
    send, _ = probe
    for headers in (desk.officer, desk.appellate, desk.custodian):
        assert 400 <= send(method, path, raw, headers).status_code < 500, (headers is desk.officer, raw[:40])


def test_a_body_with_nan_or_a_huge_number_says_why(desk, probe):
    send, _ = probe
    for raw in ('{"subject": NaN}', '{"subject": 1e999}'):
        refused = send("patch", "/requests/{id}", raw, desk.officer)
        assert (refused.status_code, refused.json()["detail"]["code"]) == (422, "invalid_json")
    assert send("patch", "/requests/{id}", '{"subject": 1e3}', desk.officer).status_code == 422  # a number: wrong type
    assert send("patch", "/requests/{id}", json.dumps({"subject": "A fine subject"}), desk.officer).status_code == 200


@pytest.mark.parametrize(
    "query",
    [
        "limit=2147483648",
        "limit=-2147483649",
        "cursor=" + "9" * 40,
        "overdue=2",
        "q=" + "%25" * 300,
        "officer=ME,me",
        "status=,,,",
    ],
)
def test_a_hostile_query_is_a_4xx(desk, query):
    assert 400 <= desk.get(f"/requests?{query}").status_code < 500 or query == "status=,,,"
    assert desk.get(f"/referrals?{query}").status_code < 500


def test_a_lone_surrogate_never_reaches_the_database(desk):
    body = '{"received_via":"post","received_on":"%s","applicant":{"name":"A\\ud800"},"subject":"Subject","information_sought":"Info","fee":{"status":"exempt"}}'
    refused = desk.client.post(
        BASE + "/requests", content=body % days(0), headers={**desk.officer, "content-type": "application/json"}
    )
    assert refused.status_code == 422
