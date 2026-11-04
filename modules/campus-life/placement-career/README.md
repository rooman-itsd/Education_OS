# placement-career

**Domain:** campus-life
**Kind:** feature
**Status:** in-progress (contract and backend; not enabled in `apps/backend` yet; widgets and pages to follow)

Campus placement for jobs: company records, drives, job openings, applications and offers.

## Scope
**Is:** company records, placement drives (dated campus events of one company), job openings in a drive or on their
own, student applications along a fixed status sequence, offers, and the reports behind the dashboard widgets
`placement-career.drives` (placement-officer), `placement-career.openings` (learner layouts, `GET /me/openings`) and
`placement-career.openings-summary` (placement staff and industry-liaison, `GET /reports/openings-summary`).

**Is not:** internships (field-training), recruiter logins (companies are records), automatic eligibility checks
(students self-declare; the officer shortlists), a one-offer policy. See [docs/prd.md](docs/prd.md) for the owner
decisions on #337 and [docs/user-stories.md](docs/user-stories.md).

**Roles:** `placement-career-officer` (placement-officer, industry-coordinator and practicum-coordinator layouts),
`placement-career-viewer` (industry-liaison), and `student` grants inherited by every learner layout.

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml), mounted at `/api/v1/placement-career`
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Backend

| Layer | Path | Contents |
|---|---|---|
| domain | `backend/src/eos_placement_career/domain/rules.py` | Statuses and the fixed application sequence; names, titles, URLs, emails, money, positions; eligibility criteria and declarations; the date rules of drives and openings. Pure Python. |
| application | `application/companies.py` | Company records: list, read, record, edit, deactivate and reactivate. |
| | `application/drives.py` | Drives: list, read with openings, create, edit and reschedule, schedule, complete, cancel (with their openings). |
| | `application/openings.py` | Openings: list, read, create, edit, publish, close, cancel. |
| | `application/applications.py` | The officer's list, read with history and status moves; the student's openings, applications, apply and withdraw. |
| | `application/reports.py` | Upcoming drives and the openings summary. |
| | `application/common.py` | Clock and Indian business date, audit, outbox, scoped queries, cursor pages, visibility. |
| infrastructure | `infrastructure/models.py` | 6 `placement_career_*` tables: `company`, `drive`, `opening`, `application`, `application_history`, `audit_entry`. Each has `organisation_id`. |
| api | `api/router.py`, `api/schemas.py`, `api/deps.py` | Every operation of the contract, request bodies, and the token and permission check through `eos_core`. |
| db | `db/` | Alembic chain `placement_career_0001` with its own version table `placement_career_alembic_version`. It applies the `tenant_isolation` policy on Postgres. |

Data model: [docs/data-model.md](docs/data-model.md). Events and platform services:
[docs/integration-points.md](docs/integration-points.md).

Rules the code keeps:
- **Jobs only (P1).** There is no internship type: an opening is a job.
- **The application sequence is fixed (P5).** applied → shortlisted → in_process → offered → accepted or declined, one
  step at a time and never back; the officer rejects (with a reason the student sees) from applied, shortlisted or
  in_process, and the student withdraws from the same three. Anything else is 409 `invalid_transition` (or
  `not_withdrawable`); `applied`, `withdrawn` or an unknown status is 422 `invalid_status`. Every move writes a history
  line (`GET /applications/{id}` shows it) and an audit record. The offer (CTC, joining date, notes) is recorded when
  moving to offered; the officer records the student's answer (PRD open question 2).
- **Eligibility is shown, never enforced (P4).** Criteria on drives and openings are checked for range only
  (`min_cgpa` 0 to 10, `max_active_backlogs` not negative, no empty programme). Applying needs `declares_eligible: true`
  (422 `declaration_required`); the declared programme, year, CGPA and backlogs are stored as given (ranges checked)
  and shown to the officer, never compared with the criteria.
- **Placed students are flagged, nothing is blocked (P5).** `student_placed` is true on every application of a student
  who has an accepted offer in the organisation, on any opening; `GET /applications?student_placed=` filters on it. A
  placed student can still apply and be offered. Students never see the flag.
