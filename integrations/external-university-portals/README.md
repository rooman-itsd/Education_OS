# external-university-portals

Exchange of academic records with partner institutions. Implements the **inter-institution-records** port defined by
`platform/integration-hub` ([`contracts/ports/inter-institution-records.yaml`](contracts/ports/inter-institution-records.yaml)):
export a learner's transcript of records in the partner's format (PDF, CSV, EMREX ELMO XML, Europass Digital
Credentials JSON-LD) and deliver it (download, email link, partner portal), and read a partner's file back into one
normalised shape, with everything it could not map, for a person to review. Indian credit transfer goes through the
Academic Bank of Credits (`integrations/nad`), not here. Erasmus Without Paper (EWP) is left for later.

**Status:** built on the draft 0.2.0 contracts (0.3.0), pending the contract review. See [docs/prd.md](docs/prd.md).

## What it does

| Provider | Formats | Notes |
|---|---|---|
| `file` | `pdf`, `csv` | PDF: the caller's already-signed PDF is registered (not copied or redesigned). CSV: one row per entry; the partner's own headers through `csv_mapping`. Import: CSV only (a PDF is kept and keyed in by a person) |
| `elmo` | `elmo_xml` | ELMO v2 (`https://github.com/emrex-eu/elmo-schemas`, v2.1.2). Export and import |
| `edc` | `edc_jsonld` | Europass EDC (ELM v3 application profile, VC 1.1). Export of the **unsealed** credential, passed entries only; import |

Delivery by the partner's `channel`: `download` and `partner_portal` answer `manual_action_required` (with the document
id) and a person records it with `record_manual_delivery`; `email` sends a time-limited download link through
platform/notification (**live mode only**; mock and sandbox deliver nothing); `api` is `unsupported` until EWP.
Import never accepts anything: it returns the normalised transcript, `integrity` and every unmapped line.
Details of each format, what it loses and what it cannot do yet: [docs/formats.md](docs/formats.md).

## Not done in this release, and why

- **Signing** (XML signature for ELMO, a Verifiable Credential proof for EDC): no signature library is on the approved
  stack and the PRD's open question 2 is undecided. Exports are unsigned; a connection that supplies a signing key is
  refused (`unsupported`) rather than silently getting an unsigned file. Imported files that carry a signature or proof
  get `integrity: failed` (they cannot be verified here), never `verified`.
- **Schema validation at runtime**: no XML schema library is on the stack. The writers are covered by golden files and
  validated against the official XSD and SHACL shapes in the tests; at runtime the transcript is validated before any
  writer runs.

## Layout

- `contracts/ports/` the port and the Adapter contract, copied from integration-hub; `openapi.yaml` (read-only
  exchanges view), `permissions.yaml`, `events.yaml` (audit only)
- `src/eos_external_university_portals/` `domain` (models, Adapter result types), `application` (transcript schema,
  formats, service, adapter), `infrastructure` (config, documents and notification clients), `api` (read-only router)
- `db/` Alembic chain with its own version table `external_university_portals_alembic_version`
- `config/env.example` link lifetime, import size limit, restricted countries
- `tests/` golden files (`tests/golden`), vendored schemas and their licences (`tests/fixtures/*/SOURCE.md`), and tests

## Setup

```
pip install -e integrations/external-university-portals     # registers the eos.integration_adapters entry point
cd integrations/external-university-portals/db && alembic upgrade head
```

Each partner is one integration-hub connection on provider `file`, `elmo` or `edc`. Non-secret settings (see
`describe()`): `partner_id`, `country`, `channel` (required), `name`, `institution_code`, `formats_out`, `formats_in`,
`email`, `portal_url`, `csv_mapping`, `grade_conversion`, `credit_conversion`. No secrets are read in this release.
Config keys: see `config/env.example`.

## Sandbox access and what is mocked

Nothing to apply for: no partner API is called. `mock` and `sandbox` write and read files but deliver nothing; `live`
emails the link. platform/documents and platform/notification are reached through clients the hub injects
(`ExternalUniversityPortalsAdapter(documents=..., courier=...)`; the `DocumentStore` and `Courier` protocols are in
`infrastructure/documents.py`); until it does, only `mock` runs, on in-memory stand-ins, and `sandbox` and `live`
answer `not_configured`. Joining EMREX as a data provider, EWP and sealing need the registrations in the PRD's
"External dependencies" table; none is needed for file, ELMO and EDC exchange.

## Tests

```
PYTHONPATH=integrations/external-university-portals/src:integrations/external-university-portals/tests:packages/core/src:packages/testing/src \
  python -m pytest integrations/external-university-portals/tests
UPDATE_GOLDEN=1 python -m pytest integrations/external-university-portals/tests/test_golden.py   # after a deliberate format change; review the diff
```

The ELMO XSD test needs `xmllint` (libxml2) and is skipped without it. See also [docs/data-model.md](docs/data-model.md)
and [docs/integration-points.md](docs/integration-points.md).
