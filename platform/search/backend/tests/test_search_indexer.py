"""Indexing from events: the organisation comes from the envelope, delivery may repeat or arrive out of order, a
failing provider retries and then dead-letters, and the other consumers (entitlement, purge)."""

import pytest
from eos_core.events import OutboxEvent
from eos_core.tenant import organisation_scope, platform_scope
from eos_search.application import consumers, indexer, service, state
from eos_search.application.health import platform_health
from eos_search.application.registry import use_registry
from eos_search.domain.documents import version_of
from eos_search.domain.models import DeadLetter, Entitlement, IndexState
from eos_search.infrastructure.config import SearchConfig
from search_support import (
    ARTICLE,
    COURSE,
    NOW,
    PERSON,
    READ_COURSE,
    READ_PERSON,
    FakeEvent,
    article,
    caller,
    course,
    later,
    new_org,
    person,
)
from sqlalchemy import select


def handle(db, event, registry, engine, **kw):
    out = indexer.index_event(db, event, registry=registry, engine=engine, config=SearchConfig.from_env(), **kw)
    db.commit()
    return out


def course_event(org, rid="c1", name="academic-management.course.updated", at=NOW, **payload):
    return FakeEvent(name, org, {"course_id": rid, **payload}, occurred_at=at)


def hits(registry, engine, org, q, *grants):
    return service.search(caller(org, *grants), q=q, registry=registry, engine=engine)["items"]


def test_an_upsert_event_indexes_what_the_provider_returns_for_the_envelope_organisation(
    search_db, search_registry, search_providers, search_engine
):
    org = new_org()
    search_providers["academic-management"].put(org, "course", "c1", **course("Fluid mechanics", "ME-301"))
    with organisation_scope(org):
        assert handle(search_db, course_event(org), search_registry, search_engine) == ["indexed"]
    assert [h["title"] for h in hits(search_registry, search_engine, org, "fluid", READ_COURSE)] == ["Fluid mechanics"]
    # The provider was asked in the event's organisation, by the module's short type name and the payload's id.
    assert search_providers["academic-management"].calls == [(org, "course", "c1")]
    doc = search_engine.document(f"{org}:{COURSE}:c1")
    assert doc["organisation_id"] == org and doc["source_version"] == version_of(NOW)


def test_an_organisation_in_the_payload_is_ignored(search_db, search_registry, search_providers, search_engine):
    real, spoofed = new_org(), new_org()
    search_providers["academic-management"].put(real, "course", "c1", **course("Genuine"))
    search_providers["academic-management"].put(spoofed, "course", "c1", **course("Spoofed"))
    with organisation_scope(real):
        handle(search_db, course_event(real, organisation_id=spoofed), search_registry, search_engine)
    assert hits(search_registry, search_engine, real, "genuine", READ_COURSE)
    assert not hits(search_registry, search_engine, spoofed, "spoofed", READ_COURSE)
    assert all(d["organisation_id"] == real for d in search_engine.all_documents())


def test_an_event_without_an_organisation_indexes_nothing(search_db, search_registry, search_providers, search_engine):
    search_providers["academic-management"].put("x", "course", "c1", **course("Nowhere"))
    assert handle(search_db, course_event(None), search_registry, search_engine) == []
    assert search_engine.all_documents() == [] and search_providers["academic-management"].calls == []


def test_repeated_delivery_changes_nothing(search_db, search_registry, search_providers, search_engine):
    org = new_org()
    search_providers["academic-management"].put(org, "course", "c1", **course("Thermodynamics"))
    event = course_event(org)
    with organisation_scope(org):
        assert handle(search_db, event, search_registry, search_engine) == ["indexed"]
        assert handle(search_db, event, search_registry, search_engine) == ["stale"]
    assert len(search_engine.all_documents()) == 1


def test_a_late_older_event_cannot_overwrite_a_newer_document(
    search_db, search_registry, search_providers, search_engine
):
    org = new_org()
    provider = search_providers["academic-management"]
    provider.put(org, "course", "c1", **course("Version two"))
    with organisation_scope(org):
        handle(search_db, course_event(org, at=later(10)), search_registry, search_engine)
        provider.put(org, "course", "c1", **course("Version one"))  # state changed back before the old event arrives
        assert handle(search_db, course_event(org, at=later(5)), search_registry, search_engine) == ["stale"]
    assert search_engine.document(f"{org}:{COURSE}:c1")["title"] == "Version two"