- **One application per student and opening, a withdrawn one included** (409 `already_applied`; a unique constraint
  backs the check, so a concurrent second request is 409 too). A withdrawn application also blocks cancelling its
  opening or drive (409 `has_applications`): applications are never deleted.
- **Who sees what.** Draft and cancelled drives are visible only with `drive:manage`, draft and cancelled openings only
  with `opening:manage`; to anyone else they are 404, like a record of another organisation, and list filters cannot
  reveal them. Every reader sees the CTC (P6). Company contacts and notes appear only on `/companies` (`company:read`);
  drives and openings carry the company's id, name, industry and website. `applications_count` on an opening is null
  without `application:read`, so the viewer gets counts only in the reports. A student reaches only their own
  applications; another student's is 404.
- **Drives.** draft → scheduled (`drive.scheduled`) → completed on or after its date (`drive.completed`), or cancelled
  with a reason from draft or scheduled while no opening of it has an application (`drive.cancelled`). Cancelling
  also cancels its draft and open openings with the same reason (each open one publishes `opening.cancelled`; closed
  ones stay closed). Editing a scheduled drive's `scheduled_on` or `ends_on` publishes `drive.rescheduled`. The company
  of a drive with openings does not change (422 `company_mismatch`), and its date cannot move before the last day to
  apply of one of its openings (422 `close_date_after_drive`).
- **Openings.** draft → open (`opening.published`) → closed (`opening.closed`), or cancelled with a reason from draft
  or open while it has no application (`opening.cancelled`, published only for an open one). An opening in a drive
  belongs to the drive's company (`company_mismatch`), closes on or before the drive date (`close_date_after_drive`),
  is created only in a draft or scheduled drive (409 `drive_not_open_for_openings`) and published only once the drive
  is scheduled (409 `drive_not_scheduled`). Its company and drive do not change once it has applications (409
  `has_applications`). Closing stops new applications; existing ones go on.
- **Companies.** A company name is unique in the organisation (409 `company_exists`). An inactive company gets no new
  drives or openings and its drafts are not scheduled or published (409 `company_inactive`); its existing drives,
  openings and applications continue.
- **Dates are Indian business dates** (PRD rule). "Today" is the date in Asia/Kolkata (UTC+05:30, a fixed offset: India
  has no daylight saving and tzdata is not on the approved stack). A drive is created, or scheduled, only for today or
  later; an opening's `applications_close_on` and an offer's `joining_on` are today or later; a student applies up to
  and including `applications_close_on`. On `PUT`, `scheduled_on` and `applications_close_on` are checked against
  today only when they change. Timestamps are stored in UTC. Money is `Numeric(14, 2)` and answered as a two-decimal
  string.
- **Events carry ids, dates and the cancel reason only (P9)**: no names, declarations, offered CTC or company contacts.
  They go to the `eos_core` outbox in the same transaction as the change, with exactly the payloads of `events.yaml`
  (a test runs every event and checks keys and types). Moving to in_process publishes nothing. The envelope's `actor`
  is the acting user.
- **Every state change is audited.** An `audit_entry` row (actor, action, entity, id; never a declaration, an offer or
  a contact) is written in the same transaction, until the audit SDK exists, as e-office does.
- **Nothing is deleted**: there is no DELETE route.
- **Pages.** Lists answer `{items, next_cursor}`; pass `next_cursor` back as `cursor` for the next page. A cursor this
  API did not return is 400 `invalid_cursor`.

### Running the tests

```sh
pip install -e packages/core -e packages/testing -e "modules/campus-life/placement-career/backend[test]"
pytest modules/campus-life/placement-career/backend
```

