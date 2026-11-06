"""Rebuilds: stale-document cleanup, the alias swap for a changed mapping, failure that leaves the old index live, the
dead-letter bookkeeping, throttling, and the job lifecycle."""

import copy
from datetime import UTC, datetime, timedelta

import pytest
from eos_core.events import OutboxEvent
from eos_core.tenant import organisation_scope, platform_scope
from eos_search.application import indexer, reindex, service, state
from eos_search.application.registry import Registry
from eos_search.domain import models
from eos_search.domain.models import DeadLetter, IndexState, ReindexJob
from eos_search.infrastructure.config import SearchConfig
from search_support import (
    ARTICLE,
    COURSE,
    READ_ARTICLE,
    READ_COURSE,
    ExampleProvider,
    article,
    caller,
    course,
    declaration,
    index,
    new_org,
    providers,
    registry_of,
)
from sqlalchemy import select

MODULE = "academic-management"


def make_job(db, org, module=MODULE, type_key=None, registry=None):
    with organisation_scope(org):
        job = reindex.start_reindex(
            db, organisation_id=org, requested_by=None, module=module, type_key=type_key, registry=registry
        )
        db.commit()
    return job.id


def run(job_id, registry, engine, **kw):
    reindex.run_reindex_job(
        job_id, registry=registry, engine=engine, config=SearchConfig.from_env(), pause=lambda s: None, **kw
    )


def job_row(db, job_id):
    db.expire_all()
    with platform_scope():
        return db.get(ReindexJob, job_id)


def events_named(db, name):
    with platform_scope():
        return list(db.scalars(select(OutboxEvent).where(OutboxEvent.name == name)))


def total(registry, engine, org, q, *grants):
    return service.search(caller(org, *grants), q=q, registry=registry, engine=engine)["total"]


def test_a_reindex_rewrites_the_organisation_and_removes_documents_deleted_at_the_source(
    search_db, search_registry, search_providers, search_engine, monkeypatch
):
    monkeypatch.setenv("SEARCH_REINDEX_BATCH_SIZE", "2")
    org, other = new_org(), new_org()
    provider = search_providers[MODULE]
    for i in range(5):
        provider.put(org, "course", f"c{i}", **course(f"Delta course {i}"))
    provider.put(other, "course", "c0", **course("Delta of another tenant"))
    index(search_engine, search_registry, org, COURSE, "ghost", course("Delta ghost"))  # deleted at source, event lost
    index(search_engine, search_registry, other, COURSE, "c0", course("Delta of another tenant"))
    assert total(search_registry, search_engine, org, "delta", READ_COURSE) == 1  # only the ghost is indexed yet

    job_id = make_job(search_db, org)
    run(job_id, search_registry, search_engine)

    job = job_row(search_db, job_id)
    assert job.status == "succeeded" and job.documents_indexed == 5 and job.documents_failed == 0 and job.error is None
    assert job.started_at and job.finished_at
    assert total(search_registry, search_engine, org, "delta", READ_COURSE) == 5  # the ghost is gone
    assert total(search_registry, search_engine, other, "delta", READ_COURSE) == 1  # another tenant untouched
    assert {d["organisation_id"] for d in search_engine.all_documents()} == {org, other}
    done = events_named(search_db, "search.reindex.completed")
    assert len(done) == 1 and done[0].organisation_id == org
    assert done[0].payload["documents_indexed"] == 5 and done[0].payload["job_id"] == job_id
    row = search_db.scalar(select(IndexState).where(IndexState.organisation_id == org))
    assert row.last_reindex_at is not None


def test_a_reindex_of_one_type_leaves_the_modules_other_types_alone(search_db, search_engine):
    decl = copy.deepcopy(declaration(MODULE))
    second = copy.deepcopy(decl["types"][0])
    second["name"] = "programme"
    second["triggers"] = []
    decl["types"].append(second)
    provider = ExampleProvider(MODULE, decl)
    registry = Registry()
    registry.add(MODULE, provider)
    org = new_org()
    provider.put(org, "course", "c1", **course("Echo course"))
    provider.put(org, "programme", "p1", **course("Echo programme"))
    run(make_job(search_db, org, type_key=COURSE, registry=registry), registry, search_engine)
    assert [d["type"] for d in search_engine.all_documents()] == [COURSE]


