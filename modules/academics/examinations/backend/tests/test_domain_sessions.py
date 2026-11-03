"""Unit tests of papers, sessions and duties (domain layer): FR-4, FR-5, FR-6, FR-9."""

from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from conftest import uid
from eos_examinations.domain import assessment as asm
from eos_examinations.domain import cycles as cyc
from eos_examinations.domain import papers as pap
from eos_examinations.domain import sessions as ses
from eos_examinations.domain.errors import DomainRuleError

IST = timezone(timedelta(hours=5, minutes=30))
START = datetime(2026, 11, 25, 4, 0, tzinfo=UTC)  # 09:30 IST on the 25th


def code(fn, *args, **kw) -> DomainRuleError:
    with pytest.raises(DomainRuleError) as e:
        fn(*args, **kw)
    return e.value


def cycle(status="draft", **over) -> cyc.Cycle:
    base = {
        "id": uid(),
        "academic_period_id": uid(),
        "code": "END",
        "name": "End term",
        "cycle_type": "end_term",
        "starts_on": date(2026, 11, 20),
        "ends_on": date(2026, 12, 10),
        "grading_scheme_id": uid(),
        "status": status,
    }
    return cyc.Cycle(**{**base, **over})


def scheme(status="active") -> asm.Scheme:
    comps = [
        {"code": "THEORY", "name": "Written", "kind": "written", "weightage_percent": 70, "max_marks": 100},
        {"code": "PRAC", "name": "Practical", "kind": "practical", "weightage_percent": 30, "max_marks": 50},
    ]
    return asm.Scheme(**{**asm.new_scheme(uid(), uid(), 40, comps).__dict__, "status": status})


def ids_of(s: asm.Scheme) -> dict[str, str]:
    return {c.code: uid() for c in s.components}


def make_papers(c=None, s=None, requested=None, **kw):
    c, s = c or cycle(), s or scheme()
    return (
        c,
        s,
        pap.plan_papers(
            c,
            s,
            kw.pop("component_ids", None) or ids_of(s),
            [{"component_code": "THEORY"}] if requested is None else requested,
            paper_id=uid,
            **kw,
        ),
    )


# ---------------------------------------------------------------- papers


def test_a_paper_is_created_per_listed_component_with_the_components_max_marks():
    c, s, papers = make_papers(
        requested=[{"component_code": "THEORY", "duration_minutes": 180}, {"component_code": "PRAC"}]
    )
    assert [(p.max_marks, p.duration_minutes, p.status) for p in papers] == [
        (Decimal(100), 180, "draft"),
        (Decimal(50), None, "draft"),
    ]
    assert {p.exam_cycle_id for p in papers} == {c.id} and {p.course_offering_id for p in papers} == {
        s.course_offering_id
    }


@pytest.mark.parametrize("status", ["draft", "scheduled"])
def test_papers_can_be_created_while_the_cycle_can_be_configured(status):
    assert make_papers(c=cycle(status))[2]


def test_papers_are_refused_once_the_cycle_is_running():
    err = code(make_papers, c=cycle("in_progress"))
    assert err.code == "cycle_not_configurable"


def test_papers_come_from_the_active_scheme_only():
    for status in ("draft", "superseded"):
        err = code(make_papers, s=scheme(status))
        assert (err.code, err.kind) == ("scheme_not_active", "unprocessable")


@pytest.mark.parametrize(
    ("requested", "expected", "kind"),
    [
        ([{"component_code": "NOPE"}], "unknown_component", "unprocessable"),
        ([{"component_code": None}], "unknown_component", "unprocessable"),
        (["THEORY"], "unknown_component", "unprocessable"),
        ([{"component_code": "THEORY"}, {"component_code": "THEORY"}], "duplicate_component", "invalid"),
        ([], "no_papers", "invalid"),
        ([{"component_code": "THEORY", "duration_minutes": 0}], "below_minimum", "invalid"),
    ],
)
def test_invalid_paper_requests_are_refused(requested, expected, kind):
    err = code(make_papers, requested=requested)
    assert (err.code, err.kind) == (expected, kind)


def test_one_paper_per_component_and_cycle():
    s = scheme()
    component_ids = ids_of(s)
    err = code(make_papers, s=s, component_ids=component_ids, existing_component_ids=[component_ids["THEORY"]])
    assert (err.code, err.kind, err.field) == ("paper_exists", "conflict", "papers[0].component_code")


def test_the_marks_pipeline_moves_forward_one_status_at_a_time():
    p = make_papers()[2][0]
    for target in ("scheduled", "marks_entry", "moderation", "locked"):
        p = pap.plan_status_change(p, target)
    assert p.status == "locked"
    err = code(pap.plan_status_change, p, "draft")
    assert (err.code, err.details["allowed"]) == ("invalid_status_transition", None)
    assert code(pap.plan_status_change, make_papers()[2][0], "moderation").kind == "conflict"


