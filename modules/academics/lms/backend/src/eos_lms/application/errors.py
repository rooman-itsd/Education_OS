"""The error every use case raises: an HTTP status and the contract's ErrorResponse body ({code, message, details})."""

from __future__ import annotations

from ..domain.rules import RuleViolationError

# Domain rule code -> HTTP status (contracts/openapi.yaml, components.responses). Anything not listed is a 422.
RULE_STATUS = {
    "invalid_status": 409,
    "course_space_archived": 409,
    "course_space_not_active": 409,
    "assignment_not_published": 409,
    "past_due": 409,
    "past_cutoff": 409,
    "no_attempts_left": 409,
    "offline_submission": 409,
    "quiz_not_open": 409,
    "attempt_in_progress": 409,
    "attempt_not_in_progress": 409,
    "questions_frozen": 409,
    "thread_closed": 409,
    "points_above_max": 409,
    "invalid_material": 400,
    "invalid_late_policy": 400,
    "invalid_submission": 400,
    "invalid_window": 400,
    "invalid_question": 400,
    "invalid_answer": 400,
}


class LmsError(Exception):
    """A refusal with an HTTP status and a contract error body."""

    def __init__(self, status: int, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details

    def body(self) -> dict:
        body: dict = {"code": self.code, "message": self.message}
        if self.details:
            body["details"] = self.details
        return body


def from_rule(v: RuleViolationError) -> LmsError:
    return LmsError(RULE_STATUS.get(v.code, 422), v.code, v.message)


def invalid(code: str, message: str, **details: object) -> LmsError:
    return LmsError(400, code, message, **details)


def forbidden(message: str, code: str = "forbidden") -> LmsError:
    return LmsError(403, code, message)


def not_found(what: str) -> LmsError:
    return LmsError(404, "not_found", f"{what} not found in your organisation")


def conflict(code: str, message: str) -> LmsError:
    return LmsError(409, code, message)


def unprocessable(code: str, message: str) -> LmsError:
    return LmsError(422, code, message)
