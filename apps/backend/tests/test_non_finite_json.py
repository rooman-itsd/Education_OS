"""Through the real app: a body no 422 could quote back (NaN, Infinity, 1e999, a lone surrogate) answers 422 for
every router, with no workaround in the module itself. Uses identity's login, which any caller may reach."""

import pytest

LOGIN = "/api/v1/identity/auth/login"


def send(client, raw: str):
    return client.post(
        LOGIN, content=raw.encode("utf-8", "surrogatepass"), headers={"content-type": "application/json"}
    )


@pytest.mark.parametrize("v", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_non_finite_numbers_answer_422(client, v):
    r = send(client, '{"email": ' + v + ', "password": "x"}')
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "email"]


def test_a_lone_surrogate_answers_422(client):
    r = send(client, '{"email": ["\\ud800"], "password": "x"}')
    assert r.status_code == 422


def test_a_normal_invalid_value_and_a_valid_request_are_unchanged(client):
    r = send(client, '{"email": 5, "password": "x"}')
    assert r.status_code == 422
    assert r.json()["detail"][0]["input"] == 5
    assert send(client, '{"email": "nobody@example.com", "password": "x"}').status_code in (401, 403, 404, 429)
