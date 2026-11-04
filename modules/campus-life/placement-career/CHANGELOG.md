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
- Backend (#337): package `eos_placement_career` serving every operation of `contracts/openapi.yaml` with its
  permission and error codes: companies, drives (schedule, reschedule, complete, cancel with their openings), openings
  (publish, close, cancel), applications along the fixed sequence with the offer, rejection, withdrawal, history and
  the placed flag, the student's openings and applications, and the upcoming drives and openings summary reports.
  Every event of `events.yaml` goes to the outbox in the same transaction; every state change writes an audit record.
- Alembic chain `placement_career_0001` (6 `placement_career_*` tables with `organisation_id` and the
  `tenant_isolation` policy on Postgres, version table `placement_career_alembic_version`).
- Tests: every route with its permission and error codes (401 and 403 on every route), the cross-tenant leak test, one
  transaction for the event, the audit record and the change, migrations against the models,
  contract drift (routes, permissions, error codes, enums, response properties) and event payloads against
  `events.yaml`.
- `docs/data-model.md`, `docs/integration-points.md` and `docs/screens.md`; README backend section with the
  assumptions to revisit.
