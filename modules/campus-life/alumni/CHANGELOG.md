# Changelog — alumni

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contract 0.1.0 (#337): alumni directory kept by staff (records verified on creation, archived not deleted, mentor
  flag), mentoring assignments (one active mentor per student) and optional sessions, and `GET /me/mentoring` behind
  the widget `alumni.mentoring`; error codes; seven events with ids only; permissions with the module roles
  `alumni-coordinator` and `alumni-mentee`.
- PRD (`docs/prd.md`) with the owner's decisions A1 to A6 (#337) and `docs/user-stories.md`. v1.0 is the directory
  and mentoring; events, donations and campaigns are v1.1.
- The management-institute layouts hold the module roles: `placement-officer` holds `alumni-coordinator` and
  `management-student` holds `alumni-mentee`, so `alumni.mentoring` is backed for the management student.
