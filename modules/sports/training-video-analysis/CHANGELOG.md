# Changelog — training-video-analysis

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Frontend: dashboard widget `training-video-analysis.reviews-pending` (coach): the most recent videos with no
  annotation yet, checking at most 20; API client for `GET /videos` and `GET /videos/{id}/annotations`; vitest tests
  with a stubbed fetch.
