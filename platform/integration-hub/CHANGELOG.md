# Changelog — integration-hub

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Contracts proposed (0.2.0), no code: PRD; six ports in `contracts/ports/` (certificate-issuance, academic-records,
  regulatory-submission, meetings, wearable-data, inter-institution-records) and the Adapter contract every adapter
  implements, with one error vocabulary; the hub API (connections, write-only credentials kept in a secret store,
  mock/sandbox/live modes and going live, OAuth for organisations and people, provider callbacks with verification,
  health, delivery log and retries, super-admin overview); 25 events (connections, account links, deliveries, and
  port events normalised across providers); 10 permission keys for `org-admin`, `member` and `super-admin`.
  `module.yaml`: status in-progress, owner, dependencies on event-bus, scheduler, documents and notification.
- Module scaffolded.
