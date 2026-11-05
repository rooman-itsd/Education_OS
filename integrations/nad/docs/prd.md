# nad: product requirements

Owner: Himanshu (@himanshu-rooman) · Backups: Faizan, Akshata · Kind: integration · Tier: common · Status: draft for review
Issue #142 · Depends on the integration-hub contracts (the academic-records port).

## Purpose

Lodge an institution's academic records with the two national depositories, keyed by the learner's APAAR id:

- **National Academic Depository (NAD)**: awards (degree, provisional, diploma, marksheet, grade card), so a degree is
  verifiable online and reaches the student's DigiLocker as an original.
- **Academic Bank of Credits (ABC)**: credits earned per course and term, so a student can carry them across
  institutions (multiple entry and exit).
- **APAAR id** (Automated Permanent Academic Account Registry, "One Nation One Student ID"; for higher education it is
  also the ABC id): check that the id a student gives is real and theirs.

It implements the **academic-records** port ([contracts/ports/academic-records.yaml](../contracts/ports/academic-records.yaml))
and the Adapter contract ([contracts/ports/adapter.yaml](../contracts/ports/adapter.yaml)), both defined by
`platform/integration-hub`.

## What it is not

| Not this | That belongs to |
|---|---|
| Deciding results, awards and credits | examinations (results), academic-management (programme and course credits) |
| Putting the award *document* in the student's DigiLocker | `integrations/digilocker` (certificate-issuance port). NAD renders its own certificate from the data and its template; issuing the institution's own signed PDF is DigiLocker's job |
| Credit transfer decisions between institutions | enrolment-registration / academic-management; ABC is the record, not the decision |
| Records for a partner abroad | `integrations/external-university-portals` |
| Connection settings, secrets, retries | `platform/integration-hub` |

## How NAD and ABC work for an institution (sources)

| Fact | Source |
|---|---|
| NAD runs on DigiLocker. An institution's authorised representative registers it on NAD with institution, Nodal Officer and authorised person details; **NAD and UGC verify** before the account is activated. An institution already on DigiLocker still registers separately for NAD. Institution names come from a list; corrections go through UGC or AICTE first | NAD FAQ, https://nad.digilocker.gov.in/faq |
| Awards are uploaded as **standard CSV files**, then a NAD certificate **template** is chosen per certificate type, then published. "NAD does not import data in other ways." Sample CSVs and guidelines are in the portal's Resources section. Scanned images and PDFs are not accepted | NAD FAQ |
| A correction is a re-upload with `M` in the MARKS REC STATUS column | NAD FAQ |
| "A secure API is available for uploading data" in bulk; its specification is not public | NAD FAQ |
| Verification by employers needs the student's consent; certificates reach the verifier within 24 hours of consent; the service is free | NAD FAQ |
| User manual | https://img1.digitallocker.gov.in/nad/assets/user_manual/NationalAcademicDepository_User_Manual_V3.pdf |
| ABC was set up by the UGC (Establishment and Operation of Academic Bank of Credits in Higher Education) Regulations 2021 (gazetted 28 Jul 2021, amended 14 Jan 2022): credit transfer with multiple entry and exit. Credits are credited by the HEI, never from documents a student sends | UGC regulations, https://www.ugc.gov.in/e-book/UGC_Regulation/files/basic-html/page557.html; ABC resources, https://www.abc.gov.in/resources.php |
| Credits are normally valid for 7 years under the National Credit Framework | UGC SOP for NCrF in HEIs, https://www.ugc.gov.in/pdfnews/0493222_Final-SOP_for_operationalization_of_NCrF_in_HEI.pdf |
| ABC "provides APIs for integration with institutional platforms" to verify APAAR ids and issue records on NAD-ABC; institutes "can integrate APIs into existing portals for creating or verifying APAAR IDs" | PIB factsheet, https://www.pib.gov.in/FactsheetDetails.aspx?id=150693, and a CAG circular; **search excerpts only, not verified** |

**Not verified**: the NAD upload API and the ABC and APAAR APIs (names, endpoints, auth, sandbox), the exact CSV columns
(the templates are behind the institution's login), and ABC's credit upload format. The design below works without any
of them and switches to the API path by configuration when they are granted.

## Design

### Two channels per operation

| Operation | API channel (when granted) | Manual channel (v1.0 default) |
|---|---|---|
| `publish_awards`, `correct_awards` | Send the batch to NAD's upload API | Write NAD's award CSV for the template, store it in `platform/documents`, return `manual_action_required` with the file and steps: sign in to NAD, upload, choose the template, publish |
| `publish_credits` | Send to ABC's API | Write ABC's credit upload file, return `manual_action_required` |
| `verify_learner_id` | APAAR verification API | Answer `unverifiable`; never guess |
| `record_manual_upload` | not needed | A person records the upload date and NAD's reference; status `uploaded_manually`, the hub publishes `integration-hub.academic-record.submission-changed` |
| `get_submission` | Poll the depository | Local status |

The channel is chosen per connection: `capabilities.awards_api` is true only when the connection has API credentials
and the deployment has the endpoint. A module does not change when an institution moves from upload files to the API.

### Validation before anything leaves

Every row is validated first and a batch with any invalid row is refused whole, with `[row, field, code]` errors:
APAAR id present and 12 digits (or an explicit `apaar_missing` reason the institution accepts), name and date of
birth present, award number unique per organisation and award kind, credits and grade points within the programme's
scheme, a correction naming an award already lodged. A file that NAD would reject is never handed to a person.

### The award CSV

Columns follow NAD's standard CSV for the chosen template (examples seen in NAD guidance: organisation name,
registration and roll number, candidate name, gender, date of birth, course and stream, session, year and month of
result, result, division or CGPA, per-subject name, marks or grade and credits, certificate number and date of issue,
ABC id, MARKS REC STATUS). The exact columns are fixed per template version (`NAD_AWARDS_CSV_TEMPLATE_VERSION`) once
the first institution downloads the templates (open question 1). Files are UTF-8, one per template and at most
`NAD_MAX_ROWS_PER_FILE` rows.

