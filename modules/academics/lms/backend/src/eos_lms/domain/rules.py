"""Domain rules of lms (docs/prd.md sections 5 and 6). Pure functions and constants: no framework, no database.
The application layer calls these before it changes state."""

from __future__ import annotations

from datetime import datetime, timedelta

# ---------------------------------------------------------------- enums (contracts/openapi.yaml components)

COURSE_SPACE_STATUSES = ("draft", "active", "archived")
MATERIAL_TYPES = ("document", "link", "page")
MATERIAL_STATUSES = ("draft", "published", "unpublished")
WORK_STATUSES = ("draft", "published", "closed")
SUBMISSION_TYPES = ("file", "text", "file_and_text", "none")
SUBMISSION_STATUSES = ("submitted", "graded", "superseded")
QUESTION_TYPES = ("single_choice", "multiple_choice", "true_false", "short_answer", "essay")
AUTO_QUESTION_TYPES = ("single_choice", "multiple_choice", "true_false", "short_answer")
ATTEMPT_STATUSES = ("in_progress", "submitted", "graded")
MANUAL_GRADING_STATES = ("none", "pending", "done")
ITEM_TYPES = ("assignment", "quiz")
GRADE_STATUSES = ("draft", "released")
THREAD_STATES = ("open", "locked", "hidden")
POST_STATES = ("visible", "hidden")
ATTEMPT_SCORING = ("highest", "latest")
GRADEBOOK_CELL_STATUSES = ("missing", "submitted", "graded", "released")

# Allowed transitions: target status -> statuses it may be reached from (docs/prd.md section 6).
COURSE_SPACE_TRANSITIONS = {"active": ("draft",), "archived": ("active",)}
MATERIAL_TRANSITIONS = {"published": ("draft", "unpublished"), "unpublished": ("published",)}
WORK_TRANSITIONS = {"published": ("draft",), "closed": ("published",)}
# Thread moderation: action -> (allowed when, effect on the locked / hidden flags).
THREAD_ACTIONS = ("lock", "unlock", "hide", "unhide")
POST_ACTIONS = ("hide", "unhide")

# Assignment fields whose change after publication publishes lms.assignment.updated (FR-6).
ASSIGNMENT_NOTIFIED_FIELDS = ("due_at", "max_points", "target_section_ids", "late_policy")

# How far back GET /me/course-materials looks when `since` is not given (contract: 14 days).
RECENT_MATERIALS_DAYS = 14


class RuleViolationError(Exception):
    """A domain rule refused the change. `code` is stable; the application maps it to a status."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def transition(transitions: dict[str, tuple[str, ...]], target: str, current: str, what: str) -> str:
    """`target` when `current` allows it, else RuleViolationError(invalid_status)."""
    if current not in transitions.get(target, ()):
        raise RuleViolationError("invalid_status", f"a {what} cannot become {target} from {current}")
    return target


# ---------------------------------------------------------------- course spaces and content


def section_visible(visible_section_ids: list[str], section_id: str | None) -> bool:
    """An empty list means every section. A student without a known section sees only unrestricted items."""
    return not visible_section_ids or (section_id is not None and section_id in visible_section_ids)


def check_material_content(material_type: str, document_id: str | None, url: str | None, body: str | None) -> None:
    """document needs document_id; link needs url; page needs body (CourseMaterialInput)."""
    needed = {"document": ("document_id", document_id), "link": ("url", url), "page": ("body", body)}[material_type]
    if not needed[1] or (isinstance(needed[1], str) and not needed[1].strip()):
        raise RuleViolationError("invalid_material", f"a {material_type} material needs {needed[0]}")


def thread_state(locked: bool, hidden: bool) -> str:
    if hidden:
        return "hidden"
    return "locked" if locked else "open"


def moderate_thread(action: str, locked: bool, hidden: bool) -> tuple[bool, bool]:
    """New (locked, hidden) flags. Locking a locked thread, hiding a hidden one and so on is refused."""
    if action == "lock":
        if locked:
            raise RuleViolationError("invalid_status", "the thread is already locked")
        return True, hidden
    if action == "unlock":
        if not locked:
            raise RuleViolationError("invalid_status", "the thread is not locked")
        return False, hidden
    if action == "hide":
        if hidden:
            raise RuleViolationError("invalid_status", "the thread is already hidden")
        return locked, True
    if not hidden:
        raise RuleViolationError("invalid_status", "the thread is not hidden")
    return locked, False


# ---------------------------------------------------------------- assignments and submissions


def check_late_policy(due_at: datetime, accept_late: bool, late_cutoff_at: datetime | None) -> None:
    if late_cutoff_at is not None and late_cutoff_at < due_at:
        raise RuleViolationError("invalid_late_policy", "late_cutoff_at must not be before due_at")
    if late_cutoff_at is not None and not accept_late:
        raise RuleViolationError("invalid_late_policy", "late_cutoff_at needs accept_late")


def submission_lateness(now: datetime, due_at: datetime, accept_late: bool, late_cutoff_at: datetime | None) -> bool:
    """Whether a submission now is late; refuses one past the cut-off or late when late work is not accepted."""
    if now <= due_at:
        return False
    if not accept_late:
        raise RuleViolationError("past_due", "the due date has passed and late submissions are not accepted")
    if late_cutoff_at is not None and now > late_cutoff_at:
        raise RuleViolationError("past_cutoff", "the late cut-off has passed")
    return True


def check_submission_content(submission_type: str, document_ids: list[str], text: str | None) -> None:
    """Content must match the assignment's submission_type (CreateSubmissionRequest)."""
    has_files, has_text = bool(document_ids), bool(text and text.strip())
    if submission_type == "none":
        raise RuleViolationError("offline_submission", "this assignment is handed in offline and graded here")
    if submission_type == "file" and (not has_files or text is not None):
        raise RuleViolationError("invalid_submission", "this assignment takes files (document_ids) only")
    if submission_type == "text" and (not has_text or document_ids):
        raise RuleViolationError("invalid_submission", "this assignment takes text only")
    if submission_type == "file_and_text" and not (has_files and has_text):
        raise RuleViolationError("invalid_submission", "this assignment takes both files (document_ids) and text")


