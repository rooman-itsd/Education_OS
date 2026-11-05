# Changelog — wearables

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Contracts proposed (0.2.0), no code: PRD for Garmin, Polar, Fitbit (Google Health API) and Strava with sources;
  implements the wearable-data port (copies of the hub's port files in `contracts/ports/`); provider callbacks and the
  coach's device alerts (`GET /alerts`, backing the `wearables.alerts` widget on the coach layout) in
  `contracts/openapi.yaml`; consumes `integration-hub.account-link.revoked` to delete collected data;
  `wearables:alert:read` for coach and org-admin; `config/env.example`.
