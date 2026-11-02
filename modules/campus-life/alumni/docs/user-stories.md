# alumni: user stories

Roles come from `contracts/permissions.yaml`. Each story names the contract operation that serves it.

## Alumni coordinator (placement officer)

| # | Story | Contract |
|---|---|---|
| C1 | As the coordinator I add an alumnus with graduation year, programme, current company, designation and contact details. The record is verified by me. | `POST /directory` |
| C2 | As the coordinator I find alumni by name, company, graduation year, programme or mentor flag. | `GET /directory`, `GET /directory/{id}` |
| C3 | As the coordinator I correct a record and mark an alumnus as a mentor, or clear the flag when they mentor nobody. | `PUT /directory/{id}` |
| C4 | As the coordinator I archive a record with a reason and restore it later; a mentor with an active assignment is not archived. | `POST /directory/{id}/archive`, `POST /directory/{id}/restore` |
| C5 | As the coordinator I assign a mentor to a student who has no active mentor, with a start date and a focus. | `POST /mentoring/assignments` |
| C6 | As the coordinator I see every assignment, by status, mentor or student, and end one. | `GET /mentoring/assignments`, `GET /mentoring/assignments/{id}`, `POST /mentoring/assignments/{id}/end` |
| C7 | As the coordinator I schedule, reschedule, complete or cancel sessions of an active assignment. | `GET`/`POST /mentoring/assignments/{id}/sessions`, `PUT /mentoring/sessions/{id}`, `POST /mentoring/sessions/{id}/complete`, `POST /mentoring/sessions/{id}/cancel` |

## Mentee (management student)

| # | Story | Contract |
|---|---|---|
| S1 | As a student I see my mentor's name, company, designation and contact details, and my next sessions, on my dashboard. With no mentor I see an empty state. | `GET /me/mentoring` (widget `alumni.mentoring`) |
| S2 | As a student I cannot see the directory or any other student's mentor. | (no operation granted) |
