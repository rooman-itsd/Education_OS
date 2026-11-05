"""Domain rules (docs/prd.md sections 5 and 6): pure functions, no database."""

from datetime import UTC, datetime, timedelta

import pytest
from eos_lms.domain import rules
from eos_lms.domain.rules import RuleViolationError

T = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)


def code(fn, *args) -> str:
    with pytest.raises(RuleViolationError) as e:
        fn(*args)
    return e.value.code


def test_transitions():
    assert rules.transition(rules.COURSE_SPACE_TRANSITIONS, "active", "draft", "space") == "active"
    assert code(rules.transition, rules.COURSE_SPACE_TRANSITIONS, "archived", "draft", "space") == "invalid_status"
    assert rules.transition(rules.MATERIAL_TRANSITIONS, "published", "unpublished", "m") == "published"
    assert code(rules.transition, rules.WORK_TRANSITIONS, "published", "closed", "quiz") == "invalid_status"


def test_section_visibility():
    assert rules.section_visible([], None) and rules.section_visible([], "a")
    assert rules.section_visible(["a"], "a") and not rules.section_visible(["a"], "b")
    assert not rules.section_visible(["a"], None)


def test_lateness():
    assert rules.submission_lateness(T, T, False, None) is False
    assert code(rules.submission_lateness, T + timedelta(seconds=1), T, False, None) == "past_due"
    assert rules.submission_lateness(T + timedelta(days=5), T, True, None) is True
    assert code(rules.submission_lateness, T + timedelta(days=2), T, True, T + timedelta(days=1)) == "past_cutoff"
    assert code(rules.check_late_policy, T, True, T - timedelta(hours=1)) == "invalid_late_policy"
    assert code(rules.check_late_policy, T, False, T + timedelta(hours=1)) == "invalid_late_policy"


def test_submission_content():
    rules.check_submission_content("file", ["d"], None)
    rules.check_submission_content("text", [], "x")
    rules.check_submission_content("file_and_text", ["d"], "x")
    assert code(rules.check_submission_content, "none", [], "x") == "offline_submission"
    assert code(rules.check_submission_content, "file", [], None) == "invalid_submission"
    assert code(rules.check_submission_content, "text", [], " ") == "invalid_submission"
    assert code(rules.check_attempts_left, 2, 2) == "no_attempts_left"


def test_quiz_scoring():
    qs = [
        {"id": "1", "question_type": "single_choice", "options": ["a", "b"], "answer_key": [1], "points": 2},
        {"id": "2", "question_type": "multiple_choice", "options": ["a", "b", "c"], "answer_key": [0, 2], "points": 3},
        {"id": "3", "question_type": "true_false", "options": None, "answer_key": False, "points": 1},
        {"id": "4", "question_type": "short_answer", "options": None, "answer_key": ["Paris"], "points": 1},
    ]
    right = [
        {"question_id": "1", "selected_options": [1]},
        {"question_id": "2", "selected_options": [2, 0]},
        {"question_id": "3", "boolean_answer": False},
        {"question_id": "4", "text_answer": "  paris "},
    ]
    assert rules.score_attempt(qs, right) == (7.0, False)
    wrong = [{"question_id": "2", "selected_options": [0]}, {"question_id": "3", "boolean_answer": True}]
    assert rules.score_attempt(qs, wrong) == (0.0, False)
    assert rules.score_attempt([*qs, {"id": "5", "question_type": "essay", "points": 4}], []) == (0.0, True)


def test_question_and_answer_shapes():
    rules.check_question({"question_type": "essay"})
    assert code(rules.check_question, {"question_type": "true_false", "answer_key": 1}) == "invalid_question"
    q = {"question_type": "single_choice", "options": ["a", "b"]}
    rules.check_answer(q, {"selected_options": [0]})
    assert code(rules.check_answer, q, {"selected_options": [0, 1]}) == "invalid_answer"
    assert code(rules.check_answer, q, {"text_answer": "a"}) == "invalid_answer"


def test_attempt_choice_for_the_grade():
    attempts = [
        {"attempt_number": 1, "status": "graded", "total": 5},
        {"attempt_number": 2, "status": "graded", "total": 3},
        {"attempt_number": 3, "status": "submitted", "total": 9},
    ]
    assert rules.attempt_for_grade(attempts, "highest")["attempt_number"] == 1
    assert rules.attempt_for_grade(attempts, "latest") is None  # the latest still waits for essay scores
    assert rules.attempt_for_grade(attempts[:2], "latest")["attempt_number"] == 2
    assert rules.attempt_for_grade([], "highest") is None


def test_deadline_and_points():
    assert rules.must_submit_by(T, 30, T + timedelta(days=1)) == T + timedelta(minutes=30)
    assert rules.must_submit_by(T, 30, T + timedelta(minutes=10)) == T + timedelta(minutes=10)
    assert rules.must_submit_by(T, None, T + timedelta(days=1)) == T + timedelta(days=1)
    assert code(rules.check_quiz_window, T, T) == "invalid_window"
    assert code(rules.check_points, 11, 10) == "points_out_of_range"
    assert rules.percent(8, 10) == 80.0 and rules.percent(0, 0) is None


def test_thread_moderation():
    assert rules.moderate_thread("lock", False, False) == (True, False)
    assert rules.moderate_thread("hide", True, False) == (True, True)
    assert rules.thread_state(True, True) == "hidden" and rules.thread_state(True, False) == "locked"
    assert code(rules.moderate_thread, "unhide", False, False) == "invalid_status"
    assert code(rules.moderate_thread, "unlock", False, True) == "invalid_status"
