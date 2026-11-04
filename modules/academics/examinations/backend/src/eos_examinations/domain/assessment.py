"""Assessment schemes (contract `AssessmentScheme`, `AssessmentComponent`; PRD 5.2, FR-2): the components of a course
offering's examination, their weightages and marks, and the one active version."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from decimal import Decimal

from .errors import DomainRuleError
from .values import require_choice, require_id, require_number, require_text

DRAFT, ACTIVE, SUPERSEDED = "draft", "active", "superseded"
SCHEME_STATUSES = (DRAFT, ACTIVE, SUPERSEDED)  # contract SchemeStatus
WRITTEN, PRACTICAL, ORAL, PROJECT, CONTINUOUS = "written", "practical", "oral", "project", "continuous"
COMPONENT_KINDS = (WRITTEN, PRACTICAL, ORAL, PROJECT, CONTINUOUS)  # contract ComponentKind
HUNDRED = Decimal(100)


@dataclass(frozen=True)
class Component:
    code: str
    name: str
    kind: str
    weightage_percent: Decimal
    max_marks: Decimal
    pass_marks: Decimal | None = None

    def __post_init__(self) -> None:
        require_text(self.code, "code", max_length=40)
        require_text(self.name, "name", max_length=200)
        require_choice(self.kind, "kind", COMPONENT_KINDS)
        if not 0 <= self.weightage_percent <= HUNDRED:
            raise DomainRuleError(
                "invalid_weightage",
                "weightage_percent must be between 0 and 100",
                kind="invalid",
                field="weightage_percent",
            )
        if self.max_marks <= 0:
            raise DomainRuleError("invalid_max_marks", "max_marks must be above 0", kind="invalid", field="max_marks")
        if self.pass_marks is not None and not 0 <= self.pass_marks <= self.max_marks:
            raise DomainRuleError(
                "invalid_pass_marks", "pass_marks must be between 0 and max_marks", kind="invalid", field="pass_marks"
            )


def new_component(data: Mapping, index: int = 0) -> Component:
    """A component from a contract `AssessmentComponent` object; every problem names the component's position."""
    where = f"components[{index}]"
    if not isinstance(data, Mapping):
        raise DomainRuleError("invalid_component", f"{where} must be an object", kind="invalid", field=where)
    try:
        pass_marks = data.get("pass_marks")
        return Component(
            code=require_text(data.get("code"), "code", max_length=40),
            name=require_text(data.get("name"), "name", max_length=200),
            kind=require_choice(data.get("kind"), "kind", COMPONENT_KINDS),
            weightage_percent=require_number(
                data.get("weightage_percent"), "weightage_percent", minimum=0, maximum=HUNDRED
            ),
            max_marks=require_number(data.get("max_marks"), "max_marks"),
            pass_marks=None if pass_marks is None else require_number(pass_marks, "pass_marks", minimum=0),
        )
    except DomainRuleError as err:
        err.field = f"{where}.{err.field}" if err.field else where
        raise


@dataclass(frozen=True)
class Scheme:
    id: str
    course_offering_id: str
    version: int
    pass_percent: Decimal
    components: tuple[Component, ...]
    status: str = DRAFT

    def __post_init__(self) -> None:
        require_id(self.id, "id")
        require_id(self.course_offering_id, "course_offering_id")
        require_choice(self.status, "status", SCHEME_STATUSES)
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise DomainRuleError("invalid_version", "version must be 1 or more", kind="invalid", field="version")
        if not 0 <= self.pass_percent <= HUNDRED:
            raise DomainRuleError(
                "invalid_pass_percent", "pass_percent must be between 0 and 100", kind="invalid", field="pass_percent"
            )
        codes = [c.code for c in self.components]
        if len(set(codes)) != len(codes):
            raise DomainRuleError(
                "duplicate_component_code", "a component code is used twice", kind="invalid", field="components"
            )

    @property
    def total_weightage(self) -> Decimal:
        return sum((c.weightage_percent for c in self.components), Decimal(0))


def new_scheme(
    scheme_id: str, course_offering_id: object, pass_percent: object, components: object, *, version: int = 1
) -> Scheme:
    """A draft scheme from a contract `AssessmentSchemeInput`. Weightages are not required to add up to 100 yet: a
    draft can be built up, and the sum is checked when the scheme is activated (FR-2)."""
    if not isinstance(components, list):
        raise DomainRuleError("invalid_components", "components must be a list", kind="invalid", field="components")
    return Scheme(
        id=scheme_id,
        course_offering_id=require_id(course_offering_id, "course_offering_id"),
        version=version,
        pass_percent=require_number(pass_percent, "pass_percent", minimum=0, maximum=HUNDRED),
        components=tuple(new_component(c, i) for i, c in enumerate(components)),
    )


def next_version(existing_versions: Iterable[int]) -> int:
    """Earlier versions are kept, so a new scheme of an offering takes the next version number."""
    return max(existing_versions, default=0) + 1


def ensure_weightages_complete(scheme: Scheme) -> None:
    """FR-2: the weightages add up to 100, and there is at least one component."""
    if not scheme.components:
        raise DomainRuleError("no_components", "a scheme needs at least one component", kind="unprocessable")
    if scheme.total_weightage != HUNDRED:
        raise DomainRuleError(
            "weightage_not_100",
            f"weightages add up to {scheme.total_weightage}, not 100",
            kind="unprocessable",
            field="components",
            details={"total": str(scheme.total_weightage)},
        )


def ensure_editable(scheme: Scheme, *, has_locked_marks: bool) -> None:
    """FR-2: a scheme used by a paper that has locked marks cannot change; a new version is needed. A superseded
    scheme is an earlier version and is kept as it was."""
    if scheme.status == SUPERSEDED:
        raise DomainRuleError("scheme_superseded", "a superseded scheme is kept as it was", kind="conflict")
    if has_locked_marks:
        raise DomainRuleError(
            "scheme_has_locked_marks",
            "a paper of this scheme has locked marks; create a new version",
            kind="conflict",
        )


@dataclass(frozen=True)
class Activation:
    """What activating a scheme changes: the scheme as it becomes and the ids of the schemes it supersedes."""

    scheme: Scheme
    superseded_ids: tuple[str, ...]


def plan_activation(scheme: Scheme, others: Iterable[Scheme]) -> Activation:
    """FR-2: activating a draft scheme supersedes the course offering's previous active one, so one scheme is active.
    `others` are the offering's other schemes; a scheme of another offering is a programming error."""
    if scheme.status != DRAFT:
        raise DomainRuleError(
            "scheme_not_draft", f"only a draft scheme can be activated, this one is {scheme.status}", kind="conflict"
        )
    ensure_weightages_complete(scheme)
    previous = []
    for other in others:
        if other.course_offering_id != scheme.course_offering_id:
            raise ValueError("schemes of another course offering")
        if other.status == ACTIVE and other.id != scheme.id:
            previous.append(other.id)
    return Activation(replace(scheme, status=ACTIVE), tuple(previous))