def test_a_document_the_provider_gives_wrongly_is_counted_failed_and_dead_lettered_not_fatal(
    search_db, search_registry, search_providers, search_engine
):
    org = new_org()
    provider = search_providers[MODULE]
    provider.put(org, "course", "c1", **course("Foxtrot good"))
    provider.put(org, "course", "c2", fields={"code": "no title"})
    provider.put(org, "course", "c3", **{**course("Foxtrot wrong tenant"), "organisation_id": new_org()})
    with organisation_scope(org):
        state.record_dead_letter(
            search_db, org, MODULE, COURSE, "old", None, "provider_failed"
        )  # repaired by a rebuild
        search_db.commit()
    job_id = make_job(search_db, org)
    run(job_id, search_registry, search_engine)
    job = job_row(search_db, job_id)
    assert job.status == "succeeded" and job.documents_indexed == 1 and job.documents_failed == 2
    with platform_scope():
        letters = {(d.record_id, d.reason) for d in search_db.scalars(select(DeadLetter))}
    assert letters == {
        ("c2", "title_missing"),
        ("c3", "organisation_mismatch"),
    }  # the old one cleared, new ones counted
    assert events_named(search_db, "search.reindex.completed")[0].payload["documents_failed"] == 2


def test_a_failing_provider_fails_the_job_with_a_sentence_and_keeps_the_old_documents(
    search_db, search_registry, search_providers, search_engine, caplog
):
    org = new_org()
    provider = search_providers[MODULE]
    index(search_engine, search_registry, org, COURSE, "kept", course("Golf keeper"))
    provider.put(org, "course", "c1", **course("Golf new"))
    provider.fail, provider.failures_left = RuntimeError("password=hunter2 in a row"), -1
    # iter_documents does not use get_document's failure hook, so fail it directly
    provider.iter_documents = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("password=hunter2 in a row"))
    job_id = make_job(search_db, org)
    run(job_id, search_registry, search_engine)
    job = job_row(search_db, job_id)
    assert job.status == "failed" and "provider failed" in job.error and "hunter2" not in job.error
    assert "hunter2" not in caplog.text
    assert total(search_registry, search_engine, org, "golf", READ_COURSE) == 1  # the old index is untouched
    failed = events_named(search_db, "search.reindex.failed")
    assert len(failed) == 1 and failed[0].payload["job_id"] == job_id and "hunter2" not in str(failed[0].payload)
    assert events_named(search_db, "search.reindex.completed") == []


def test_an_engine_outage_fails_the_job_cleanly(search_db, search_registry, search_providers, search_engine):
    org = new_org()
    search_providers[MODULE].put(org, "course", "c1", **course("Hotel"))
    job_id = make_job(search_db, org)
    search_engine.down = True
    run(job_id, search_registry, search_engine)
    job = job_row(search_db, job_id)
    assert job.status == "failed" and "engine" in job.error
    # and the scope is free again for the next request
    assert make_job(search_db, org)


def test_a_changed_mapping_builds_a_new_version_for_every_organisation_and_swaps_the_alias_atomically(
    search_db, search_engine, search_providers
):
    org, other = new_org(), new_org()
    old_registry = registry_of(search_providers)  # the mapping the live index was built from
    provider = search_providers[MODULE]
    for o in (org, other):
        provider.put(o, "course", "c1", **course(f"India course of {o[:4]}"))
        index(search_engine, old_registry, o, COURSE, "c1", course("India stale copy"))
        with organisation_scope(o):
            state.touch_state(search_db, o, COURSE)
            search_db.commit()
    live_before = search_engine.aliases["eos-dev-academic-management-course"]
    assert live_before.endswith("-v1")

    # The module added a field: the mapping hash changes, so the live index is out of date.
    newer = copy.deepcopy(declaration(MODULE))
    newer["types"][0]["fields"]["level"] = {"kind": "keyword", "filterable": True}
    registry = Registry()
    provider.declaration = newer
    registry.add(MODULE, provider)
    spec = registry.types[COURSE]
    assert not search_engine.mapping_current(spec)

    job_id = make_job(search_db, org, registry=registry)
    run(job_id, registry, search_engine)

    assert job_row(search_db, job_id).status == "succeeded"
    assert search_engine.aliases["eos-dev-academic-management-course"].endswith("-v2")
    assert search_engine.mapping_current(spec)
    titles = {d["organisation_id"]: d["title"] for d in search_engine.all_documents()}
    assert titles[org].startswith("India course of") and titles[other].startswith("India course of")  # both rebuilt