def test_only_a_scheduled_paper_returns_to_draft():
    draft = make_papers()[2][0]
    scheduled = pap.plan_status_change(draft, "scheduled")
    assert pap.return_to_draft(scheduled).status == "draft"
    for p in (draft, pap.plan_status_change(scheduled, "marks_entry")):
        assert code(pap.return_to_draft, p).code == "paper_not_scheduled"


# ---------------------------------------------------------------- sessions


def session(**over) -> ses.Session:
    return ses.new_session(
        over.pop("id", uid()),
        over.pop("cycle_id", uid()),
        over.pop("starts", START),
        over.pop("ends", START + timedelta(hours=3)),
        **over,
    )


def test_a_session_is_scheduled_with_a_trimmed_venue_and_invigilators():
    s = session(invigilators_required=2, venue_label="  Hall A ")
    assert (s.status, s.venue_label, s.invigilators_required, s.cancel_reason) == ("scheduled", "Hall A", 2, None)
    assert session(venue_label="   ").venue_label is None


@pytest.mark.parametrize(
    ("change", "expected", "field"),
    [
        ({"ends": START}, "invalid_session_times", "ends_at"),
        ({"starts": datetime(2026, 11, 25, 9, 0)}, "invalid_datetime", "starts_at"),
        ({"invigilators_required": -1}, "below_minimum", "invigilators_required"),
        ({"invigilators_required": "2"}, "invalid_integer", "invigilators_required"),
        ({"venue_label": 5}, "invalid_text", "venue_label"),
        ({"venue_label": "x" * 201}, "text_too_long", "venue_label"),
    ],
)
def test_invalid_sessions_are_refused(change, expected, field):
    err = code(session, **change)
    assert (err.code, err.kind, err.field) == (expected, "invalid", field)


def test_a_session_must_fall_within_the_cycle_dates_read_in_the_organisation_zone():
    c = cycle(starts_on=date(2026, 11, 25), ends_on=date(2026, 11, 25))
    ses.ensure_within_cycle(session(), c, IST)  # 09:30 to 12:30 IST on the 25th
    late = session(starts=datetime(2026, 11, 25, 20, 0, tzinfo=UTC), ends=datetime(2026, 11, 25, 22, 0, tzinfo=UTC))
    ses.ensure_within_cycle(late, c, UTC)
    err = code(ses.ensure_within_cycle, late, c, IST)  # 01:30 to 03:30 IST on the 26th
    assert (err.code, err.kind) == ("session_outside_cycle", "unprocessable")
    assert (
        code(
            ses.ensure_within_cycle,
            session(starts=START - timedelta(days=9), ends=START - timedelta(days=9, hours=-2)),
            c,
            IST,
        ).kind
        == "unprocessable"
    )


def test_both_ends_of_the_cycle_are_inclusive():
    ses.ensure_within_cycle(session(), cycle(starts_on=date(2026, 11, 25), ends_on=date(2026, 12, 1)), IST)
    ses.ensure_within_cycle(session(), cycle(starts_on=date(2026, 11, 1), ends_on=date(2026, 11, 25)), IST)


def test_papers_of_a_session_must_be_draft_papers_of_its_cycle_in_no_other_session():
    c = cycle()
    s = scheme()
    papers = pap.plan_papers(c, s, ids_of(s), [{"component_code": "THEORY"}, {"component_code": "PRAC"}], paper_id=uid)
    ses.ensure_papers_schedulable(papers, c.id)
    cases = [
        (dict(papers=[], exam_cycle_id=c.id), "no_papers", "invalid"),
        (dict(papers=[papers[0], papers[0]], exam_cycle_id=c.id), "duplicate_paper", "invalid"),
        (dict(papers=papers, exam_cycle_id=uid()), "paper_not_in_cycle", "unprocessable"),
        (
            dict(papers=papers, exam_cycle_id=c.id, papers_in_sessions=[papers[1].id]),
            "paper_already_scheduled",
            "conflict",
        ),
        (
            dict(papers=[pap.plan_status_change(papers[0], "scheduled")], exam_cycle_id=c.id),
            "paper_not_draft",
            "conflict",
        ),
    ]
    for kwargs, expected, kind in cases:
        err = code(ses.ensure_papers_schedulable, **kwargs)
        assert (err.code, err.kind) == (expected, kind), kwargs
    assert code(
        ses.ensure_papers_schedulable, papers=papers, exam_cycle_id=c.id, papers_in_sessions=[papers[1].id]
    ).details == {"exam_paper_id": papers[1].id}


