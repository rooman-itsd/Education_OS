# nad: data model

Own schema, tables prefixed `nad_`. Every table has `organisation_id` and, on Postgres, the forced `tenant_isolation`
row-level-security policy (`db/migrations/versions/20261105_0001_initial.py`). The Alembic chain has its own version
table, `nad_alembic_version`. **Learners' rows are not kept**: the upload file holds them, in platform/documents, and
the source of truth stays in examinations.

| Table | Purpose |
|---|---|
| `nad_submission` | One batch (awards, award corrections or credits): status, row counts, channel, template, session and term, the caller's `batch_key`, the steps for the person who uploads, row errors (`[{row, field, code}]`, never the learner's data), and once recorded the portal reference, date, uploader and acknowledgement document |
| `nad_submission_file` | The upload files of a submission: document id, filename, rows, template version |
| `nad_lodged_award` | An award prepared for NAD, unique per organisation, award kind and award number, with the APAAR id as a keyed hash (`NAD_APAAR_HASH_PEPPER`), so a duplicate is refused and a correction must name an award for the same learner |

`submission.payload_digest` is the SHA-256 of the batch as received: the same `batch_key` with the same batch answers
from the record; with another batch it is a conflict, unless the first was rejected, which is replaced.

## Status flow (manual channel)

`rejected` (row errors, nothing written) or `manual_action_required` (file written) then `uploaded_manually` once
`record_manual_upload` records the portal upload. `prepared`, `submitted`, `accepted` and `partially_accepted` belong to
the API channel, which is not built; the adapter never sets them.

## Personal data (DPDP Act 2023)

The upload files hold names, dates of birth, APAAR ids and results, so they live in platform/documents with access for
the uploading staff only; retention after upload is PRD open question 5. This schema holds no name, date of birth,
APAAR id in clear, or result.