### Connection (per organisation, in integration-hub)

| Kind | Name | Notes |
|---|---|---|
| setting | `nad_institution_id` | From the NAD account |
| setting | `abc_institution_id` | From the ABC registration |
| setting | `award_templates` | `[{award_kind, template_code, programme_level}]` |
| secret | `nad_api_key`, `abc_api_client_id`, `abc_api_client_secret` | Only once granted; names to be fixed by the API specs |

### Error mapping

| Depository answer | Port error | Retryable |
|---|---|---|
| Network error, timeout | `transport_unavailable` | yes |
| HTTP 5xx | `provider_error` | yes |
| HTTP 429 | `throttled` | yes |
| HTTP 401 or 403 | `auth_failed` | no |
| Batch or row refused by the API | `invalid_request` with row errors | no |
| No API configured for the operation | `manual_action_required` (with the file) | no |
| Correction for an award not lodged | `not_found` | no |

### Rate limits

None published. API batches are sent one at a time per connection; the hub holds the queue on `throttled`.

## Sandbox and mock

- **No public sandbox** for NAD or ABC. The manual channel needs none: it writes files, and tests compare them with
  sample files and the template's columns.
- **Recorded mock** for the API channel, built from the specs once NAD and ABC share them: accept, partial accept with
  row errors, auth failure, 5xx. Until the specs exist the API channel is not built; the port and the manual channel
  are (lead's decision, 5 Nov 2026: ship against a recorded mock where no sandbox exists, go live when the agency
  approves).

## Data model (summary)

Own schema `nad`; every table has `organisation_id` with row-level security.

| Entity | Key fields |
|---|---|
| submission | id, organisation_id, kind (awards, award_corrections, credits), depository (nad, abc), channel, award_kind, template_code, programme_code, session, term, status, rows, accepted_rows, rejected_rows, caller_reference, batch_key, portal_reference, uploaded_on, uploaded_by |
| submission_file | organisation_id, submission_id, document_id, filename, rows, template_version |
| lodged_award | organisation_id, award_number, award_kind, person_id, apaar_id_hash, submission_id, status (lodged, corrected) |

Rows themselves are not kept here after the file is written: the source of truth stays in examinations.

## Personal data (DPDP Act 2023)

- Lodging awards and credits is the institution's statutory duty under the UGC regulations; the APAAR id is created
  with the student's (or guardian's) consent upstream, not here.
- The upload files hold learners' names, dates of birth and results; they live in `platform/documents` with access for
  the uploading staff only, and are deleted once the submission is `uploaded_manually` or `accepted` and the
  retention period has passed (open question 5 sets the period).
- Stored here: the APAAR id as a hash for matching corrections, never in clear outside the upload file.
- NAD and ABC are Government of India services hosted in India.

## Permissions and events

- `nad:submission:read` (org-admin): `GET /submissions` and `GET /submissions/{id}`.
- No events of its own: the hub publishes `integration-hub.academic-record.submission-changed` and the delivery events.

## External dependencies (what Rooman must apply for)

| What | With whom | How | Needed for |
|---|---|---|---|
| **NAD registration, per institution** (Nodal Officer, authorised person) | NAD on DigiLocker; verified by UGC | https://nad.digilocker.gov.in | Any upload, manual or API |
| The award CSV templates and guidelines | NAD | Portal Resources section, after registration | Fixing the CSV columns |
| **NAD bulk upload API** specification and credentials | NAD / DigiLocker (NeGD) | Request through the NAD support contact or API Setu | API channel for awards |
| **ABC registration, per institution** | ABC (UGC, with NeGD) | https://www.abc.gov.in | Credits |
| **ABC and APAAR APIs** for HEIs (credit upload, APAAR verification), with sandbox | ABC / Ministry of Education | ABC portal or API Setu (https://apisetu.gov.in) | API channel for credits, `verify_learner_id` |

## Out of scope (v1.0)

- Creating APAAR ids (done by the student with consent through DigiLocker or ABC).
- NAD's own certificate rendering and template design (chosen on the portal).
- Verification requests from employers (they go to NAD with the student's consent).

## Open questions (for review)

1. **CSV templates (Himanshu, first institution).** The column list is fixed only when an institution downloads NAD's
   templates after registration. Which institution goes first, and who downloads them?
2. **Which result fields (Akshata, Madhumita).** NAD and ABC need course-level credits, grades, grade points and
   division or CGPA from `examinations.result.published` (examinations Q12).
3. **Credits source.** Credits per course come from academic-management's offerings; examinations caches them. Does
   the caller (examinations) send them, as the port assumes?
4. **Missing APAAR ids.** Many students will not have one at launch. Refuse their rows (proposed), or lodge with the
   enrolment number only where NAD's template allows it?
5. **File retention.** How long do upload files stay in `platform/documents` after upload?
6. **Operator view.** Should `examination-staff` also hold `nad:submission:read`?
