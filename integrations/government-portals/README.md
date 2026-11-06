# government-portals

AISHE, NIRF and NAAC submission adapter. Implements the **regulatory-submission** port defined by
`platform/integration-hub` ([`contracts/ports/regulatory-submission.yaml`](contracts/ports/regulatory-submission.yaml)).
None of these portals has an API an institution can use, so the adapter prepares a **submission package** in each
portal's own format (keying sheet, upload templates, the NIRF website copy, NAAC evidence arranged by metric, a zip and
a checklist), a person files it on the portal with the institution's own login, and records the filing and its
acknowledgement. **Portal credentials are never stored and no portal's web page is ever automated.**

**Status:** built on the draft 0.2.0 contracts (0.3.0), pending the contract review. See [docs/prd.md](docs/prd.md).

## What it prepares

| Forms | Package |
|---|---|
| `aishe.dcf-i`, `.dcf-ii`, `.dcf-iii` | Keying sheet (CSV) in Web DCF section order, with enrolment totals cross-checked; DCF-II adds the teacher list |
| `nirf.dcs.<category>` (17 categories) | Keying sheet by parameter group, and the website copy as a PDF (aggregates only) |
| `naac.iiqa` | Keying sheet |
| `naac.ssr`, `naac.aqar` | Keying sheet, data template, evidence arranged `evidence/<metric>/NN-title.ext` |
| `naac.dvv-response` | Keying sheet, responses template, evidence per query |

Every package also gets a deterministic zip bundle and a six-step checklist. **Formats:** spreadsheets are UTF-8 CSV
with a byte order mark (paste into the portal's Excel template), and the PDF is plain text written by
`application/pdf.py`, because no spreadsheet or PDF library is on the approved stack (`docs/architecture/approved-stack.yaml`).
If a portal insists on `.xlsx` or a styled PDF, propose the library on the stack list first.

## Layout

- `contracts/ports/` the port and the Adapter contract, copied from integration-hub
- `contracts/openapi.yaml` read-only forms catalogue and packages view; `permissions.yaml`; `events.yaml` (audit only)
- `src/eos_government_portals/` `domain` (models, Adapter result types), `application` (catalogue, rules, writers,
  service, adapter), `infrastructure` (config, documents client), `api` (read-only router)
- `db/` Alembic chain with its own version table `government_portals_alembic_version`
- `config/env.example` format cycles and package limits; no credentials
- `tests/` golden files in `tests/golden/<case>/{input.json,expected/}`, a failing fixture per rule, contract,
  filing, tenancy, API, migration and writer tests

## Setup

```
pip install -e integrations/government-portals      # registers the eos.integration_adapters entry point
cd integrations/government-portals/db && alembic upgrade head
```

The hub finds the adapter by the `government-portals` entry point and creates one connection per authority
(`aishe`, `nirf`, `naac`). The connection's non-secret settings are in `describe()`: `institution_type`,
`aishe_code`, `nirf_institute_id`, `nirf_categories`, `naac_hei_id`. There are no secrets.

## Config keys

See `config/env.example`: `GOVERNMENT_PORTALS_{AISHE,NIRF,NAAC}_FORMAT` (the cycle; an unknown cycle is refused,
never replaced by last year's), `GOVERNMENT_PORTALS_MAX_EVIDENCE_FILE_BYTES`, `GOVERNMENT_PORTALS_MAX_PACKAGE_BYTES`.

## Sandbox access and what is mocked

There is nothing to sign up for and nothing to mock on the provider side: no portal is called, so `mock`, `sandbox`
and `live` behave the same. What *is* provisional is the **field lists**: the current cycle's DCF, DCS and NAAC
templates are visible only after an institution signs in (PRD open question 1). The fields here are the adapter's
reading of the published frameworks; the first institution's filing in each cycle is the acceptance test, and a field
the portal wants or refuses becomes a catalogue change with a new golden file.

platform/documents is reached through the client the hub injects (`GovernmentPortalsAdapter(documents=...)`); until the
hub does, only `mock` mode runs, on an in-memory store, and `sandbox` and `live` answer `not_configured`.

## Tests

```
PYTHONPATH=integrations/government-portals/src:integrations/government-portals/tests:packages/core/src:packages/testing/src \
  python -m pytest integrations/government-portals/tests
UPDATE_GOLDEN=1 python -m pytest integrations/government-portals/tests/test_golden.py   # after a deliberate format change; review the diff
```

See also [docs/data-model.md](docs/data-model.md) and [docs/integration-points.md](docs/integration-points.md).
