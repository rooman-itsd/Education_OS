# admissions — integration points

## Events published (contracts/events.yaml)

| Event | Known/likely consumers |
|---|---|
| `admissions.application.submitted` | None required this week; available for `platform/notification` (confirmation email) once that module's contract exists |
| `admissions.application.status-changed` | `platform/notification` (status update emails), when it exists |
| `admissions.merit-list.published` | `platform/notification`; applicants poll the public tracking endpoint rather than being pushed to |
| `admissions.offer.made` | `platform/notification` |
| `admissions.application.accepted` | **`finance-operations/fees-accounts`** — confirmed by the existing example in `docs/architecture/ARCHITECTURE.md` ("fees-accounts... subscribes to admissions.application.accepted and creates a fee invoice") |
| `admissions.application.declined` | `platform/notification` |

## Events consumed

None. `module.yaml`'s `consumes_events: []` stays empty. This module does not react to any other
module's event in this release.

## Platform services used (via packages/sdk)

| Service | Use |
|---|---|
| `platform/documents` | Storage for uploaded application documents; this module stores only `document_id` references (opaque; not validated, since documents has no service to call yet) |
| `platform/audit` | Every status change, document verification, offer and decision is audited. Until audit has a service, rows go to this module's own `admissions_audit_entry` table, as other built modules do |

## What the host must provide

- **Public routes through the gateway.** `apps/backend`'s entitlement gate must let
  `/api/v1/admissions/public/{org_slug}/*` through without a token, after resolving the slug to an
  active organisation entitled to admissions (404 otherwise), and pass that organisation id to the
  route. Every other admissions path keeps the normal token check.

## Cross-module API dependencies

None. This module does not call `student-information`, `fees-accounts`, `practice/portfolio`,
`practice/selection-process`, `platform/tenancy` or `platform/identity`'s business endpoints.
`programme_id`, `selection_process_round_id` and `portfolio_item_id` are stored as opaque id
references, never validated against another module's schema or API in this release.

## Known future integrations (not dependencies today)

- **student-information**: once an application is `accepted`, an authorised staff member creates
  a Person record there directly (a manual action through student-information's own API), passing
  a `source` reference back to this application's id. This module does not call that API and does
  not need its contract to exist to publish its own — the relationship is staff-mediated, not
  code-mediated.
- **An authenticated applicant experience**: not planned. Applicants stay anonymous (see
  `docs/prd.md` §6) and use the public Track application page. `admissions.application-status`
  and `admissions.pending-documents` are built as staff widgets; `applicant.yaml` still lists
  them, and the shell hides them there (see `docs/screens.md`).