def test_a_record_gone_at_the_source_is_removed(search_db, search_registry, search_providers, search_engine):
    org = new_org()
    provider = search_providers["academic-management"]
    provider.put(org, "course", "c1", **course("Soon gone"))
    with organisation_scope(org):
        handle(search_db, course_event(org, at=later(1)), search_registry, search_engine)
        provider.remove(org, "course", "c1")
        assert handle(search_db, course_event(org, at=later(2)), search_registry, search_engine) == ["deleted"]
    assert search_engine.all_documents() == []


def test_a_delete_trigger_removes_without_calling_the_provider(
    search_db, search_registry, search_providers, search_engine
):
    org = new_org()
    provider = search_providers["academic-management"]
    provider.put(org, "course", "c1", **course("Archived soon"))
    with organisation_scope(org):
        handle(search_db, course_event(org, at=later(1)), search_registry, search_engine)
        calls = len(provider.calls)
        out = handle(
            search_db,
            course_event(org, name="academic-management.course.archived", at=later(2)),
            search_registry,
            search_engine,
        )
    assert out == ["deleted"] and len(provider.calls) == calls and search_engine.all_documents() == []


def test_one_event_can_trigger_two_types_and_an_unknown_event_none(search_db, search_registry, search_engine):
    assert handle(search_db, FakeEvent("billing.invoice.issued", new_org(), {}), search_registry, search_engine) == []


def test_a_payload_without_the_id_field_is_skipped_not_a_crash(search_db, search_registry, search_engine):
    org = new_org()
    for payload in ({}, {"course_id": None}, {"course_id": ""}, {"course_id": ["x"]}, {"course_id": "a" * 500}):
        with organisation_scope(org):
            assert handle(
                search_db, FakeEvent("academic-management.course.updated", org, payload), search_registry, search_engine
            ) == ["skipped"]


def test_a_failing_provider_is_retried_with_backoff_and_then_succeeds(
    search_db, search_registry, search_providers, search_engine
):
    org = new_org()
    provider = search_providers["academic-management"]
    provider.put(org, "course", "c1", **course("Flaky source"))
    provider.fail, provider.failures_left = RuntimeError("db down: secret row text"), 2
    pauses = []
    with organisation_scope(org):
        assert handle(search_db, course_event(org), search_registry, search_engine, pause=pauses.append) == ["indexed"]
    assert len(provider.calls) == 3 and len(pauses) == 2
    assert pauses[1] == pauses[0] * 2 or pauses == [0, 0]  # backoff doubles (zero in tests)
    assert search_db.scalar(select(DeadLetter)) is None


def test_after_the_last_retry_the_document_is_dead_lettered_and_counted(
    search_db, search_registry, search_providers, search_engine, caplog
):
    org = new_org()
    provider = search_providers["academic-management"]
    provider.put(org, "course", "c1", **course("Never indexed"))
    provider.fail, provider.failures_left = RuntimeError("secret row text"), -1  # always
    with organisation_scope(org):
        assert handle(search_db, course_event(org), search_registry, search_engine) == ["dead_lettered"]
    assert len(provider.calls) == 3  # SEARCH_INDEX_ATTEMPTS
    assert search_engine.all_documents() == []
    row = search_db.scalar(select(DeadLetter))
    assert (row.organisation_id, row.type_key, row.record_id, row.reason) == (org, COURSE, "c1", "provider_failed")
    assert "secret row text" not in caplog.text  # the exception type is logged, never its message
    assert platform_health(search_db, search_engine, search_registry)["dead_lettered"] == 1


def test_a_later_success_clears_the_dead_letter(search_db, search_registry, search_providers, search_engine):
    org = new_org()
    provider = search_providers["academic-management"]
    provider.put(org, "course", "c1", **course("Recovered"))
    provider.fail, provider.failures_left = RuntimeError("x"), -1
    with organisation_scope(org):
        handle(search_db, course_event(org, at=later(1)), search_registry, search_engine)
        provider.failures_left = 0
        handle(search_db, course_event(org, at=later(2)), search_registry, search_engine)
    assert search_db.scalar(select(DeadLetter)) is None and len(search_engine.all_documents()) == 1


