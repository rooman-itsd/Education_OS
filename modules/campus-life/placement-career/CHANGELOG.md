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
