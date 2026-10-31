# Changelog — training-video-analysis

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Frontend: dashboard widget `training-video-analysis.reviews-pending` (coach): the most recent videos with no
  annotation yet, checking at most 20; API client for `GET /videos` and `GET /videos/{id}/annotations`; vitest tests
  with a stubbed fetch.
- Frontend: `reviews-pending` reads the unannotated videos in one request (`GET /videos?annotated=false`, total as
  the count) instead of one annotations request per video; the 20-video cap and the reviewed count are gone.
