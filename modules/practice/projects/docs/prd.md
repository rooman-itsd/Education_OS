# projects: product requirements

Owner: Tejaswini (@tejaswini-rooman) · Status: draft for review · Issue #67
Practice suite · tier `common` (every academy type enables it) · generic pattern "Projects"

## Purpose

One module for every kind of guided learner project: capstones, research projects and trials, film
projects, live business projects, artwork and collection projects, case research, scripts, lesson plans.
The module knows only the generic pattern: a **project** with a **team** of learners and one or more
**guides**, broken into **milestones** that the team **submits** and a guide **reviews**, ending in a
**final submission** and **evaluation**. The contract is `contracts/openapi.yaml`, `events.yaml` and
`permissions.yaml`.

## Vocabulary, not field words

The contract uses only the generic words above. What users see comes from the academy profile
(`platform/identity/config/profiles/<profile>.yaml`, key `projects.<term>`):

| Term key | Generic word | Examples from the profiles |
|---|---|---|
| `projects.project` | Project | Capstone / project, Research project, Research trial, Film project, Live project, Artwork project, Collection / industry project, Case research, Script, Lesson plan |
| `projects.milestone` | Milestone | Thesis milestone |
| `projects.guide` | Guide | Project guide, research supervisor, mentor, director (not yet in any profile) |

Free-text labels inside the data (a project's `kind`, the evaluation `outcome` scale) are set by each
organisation, never by the module. No academy type is named in code or contract.

## Users and what they need

Role ids are those of the dashboard layouts. Any academy's roles map onto the four generic actors.

| Generic actor | Example roles | Needs | Dashboard widget |
|---|---|---|---|
| Team member | engineering-student, research-scholar, filmmaker, artist, designer, medical-student, field-trainee, law-student, management-student | Propose a project, see own projects and progress, submit milestones and the final work, see feedback | `projects.my-projects` (`GET /me/projects`), `projects.milestones-due` (`GET /me/milestones`) |
| Guide | project-guide, research-supervisor, studio-instructor, design-mentor, corporate-mentor, legal-mentor, mentor-teacher, director, production-supervisor | Set milestones, review submissions, evaluate the final work, watch the projects they guide | `projects.to-review` (`GET /me/reviews`), `projects.active` (`GET /projects?status=active`) |
| Coordinator | research-office, research-lead, industry-liaison, farm-supervisor, department-admin | Approve proposals, form teams, assign guides, watch all active projects | `projects.active` |
| Viewer | management, org-admin | Overview, read only | — |

## Main flows

1. **Propose.** A learner proposes a project (title, summary, kind, period, optional external partner) and
   becomes its lead; they may add team members while it is proposed. Or a coordinator creates a project
   directly with its team and guides, which starts it as active.
2. **Approve.** A coordinator approves a proposal (proposed → active), assigning one or more guides, or
   rejects it with a reason.
3. **Milestones.** A guide or coordinator sets milestones: title, description, due date, optional weight.
   A milestone can be moved or cancelled until it is accepted.
4. **Submit.** Any team member submits a milestone: a note and document references (files go through
   platform/documents). A returned milestone can be resubmitted. A daily job publishes
   `projects.milestone.overdue` once per milestone due and not submitted.
5. **Review.** A guide accepts or returns a submission, with comments and an optional score. A guide never
   reviews a project they are a member of.
6. **Final submission and evaluation.** The team submits the project (active → submitted). A guide records
   the evaluation: outcome on the organisation's scale, optional score, comments (submitted → completed), or
   returns it for more work (submitted → active).
7. **Change and cancel.** A coordinator changes the team or guides of an active project, or cancels it with a reason.

## Rules

- Every table carries `organisation_id` with row-level security; every event carries `organisation_id`.
- Every state change writes an audit record through `packages/sdk`.
- A team member sees only their own projects (`/me/*`). A guide sees the projects they guide unless they also
  hold coordinator permissions.
- A project has exactly one lead while proposed or active; removing the lead needs a new lead.
- A person is never both team member and guide on the same project.
- Nothing is deleted: projects are rejected, cancelled or completed; milestones cancelled; submissions kept with every version.
- No real learner data in tests or seeds.
- No dependency on another module being enabled. portfolio, skill-progress or productions may react to
  projects events if they are enabled.

## Data model (summary)

| Entity | Key fields |
|---|---|
| Project | id, title, summary, kind, academic_year, starts_on, ends_on, external_partner, status (proposed, active, submitted, completed, rejected, cancelled), outcome, score |
| Member | project_id, person_id, role (lead, member), joined_at, left_at |
| Guide | project_id, person_id, assigned_at |
| Milestone | id, project_id, title, description, due_on, weight, status (pending, submitted, accepted, returned, cancelled) |
| Submission | id, milestone_id (null for the final submission), project_id, note, document_ids, submitted_by, submitted_at, version |
| Review | id, submission_id, reviewer_id, decision (accepted, returned), comments, score, reviewed_at |

## Integration points

| Direction | With | How |
|---|---|---|
| Publishes | portfolio, skill-progress and anyone | `projects.project.*`, `milestone.*` and the rest of `events.yaml` |
| Platform | identity, audit, notification, scheduler, documents | through `packages/sdk` (vocabulary, notifications, the daily overdue job, submission files) |
| References | student-information, hr-payroll | `person_id`s for members and guides; names cached from their events |

## Out of scope

- Grants and budgets for projects (budget-grants); purchases (procurement).
- Rubric-based skill and competency assessment (skill-progress); course grades (examinations).
- Showcasing finished work (portfolio) and staging it (productions).
- Plagiarism checks, ethics approvals and thesis viva workflows (later integrations or a specialized module).

## Open questions (for review)

1. Add `projects.guide` to the profiles' vocabulary? Profiles are owned by Faizan; this PR does not change them,
   and the UI falls back to the generic word.
2. Can a guide approve a proposal, or only a coordinator? Proposed: only `projects:project:manage`, which an
   academy may also grant to senior guides.
3. Should `projects.milestones-due` show the next 14 days by default? Proposed: yes, adjustable by query.
