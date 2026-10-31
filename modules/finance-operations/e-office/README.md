# e-office

**Domain:** finance-operations
**Kind:** feature
**Status:** in-progress (backend built; not yet enabled in `apps/backend`; widget and pages to follow)

Paperless office files: a file with its note sheet and attachments moves from person to person until the competent
authority decides and the file is closed. Inward letters are registered and routed; approved letters are dispatched.
Requirements: [docs/prd.md](docs/prd.md).

## Scope
- **In scope:** file categories and file numbering; files with a numbered, append-only note sheet, attachments and
  movement history; forwarding with the action expected and a due date; decisions (approve, reject, return) by the
  competent authority; closing and reopening; each person's inbox and sent files; inward receipts registered by the
  central registry and attached to files; outward dispatch of approved letters; the pendency report; flagging files
  held past their due date.
- **Not in scope:**
  - approval chains for other modules' records (leave, purchase orders): those modules approve their own records;
  - digital signatures: a decision is recorded against the signed-in user;
  - sending email or post: a dispatch is recorded after it is sent;
  - storing documents: attachments and scans are platform/documents ids.

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml), mounted at `/api/v1/e-office`
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Backend

| Layer | Path | Contents |
|---|---|---|
| domain | `backend/src/eos_e_office/domain/rules.py` | File and register numbers, category codes, the date a holding falls due, overdue, age buckets, hours held. Pure Python. |
| application | `application/service.py` | Categories; files (open, note, attach, forward, decide, close, reopen, movements); inbox, sent and own receipts; receipts (register, attach, open a file from one); dispatches (request, mark sent); `flag_overdue`. |
| | `application/reports.py` | The pendency report. |
| | `application/jobs.py`, `application/consumers.py` | The `e-office.flag-overdue` scheduler job and its `scheduler.job.due` handler. |
| infrastructure | `infrastructure/models.py` | 9 `e_office_*` tables, including `file_holder` (who has held each file) and `audit_entry`. Each has `organisation_id`. |
| | `infrastructure/config.py` | `E_OFFICE_*` settings. |
| api | `api/router.py`, `api/schemas.py`, `api/deps.py` | Every operation of the contract, strict request bodies, and the token and permission check through `eos_core`. |
| db | `db/` | Alembic chain `e_office_0001` with its own version table `e_office_alembic_version`. It applies the `tenant_isolation` policy on Postgres. |

Rules the code keeps:
- **The note sheet and the movement history are append-only** (PRD). Notings are numbered
  paragraphs from 1 and are never edited or deleted: there is no route to do so. Decisions, closing, reopening,
  attached receipts and dispatches add their own paragraphs (kind `decision` or `system`). Movements are numbered per
  file too, so a decision and the forward made with it keep their order.
- **Only the holder acts.** Noting, attaching, forwarding, deciding, closing, attaching a receipt and requesting
  dispatch need the caller to hold the open file: anyone else who can see it gets 409 `not_holder`, and a closed file
  answers 409 `file_closed`. Deciding also needs `e-office:file:decide` (403 otherwise).
- **Who sees a file** (PRD). Everyone who has held it, for good. With
  `e-office:file:read-all`, every non-confidential file of the organisation as well. A confidential file is visible
  only to the people who have held it, read-all or not. A file the caller cannot see is 404, like one that does not
  exist, so its existence is not revealed. Reading is not holding: read-all users cannot note on a file they do not hold.
- **Nothing private goes into events** (PRD). Note text, forwarding remarks and decision
  remarks never reach an event; a confidential file publishes an empty subject. Events go to the outbox in the same
  transaction as the change, with exactly the payloads of `events.yaml` (a test checks every published event).
- **Every state change is audited.** An `audit_entry` row (actor, action, entity, id; never text) is written in the
  same transaction, until the audit SDK exists, as procurement does.
- **Numbers.** A file is `<category code>/<year>/<sequence>` (e.g. `ADM/2026/0007`), the sequence running per category
  and calendar year (Indian date). Receipts are `IN/<year>/<sequence>` and dispatches `OUT/<year>/<sequence>`, per
  organisation and year. On Postgres an advisory lock per organisation makes concurrent writers take turns; a number
  taken concurrently anyway is 409 `number_taken`, never 500. A changed category code applies to files opened after.
- **Business dates are Indian** (as procurement; decided by the owner on #335). "Today" is the date in Asia/Kolkata (UTC+05:30, a
  fixed offset: India has no daylight saving and tzdata is not on the approved stack). It decides file-number years,
  due dates, overdue, report ages and the dates that can't be in the future (`received_on`, `sent_on`) or the past
  (`due_on`). Timestamps are stored in UTC.
- **Overdue.** A holding falls due on the `due_on` given when the file was sent, or else on the date the holder received
  it plus `E_OFFICE_DEFAULT_DUE_DAYS_<PRIORITY>` (7, 2 and 1 days by default). It is overdue from the day after.
  `overdue` on every file summary and the inbox and report counts are computed on read. The `e-office.flag-overdue`
  job flags each overdue holding once and publishes `e-office.file.overdue` with the due date; a new holding (forward,
  reopen) starts unflagged. A file never counts as overdue once closed.
