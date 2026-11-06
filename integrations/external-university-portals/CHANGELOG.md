# Changelog: external-university-portals

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]

## [0.3.0]
- Adapter implementation (`src/eos_external_university_portals`), built on the draft 0.2.0 contracts:
  - the Adapter contract (providers `file`, `elmo`, `edc`; `describe`, `capabilities`, `healthcheck`; authorisation and
    inbound operations answered for partners that have none) and the inter-institution-records port (`export_records`,
    `send_records`, `record_manual_delivery`, `import_records`, `list_partners`), found by the hub through the
    `eos.integration_adapters` entry point;
  - writers and readers: CSV (with a per-partner column mapping), EMREX ELMO XML (elmo-schemas v2.1.2), Europass EDC
    JSON-LD (unsealed credential); PDF is registered as the caller's signed file;
  - import returns the normalised transcript, `integrity` (`unsigned`, or `failed` when a signature or proof is present
    because this release cannot verify one) and every line it could not map, by position and reason;
  - delivery: download and partner portal answer `manual_action_required`; email sends a time-limited link (live only);
    manual deliveries are recorded with the partner's reference; the API channel (EWP) is left for later;
  - own schema `external_university_portals` (Alembic chain `eup_0001`, own version table, forced row-level security),
    outbox events in the same transaction as each change (the audit trail), read-only API `/exchanges`;
  - DPDP: no export or delivery to a partner in a configured restricted country.
- Tests: golden files per format, ELMO validated against the vendored official XSD (xmllint), EDC checked against the
  vendored official SHACL shapes and JSON-LD context, round trips, tampered, signed, partially unmappable and hostile
  files, tenancy, API and migration tests. Fixtures and licences under `tests/fixtures`.
- Contracts: `Exchange` gains `organisation_id`; `events.yaml` lists five audit-only events; the transcript's `issuer`
  gains an optional `url` (required by ELMO) and `learner` optional `given_names` and `family_name` (documented in docs/formats.md).

## [0.2.0]
- PRD and draft contracts.
