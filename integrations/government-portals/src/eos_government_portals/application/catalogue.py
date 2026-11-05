"""The forms catalogue (docs/prd.md, "Forms catalogue (v1.0)"): which forms this adapter prepares, each with its
authority, channel, format cycle, period kind, the JSON Schema of the data it needs and the evidence each metric takes.

The field lists are the adapter's reading of the published frameworks; the portals show the current cycle's exact
fields only after an institution signs in (open question 1). When the first institution's nodal officer reports a
field the portal wants or refuses, it changes here, with a new golden file, never silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..infrastructure.config import Settings

AUTHORITIES = ("aishe", "nirf", "naac")
CHANNEL = "manual_entry"  # every form is keyed or uploaded by a person; "api" is for the day a portal opens one

NIRF_CATEGORIES = (
    "overall",
    "university",
    "college",
    "engineering",
    "management",
    "pharmacy",
    "medical",
    "law",
    "architecture",
    "dental",
    "research",
    "agriculture",
    "innovation",
    "open-university",
    "skill-university",
    "state-public-university",
    "sdg",
)

EVIDENCE_TYPES = ["pdf", "jpg", "jpeg", "png", "xlsx", "xls", "docx", "csv"]

UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
METRIC_PATTERN = r"^[1-7]\.[0-9]{1,2}(\.[0-9]{1,2})?$"
PERIOD_AY_PATTERN = r"^[0-9]{4}-[0-9]{2}$"
PERIOD_YEAR_PATTERN = r"^[0-9]{4}$"
PERIOD_CYCLE_PATTERN = r"^[A-Za-z0-9._-]{1,40}$"

COUNT = {"type": "integer", "minimum": 0, "maximum": 100_000_000}
AMOUNT = {"type": "number", "minimum": 0, "maximum": 1e12}
PCT = {"type": "number", "minimum": 0, "maximum": 100}
TEXT = {"type": "string", "minLength": 1, "maxLength": 200}
LONG_TEXT = {"type": "string", "minLength": 1, "maxLength": 5000}


def _obj(props: dict[str, Any], required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": props,
        "required": list(props) if required is None else required,
        "additionalProperties": False,
    }


GENDER = _obj({"male": COUNT, "female": COUNT, "transgender": COUNT})
CATEGORY = _obj({"general": COUNT, "sc": COUNT, "st": COUNT, "obc": COUNT, "ews": COUNT, "other": COUNT})

AISHE_FORMS = {
    "aishe.dcf-i": ("DCF-I (universities)", "university"),
    "aishe.dcf-ii": ("DCF-II (colleges)", "college"),
    "aishe.dcf-iii": ("DCF-III (standalone institutions)", "standalone"),
}

NAAC_FORMS = {
    "naac.iiqa": "IIQA (Institutional Information for Quality Assessment)",
    "naac.ssr": "SSR (Self Study Report)",
    "naac.aqar": "AQAR (Annual Quality Assurance Report)",
    "naac.dvv-response": "DVV (Data Validation and Verification) response",
}

# NIRF Data Capturing System parameter groups, in the order of the framework; each field is (kind). Perception is
# collected by NIRF itself, so there is nothing to key for it.
NIRF_GROUPS: dict[str, tuple[str, dict[str, dict]]] = {
    "tlr": (
        "Teaching, Learning and Resources",
        {
            "sanctioned_intake": COUNT,
            "total_enrolment": COUNT,
            "full_time_faculty": COUNT,
            "faculty_with_phd_pct": PCT,
            "faculty_experience_years_avg": {"type": "number", "minimum": 0, "maximum": 60},
            "expenditure_lakh": AMOUNT,
        },
    ),
    "rpp": (
        "Research and Professional Practice",
        {
            "publications": COUNT,
            "citations": COUNT,
            "patents_published": COUNT,
            "patents_granted": COUNT,
            "sponsored_research_lakh": AMOUNT,
            "consultancy_lakh": AMOUNT,
        },
    ),
    "go": (
        "Graduation Outcomes",
        {
            "graduating_students": COUNT,
            "placed_students": COUNT,
            "higher_studies_students": COUNT,
            "median_salary_lakh": AMOUNT,
            "phd_awarded": COUNT,
        },
    ),
    "oi": (
        "Outreach and Inclusivity",
        {
            "women_students_pct": PCT,
            "women_faculty_pct": PCT,
            "outside_state_students_pct": PCT,
            "economically_backward_students_pct": PCT,
            "differently_abled_students": COUNT,
        },
    ),
}


@dataclass(frozen=True)
class FormSpec:
    form_code: str
    authority: str
    title: str
    period_kind: str
    period_pattern: str
    portal_url: str
    data_schema: dict
    evidence: tuple[dict, ...] = ()

    def describe(self, settings: Settings) -> dict:
        return {
            "form_code": self.form_code,
            "authority": self.authority,
            "title": self.title,
            "channel": CHANNEL,
            "format_version": settings.format_for(self.authority),
            "period_kind": self.period_kind,
            "data_schema": self.data_schema,
            "evidence": [dict(e) for e in self.evidence],
            "portal_url": self.portal_url,
        }


def _aishe_schema(kind: str) -> dict:
    props: dict[str, Any] = {
        "basic_details": _obj(
            {
                "institution_name": TEXT,
                "aishe_code": {"type": "string", "pattern": r"^[CUS]-[0-9]{1,6}$"},
                "institution_type": {"type": "string", "enum": ["university", "college", "standalone"]},
                "year_of_establishment": {"type": "integer", "minimum": 1800, "maximum": 2100},
                "management": TEXT,
                "state": TEXT,
                "district": TEXT,
            }
        ),
        "programmes": {
            "type": "array",
            "maxItems": 2000,
            "items": _obj(
                {
                    "name": TEXT,
                    "level": {"type": "string", "enum": ["certificate", "diploma", "ug", "pg", "integrated", "phd"]},
                    "discipline": TEXT,
                    "duration_years": {"type": "number", "minimum": 0.5, "maximum": 10},
                    "intake": COUNT,
                    "enrolment_by_gender": GENDER,
                    "enrolment_by_category": CATEGORY,
                }
            ),
        },
        "examination_results": {
            "type": "array",
            "maxItems": 2000,
            "items": _obj({"programme": TEXT, "appeared": COUNT, "passed": COUNT}),
        },
        "staff": _obj({"teaching": GENDER, "non_teaching": GENDER}),
        "infrastructure": _obj(
            {"classrooms": COUNT, "laboratories": COUNT, "library_books": COUNT, "computers": COUNT, "hostels": COUNT}
        ),
        "finance": _obj({"income_total": AMOUNT, "expenditure_total": AMOUNT, "salary_expenditure": AMOUNT}),
    }
    if kind == "university":
        props["departments"] = {
            "type": "array",
            "maxItems": 1000,
            "items": _obj({"name": TEXT, "discipline": TEXT}),
        }
    if kind == "college":
        props["teachers"] = {
            "type": "array",
            "maxItems": 20000,
            "items": _obj(
                {
                    "name": TEXT,
                    "designation": TEXT,
                    "gender": {"type": "string", "enum": ["male", "female", "transgender"]},
                    "category": {"type": "string", "enum": ["general", "sc", "st", "obc", "ews", "other"]},
                    "highest_qualification": TEXT,
                    "nature_of_appointment": {"type": "string", "enum": ["regular", "contractual", "visiting"]},
                    "date_of_joining": {"type": "string", "pattern": r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"},
                }
            ),
        }
    return _obj(props)


def _nirf_schema() -> dict:
    props: dict[str, Any] = {
        "institute": _obj(
            {
                "name": TEXT,
                "nirf_institute_id": {"type": "string", "minLength": 1, "maxLength": 40},
                "year_of_establishment": {"type": "integer", "minimum": 1800, "maximum": 2100},
            }
        )
    }
    for key, (_title, fields) in NIRF_GROUPS.items():
        props[key] = _obj(dict(fields))
    return _obj(props)


_INSTITUTE = _obj(
    {
        "name": TEXT,
        "naac_hei_id": {"type": "string", "minLength": 1, "maxLength": 40},
        "aishe_code": {"type": "string", "pattern": r"^[CUS]-[0-9]{1,6}$"},
        "year_of_establishment": {"type": "integer", "minimum": 1800, "maximum": 2100},
    },
    required=["name", "naac_hei_id"],
)

_METRIC_VALUE = {"type": ["number", "string"], "minimum": 0, "maximum": 1e12, "maxLength": 5000}


def _naac_schema(code: str) -> dict:
    if code == "naac.iiqa":
        return _obj(
            {
                "institute": _INSTITUTE,
                "programmes_offered": COUNT,
                "students_enrolled": COUNT,
                "full_time_teachers": COUNT,
                "previous_cycle": _obj(
                    {
                        "cycle": {"type": "integer", "minimum": 1, "maximum": 9},
                        "valid_until": {"type": "string", "pattern": r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"},
                    },
                    required=[],
                ),
            },
            required=["institute", "programmes_offered", "students_enrolled", "full_time_teachers"],
        )
    if code == "naac.dvv-response":
        return _obj(
            {
                "institute": _INSTITUTE,
                "queries": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 500,
                    "items": _obj(
                        {
                            "query_id": {"type": "string", "minLength": 1, "maxLength": 40},
                            "metric": {"type": "string", "pattern": METRIC_PATTERN},
                            "clarification": LONG_TEXT,
                        }
                    ),
                },
            }
        )
    return _obj(
        {
            "institute": _INSTITUTE,
            "criteria": {
                "type": "array",
                "minItems": 1,
                "maxItems": 7,
                "items": _obj(
                    {
                        "criterion": {"type": "integer", "minimum": 1, "maximum": 7},
                        "metrics": {
                            "type": "array",
                            "maxItems": 200,
                            "items": _obj(
                                {
                                    "metric": {"type": "string", "pattern": METRIC_PATTERN},
                                    "kind": {"type": "string", "enum": ["quantitative", "qualitative"]},
                                    "value": _METRIC_VALUE,
                                }
                            ),
                        },
                    }
                ),
            },
        }
    )


def _naac_evidence(required: bool) -> tuple[dict, ...]:
    return ({"metric": "*", "required": required, "accepts": list(EVIDENCE_TYPES)},)


def _build() -> dict[str, FormSpec]:
    forms: dict[str, FormSpec] = {}
    for code, (title, kind) in AISHE_FORMS.items():
        forms[code] = FormSpec(
            code,
            "aishe",
            f"AISHE {title}",
            "academic_year",
            PERIOD_AY_PATTERN,
            "https://aishe.gov.in",
            _aishe_schema(kind),
        )
    for category in NIRF_CATEGORIES:
        forms[f"nirf.dcs.{category}"] = FormSpec(
            f"nirf.dcs.{category}",
            "nirf",
            f"NIRF Data Capturing System, {category.replace('-', ' ')} category",
            "calendar_year",
            PERIOD_YEAR_PATTERN,
            "https://www.nirfindia.org",
            _nirf_schema(),
        )
    for code, title in NAAC_FORMS.items():
        aqar = code == "naac.aqar"
        forms[code] = FormSpec(
            code,
            "naac",
            f"NAAC {title}",
            "academic_year" if aqar else "accreditation_cycle",
            PERIOD_AY_PATTERN if aqar else PERIOD_CYCLE_PATTERN,
            "https://www.naac.gov.in",
            _naac_schema(code),
            () if code == "naac.iiqa" else _naac_evidence(code == "naac.dvv-response"),
        )
    return forms


FORMS: dict[str, FormSpec] = _build()


def get_form(form_code: str) -> FormSpec | None:
    return FORMS.get(form_code)
