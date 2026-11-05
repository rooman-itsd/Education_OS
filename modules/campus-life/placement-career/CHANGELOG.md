# Changelog — placement-career

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contract 0.1.0 (#337): company records, drives, job openings, applications with the fixed status sequence and
  offers, the student's own openings and applications, and the reports behind the `drives` and `openings` widgets;
  every error code by status. Events for drives, openings and applications (no consumers in v1.0).
- Permissions: roles `placement-career-officer` and `placement-career-viewer`, and `student` grants to read openings
  and apply. The placement-officer, industry-coordinator and practicum-coordinator layouts list
  `placement-career-officer`; industry-liaison lists `placement-career-viewer`.
- `docs/prd.md` with the owner decisions P1 to P7 (#337) and `docs/user-stories.md`.
- Review of #424: two widget ids (P8): `placement-career.openings` for learners (`GET /me/openings`, `self:read`)
  and `placement-career.openings-summary` for staff (`GET /reports/openings-summary`, `report:read`); the four staff
  layouts use the new id. Event rule (P9): ids, dates and the cancel reason only. New event
  `placement-career.drive.rescheduled`. `PUT /drives/{id}` and `PUT /openings/{id}` check dates against today only
  when they change. `GET /me/openings` and `GET /me/applications` are cursor pages. events.yaml has an `envelope`,
  `consumers` per event and `"date?"`/`"uuid?"` for nullable fields. PRD open questions 7 to 9.
- Frontend (#337): dashboard widgets `placement-career.openings` ("Job openings", learners, `GET /me/openings`),
  `placement-career.openings-summary` ("Placement openings", placement staff and industry-liaison,
  `GET /reports/openings-summary`) and `placement-career.drives` ("Upcoming drives", placement-officer,
  `GET /reports/drives-upcoming`), with a typed client, loading, empty and error states with retry, Indian dates
  and rupees, and vitest tests. The module is not enabled in the apps yet.
