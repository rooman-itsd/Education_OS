# library: user stories

Owner: Tejaswini (@tejaswini-rooman) · Status: draft for review · Batch #338

Stories by role for the library module. Each story follows `prd.md` and is bounded by the contract in
`contracts/openapi.yaml`, `events.yaml` and `permissions.yaml` (0.2.0); where a need is not in the contract it is
listed under [Gaps](#gaps-not-in-the-contract) instead of being written as a story. Paths are relative to
`/api/v1/library`.

## Roles

| Role (`permissions.yaml`) | Who | Grants |
|---|---|---|
| `library-member` | Every student (the student layout lists it in `module_roles`), and other members such as faculty and staff | `self:read`, `self:borrow` |
| `librarian` | Desk and cataloguing staff | `catalogue:read`, `catalogue:manage`, `member:manage`, `circulation:manage`, `fine:manage` |
| `library-admin` | Head librarian | everything the librarian has, plus `policy:manage` |
| `library-viewer` | Management and org admin, read only | `catalogue:read` |

All keys above are short for `library:<resource>:<action>`. A call without the permission named for its endpoint is
refused with 403 and changes nothing. Desk refusals answer 409 with the contract's `Refusal` body
(`{code, message}`), the code one of `not-a-member`, `member-blocked`, `loan-limit`, `unpaid-fines`,
`copy-unavailable`, `held-for-other`, `no-renewals-left`, `title-reserved`.

## Rules every story inherits

- **R1 Tenant isolation.** Every record carries `organisation_id` and is protected by row-level security. A user sees
  and changes only their own organisation's records; another organisation's record is never listed and a request
  for it answers 404. The cross-tenant leak test from `eos_testing` passes for every list.
- **R2 Events carry the tenant.** Every published event carries `organisation_id`.
- **R3 Audit.** Every state change writes an audit record with the actor.
- **R4 Exact money.** Amounts are exact decimals (`Numeric(12, 2)` in the database, strings like `"25.00"` in the
  API); never floating point.
- **R5 Nothing is deleted.** Copies are withdrawn, loans returned or lost, fines paid or waived, reservations
  cancelled, fulfilled or expired. Loan policies are configuration and are replaced as a whole.
- **R6 Own data only.** `/me/*`, renewing and cancelling own reservations are limited to the caller.
- **R7 One loan, one hold.** A copy has at most one active loan and at most one active hold.
- **R8 No hard dependency.** Fines can always be settled at the desk; fees-accounts is optional.

## 1. Catalogue

**CA-1 Catalogue a title.** As a librarian, I add a title so that members can find it.
- `POST /titles` with `catalogue:manage`, `title` and `kind` required; `isbn`, `authors`, `publisher`, `year`,
  `subjects` optional. A second title with the same ISBN answers 409.

**CA-2 Add and move copies.** As a librarian, I add physical copies with an accession number and barcode.
- `POST /titles/{id}/copies`; a used accession number or barcode answers 409. A new copy is held for the first
  member waiting for the title, if any, else it is available.
- `PATCH /copies/{id}` moves a copy (`location`) or withdraws it with a reason; a copy on loan or on hold answers
  409. Restoring a withdrawn copy makes it available (or holds it for the queue).

**CA-3 Search the catalogue.** As a member or librarian, I search titles.
- `GET /titles` with `catalogue:read` or `self:read`; `q` matches title, author, subject or ISBN, ignoring case;
  `kind` and `available` filter; every title carries `copies_total` (not withdrawn) and `copies_available`.
- `GET /titles/{id}` adds the copies and the number of reservations waiting.

**CA-4 Digital resources.** As a librarian, I list e-books, journals and databases by link.
- `POST`/`PATCH /digital-resources` with `catalogue:manage`; `url` must be http(s); `access` is open, campus or
  licensed. Members see active resources only; staff with `catalogue:read` see all.

## 2. Members and policies

**ME-1 Add a member.** As a librarian, I register a person who borrows, with a category such as student or faculty.
- `POST /members`; a person already a member answers 409; `person_id` must be a uuid.

**ME-2 Block and unblock.** As a librarian, I block a member from borrowing, with a reason.
- `PATCH /members/{person_id}` with `blocked: true` and a reason of at least 3 characters publishes
  `library.member.blocked`; without a reason it answers 422. Unblocking clears the reason.
- `GET /members?blocked=true` lists blocked members; `GET /members/{person_id}` shows active loans and the open
  fines total.

**PO-1 Loan policies.** As the head librarian, I set the rules per member category.
- `PUT /loan-policies` with `policy:manage` replaces all policies: `max_loans`, `loan_days`, `max_renewals`,
  `fine_per_day`, `max_unpaid_fines`, `hold_days`. A category listed twice, or an amount that is not exact money,
  answers 422. New loans and renewals use the new rules.

## 3. Circulation

**CI-1 Issue at the desk.** As a librarian, I scan a copy and lend it to a member.
- `POST /loans` with `circulation:manage`, `barcode` and `person_id`. Refused (409) when the person is not a member,
  is blocked, has no policy for their category or is at the loan limit, has open fines above `max_unpaid_fines`,
  or the copy is not available or is held for someone else. An unknown barcode answers 404.
- The due date is today plus `loan_days`. Issuing a copy held for this member fulfils their reservation.
- Publishes `library.loan.issued`.

**CI-2 Return.** As a librarian, I scan a returned copy.
- `POST /returns` with the barcode (and an optional damage note). A copy not on loan answers 409.
- Late by N days raises an `overdue` fine of N × `fine_per_day` (`library.fine.raised`); on time raises none.
- If someone is waiting for the title, the copy is held for the first in the queue for `hold_days`
  (`library.reservation.ready`); else it is available. Publishes `library.loan.returned` with `days_late`.

**CI-3 Renew.** As a member, I renew my own loan; a librarian can renew any.
- `POST /loans/{id}/renew` with `self:borrow` for the caller's own loan (another's answers 404) or
  `circulation:manage`. Refused with `no-renewals-left` or `title-reserved`.