def test_an_engine_outage_during_indexing_is_retried_then_dead_lettered(
    search_db, search_registry, search_providers, search_engine
):
    org = new_org()
    search_providers["academic-management"].put(org, "course", "c1", **course("Engine down"))
    search_engine.down = True
    with organisation_scope(org):
        assert handle(search_db, course_event(org), search_registry, search_engine) == ["dead_lettered"]
    assert search_db.scalar(select(DeadLetter)).reason == "engine_unavailable"


def test_a_document_for_another_organisation_is_rejected_and_the_old_version_removed(
    search_db, search_registry, search_providers, search_engine
):
    org, other = new_org(), new_org()
    provider = search_providers["academic-management"]
    provider.put(org, "course", "c1", **course("Honest first version"))
    with organisation_scope(org):
        handle(search_db, course_event(org, at=later(1)), search_registry, search_engine)
        provider.put(org, "course", "c1", **{**course("Wrong tenant"), "organisation_id": other})
        assert handle(search_db, course_event(org, at=later(2)), search_registry, search_engine) == ["rejected"]
    assert search_engine.all_documents() == []  # fail closed: the earlier document does not outlive a refused one
    assert search_db.scalar(select(DeadLetter)).reason == "organisation_mismatch"


def test_a_record_that_is_no_longer_readable_by_anyone_is_removed(
    search_db, search_registry, search_providers, search_engine
):
    org = new_org()
    provider = search_providers["knowledge-base"]
    provider.put(org, "article", "a1", **article("Draft policy"))
    with organisation_scope(org):
        handle(
            search_db,
            FakeEvent("knowledge-base.article.published", org, {"article_id": "a1"}, occurred_at=later(1)),
            search_registry,
            search_engine,
        )
        provider.put(org, "article", "a1", **{**article("Draft policy"), "read_any_of": []})
        out = handle(
            search_db,
            FakeEvent("knowledge-base.article.published", org, {"article_id": "a1"}, occurred_at=later(2)),
            search_registry,
            search_engine,
        )
    assert out == ["rejected"] and search_engine.all_documents() == []


def test_index_state_records_the_last_indexed_time(search_db, search_registry, search_providers, search_engine):
    org = new_org()
    search_providers["student-information"].put(org, "person", "p1", **person("Meera Nair"))
    with organisation_scope(org):
        handle(
            search_db,
            FakeEvent("student-information.person.created", org, {"person_id": "p1"}),
            search_registry,
            search_engine,
        )
    row = search_db.scalar(select(IndexState).where(IndexState.organisation_id == org))
    assert row.type_key == PERSON and row.last_indexed_at is not None and row.last_reindex_at is None


def test_the_consumer_registers_the_first_modules_events_and_the_platform_ones():
    names = set(consumers.CONSUMERS)
    assert set(consumers.FIRST_MODULE_EVENTS) <= names
    assert {"tenancy.organisation.purged", "tenancy.entitlement.changed"} <= names
    assert all(callable(h) for h in consumers.CONSUMERS.values())


def test_build_consumers_adds_the_trigger_events_of_every_registered_declaration(search_registry):
    assert search_registry.trigger_events() <= set(consumers.build_consumers())


def test_on_trigger_goes_through_the_process_registry(search_db, search_registry, search_providers, search_engine):
    org = new_org()
    search_providers["academic-management"].put(org, "course", "c9", **course("Via the consumer"))
    with organisation_scope(org):
        consumers.on_trigger(search_db, course_event(org, "c9"))
        search_db.commit()
    assert search_engine.document(f"{org}:{COURSE}:c9")


