# placement-career: screens

The dashboard widgets and pages come with the frontend PRs; this lists what they will show and the endpoint behind
each.

| Screen | For | Endpoint |
|---|---|---|
| Widget `placement-career.drives` | placement officer | `GET /reports/drives-upcoming` |
| Widget `placement-career.openings-summary` | officer, coordinators, industry liaison | `GET /reports/openings-summary` |
| Widget `placement-career.openings` | learners | `GET /me/openings` |
| Companies (list, record, edit) | officer; viewer read only | `/companies` |
| Drives (list, detail with openings, plan, schedule, complete, cancel) | officer; viewer and students read scheduled and completed ones | `/drives` |
| Openings (list, detail, post, publish, close, cancel) | officer; viewer and students read open and closed ones | `/openings` |
| Applications (by opening or drive, detail with history, status moves) | officer | `/applications` |
| My openings and applications (apply with a declaration, withdraw) | learners | `/me/openings`, `/me/applications` |

Mobile: none planned in v1.0.