def test_a_failure_before_the_swap_leaves_the_old_index_live(search_db, search_engine, search_providers):
    org = new_org()
    provider = search_providers[MODULE]
    old_registry = registry_of(search_providers)
    index(search_engine, old_registry, org, COURSE, "c1", course("Juliet original"))
    newer = copy.deepcopy(declaration(MODULE))
    newer["types"][0]["fields"]["level"] = {"kind": "keyword"}
    provider.declaration = newer
    registry = Registry()
    registry.add(MODULE, provider)
    provider.iter_documents = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    job_id = make_job(search_db, org, registry=registry)
    run(job_id, registry, search_engine)
    assert job_row(search_db, job_id).status == "failed"
    assert search_engine.aliases["eos-dev-academic-management-course"].endswith("-v1")
    assert [d["title"] for d in search_engine.all_documents()] == ["Juliet original"]
    assert events_named(search_db, "search.reindex.failed")


def test_reindex_is_rate_limited(search_db, search_registry, search_providers, search_engine, monkeypatch):
    monkeypatch.setenv("SEARCH_REINDEX_BATCH_SIZE", "2")
    monkeypatch.setenv("SEARCH_REINDEX_MAX_DOCS_PER_SECOND", "1")
    org = new_org()
    for i in range(4):
        search_providers[MODULE].put(org, "course", f"c{i}", **course(f"Kilo {i}"))
    pauses = []
    reindex.run_reindex_job(
        make_job(search_db, org),
        registry=search_registry,
        engine=search_engine,
        config=SearchConfig.from_env(),
        pause=pauses.append,
    )
    assert len(pauses) == 2 and all(p > 1.0 for p in pauses)  # two batches of two at one document per second


def test_running_a_job_twice_or_an_unknown_job_does_nothing(
    search_db, search_registry, search_providers, search_engine
):
    org = new_org()
    search_providers[MODULE].put(org, "course", "c1", **course("Lima"))
    job_id = make_job(search_db, org)
    run(job_id, search_registry, search_engine)
    run(job_id, search_registry, search_engine)
    run("00000000-0000-0000-0000-000000000000", search_registry, search_engine)
    assert len(events_named(search_db, "search.reindex.completed")) == 1


def test_an_abandoned_job_is_failed_so_the_scope_frees_up(search_db, search_registry, monkeypatch):
    monkeypatch.setenv("SEARCH_JOB_STALE_SECONDS", "60")
    org = new_org()
    job_id = make_job(search_db, org)
    with platform_scope():
        row = search_db.get(ReindexJob, job_id)
        row.status, row.started_at = models.RUNNING, datetime.now(UTC) - timedelta(hours=1)
        search_db.commit()
    with organisation_scope(org):
        fresh = reindex.start_reindex(
            search_db,
            organisation_id=org,
            requested_by=None,
            module=MODULE,
            type_key=None,
            registry=search_registry,
            config=SearchConfig.from_env(),
        )
        search_db.commit()
    old = job_row(search_db, job_id)
    assert old.status == "failed" and "abandoned" in old.error and fresh.id != job_id


def test_the_database_itself_allows_one_active_job_per_scope(search_db):
    org = new_org()
    with organisation_scope(org):
        search_db.add(ReindexJob(organisation_id=org, module=MODULE, scope_key=f"{MODULE}|", status="queued"))
        search_db.commit()
        search_db.add(ReindexJob(organisation_id=org, module=MODULE, scope_key=f"{MODULE}|", status="running"))
        with pytest.raises(Exception, match="UNIQUE|unique"):
            search_db.commit()
        search_db.rollback()
        search_db.add(ReindexJob(organisation_id=org, module=MODULE, scope_key=f"{MODULE}|", status="succeeded"))
        search_db.commit()  # finished jobs are history, any number


def test_article_visibility_survives_a_rebuild(search_db, search_registry, search_providers, search_engine):
    """A rebuild writes the same permission lists the event path does: an internal article stays internal."""
    org = new_org()
    search_providers["knowledge-base"].put(org, "article", "i1", **article("Mike internal memo", internal=True))
    search_providers["knowledge-base"].put(org, "article", "p1", **article("Mike public memo"))
    run(make_job(search_db, org, "knowledge-base"), search_registry, search_engine)
    assert total(search_registry, search_engine, org, "mike", READ_ARTICLE) == 1
    assert total(search_registry, search_engine, org, "mike", READ_ARTICLE, "knowledge-base:article:read-internal") == 2
    assert indexer and ARTICLE and providers