The suite needs no other module: tokens are made with the platform's signing secret through `eos_core`, and every
`contracts/permissions.yaml` and dashboard layout is read from the repository, as the host does. It covers every route
with its permission and every error code (401 without a token and 403 for every role without the operation's
permission, on every route), the cross-tenant leak test, the event, audit record and change kept or dropped together, the Alembic chain against the models (upgrade and
downgrade), drift between code and contract (routes, permissions, error codes both ways, enums, response properties)
and every event's payload against `events.yaml`.

### Migrations

```sh
cd modules/campus-life/placement-career/db
alembic upgrade head                     # uses EOS_DATABASE_URL
```

### Needs from the host repo
- **Mounting, install and CI:** a `campus-life/placement-career` entry in `apps/backend/config/modules.enabled.yaml`
  (a separate PR) mounts the router at `/api/v1/placement-career` (package `eos_placement_career`) behind the
  entitlement gate; `py-setup.sh`, the API image, CI and the auto-deploy then install it, run its tests and upgrade its
  chain from that entry. Until then CI runs its suite with the disabled modules.
- **Identity:** tokens carry `sub`, `org` and `roles`; the layouts' `module_roles` and `extends` give the roles their
  keys (`eos_core.config.permissions_for`). The applicant's name is read from a `name` claim when the token has one.
- **Notification:** every event is meant for notification, which has no handler for them yet. No module consumes them
  in v1.0 and this module consumes nothing.
- **Configuration:** none (see `config/env.example`).

### Assumptions to revisit
Where the contract is silent the code takes the conservative reading below; the owner may decide otherwise.
- **An offer or a reason sent with another step is not recorded** (PRD open question 9): the contract says the offer
  is "recorded when status is offered" and the reason is "required for rejected", so with any other status they are
  ignored rather than refused.
- **`student_name` is the token's `name` claim, or empty.** Identity's tokens carry no name claim today, so the
  officer sees an empty name until they do (or until an identity SDK can look the person up).
- **Company names are compared ignoring case and repeated spaces** ("Infosys  Ltd" and "infosys ltd" are the same).
- **`PUT /companies/{id}` without `active` makes the company active**, as the contract's default (`true`) says.
- **An inactive company is checked only when a drive or opening moves to it** (or a draft is scheduled or published):
  editing an existing drive or opening of an inactive company is allowed, since "its existing ones continue".
- **A drive "has openings" when any opening, a cancelled one included, points to it** (its company then stays); the
  date check against openings counts those not cancelled.
- **An open opening moves into a drive only if that drive is scheduled** (409 `drive_not_scheduled`, the code publish
  uses), so no open opening sits in a draft drive.
- **Counts follow what the caller may see:** `drives_count` and `openings_count` on a company and `openings_count` on a
  drive leave out draft and cancelled records for callers without the manage permission. In the upcoming drives report
  `openings_count` counts open and closed openings, the ones students see.
- **The upcoming drives report takes drives whose `scheduled_on` is today or later**; a drive over several days that
  began before today is not listed. `closing_soon` lists every open opening, one whose last day has passed included
  (it is still open until the officer closes it).
- **An opening's `drive` is null when the caller cannot see that drive** (a closed opening of a cancelled drive).
- **Request bodies:** a missing reason body is 422 `reason_required`; a `ctc_per_annum` sent as a JSON number is 422
  `invalid_amount` (Money is a string); `CompanyInput`, `DriveInput` and `OpeningInput` ignore read-only fields so a
  record read from the API can be sent back, the other bodies refuse unknown fields. Field values are checked (422)
  before records are looked up (404) and before state (409).
- **A cursor is the position of the next item**, as in e-office and hr-payroll.

## Layout
| Path | Purpose |
|---|---|
| `docs/` | PRD, user stories, data model, integration points, screens |
| `contracts/` | OpenAPI, event schemas, permission catalogue |
| `backend/` | Domain, application, infrastructure, API layers and tests |
| `frontend/` | Widgets and pages (to follow) |
| `mobile/` | Mobile screens (optional) |
| `db/` | Alembic chain, own tables only |
| `config/` | `env.example` |
| `tests/e2e` | End-to-end tests runnable in isolation |

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../../docs/architecture/module-standard.md#portability-checklist).
