"""A plan's limits, typed. config/plans.yaml and the super admin's PUT /admin/plans/{id} both give them as
{users, students, storage_gb}; each is a whole number of at least 0, or absent. One rule for "no limit"
everywhere: absent, null or 0.

- `users`: active **staff** accounts (identity's `count_staff_users`). Learners are not users.
- `students`: active learners (students, applicants and roles extending them). Not counted yet: usage reports
  null until a module counts them, and nothing is refused on it.
- `storage_gb`: stored files, in GB. Not counted yet either."""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, Field, ValidationError

log = logging.getLogger("eos.billing")

LIMIT_KEYS = ("users", "students", "storage_gb")


class PlanLimits(BaseModel):
    """Strict: "50", 50.5, true and -1 are refused (422 at the API), never coerced."""

    model_config = ConfigDict(extra="forbid", strict=True)

    users: int | None = Field(default=None, ge=0, description="Active staff accounts; learners are not counted.")
    students: int | None = Field(default=None, ge=0, description="Active learners (students and applicants).")
    storage_gb: int | None = Field(default=None, ge=0, description="Stored files, in GB.")

    def ceiling(self, key: str) -> int | None:
        """The limit on `key`, or None when there is none (absent, null or 0)."""
        value = getattr(self, key)
        return value or None

    def stored(self) -> dict:
        """What the plan row keeps: the limits that are set."""
        return self.model_dump(exclude_none=True)

    @classmethod
    def read(cls, raw: object, *, plan_id: str = "?") -> PlanLimits:
        """The limits a plan row holds, whatever was stored before they were typed. A value that is not a
        whole number of at least 0 is no limit, and says so in the log, rather than a 500 for every request
        that asks; an unknown key is ignored."""
        values: dict[str, int | None] = {}
        source = raw if isinstance(raw, dict) else {}
        if raw is not None and not isinstance(raw, dict):
            log.warning("plan %s: limits %r are not a mapping; treated as no limits", plan_id, raw)
        for key in LIMIT_KEYS:
            if key not in source:
                continue
            try:
                values[key] = getattr(cls.model_validate({key: source[key]}), key)
            except ValidationError:
                log.warning(
                    "plan %s: limit %s=%r is not a whole number >= 0; treated as no limit", plan_id, key, source[key]
                )
        return cls(**values)
