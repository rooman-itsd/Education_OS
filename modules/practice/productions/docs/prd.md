# productions: product requirements

**Owner:** Himanshu (@himanshu-rooman) · **Backup:** @akshatatrathodrooman · **Tier:** common · **Status:** built (sprint v1.0, issue #318)

## 1. Purpose

productions is the **generic "something is being put on" pattern** of Education OS (ADR-0004). An
academy rehearses and performs; an engineering college runs a hackathon; a law school holds a moot
court; a research office puts on a conference. All of them do the same four things: put a date in a
calendar, decide who is in it, work through a list of things that must be ready first, and then
perform it.

The same module serves every academy type; the word people see comes from the profile vocabulary:

| Profile | `productions.production` |
|---|---|
| theatre-academy, dance-academy | Production |
| music-academy | Concert / recital |
| arts-academy | Exhibition |
| film-media-institute | Screening |
| engineering-college | Hackathon |
| law-school | Moot court |
| hospitality-institute | Banquet / service |
| research-university | Conference |

The contract never uses a field-specific word: it speaks of **productions**, **parts** (cast and
crew) and **preparation tasks**. `kind` records which sort of thing it is, for display and filtering
only — no rule depends on it.

## 2. Scope

**In scope**
- A production: title, kind, department, venue, dates, call time, the person leading it
- Its life: planned → in preparation → scheduled → completed, and cancelled from any of those
- Cast and crew: offering a part, the person accepting or declining it, withdrawing an assignment
- Preparation tasks with an optional due date and assignee, and what is still outstanding
- The four dashboard widgets below
- An event for every state change, on the outbox

**Out of scope**
- **Booking the hall**: `facilities/facility-booking`. A production may carry the `resource_id` of
  the booking, as a plain reference with no foreign key.
- **Costumes, instruments and equipment**: `facilities/inventory-equipment`.
- **Ticketing, box office and payments**: not planned for v1.0.
- **Marks for a performance**: `academics/examinations`. A production is not an assessment.
- **Selecting who may audition**: `practice/selection-process`.
- **Rehearsal timetabling**: out of scope; a rehearsal is not modelled. Preparation tasks carry the
  things that must happen, not a schedule of them.

## 3. Data

| Table | What it holds |
|---|---|
| `productions_production` | One production and its dates, venue, status and lead |
| `productions_role` | One part or crew job, offered to one person |
| `productions_task` | One thing that must be done before the production can go ahead |

Every table carries `organisation_id` and the `tenant_isolation` row-level-security policy. No
foreign key leaves the module: `resource_id` and every user id are plain references.

## 4. Rules

1. **A production needs no dates to exist.** An academy puts a show on the calendar long before it
   knows the hall. Dates are required only to schedule it.
2. **It must end after it starts**, and a run longer than `PRODUCTIONS_MAX_RUN_HOURS` is refused as
   a typo rather than accepted silently.
3. **The call time may not be after the start.** With none given it is
   `PRODUCTIONS_DEFAULT_CALL_MINUTES` before it.
4. **Dates in the past are allowed.** An academy records a recital that already happened; only the
   order of the dates is a rule.
5. **Nothing changes a completed or a cancelled production** — not an edit, not a new part, not a
   task.
6. **Preparation starts once**, from `planned`. Completion happens only from `scheduled`.
7. **Scheduling closer than `PRODUCTIONS_MIN_PREPARATION_DAYS` warns but goes ahead.** The academy
   decides, not the software; the warning is returned with the production.
8. **Only the person a part was offered to may answer it**, and only once, and only while the
   production is alive. Answering somebody else's part is 403; answering it twice is 409.
9. **Offering the same person the same part twice is the same offer**, not a second one. Offering a
   part that was declined or withdrawn opens the same row again.
10. **Cancelling withdraws every part people still hold**, each with its own event, so notification
    can tell them.
11. **Two callers cannot both act on one row.** A decision and a withdrawal take a row lock
    (`FOR NO KEY UPDATE`), so an accept and a withdrawal racing cannot both apply — the bug the
    audit of #317 found in workflow.
12. **`client_token` is unique per caller, not per organisation.** The same audit found a shared
    token handing one user another user's row.

## 5. Permissions

| Key | Who holds it |
|---|---|
| `productions:production:read` | everyone on a dashboard that shows a production widget |
| `productions:production:manage` | coordinating roles only |
| `productions:role:read-own` | everyone: their own parts |
| `productions:role:respond` | everyone: answering their own invitation |
| `productions:role:manage` | leads and coordinators |
| `productions:task:read` / `:manage` | leads and coordinators |

Three module roles gather them: **productions-member** (performers and crew),
**productions-lead** (directors, choreographers, mentors) and **productions-coordinator**
(production and stage managers, the coordinating offices). Each academy profile role whose dashboard
shows a widget is granted the keys of the module role its widget needs, in
`contracts/permissions.yaml`.

## 6. Widgets

| Widget | For | Shows | Endpoint |
|---|---|---|---|
| `productions.calendar` | coordinating roles | What is on over the next weeks, with venue, time and how many have confirmed | `GET /calendar` |
| `productions.upcoming` | learners, performers, management | The next productions, with no window and no cast figures | `GET /upcoming` |
| `productions.my-roles` | performers | The caller's own parts, and which still need an answer | `GET /my-roles` |
| `productions.in-preparation` | leads and mentors | What is being got ready, most pressing first, and what is outstanding on each | `GET /in-preparation` |

## 7. Events

`productions.production.{created,updated,preparation-started,scheduled,cancelled,completed}`,
`productions.role.{assigned,accepted,declined,withdrawn}` and
`productions.task.{added,completed}`, all on the transactional outbox in the same transaction as the
change. `role.assigned`, `role.withdrawn` and `production.cancelled` carry the user ids a
notification consumer needs.

## 8. Open points

- **No notification consumer yet.** The events carry what is needed; nothing listens. A person
  offered a part learns of it on their dashboard, not by email.
- **No reporting metrics yet.** `platform/reporting`'s ingestion (#452) could count productions per
  department once it is merged.
- **Rehearsals are not modelled.** If an academy needs them, they are facility-booking bookings that
  carry the production's id, not a new table here.
