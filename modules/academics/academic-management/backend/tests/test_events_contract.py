"""contracts/events.yaml against platform/event-bus's envelope rules, and every event the module actually publishes
against contracts/events.yaml."""

import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[5]
EVENTS = yaml.safe_load((Path(__file__).resolve().parents[2] / "contracts" / "events.yaml").read_text(encoding="utf-8"))
ENVELOPE = yaml.safe_load((ROOT / "platform/event-bus/contracts/events.yaml").read_text(encoding="utf-8"))["envelope"]
DECLARED = {e["name"]: e for e in EVENTS["events"]}


def test_every_event_declares_payload_version_1():
    assert all(e.get("version") == 1 for e in EVENTS["events"])


def test_no_payload_repeats_the_envelope_metadata():
    """The envelope's payload rule: never repeat organisation_id, actor or occurred_at; and `version` is the envelope's.
    (Entity fields that share a key with the envelope's `name`, such as a term's name, are a separate question for
    the event-bus owner and are left as the contract has them.)"""
    assert {"organisation_id", "actor", "occurred_at", "version"} <= set(ENVELOPE)
    for e in EVENTS["events"]:
        assert not {"organisation_id", "actor", "occurred_at", "version"} & set(e["payload"]), e["name"]


def test_the_curriculum_version_is_named_apart_from_the_envelope_version():
    payload = DECLARED["academic-management.curriculum.published"]["payload"]
    assert "curriculum_version" in payload and "version" not in payload


@pytest.mark.skipif(importlib.util.find_spec("eos_core") is None, reason="needs eos_core on PYTHONPATH")
def test_every_published_event_matches_its_declared_payload(client, org):
    from conftest import BASE, assign, make_course, make_offering, make_programme, make_term, ok, open_offering, outbox

    _, admin = org.user("org-admin")
    teacher, _ = org.user("faculty", name="T")
    term = make_term(client, admin)
    ok(client.post(f"{BASE}/terms/{term['id']}/activate", headers=admin))
    programme = make_programme(client, admin, duration_terms=1, credits_required=4)
    course = make_course(client, admin)
    ok(client.patch(f"{BASE}/programmes/{programme['id']}", json={"name": "Renamed"}, headers=admin))
    ok(client.patch(f"{BASE}/courses/{course['id']}", json={"title": "Renamed"}, headers=admin))
    item = {"course_id": course["id"], "programme_term": 1, "category": "core", "credits": 4}
    cur = ok(client.post(f"{BASE}/programmes/{programme['id']}/curricula", json={"items": [item]}, headers=admin), 201)
    ok(client.post(f"{BASE}/curricula/{cur['id']}/publish", headers=admin))
    o = make_offering(client, admin, course["id"], term["id"])
    ok(client.patch(f"{BASE}/offerings/{o['id']}", json={"programme_ids": [programme["id"]]}, headers=admin))
    ok(client.patch(f"{BASE}/sections/{o['sections'][0]['id']}", json={"capacity": 5}, headers=admin))
    open_offering(client, admin, o["id"], teacher)
    helper = assign(client, admin, o["id"], teacher, role="co_instructor", hours=1)
    ok(client.post(f"{BASE}/faculty-assignments/{helper['id']}/end", headers=admin))
    ok(client.post(f"{BASE}/programmes/{programme['id']}/archive", headers=admin))
    ok(client.post(f"{BASE}/courses/{course['id']}/archive", headers=admin))

    published = outbox(org.id)
    assert {name for name, _, _ in published} == set(DECLARED)  # every declared event was exercised
    for name, payload, actor in published:
        declared = DECLARED[name]["payload"]
        assert set(payload) == set(declared), name
        assert actor is not None, name
