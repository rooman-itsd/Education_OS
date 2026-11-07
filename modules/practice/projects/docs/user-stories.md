# projects: user stories

Owner: Tejaswini (@tejaswini-rooman) · Status: draft for review · Issue #339

Stories by role for the projects module. Each story follows `prd.md` and is bounded by the contract in
`contracts/openapi.yaml` (0.1.0), `events.yaml` and `permissions.yaml`. Paths are relative to `/api/v1/projects`.
The words project, milestone and guide are the generic ones; users see the academy profile's labels
(`projects.project`, `projects.milestone`, `projects.guide`).

## Roles

| Role (`permissions.yaml`) | Who | Grants |
|---|---|---|
| `projects-member` | Learner on a project team (engineering-student, research-scholar, filmmaker, ... through their layout's `module_roles`) | `self:read`, `self:propose`, `self:submit` |
| `projects-guide` | Guide of project teams (project-guide, research-supervisor, mentor, director, ...) | `guidance:read`, `milestone:manage`, `review:record` |
| `projects-coordinator` | Coordinates projects for the organisation (research office, department admin, ...) | `project:read`, `project:manage` |
| `projects-viewer` | Management and org admin, read only | `project:read` |

All keys above are short for `projects:<resource>:<action>`. A call without the permission named for its endpoint is
refused with 403 and changes nothing. A **member** is a person on the team (no `left_at`); a **guide** is a person in
the project's current guides. Holding `guidance:read`, `milestone:manage` or `review:record` acts only on projects the
caller guides; the self-service keys act only on the caller's own projects.

## Rules every story inherits

- **R1 Tenant isolation.** Every record carries `organisation_id` and is protected by row-level security. Another
  organisation's record is never listed, and a request for it by id answers 404. The cross-tenant leak test passes.
- **R2 Events carry the tenant.** Every published event carries `organisation_id`. Submission notes, files and review
  comments are never published.
- **R3 Audit.** Every state change writes an audit record with the actor (ids and action only).
- **R4 Nothing is deleted.** Projects are rejected, cancelled or completed; members leave (`left_at`), guides are
  replaced (kept with the date they were removed); milestones are cancelled; every submission version is kept.
- **R5 One lead, no double roles.** A proposed or active project has exactly one lead; nobody is both team member and
  guide of the same project; so a guide never reviews a project they are on.
- **R6 Inputs are checked, never a 500.** Any id in a path, query or body that is not a uuid is a 422. Every string,
  list and number is bounded; dates lie between the years 1900 and 9998. A NUL character in a path id is a 404, in a
  query parameter a 422 `invalid_query`, in a body a 422. The title search takes `%` and `_` literally. A cursor the
  API never handed out (bad, negative or past 1,000,000) starts from the top. A duplicate write that slips past the
  row locks (two requests at once) is a 409 (`already_submitted`, `already_reviewed`).
- **R7 Business dates are Indian.** Overdue, days left and days waiting are judged on today's date in Asia/Kolkata.
- **R8 No hard dependency.** The module works whether portfolio, skill-progress or productions are enabled or not.
- **R9 Test data.** No real learner data in tests or seeds.

## 1. Proposals and decisions (PR)

**PR-1 Propose a project.** As a learner (`self:propose`), I propose a project with a title, summary, kind, academic
year, period and optional external partner, and become its lead.
- `POST /projects` answers 201 with status `proposed`, `lead_id` = me, no guides. `member_ids`, `lead_id` and
  `guide_ids` in my body are ignored.
- `ends_on` before `starts_on` is 422. `projects.project.proposed` is published with the title, kind and lead.

**PR-2 Create a project directly.** As a coordinator (`project:manage`), I create a project with its team, lead and
guides; it starts `active` and `projects.project.approved` is published with the members, guides and period.
- No lead, or a lead who is not a member (the lead is added to the team when `member_ids` leaves them out): 409
  `no_lead`. No guide: 409 `guide_required`. A guide who is also a member: 409 `member_is_guide`.

**PR-3 Edit my proposal.** As the lead, I change the title, summary, kind, year, period or partner while the project
is proposed (`PATCH /projects/{id}`); fields left out keep their value.
- Another member of the team: 403 `not_lead`. After the decision: 403 `not_proposed`. A project I am not on: 404.
- A coordinator may edit any project that is not completed, rejected or cancelled (otherwise 409 `invalid_status`).

**PR-4 Approve or reject.** As a coordinator, I approve a proposal with at least one guide (proposed → active,
`projects.project.approved`) or reject it with a reason of at least three characters (→ rejected,
`projects.project.rejected`).
- Approving without a guide: 409 `guide_required`; with a team member as guide: 409 `member_is_guide`.
- Rejecting without a reason: 422 `reason_required`. Deciding a project that is not proposed: 409 `invalid_status`.

**PR-5 Find projects.** As a coordinator or viewer (`project:read`), I list every project
(`GET /projects`) by `status`, `kind`, `academic_year`, `guide_id`, `member_id` and `q` (title contains), 20 a page
(`limit` 1..100, `cursor`), ending soonest first; and open one with its team, guides and milestones
(`GET /projects/{id}`).

## 2. Teams and guides (TM)

**TM-1 Add a member or change the lead.** As a coordinator (proposed or active project) or the lead (while proposed),
I add a person to the team, or make a member the lead (`POST /projects/{id}/members`, 201).
- Making someone lead demotes the current lead to member; there is always exactly one lead.
- Already on the team in that role: 409 `already_member`. A guide of the project: 409 `member_is_guide`.
- `projects.member.added` is published with the role (also when a member becomes lead). A former member may rejoin.

**TM-2 Remove a member.** `DELETE /projects/{id}/members/{person_id}` answers 204, sets `left_at` and publishes
`projects.member.removed`. The lead: 409 `member_is_lead` until another member is made lead. Not on the team: 404.

**TM-3 Replace the guides.** As a coordinator, I set the project's guides (`PUT /projects/{id}/guides`, at least one).
Guides kept keep their assignment date; removed guides stop seeing the project. A team member as guide: 409
`member_is_guide`. `projects.guide.assigned` is published when the set changes. Closed projects: 409.

## 3. Milestones (MS)

**MS-1 Set milestones.** As a guide of the project (`milestone:manage`) or a coordinator, I add a milestone with a
title, description, due date and optional weight 0..100 to an active project (`POST /projects/{id}/milestones`,
201, status `pending`). `projects.milestone.created` is published. A guide of another project: 403 `not_guide`. A
project that is not active: 409 `project_not_active`.

**MS-2 Move or cancel a milestone.** `PATCH /milestones/{id}` changes the title, description, due date or weight, or
cancels it (`status: cancelled`, optional reason). Once accepted: 409 `milestone_accepted`; once cancelled: 409
`invalid_status`. Cancelled milestones do not count in a project's progress.

**MS-3 See milestones.** `GET /projects/{id}/milestones` lists them in due order, each with `overdue` and the time of
the latest submission. Visible to `project:read`, a guide of the project, and its members; anyone else gets 404.

## 4. Submissions and reviews (SR)

**SR-1 Submit a milestone.** As a team member (`self:submit`), I submit a pending or returned milestone with a note
(up to 4000 characters) and up to 20 document ids uploaded through platform/documents
(`POST /milestones/{id}/submissions`, 201). Each submission is a new version (1, 2, ...); the milestone becomes
`submitted` and `projects.milestone.submitted` is published with the version.
- Not a member: 403 `not_member`. Already submitted, accepted or cancelled: 409 `invalid_status`. Project not active:
  409 `project_not_active`.

**SR-2 Review a milestone.** As a guide of the project (`review:record`), I accept or return the latest submission
with comments and an optional score 0..100 (`POST /milestones/{id}/review`). Returning needs comments (422
`comments_required`). Accepted publishes `projects.milestone.accepted` with the score; returned publishes
`projects.milestone.returned`, and the team may submit again.
- Not a guide of this project (a coordinator included): 403 `not_guide`. Nothing submitted: 409 `nothing_submitted`.
- The milestone row is locked while it is reviewed, so two guides cannot both review the same submission.

**SR-3 See the history.** `GET /milestones/{id}/submissions` lists every version, oldest first, each with its review.
Same visibility as MS-3.

## 5. Final submission and evaluation (FE)

**FE-1 Submit the project.** As a team member, I make the final submission of an active project
(`POST /projects/{id}/submit`, 201; active → submitted). Milestones neither accepted nor cancelled are listed in
`milestones_not_accepted` as a warning, not refused. `projects.project.submitted` is published. Not a member: 403;
not active: 409 `project_not_active`.

**FE-2 Evaluate.** As a guide of the project, I record the evaluation (`POST /projects/{id}/evaluation`):
`completed` needs an outcome on the organisation's scale (422 `outcome_required`), takes an optional score and
comments (submitted → completed, `projects.project.completed` with members, guides, outcome and score); `returned`
sends it back for more work (submitted → active, `projects.project.returned`), and the team submits again as version 2.
Not submitted: 409 `project_not_submitted`. Not a guide of this project: 403 `not_guide`.

## 6. Cancel (CA)

**CA-1 Cancel a project.** As a coordinator, I cancel a proposed or active project with a reason
(`POST /projects/{id}/cancel`; reason 3..2000 characters). `projects.project.cancelled` is published. Completed,
rejected, cancelled or submitted: 409 `invalid_status`. A cancelled project takes no members, guides, milestones or
submissions (409).

## 7. Self-service (SS)

**SS-1 My projects.** As a learner (`self:read`), `GET /me/projects` lists the projects I am on: active and
submitted first, then proposed (completed ones too with `include_past=true`), each with my role, progress
(milestones accepted of total) and the next pending or returned milestone.

**SS-2 Milestones due.** `GET /me/milestones` lists pending and returned milestones of my active projects due within
`within_days` (1..180, default 14), overdue ones included, earliest first, with the project title and the days left
(negative when overdue).

**SS-3 Work to review.** As a guide (`guidance:read`), `GET /me/reviews` lists the submitted milestones and submitted
projects of the projects I guide, oldest submission first, with the days they have waited (`limit` 1..100).

**SS-4 My guided projects.** As a guide, `GET /projects` lists only the projects I guide; any other project by id is
404.

## 8. Daily job (JB)

**JB-1 Overdue milestones.** Once a day (`application/jobs.py`, `run_daily`), every pending or returned milestone of
an active project whose due date has passed (Asia/Kolkata) publishes `projects.milestone.overdue` once. A milestone
due today is not overdue; submitted, accepted and cancelled milestones and milestones of projects that are not
active are never flagged.

## 9. Widgets (WG)

Each widget declares one permission (`packages/ui-kit` `DashboardWidget.permission`) and shows loading, empty, data
and error states. The error state says why: 404, 502, 503 or no network → "Projects data is not available yet." with
a retry; 401 → "Sign in again to see this." and 403 → "You do not have access to this.", without a retry; any other
error → "Could not load <what>" with a retry.

| Widget | Permission | Endpoint | For |
|---|---|---|---|
| `projects.my-projects` | `projects:self:read` | `GET /me/projects` | Learners: my projects, progress, next milestone |
| `projects.milestones-due` | `projects:self:read` | `GET /me/milestones?within_days=14` | Learners: due in two weeks and overdue |
| `projects.to-review` | `projects:guidance:read` | `GET /me/reviews?limit=5` | Guides: submissions waiting, oldest first |
| `projects.active` | `projects:guidance:read` | `GET /projects?status=active&limit=5` | Guides (their projects); a coordinator layout that should show it also lists `projects-guide` |

`projects.active` is backed by an endpoint that accepts `project:read` or `guidance:read`; the widget can declare only
one. It declares `guidance:read`, because giving guides `project:read` would show them every project (PRD rule: a
guide sees the projects they guide). A coordinator who also holds `project:read` sees every active project in it.
