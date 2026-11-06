# rti: data model

Tables are created by the Alembic chain in `db/migrations` (revision `rti_0001`, version table `rti_alembic_version`).
Every table has `organisation_id` and the forced `tenant_isolation` row-level-security policy on Postgres, and every
query is also scoped to the caller's organisation in code. No foreign key leaves the module: every person is an identity
person id, held as a plain 36-character string. Models are in `backend/src/eos_rti/infrastructure/models.py`.

```
rti_request 1 ── * rti_referral
            1 ── 0..1 rti_response
            1 ── 0..1 rti_transfer
            1 ── 0..1 rti_appeal
rti_audit_entry (refers to a request or a referral by id, no foreign key)
```

## rti_request
One request for information (contract `Request`). Never deleted.

| Column | Type | Notes |
|---|---|---|
| id | string(36) | primary key |
| organisation_id, created_at | | tenant and creation time |
| seq | integer | 1, 2, 3 ... per organisation; unique with `organisation_id` |
| number | string(20) | `RTI-000045`: prefix (`RTI_REQUEST_NUMBER_PREFIX`) when recorded, dash, six digits of `seq`; unique per organisation |
| received_via | string(12) | `post`, `in_person`, `email`, `online_portal` |
| received_on | date | day received, 1900 to 2199, not after today in India |
| applicant_name | string(200) | personal data |
| applicant_address | text, null | personal data, at most 1000 characters |
| applicant_email | string(254), null | personal data |
| applicant_phone | string(40), null | personal data |
| applicant_person_id | string(36), null | identity person id when the applicant is a user; personal data |
| subject | string(200) | |
| information_sought | text | at most 10 000 characters |
| fee_status | string(8) | `paid`, `exempt`, `pending` |
| fee_amount, fee_currency | numeric(12,2), string(3) | null together; currency defaults to `RTI_DEFAULT_CURRENCY` |
| fee_mode, fee_receipt_reference | string(100), null | as recorded by the officer |
| officer_id | string(36), null | assigned officer |
| status | string(14) | `received`, `assigned`, `responded`, `appealed`, `appeal_decided`, `transferred`, `closed` |
| closure | string(16), null | `responded`, `appeal_decided` or `transferred`, set when the request is final |
| created_by | string(36) | who recorded it |
| assigned_at, responded_at, closed_at, updated_at | timestamptz | |

Indexes: `(organisation_id, status)`, `(organisation_id, officer_id)`. Due dates and `overdue` are not stored: they are
worked out when read from `received_on`, the response's or appeal's dates and the `RTI_*` settings.

## rti_referral
A question to an internal custodian. The custodian sees `question`, `due_on`, the status, their reply and the request
number; never the applicant, subject or response.

| Column | Type | Notes |
|---|---|---|
| id, organisation_id, created_at | | |
| request_id | string(36) | to `rti_request` |
| custodian_id | string(36) | identity person id |
| question | text | must not repeat the applicant's name, email or phone |
| due_on | date, null | |
| status | string(8) | `open`, `replied` |
| reply, replied_at | text, timestamptz, null | |
| created_by | string(36) | the officer |

Indexes: `(organisation_id, request_id)`, `(organisation_id, custodian_id, status)`.

## rti_response
The response (at most one per request: `uq_rti_response_request`).

| Column | Type | Notes |
|---|---|---|
| request_id | string(36) | |
| type | string(20) | `information_provided`, `partly_provided`, `refused` |
| summary | text | |
| grounds | text, null | required for `partly_provided` and `refused` |
| dispatched_on | date | not before `received_on`, not after today; the appeal window runs from it |
| dispatch_mode | string(12) | a channel |
| responded_by | string(36) | |

## rti_transfer
The transfer to another public authority (at most one per request).

| Column | Type | Notes |
|---|---|---|
| request_id | string(36) | |
| authority_name | string(200) | |
| authority_address | text, null | |
| transferred_on | date | not before `received_on`, not after today |
| reason | text | |
| transferred_by | string(36) | |

## rti_appeal
The first appeal (at most one per request).

| Column | Type | Notes |
|---|---|---|
| request_id | string(36) | |
| filed_on | date | within the appeal window, not before `dispatched_on`, not after today |
| grounds | text | |
| filed_by | string(36) | |
| outcome | string(14), null | `upheld`, `partly_upheld`, `dismissed` |
| decision_note, decided_by, decided_on | text, string(36), date, null | `decided_on` not before `filed_on`, not after today |

## rti_audit_entry
Who changed or read what (stands in for the audit SDK).

| Column | Type | Notes |
|---|---|---|
| id, organisation_id | | |
| actor | string(36), null | |
| action | string(60) | `request.recorded`, `request.corrected`, `request.assigned`, `request.responded`, `request.transferred`, `request.closed`, `request.read`, `referral.created`, `referral.replied`, `appeal.filed`, `appeal.decided` |
| entity, entity_id | string(40), string(36) | `request` or `referral`, and its id |
| occurred_at | timestamptz | |

Index: `(organisation_id, entity, entity_id)`. Rows hold ids and the action only, never applicant data or request content.
