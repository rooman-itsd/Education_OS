# placement-career: user stories

Roles come from `contracts/permissions.yaml`. Each story names the contract operation that serves it.

## Placement officer (`placement-career-officer`)

| # | Story | Contract |
|---|---|---|
| O1 | As the officer I record a company with its industry, website and recruiter contact, find it again, and deactivate it when we stop working with it. | `POST /companies`, `GET /companies`, `GET /companies/{id}`, `PUT /companies/{id}` |
| O2 | As the officer I plan a drive for a company with its date, venue, registration closing date, rounds and eligibility criteria, and announce it to students. | `POST /drives`, `PUT /drives/{id}`, `POST /drives/{id}/schedule` |
| O3 | As the officer I mark a drive as held, or cancel one nobody has applied to yet. | `POST /drives/{id}/complete`, `POST /drives/{id}/cancel` |
| O4 | As the officer I post a job opening, in a drive or on its own, with CTC, positions, criteria and the last day to apply, and publish it. | `POST /openings`, `PUT /openings/{id}`, `POST /openings/{id}/publish` |
| O5 | As the officer I close an opening to new applications, or cancel one with no applications. | `POST /openings/{id}/close`, `POST /openings/{id}/cancel` |
| O6 | As the officer I see the applications to an opening or drive with each student's declaration, and which students are already placed. | `GET /applications`, `GET /applications/{id}` |
| O7 | As the officer I shortlist, move to in process, record an offer and the student's answer, or reject with a reason, one step at a time. | `POST /applications/{id}/status` |
| O8 | As the officer I see the upcoming drives with their application counts on my dashboard. | `GET /reports/drives-upcoming` (widget `drives`) |
| O9 | As the officer or a coordinator I see openings and applications by status, students placed, and the openings closing soonest. | `GET /reports/openings-summary` (widget `openings`) |

## Viewer (`placement-career-viewer`)

| # | Story | Contract |
|---|---|---|
| V1 | As an industry liaison I see the companies, drives and openings, and the summary, without individual applications. | `GET /companies`, `GET /drives`, `GET /openings`, `GET /reports/openings-summary` (widget `openings`) |

## Student (`student`)

| # | Story | Contract |
|---|---|---|
| S1 | As a student I see the openings I can still apply to, with the company, criteria, CTC and last day, and whether I applied. | `GET /me/openings` (widget `openings`) |
| S2 | As a student I see scheduled drives and an opening's details. | `GET /drives`, `GET /drives/{id}`, `GET /openings/{id}` |
| S3 | As a student I apply to an opening, declaring that I meet its criteria. | `POST /me/applications` |
| S4 | As a student I follow my applications and see any offer. | `GET /me/applications` |
| S5 | As a student I withdraw an application before an offer. | `POST /me/applications/{id}/withdraw` |