# --- entitlement -------------------------------------------------------------------------------------------------
def test_entitlement_changes_keep_search_s_copy_and_hide_a_switched_off_module(
    search_db, search_registry, search_providers, search_engine
):
    org = new_org()
    search_providers["academic-management"].put(org, "course", "c1", **course("Entitled content"))
    with organisation_scope(org):
        handle(search_db, course_event(org), search_registry, search_engine)
        assert state.entitled_modules(search_db, org) is None  # not known yet: nothing is filtered on its account
        consumers.on_entitlement_changed(
            search_db,
            FakeEvent(
                "tenancy.entitlement.changed",
                org,
                {"modules": ["academics/academic-management", "x/y"], "organisation_id": org},
            ),
        )
        search_db.commit()
        modules = state.entitled_modules(search_db, org)
    assert "academic-management" in modules and "knowledge-base" not in modules and "identity" in modules
    mine = caller(org, READ_COURSE, entitled=modules)
    assert service.search(mine, q="entitled", registry=search_registry, engine=search_engine)["total"] == 1
    with organisation_scope(org):
        consumers.on_entitlement_changed(search_db, FakeEvent("tenancy.entitlement.changed", org, {"modules": []}))
        search_db.commit()
        modules = state.entitled_modules(search_db, org)
    off = caller(org, READ_COURSE, entitled=modules)
    assert (
        service.search(off, q="entitled", registry=search_registry, engine=search_engine)["total"] == 0
    )  # next request
    assert search_db.scalars(select(Entitlement).where(Entitlement.organisation_id == org)).all()


def test_entitlement_event_without_an_organisation_is_ignored(search_db):
    consumers.on_entitlement_changed(search_db, FakeEvent("tenancy.entitlement.changed", None, {"modules": ["a"]}))
    assert search_db.scalar(select(Entitlement)) is None


# --- purge -------------------------------------------------------------------------------------------------------
def test_a_purge_removes_every_document_and_row_of_the_organisation_and_reports_it(
    search_db, search_registry, search_providers, search_engine
):
    gone, kept = new_org(), new_org()
    for org in (gone, kept):
        search_providers["academic-management"].put(org, "course", "c1", **course("Purge candidate"))
        with organisation_scope(org):
            handle(search_db, course_event(org), search_registry, search_engine)
            state.set_entitlement(search_db, org, ["x"])
            state.record_dead_letter(search_db, org, "academic-management", COURSE, "zz", None, "provider_failed")
            search_db.commit()
    with platform_scope():  # the envelope has no organisation, so the relay runs this in platform scope
        consumers.on_purged(
            search_db, FakeEvent("tenancy.organisation.purged", None, {"organisation_id": gone, "slug": "x"})
        )
        search_db.commit()
    assert [d["organisation_id"] for d in search_engine.all_documents()] == [kept]
    with platform_scope():
        assert search_db.scalars(select(DeadLetter.organisation_id)).all() == [kept]
        assert search_db.scalars(select(IndexState.organisation_id)).all() == [kept]
        emitted = search_db.scalars(select(OutboxEvent).where(OutboxEvent.name == "search.organisation.purged")).all()
    assert len(emitted) == 1 and emitted[0].organisation_id is None
    assert emitted[0].payload["organisation_id"] == gone and emitted[0].payload["documents_deleted"] == 1
    # Redelivery is harmless: nothing left to delete, another notice with a count of zero.
    with platform_scope():
        consumers.on_purged(search_db, FakeEvent("tenancy.organisation.purged", None, {"organisation_id": gone}))
        search_db.commit()
    assert len(search_engine.all_documents()) == 1


@pytest.mark.parametrize(
    "payload", [{}, {"organisation_id": None}, {"organisation_id": "not-a-uuid"}, {"organisation_id": "*"}]
)
def test_a_purge_without_a_usable_organisation_deletes_nothing(
    search_db, search_registry, search_providers, search_engine, payload
):
    org = new_org()
    search_providers["academic-management"].put(org, "course", "c1", **course("Survivor"))
    with organisation_scope(org):
        handle(search_db, course_event(org), search_registry, search_engine)
    with platform_scope():
        consumers.on_purged(search_db, FakeEvent("tenancy.organisation.purged", None, payload))
    assert len(search_engine.all_documents()) == 1


def test_a_purge_during_an_outage_raises_so_the_relay_retries(search_db, search_engine):
    search_engine.down = True
    with platform_scope(), pytest.raises(Exception, match="unavailable"):
        consumers.on_purged(search_db, FakeEvent("tenancy.organisation.purged", None, {"organisation_id": new_org()}))


def test_registry_is_not_leaked_between_tests(search_registry):
    with use_registry(search_registry) as r:
        assert r is search_registry
    assert ARTICLE in search_registry.types and READ_PERSON
