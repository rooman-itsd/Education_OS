# Changelog: government-portals

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]

## [0.3.0]
- Adapter implementation (`src/eos_government_portals`), built on the draft 0.2.0 contracts:
  - the Adapter contract (`describe`, `capabilities`, `healthcheck`, authorisation and inbound operations answered
    for a portal that has none) and the regulatory-submission port (`list_forms`, `validate`, `prepare_package`,
    `submit`, `record_manual_submission`, `get_package`), found by the hub through the `eos.integration_adapters`
    entry point;
  - submission-package generators: AISHE DCF-I, DCF-II and DCF-III keying sheets; NIRF DCS keying sheet and website
    copy PDF for each of the 17 categories; NAAC IIQA, SSR, AQAR and DVV response sheets, upload templates and
    evidence arranged by metric; a deterministic zip bundle and a checklist of portal steps for each;
  - validation against each form's schema and the authority's rules (cross-totals, year ranges, evidence), with
    issues that name a field and never a value;
  - recording a manual filing with its portal reference and acknowledgement; superseding on re-prepare; a filed
    package is read-only;
  - own schema `government_portals` (Alembic chain `gp_0001`, own version table, forced row-level security);
  - read-only API: `/forms`, `/packages`, `/packages/{id}`.
- Golden-file tests per form and cycle, a failing fixture per rule, tenancy and migration tests.
- Contracts: `Package` gains `organisation_id` (cross-tenant leak test); `events.yaml` lists the two audit events
  `government-portals.package.prepared` and `.filed`.
- Spreadsheets are CSV and the NIRF website copy is a text-only PDF written by this module: no spreadsheet or PDF
  library is on the approved stack.

## [0.2.0]
- PRD and draft contracts.