def check_attempts_left(used: int, allowed: int) -> None:
    if used >= allowed:
        raise RuleViolationError("no_attempts_left", f"all {allowed} attempts have been used")


# ---------------------------------------------------------------- quizzes


def check_quiz_window(opens_at: datetime, closes_at: datetime) -> None:
    if closes_at <= opens_at:
        raise RuleViolationError("invalid_window", "closes_at must be after opens_at")


def check_question(q: dict) -> None:
    """A question as QuizQuestionInput describes it: choice types carry options and option indexes as the key,
    true_false a boolean, short_answer accepted strings, essay no key at all."""
    kind, options, key = q["question_type"], q.get("options"), q.get("answer_key")

    def bad(message: str) -> RuleViolationError:
        return RuleViolationError("invalid_question", message)

    if kind in ("single_choice", "multiple_choice"):
        if not options or len(options) < 2:
            raise bad(f"a {kind} question needs at least two options")
        if not isinstance(key, list) or not key or not all(type(i) is int for i in key):
            raise bad(f"a {kind} question's answer_key is a list of option indexes")
        if any(i < 0 or i >= len(options) for i in key) or len(set(key)) != len(key):
            raise bad("answer_key names an option that does not exist, or one twice")
        if kind == "single_choice" and len(key) != 1:
            raise bad("a single_choice question has exactly one correct option")
        return
    if options:
        raise bad(f"a {kind} question has no options")
    if kind == "true_false":
        if type(key) is not bool:
            raise bad("a true_false question's answer_key is true or false")
    elif kind == "short_answer":
        if not isinstance(key, list) or not key or not all(isinstance(s, str) and s.strip() for s in key):
            raise bad("a short_answer question's answer_key is a list of accepted answers")
    elif key is not None:
        raise bad("an essay question has no answer_key")


def must_submit_by(started_at: datetime, time_limit_minutes: int | None, closes_at: datetime) -> datetime:
    """The earlier of the time limit and the quiz's closing time."""
    if time_limit_minutes is None:
        return closes_at
    return min(started_at + timedelta(minutes=time_limit_minutes), closes_at)


def check_answer(question: dict, answer: dict) -> None:
    """An answer has the shape its question takes."""
    kind = question["question_type"]

    def bad(message: str) -> RuleViolationError:
        return RuleViolationError("invalid_answer", message)

    given = {k for k in ("selected_options", "boolean_answer", "text_answer") if answer.get(k) is not None}
    if kind in ("single_choice", "multiple_choice"):
        if given - {"selected_options"}:
            raise bad(f"a {kind} question is answered with selected_options")
        picked = answer.get("selected_options") or []
        if any(i >= len(question["options"] or []) for i in picked) or len(set(picked)) != len(picked):
            raise bad("selected_options names an option that does not exist, or one twice")
        if kind == "single_choice" and len(picked) > 1:
            raise bad("a single_choice question takes one option")
    elif kind == "true_false":
        if given - {"boolean_answer"}:
            raise bad("a true_false question is answered with boolean_answer")
    elif given - {"text_answer"}:
        raise bad(f"a {kind} question is answered with text_answer")


def auto_points(question: dict, answer: dict | None) -> float:
    """Points for an automatically scored question: all or nothing. short_answer compares trimmed text without
    regard to case (docs: "Assumptions to revisit")."""
    if answer is None:
        return 0.0
    kind, key, points = question["question_type"], question["answer_key"], float(question["points"])
    if kind in ("single_choice", "multiple_choice"):
        picked = answer.get("selected_options")
        return points if picked is not None and set(picked) == set(key) else 0.0
    if kind == "true_false":
        return points if answer.get("boolean_answer") is key else 0.0
    text = answer.get("text_answer")
    if text is None:
        return 0.0
    return points if text.strip().casefold() in {k.strip().casefold() for k in key} else 0.0


def score_attempt(questions: list[dict], answers: list[dict]) -> tuple[float, bool]:
    """(automatic score, whether essay questions wait for an instructor)."""
    by_question = {a["question_id"]: a for a in answers}
    auto = sum(auto_points(q, by_question.get(q["id"])) for q in questions if q["question_type"] in AUTO_QUESTION_TYPES)
    return auto, any(q["question_type"] == "essay" for q in questions)


def attempt_for_grade(attempts: list[dict], scoring: str) -> dict | None:
    """The attempt a quiz grade comes from: the highest-scoring graded attempt, or the latest submitted attempt once
    it is graded. Each attempt dict has attempt_number, status and total."""
    done = [a for a in attempts if a["status"] in ("submitted", "graded")]
    if not done:
        return None
    if scoring == "latest":
        latest = max(done, key=lambda a: a["attempt_number"])
        return latest if latest["status"] == "graded" else None
    graded = [a for a in done if a["status"] == "graded"]
    if not graded:
        return None
    return max(graded, key=lambda a: (a["total"], a["attempt_number"]))


# ---------------------------------------------------------------- grades


def check_points(points: float, max_points: float) -> None:
    if points < 0 or points > max_points:
        raise RuleViolationError("points_out_of_range", f"points must be between 0 and {max_points:g}")


def percent(points: float, max_points: float) -> float | None:
    """Unweighted released percentage; None when nothing is released (FR-13)."""
    if max_points <= 0:
        return None
    return round(points * 100 / max_points, 2)
