"""Two requests for one trainee on different openings must not both pass the overlap check (found in the review of
#504, where 15 of 15 rounds on Postgres made two overlapping placements). The row locks on the openings do not cover
it, so every overlap check first takes a transaction lock on the trainee. The tests here run on SQLite, which cannot
race: they check that the lock is asked for, in time and for the right person, and what it sends on Postgres."""

from types import SimpleNamespace

from eos_field_training.infrastructure import repository as repo


def recorded(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(repo, "lock_trainee", lambda db, trainee_id: calls.append(trainee_id))
    return calls


def test_on_postgres_the_lock_is_a_transaction_advisory_lock_keyed_by_the_trainee():
    sent = []
    db = SimpleNamespace(
        get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
        execute=lambda stmt, params: sent.append((str(stmt), params)),
    )
    repo.lock_trainee(db, "t-1")
    repo.lock_trainee(db, "t-2")
    assert "pg_advisory_xact_lock" in sent[0][0]
    assert sent[0][1] != sent[1][1]  # one lock per trainee
    assert sent[0][1] == {"key": "field-training-trainee:t-1"}


def test_on_sqlite_the_lock_does_nothing():
    db = SimpleNamespace(
        get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="sqlite")),
        execute=lambda *a: (_ for _ in ()).throw(AssertionError("no statement on SQLite")),
    )
    repo.lock_trainee(db, "t-1")


def test_assigning_a_placement_locks_the_trainee(prog, monkeypatch):
    calls = recorded(monkeypatch)
    trainee_id, _, _ = prog.assigned()
    assert calls == [trainee_id]


def test_applying_locks_the_applicant(prog, monkeypatch):
    calls = recorded(monkeypatch)
    trainee_id, me = prog.trainee()
    prog.ok(prog.post(f"/openings/{prog.opening['id']}/apply", None, me), 201)
    assert calls == [trainee_id]


def test_approving_an_application_locks_its_trainee(prog, monkeypatch):
    trainee_id, me = prog.trainee()
    p = prog.ok(prog.post(f"/openings/{prog.opening['id']}/apply", None, me), 201)
    calls = recorded(monkeypatch)
    prog.ok(prog.post(f"/placements/{p['id']}/decision", {"decision": "approved"}, prog.coordinator))
    assert calls == [trainee_id]


def test_changing_the_dates_of_a_placement_locks_its_trainee(prog, monkeypatch):
    trainee_id, _, p = prog.assigned()
    calls = recorded(monkeypatch)
    prog.ok(prog.patch(f"/placements/{p['id']}", {"ends_on": "2026-12-30"}, prog.coordinator))
    assert calls == [trainee_id]


def test_an_overlap_is_still_refused_with_the_lock_in_place(prog):
    trainee_id, _, _ = prog.assigned()
    other = prog.new_opening(title="Same dates")
    r = prog.post("/placements", {"opening_id": other["id"], "trainee_id": trainee_id}, prog.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "overlapping_placement"