def test_a_scheduled_session_is_rescheduled_and_reports_what_changed():
    s = session(venue_label="Hall A")
    moved, changed = ses.plan_reschedule(
        s, starts_at=START + timedelta(days=1), ends_at=START + timedelta(days=1, hours=3), venue_label="Hall B"
    )
    assert changed == ["starts_at", "ends_at", "venue_label"]
    assert (moved.id, moved.status, moved.venue_label) == (s.id, "scheduled", "Hall B")
    assert ses.plan_reschedule(s, starts_at=s.starts_at, venue_label="Hall A") == (s, [])
    assert ses.plan_reschedule(s, venue_label=None)[0].venue_label is None
    assert code(ses.plan_reschedule, s, ends_at=START).code == "invalid_session_times"


def test_only_a_scheduled_session_changes_and_cancelling_needs_a_reason():
    s = session()
    cancelled = ses.plan_cancel(s, "  Strike ")
    assert (cancelled.status, cancelled.cancel_reason) == ("cancelled", "Strike")
    for done in (cancelled, ses.Session(**{**s.__dict__, "status": "completed"})):
        for action in (lambda x: ses.plan_reschedule(x, venue_label="B"), lambda x: ses.plan_cancel(x, "r")):
            err = code(action, done)
            assert (err.code, err.kind) == ("session_not_scheduled", "conflict")
    assert code(ses.plan_cancel, s, " ").code == "invalid_text"
    assert code(ses.plan_cancel, s, None).code == "invalid_text"
    assert s.status == "scheduled"


# ---------------------------------------------------------------- duties


def test_invigilation_needs_a_session_and_evaluation_or_moderation_a_paper_never_both():
    cycle_id, staff, sid, pid = uid(), uid(), uid(), uid()
    assert ses.Duty(uid(), cycle_id, staff, "invigilation", exam_session_id=sid).status == "assigned"
    for kind in ("evaluation", "moderation"):
        assert ses.Duty(uid(), cycle_id, staff, kind, exam_paper_id=pid).exam_session_id is None
    bad = [
        dict(duty_type="invigilation"),
        dict(duty_type="invigilation", exam_session_id=sid, exam_paper_id=pid),
        dict(duty_type="invigilation", exam_paper_id=pid),
        dict(duty_type="evaluation"),
        dict(duty_type="moderation", exam_session_id=sid),
        dict(duty_type="evaluation", exam_session_id=sid, exam_paper_id=pid),
    ]
    for kwargs in bad:
        err = code(ses.Duty, uid(), cycle_id, staff, **kwargs)
        assert (err.kind, err.code) in {
            ("invalid", "invigilation_needs_session"),
            ("invalid", "paper_duty_needs_paper"),
        }, kwargs
    assert code(ses.Duty, uid(), cycle_id, "not-a-uuid", "invigilation", exam_session_id=sid).field == "staff_id"
    assert code(ses.Duty, uid(), cycle_id, staff, "marking", exam_paper_id=pid).code == "invalid_choice"


def test_a_staff_member_cannot_invigilate_two_overlapping_sessions():
    cid = uid()
    a = session(id=uid(), cycle_id=cid)
    overlapping = session(cycle_id=cid, starts=START + timedelta(hours=2), ends=START + timedelta(hours=5))
    back_to_back = session(cycle_id=cid, starts=START + timedelta(hours=3), ends=START + timedelta(hours=6))
    ses.ensure_no_invigilation_clash(a, [back_to_back, a])  # touching is not overlapping; the session itself is ignored
    err = code(ses.ensure_no_invigilation_clash, a, [back_to_back, overlapping])
    assert (err.code, err.kind, err.details) == (
        "invigilation_overlap",
        "conflict",
        {"exam_session_id": overlapping.id},
    )


def test_windows_overlap_only_when_they_share_time():
    t = START
    assert ses.windows_overlap((t, t + timedelta(hours=2)), (t + timedelta(hours=1), t + timedelta(hours=3)))
    assert ses.windows_overlap((t, t + timedelta(hours=5)), (t + timedelta(hours=1), t + timedelta(hours=2)))
    assert not ses.windows_overlap((t, t + timedelta(hours=1)), (t + timedelta(hours=1), t + timedelta(hours=2)))


def test_an_assigned_duty_is_cancelled_with_a_reason():
    d = ses.Duty(uid(), uid(), uid(), "invigilation", exam_session_id=uid())
    cancelled = ses.plan_duty_cancel(d, " Unwell ")
    assert (cancelled.status, cancelled.cancel_reason) == ("cancelled", "Unwell")
    assert code(ses.plan_duty_cancel, d, "").code == "invalid_text"
    assert code(ses.plan_duty_cancel, cancelled, "again").code == "duty_not_assigned"
    assert code(ses.plan_duty_cancel, ses.Duty(**{**d.__dict__, "status": "completed"}), "r").kind == "conflict"
