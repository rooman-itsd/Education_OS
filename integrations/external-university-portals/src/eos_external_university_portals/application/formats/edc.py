"""Europass Digital Credentials (EDC): JSON-LD, the European Learning Model v3 application profile, W3C Verifiable
Credentials 1.1 data model (https://europass.europa.eu/en/information-developers).

The writer produces the *unsealed* credential: the form the Europass issuer accepts for sealing. This release cannot
seal it (no signature library is on the approved stack), so `credentialProfiles`, `credentialSchema` and the claims are
complete but there is no `proof`. EDC says what a person has *achieved*, so only passed entries are written.

The reader maps the claims it understands and lists each claim it cannot map, with its position, never its content.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from ..transcript import num, split_name
from .countries import ALPHA3

CONTEXT = ["https://www.w3.org/2018/credentials/v1", "http://data.europa.eu/snb/model/context/edc-ap"]
AUTH = "http://publications.europa.eu/resource/authority"
ENG = {
    "id": f"{AUTH}/language/ENG",
    "type": "Concept",
    "inScheme": {"id": f"{AUTH}/language", "type": "ConceptScheme"},
    "notation": "language",
    "prefLabel": {"en": "English"},
}
BASE64 = {
    "id": "http://data.europa.eu/snb/encoding/6146cde7dd",
    "type": "Concept",
    "inScheme": {"id": "http://data.europa.eu/snb/encoding/25831c2", "type": "ConceptScheme"},
    "prefLabel": {"en": "base64"},
}
PNG = {
    "id": f"{AUTH}/file-type/PNG",
    "type": "Concept",
    "inScheme": {"id": f"{AUTH}/file-type", "type": "ConceptScheme"},
    "notation": "file-type",
    "prefLabel": {"en": "PNG"},
}
# A 1x1 transparent PNG: the credential's display needs an image, and a transcript has none of its own.
PIXEL = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
ECTS = {
    "id": "http://data.europa.eu/snb/education-credit/6fcec5c5af",
    "type": "Concept",
    "inScheme": {"id": "http://data.europa.eu/snb/education-credit/25831c2", "type": "ConceptScheme"},
    "prefLabel": {"en": "European Credit Transfer System"},
}
GENERIC = {
    "id": "http://data.europa.eu/snb/credential/e34929035b",
    "type": "Concept",
    "inScheme": {"id": "http://data.europa.eu/snb/credential/25831c2", "type": "ConceptScheme"},
    "prefLabel": {"en": "Generic"},
}
EQF = "http://data.europa.eu/snb/eqf/"


def _concept(iri: str, scheme: str, label: str) -> dict:
    return {
        "id": iri,
        "type": "Concept",
        "inScheme": {"id": scheme, "type": "ConceptScheme"},
        "prefLabel": {"en": label},
    }


def _framework(system: str) -> dict:
    if system == "ects":
        return ECTS
    # Only ECTS is in the EDC credit vocabulary. Any other system travels as a concept of our own, which the Europass
    # validator's vocabulary check may flag: documented in docs/formats.md.
    labels = {"indian_credit": "Indian credit system (UGC)", "other": "Other credit system"}
    return _concept(f"urn:eos:education-credit:{system}", "urn:eos:education-credit", labels[system])


def _identifier(n: int, scheme: str, value: str) -> dict:
    return {"id": f"urn:epass:identifier:{n}", "type": "Identifier", "notation": value, "schemeName": scheme}


def _stamp(date_text: str) -> str:
    return f"{date_text}T00:00:00Z"


def write(transcript: dict, credential_id: str, issued_at: datetime) -> bytes:
    issuer_in, learner_in = transcript["issuer"], transcript["learner"]
    country = {
        "id": f"{AUTH}/country/{ALPHA3[issuer_in['country']]}",
        "type": "Concept",
        "inScheme": {"id": f"{AUTH}/country", "type": "ConceptScheme"},
        "notation": "country",
        "prefLabel": {"en": issuer_in["country"]},
    }
    issuer: dict[str, Any] = {
        "id": "urn:epass:org:1",
        "type": "Organisation",
        "legalName": {"en": issuer_in["institution_name"]},
        "location": {
            "id": "urn:epass:location:1",
            "type": "Location",
            "address": {"id": "urn:epass:address:1", "type": "Address", "countryCode": country},
        },
        "registration": {
            "id": "urn:epass:legalIdentifier:1",
            "type": "LegalIdentifier",
            "spatial": country,
            "notation": issuer_in["institution_code"],
        },
    }
    if "url" in issuer_in:
        issuer["homepage"] = {"id": "urn:epass:webResource:1", "type": "WebResource", "contentURL": issuer_in["url"]}
    given, family = split_name(learner_in)
    subject: dict[str, Any] = {
        "id": "urn:epass:person:1",
        "type": "Person",
        "givenName": {"en": given},
        "familyName": {"en": family},
        "fullName": {"en": learner_in["name"]},
        "dateOfBirth": _stamp(learner_in["date_of_birth"]),
    }
    idents = []
    if "partner_student_id" in learner_in:
        idents.append(_identifier(1, "partnerStudentId", learner_in["partner_student_id"]))
    if "apaar_id" in learner_in:
        idents.append(_identifier(2, "apaar", learner_in["apaar_id"]))
    if idents:
        subject["identifier"] = idents
    if "email" in learner_in:
        subject["contactPoint"] = {
            "id": "urn:epass:contactPoint:1",
            "type": "ContactPoint",
            "emailAddress": {"id": f"mailto:{learner_in['email']}", "type": "Mailbox"},
        }
    claims = []
    passed = [e for e in transcript["entries"] if e["status"] == "passed"]
    for n, e in enumerate(passed, start=1):
        awarding = {
            "id": f"urn:epass:awardingProcess:{n}",
            "type": "AwardingProcess",
            "awardingBody": [{"id": "urn:epass:org:1"}],
            "awardingDate": _stamp(e.get("completed_on", transcript["issued_on"])),
        }
        spec: dict[str, Any] = {
            "id": f"urn:epass:learningAchievementSpec:{n}",
            "type": "LearningAchievementSpecification",
            "title": {"en": e["title"]},
            "identifier": [_identifier(100 + n, "courseCode", e["course_code"])],
            "creditPoint": [
                {
                    "id": f"urn:epass:creditPoint:{n}",
                    "type": "CreditPoint",
                    "framework": _framework(e["credit_system"]),
                    "point": num(e["credits"]),
                }
            ],
        }
        claim: dict[str, Any] = {
            "id": f"urn:epass:learningAchievement:{n}",
            "type": "LearningAchievement",
            "title": {"en": e["title"]},
            "awardedBy": awarding,
            "specifiedBy": spec,
        }
        if "grade" in e:
            assessment_spec: dict[str, Any] = {
                "id": f"urn:epass:learningAssessmentSpec:{n}",
                "type": "LearningAssessmentSpecification",
                "title": {"en": e["title"]},
            }
            if "grade_scheme" in e:
                assessment_spec["gradingScheme"] = {
                    "id": f"urn:epass:gradingScheme:{n}",
                    "type": "GradingScheme",
                    "title": {"en": e["grade_scheme"]},
                }
            claim["provenBy"] = [
                {
                    "id": f"urn:epass:learningAssessment:{n}",
                    "type": "LearningAssessment",
                    "title": {"en": e["title"]},
                    "grade": {"id": f"urn:epass:note:{n}", "type": "Note", "noteLiteral": {"en": e["grade"]}},
                    "awardedBy": {
                        "id": f"urn:epass:awardingProcess:{n}a",
                        "type": "AwardingProcess",
                        "awardingBody": [{"id": "urn:epass:org:1"}],
                        "awardingDate": awarding["awardingDate"],
                    },
                    "specifiedBy": assessment_spec,
                }
            ]
        claims.append(claim)
    subject["hasClaim"] = claims
    doc = {
        "@context": CONTEXT,
        "id": f"urn:credential:{credential_id}",
        "type": ["VerifiableCredential", "EuropeanDigitalCredential"],
        "credentialProfiles": [GENERIC],
        "displayParameter": {
            "id": "urn:epass:displayParameter:1",
            "type": "DisplayParameter",
            "title": {"en": f"Transcript of records: {transcript['programme']['name']}"},
            "language": [ENG],
            "primaryLanguage": ENG,
            "individualDisplay": [
                {
                    "id": "urn:epass:individualDisplay:1",
                    "type": "IndividualDisplay",
                    "language": ENG,
                    "displayDetail": [
                        {
                            "id": "urn:epass:displayDetail:1",
                            "type": "DisplayDetail",
                            "page": 1,
                            "image": {
                                "id": "urn:epass:mediaObject:1",
                                "type": "MediaObject",
                                "content": PIXEL,
                                "contentEncoding": BASE64,
                                "contentType": PNG,
                            },
                        }
                    ],
                }
            ],
        },
        "credentialSchema": [
            {"id": "http://data.europa.eu/snb/model/ap/edc-generic-full", "type": "ShaclValidator2017"}
        ],
        "credentialSubject": subject,
        "issuer": issuer,
        "validFrom": issued_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return (json.dumps(doc, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


# ------------------------------------------------------------------ reading


class EdcError(ValueError):
    """The file is not an EDC JSON-LD credential this reader can open. The message never quotes the file."""


def _no_constants(name: str) -> Any:
    raise ValueError("NaN and Infinity are not JSON")


def _lang(value: Any) -> str | None:
    """A language map {"en": "x"} or a plain string, as one string."""
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        for key in ("en", *value):
            v = value.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return None


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else [] if value is None else [value]


def _date(value: Any) -> str | None:
    return value[:10] if isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}.*", value) else None


def read(content: bytes) -> tuple[dict, list[dict], str]:
    """(transcript, unmapped, integrity). Raises EdcError for a file that is not an EDC credential."""
    try:
        doc = json.loads(content.decode("utf-8-sig"), parse_constant=_no_constants)
    except (ValueError, RecursionError, UnicodeDecodeError) as e:
        raise EdcError("not valid JSON") from e
    if not isinstance(doc, dict):
        raise EdcError("not a credential")
    types = _as_list(doc.get("type"))
    if "EuropeanDigitalCredential" not in types and "VerifiableCredential" not in types:
        raise EdcError("not a Verifiable Credential")
    subject = doc.get("credentialSubject")
    if not isinstance(subject, dict):
        raise EdcError("a credential needs one credential subject")
    integrity = "failed" if "proof" in doc else "unsigned"  # a proof this release cannot verify is never trusted
    unmapped: list[dict] = []

    learner: dict[str, Any] = {"name": _lang(subject.get("fullName")) or ""}
    if given := _lang(subject.get("givenName")):
        learner["given_names"] = given
    if family := _lang(subject.get("familyName")):
        learner["family_name"] = family
    if not learner["name"]:
        learner["name"] = " ".join(x for x in (given, family) if x)
    if dob := _date(subject.get("dateOfBirth")):
        learner["date_of_birth"] = dob
    for ident in _as_list(subject.get("identifier")):
        if isinstance(ident, dict) and isinstance(ident.get("notation"), str):
            if ident.get("schemeName") == "partnerStudentId":
                learner["partner_student_id"] = ident["notation"]
            elif ident.get("schemeName") == "apaar":
                learner["apaar_id"] = ident["notation"]

    issuer_in = doc.get("issuer") if isinstance(doc.get("issuer"), dict) else {}
    reg = issuer_in.get("registration") if isinstance(issuer_in.get("registration"), dict) else {}
    issuer: dict[str, Any] = {
        "institution_name": _lang(issuer_in.get("legalName")) or "",
        "institution_code": reg.get("notation") if isinstance(reg.get("notation"), str) else "",
        "country": "",
    }
    spatial = reg.get("spatial") if isinstance(reg.get("spatial"), dict) else {}
    alpha3 = str(spatial.get("id", "")).rsplit("/", 1)[-1]
    issuer["country"] = next((a2 for a2, a3 in ALPHA3.items() if a3 == alpha3), "")

    entries: list[dict] = []
    for i, claim in enumerate(_as_list(subject.get("hasClaim"))[:2000]):
        position = f"credentialSubject.hasClaim[{i}]"
        entry, reason = _claim(claim)
        if reason:
            unmapped.append({"position": position, "reason": reason})
        else:
            entries.append(entry)
    transcript: dict[str, Any] = {"learner": learner, "issuer": issuer, "programme": {}, "entries": entries}
    if issued := _date(doc.get("validFrom") or doc.get("issuanceDate")):
        transcript["issued_on"] = issued
    return transcript, unmapped, integrity


def _claim(claim: Any) -> tuple[dict, str | None]:
    if not isinstance(claim, dict):
        return {}, "not_an_object"
    title = _lang(claim.get("title"))
    if not title:
        return {}, "missing_title"
    spec = claim.get("specifiedBy") if isinstance(claim.get("specifiedBy"), dict) else {}
    points = [
        p
        for p in _as_list(spec.get("creditPoint"))
        if isinstance(p, dict) and isinstance(p.get("point"), str | int | float)
    ]
    if not points:
        return {}, "no_credit_value"
    try:
        value = float(points[0]["point"])
    except (ValueError, TypeError):
        return {}, "bad_credit_value"
    if not (0 <= value <= 1000) or value != value:
        return {}, "bad_credit_value"
    framework = points[0].get("framework") if isinstance(points[0].get("framework"), dict) else {}
    fid = str(framework.get("id", ""))
    system = "ects" if fid == ECTS["id"] else "indian_credit" if fid.endswith(":indian_credit") else "other"
    code = next(
        (
            i["notation"]
            for i in _as_list(spec.get("identifier"))
            if isinstance(i, dict) and isinstance(i.get("notation"), str)
        ),
        "",
    )
    entry: dict[str, Any] = {
        "course_code": code,
        "title": title,
        "credits": value,
        "credit_system": system,
        "status": "passed",
    }
    for assessment in _as_list(claim.get("provenBy")):
        if (
            isinstance(assessment, dict)
            and isinstance(assessment.get("grade"), dict)
            and (g := _lang(assessment["grade"].get("noteLiteral")))
        ):
            entry["grade"] = g[:30]
            scheme = (
                (assessment.get("specifiedBy") or {}).get("gradingScheme")
                if isinstance(assessment.get("specifiedBy"), dict)
                else None
            )
            if isinstance(scheme, dict) and (s := _lang(scheme.get("title"))):
                entry["grade_scheme"] = s[:60]
            break
    awarding = claim.get("awardedBy") if isinstance(claim.get("awardedBy"), dict) else {}
    if done := _date(awarding.get("awardingDate")):
        entry["completed_on"] = done
    return entry, None