- **Decisions.** The holder with `e-office:file:decide` approves, rejects or returns with a remark. The decision becomes
  a paragraph and a movement, and `last_decision` on the file; a later decision replaces it. With
  `forward_to_user_id` the file goes on in the same step.
- **Close and reopen.** The holder closes with a remark; `e-office.file.closed` is published and nothing more can be
  done until someone with `e-office:file:create` who can see the file reopens it with a remark and becomes the holder.
- **Inward.** The registry (`e-office:correspondence:manage`) registers a receipt, received today or earlier, and sends
  it to one person; `e-office.receipt.registered` tells them. Only that person attaches it, either to an open file they
  hold (`POST /receipts/{id}/attach`) or to a new file (`receipt_id` on `POST /files`). It becomes an attachment of kind
  `correspondence` carrying the scan, and a paragraph. The inbox counts receipts still to attach; `GET /me/receipts`
  lists them.
- **Outward.** The holder of an open file whose last decision is approved requests dispatch of one of its attachments
  to an addressee (one pending request per letter and addressee). The registry marks it sent with the mode, the date
  (not after today, not before the request) and a reference; `e-office.dispatch.sent` is published and the file's note
  sheet records the number, even if the file has been closed meanwhile.

### Running the tests

```sh
pip install -e packages/core -e packages/testing -e "modules/finance-operations/e-office/backend[test]"
pytest modules/finance-operations/e-office/backend
```

The suite needs no other module: tokens are made with `eos_core.security`, and the scheduler and relay are stood in for
by calling the job's handler directly.

### Migrations

```sh
cd modules/finance-operations/e-office/db
alembic upgrade head                     # uses EOS_DATABASE_URL
```

### Needs from the host repo
- **Mounting, install and CI:** a `finance-operations/e-office` entry in `apps/backend/config/modules.enabled.yaml`
  mounts the router at `/api/v1/e-office` (package `eos_e_office`) and lets the install, CI and deploy scripts pick it
  up. That is a separate PR; until then the API is not served.
- **Scheduler:** installing the package declares `e-office.flag-overdue` on `eos.scheduler_jobs`, a platform job with a
  default schedule of 18:45 UTC (00:15 IST) daily, and its handler on `eos.event_consumers`. It runs once the scheduler
  loop and the event-bus relay run in the deployment; the run is closed by `e-office.job.finished`.
- **Notification:** `file.forwarded`, `file.overdue` and `receipt.registered` are meant for notification, which has no
  handler for them yet.
- **Roles:** `e-office:file:use` is granted to the staff roles in `contracts/permissions.yaml`; other profiles' staff
  roles need it too (PRD open question 2).

### Assumptions to revisit
- **People are not checked.** There is no identity SDK, so `to_user_id`, `forward_to_user_id` and `send_to_user_id`
  are taken as given: a file forwarded to a mistyped id is stuck (read-all can still see a non-confidential one, but
  nobody holds it to act), and a receipt sent to one can only be seen by the registry, which registers it again. `UserRef.name` is empty and `designation` null until identity names are
  available.
- **Documents are ids only.** The documents service has no SDK, so nothing is uploaded
  or checked: an attachment's `document_id` is stored as given. A receipt's scan (`document_id`) is optional, and so
  nullable on the receipt and on the attachment made from it, until the documents service exists; the contract said
  required.
- **Central registry = holders of `e-office:correspondence:manage`**, HR staff by default (as the contract grants;
  PRD open question 3). They see every receipt and dispatch, but only the person a receipt was sent to attaches
  it; another registry member gets 403.
- **Reopening needs `e-office:file:create` and sight of the file**, as the contract says; reopening publishes no event
  (none is defined).
- **Repeated decisions are allowed.** A later decision replaces `last_decision` (a returned file can be decided again);
  dispatch needs the last decision to be approved.
- **`urgent` in the inbox** counts files of priority urgent or immediate.
- **Departments are not enforced.** `department_id` is recorded and filtered on; identity issues no department claim.
- **The pendency report counts every open file**, confidential ones included, because it shows no subject.
- **File movement stays in this module** until platform/workflow has a contract (PRD open question 1).

## Frontend

Not built yet. The `e-office.files-pending` widget (HR Staff dashboard) will read `GET /me/inbox`, which this backend
serves as the contract describes; it and the pages come in a separate PR.

## Layout
| Path | Purpose |
|---|---|
| `docs/` | PRD |
| `contracts/` | OpenAPI, event schemas, permission catalogue |
| `backend/` | Domain, application, infrastructure, API layers and tests |
| `frontend/` | Widget and pages (to follow) |
| `db/` | Alembic chain, own tables only |
| `config/` | `env.example` |

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../../docs/architecture/module-standard.md#portability-checklist).
