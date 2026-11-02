# Integration points — admissions

Admissions is the front door of the student lifecycle. It coordinates with several other modules
across its lifecycle. Every integration is event-driven or reference-driven; this module does not
import code from, nor make direct database joins into, another module's tables.

## Modules that consume admissions events

| Event | Consumer | Purpose |
|---|---|---|
| `admissions.application.accepted` | `finance-operations/fees-accounts` | Raise confirmation / seat fee invoice (see `docs/architecture/ARCHITECTURE.md`) |
| `admissions.application.accepted` | `student-lifecycle/student-information` (manual) | Staff creates Person / Student record referencing the application as `source` |

## Outgoing references stored by admissions

| Reference | Target module | Format | Notes |
|---|---|---|---|
| `programme_id` | `academics/academic-management` | UUID | Stored on `Application` and `MeritList`; no foreign key constraint |
| `selection_process_round_id` | `practice/selection-process` | UUID (nullable) | Optional reference when admission uses a selection round |
| `portfolio_item_id` | `practice/portfolio` | UUID (nullable) | Optional reference when admission reviews a portfolio item |
| `document_id` | `platform/documents` | String | References an uploaded file |

## Incoming calls into admissions

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
- **An authenticated applicant experience**: Supported via `POST /me/applications` and `GET /me/applications`.
  Applicants submit applications anonymously and track them via public tracking or link their application to
  their identity account (`applicant` role holding `admissions:self:read`) to track status and documents on
  the Applicant dashboard (`platform/identity/config/dashboards/applicant.yaml`).