- The new due date is today plus `loan_days`, never earlier than before. Renewing a loan that is already late first
  raises the overdue fine for the days late, so renewing never erases a fine. Publishes `library.loan.renewed`.

**CI-4 Lost.** As a librarian, I mark a loaned copy lost.
- `POST /loans/{id}/lost` with a `replacement_amount` raises a `lost` fine and marks the copy lost; publishes
  `library.loan.lost` and `library.fine.raised`. A loan that is not active answers 409.

**CI-5 My loans.** As a student, I see what I have borrowed.
- `GET /me/loans` with `self:read`: active loans, earliest due first, each with `overdue`, `renewals_left` and the
  `fine_accrued` so far. This backs the Student widget `library.loans`.

**CI-6 Staff views.** As a librarian, I list loans by status, overdue or person (`GET /loans`).

## 4. Reservations

**RE-1 Reserve.** As a member, I reserve a title with no copy available.
- `POST /me/reservations` with `self:borrow`. Answers 409 when a copy is available, when I already have an active
  reservation for the title, or when I am not a member. The answer shows my place in the queue; publishes
  `library.reservation.placed`.

**RE-2 Collect a held copy.** As the first member waiting, I collect the copy held for me.
- When a copy comes back it is held for me until `hold_expires_on`; another member cannot borrow it
  (`held-for-other`). Issuing it to me fulfils my reservation.

**RE-3 Cancel.** As a member, I cancel my own reservation; a librarian can cancel any.
- `POST /reservations/{id}/cancel`; another member's answers 404; a reservation already fulfilled, cancelled or
  expired answers 409. Cancelling a ready reservation passes the held copy to the next in the queue.

**RE-4 See my reservations.** `GET /me/reservations`: waiting (with position) and ready (with the hold expiry).

## 5. Fines

**FI-1 Pay at the desk.** `POST /fines/{id}/pay` with `fine:manage` and a receipt reference; publishes
`library.fine.paid`. A fine not open answers 409.

**FI-2 Waive.** `POST /fines/{id}/waive` with a reason; publishes `library.fine.waived` with who waived it.

**FI-3 My fines.** `GET /me/fines`: open fines and their exact total.

**FI-4 Paid through fees-accounts.** As the organisation, when we invoice fines in fees-accounts, a paid invoice
marks the fine paid in library.
- library consumes `fees-accounts.invoice.paid` (agreed on #175): when `source_module` is `library`, the fine
  `source_reference` is marked paid with the receipt `fees-accounts:<invoice_id>` and `library.fine.paid` is
  published. A repeated event, a fine already settled, another module's invoice or a malformed payload changes
  nothing. The handler is found by the event-bus relay through the `eos.event_consumers` entry point.

## 6. Daily jobs

**JO-1 Overdue.** Once a day, every active loan past its due date publishes `library.loan.overdue` exactly once.

**JO-2 Expired holds.** Once a day, a ready reservation whose hold ran out is expired
(`library.reservation.expired`) and the copy is held for the next member waiting, or becomes available.

## Gaps (not in the contract)

- Member names and categories are entered by the librarian; no event from student-information or hr-payroll feeds
  them yet (PRD question 2).
- A damage note is recorded on the loan; a `damage` fine has no endpoint of its own yet.
- No staff dashboard widgets in wave A (the librarian dashboard is a later wave).
