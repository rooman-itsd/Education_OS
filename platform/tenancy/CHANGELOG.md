# Changelog — tenancy

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- The registration verification mail goes through `platform/notification` (template
  `tenancy.organisation.verify`) instead of the `eos_core.notify` stub (#316). It is recorded in the
  registration's transaction and sent only after that commits, so a failed registration sends nothing. If
  notification refuses it (503 when no mail transport is configured), the registration is refused with the same
  status and nothing is kept. A delivery failure after the commit does not fail the request.
- `organisation_name(db, organisation_id)`, published on the `eos.organisation_directory` entry point, so a
  platform service that may not import tenancy can render an organisation's display name (#316).
  platform/notification needs it for every organisation-facing template. An entry point rather than a hook
  wired by `apps/backend`, because the event-bus relay and the scheduler run as their own processes and never
  execute the API's lifespan.
- Module scaffolded.
