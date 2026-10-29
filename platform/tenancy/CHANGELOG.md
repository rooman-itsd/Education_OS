# Changelog — tenancy

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- `organisation_name(db, organisation_id)`, published on the `eos.organisation_directory` entry point, so a
  platform service that may not import tenancy can render an organisation's display name (#316).
  platform/notification needs it for every organisation-facing template. An entry point rather than a hook
  wired by `apps/backend`, because the event-bus relay and the scheduler run as their own processes and never
  execute the API's lifespan.
- Module scaffolded.
