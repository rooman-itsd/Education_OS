# enrolment-registration — screen inventory

## Staff screens (planned; this release ships the API and the widget)

| Screen | Purpose | Permission |
|---|---|---|
| Enrolments | Search enrolments by name, roll number, programme, status | `enrolment-registration:enrolment:read` |
| Enrol student | Enrol a person in a programme; shows the assigned roll number | `enrolment-registration:enrolment:manage` |
| Registration windows | Open and close each term's window | `enrolment-registration:registration:manage` |
| Registrations | Filter by term, offering, section, type, status | `enrolment-registration:registration:read` |
| Register (single or batch) | Pick offering and section, add students, see a result per student | `enrolment-registration:registration:manage` |
| Registration detail | Withdraw, or move to another section from a date | `enrolment-registration:registration:manage` |

The super admin console's sample screen (`apps/frontend/src/admin/data/moduleDashboards.ts`) also shows electives,
registration holds and monthly charts; electives and holds are out of scope for this release (PRD §3).

## Dashboard widgets

| Widget id | Dashboard | Kind | Permission | Data |
|---|---|---|---|---|
| `enrolment-registration.registered-candidates` | Examination Staff | list | `enrolment-registration:registration:read` | `GET /reports/registered-candidates` |

It shows the total registered in the active (or chosen) term, the supplementary and backlog counts, and the course
offerings with the most registrations: course code and title from the local copy of academic-management, or the
offering id while that copy is empty.
