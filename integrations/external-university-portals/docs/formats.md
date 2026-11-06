# external-university-portals: formats

## The normalised transcript

As the port defines it (`learner`, `issuer`, `programme`, `entries`, `totals`, `issued_on`), validated before any writer
runs (`application/transcript.py`; every field is bounded; NaN and Infinity are refused). Required: `learner.name`,
`learner.date_of_birth`, the three `issuer` fields, the three `programme` fields, at least one entry with `course_code`,
`title`, `credits`, `credit_system` and `status`, and `issued_on`. Additions to the draft, all optional: `issuer.url`
(**required for ELMO**, whose schema demands it), `learner.given_names` and `learner.family_name` (otherwise the last word
of `name` is the family name; ELMO and EDC both want the two parts). Validation errors name fields, never values.

## CSV

One row per entry, learner and programme repeated on each row. Columns: `partner_student_id, learner_name,
date_of_birth, programme_code, programme_name, course_code, title, credits, credit_system, grade, grade_scheme,
grade_point, term, started_on, completed_on, status`. A partner's `csv_mapping` renames them (`{"credits": "ECTS"}`) in
both directions. UTF-8 with a byte order mark. Text starting with `= + - @` is prefixed with `'` on export and the prefix
is removed on import. Import needs `course_code, title, credits, status`; a row with no title, a credit value that is not
a finite number from 0 to 1000, or an unknown status is not mapped (listed as `row N`, with the reason); a bad date or
grade point is dropped from an otherwise mapped row and listed.

## ELMO XML

`elmo-schemas` v2.1.2 (namespace `https://github.com/emrex-eu/elmo-schemas/tree/v2`). The degree programme is a
`learningOpportunitySpecification` of type `Degree Programme` with each course as a `hasPart` of type `Course`; credits sit
on the courses only (the schema forbids repeating them on the parent). Written: learner identifiers (partner student id,
APAAR), names, date of birth; issuer country, code, name, url; per course the code, title, status (`passed`, `failed`,
`in-progress`), grading scheme, grade as `resultLabel`, credit scheme and value, dates, and an `academicTerm` where the
term and both dates are present (the schema wants all three). **Not carried:** `grade_point`, `totals`, and a term without
dates. Read: the same elements, found by exact path (depth bounded at 8); a missing status means passed, as the schema
says; entries with no title, an unknown status or no credit value are listed as `report/.../hasPart[n]`.
DOCTYPE and entity declarations are refused before parsing.

## Europass EDC (JSON-LD)

The unsealed `EuropeanDigitalCredential` (ELM v3 application profile `edc-generic-full`, W3C VC 1.1 data model,
context `http://data.europa.eu/snb/model/context/edc-ap`): the form the Europass issuer takes for sealing. One
`LearningAchievement` claim per **passed** entry (EDC states what was achieved; failed and in-progress entries are not
written, and a transcript with none is refused), each with its credit points, and a `provenBy` `LearningAssessment`
carrying the grade and grading scheme. The credit framework is ECTS where the system is `ects`; **only ECTS is in the EDC
credit vocabulary**, so other systems travel as a concept of our own (`urn:eos:education-credit:<system>`) which the
Europass validator's vocabulary check may flag. The display needs an image: a 1x1 transparent PNG stands in. Not carried:
`grade_point`, `totals`, `term`, `started_on`. Read: names, birth date, identifiers, and each claim with a title and credit
points; claims without them (a webinar, say) are listed as `credentialSubject.hasClaim[n]`.

## Integrity

Never `verified` in this release. `unsigned` when a file carries no signature (XML `Signature`) or `proof`; `failed` when
it does, because it cannot be checked here. A reviewer sees the value and decides.

## Validation in the tests

ELMO: the official XSD (vendored, with its source URL and licence, in `tests/fixtures/elmo-schemas`), checked with
`xmllint`. EDC: no JSON Schema is published; the Commission validates with SHACL. `tests/edc_shacl.py` checks the
cardinality of every property of every class against the vendored official shapes, and that every key is a term of the
official context, calibrated on the Commission's sample credential. It does not check controlled-vocabulary membership or
datatypes (that needs a SHACL engine, which is not on the approved stack).
