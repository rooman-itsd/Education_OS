# government-portals

AISHE, NIRF and NAAC submission adapter. Implements the **regulatory-submission** port defined by
`platform/integration-hub` ([`contracts/ports/regulatory-submission.yaml`](contracts/ports/regulatory-submission.yaml)).
None of these portals has an API an institution can use, so the adapter prepares a **submission package** in each
portal's own format (keying sheet, upload templates, the NIRF website copy, NAAC evidence arranged by metric, a zip and
a checklist), a person files it on the portal with the institution's own login, and records the filing and its
acknowledgement.

**Status:** contracts proposed (0.2.0); not built. See [docs/prd.md](docs/prd.md).

- `contracts/ports/` — the port and the Adapter contract, copied from integration-hub
- `contracts/openapi.yaml` — read-only forms catalogue and packages view
- `src/` — adapter implementation: one form writer per authority and cycle
- `config/env.example` — format cycles and package limits; no credentials
- `tests/` — golden-file tests per form and cycle
