# external-university-portals

Exchange of academic records with partner institutions. Implements the **inter-institution-records** port defined by
`platform/integration-hub` ([`contracts/ports/inter-institution-records.yaml`](contracts/ports/inter-institution-records.yaml)):
export a learner's transcript of records in the partner's format (PDF, CSV, EMREX ELMO XML, Europass Digital
Credentials JSON-LD) and deliver it (download, email link, partner portal), and read a partner's file back into one
normalised shape for a person to review. Indian credit transfer goes through the Academic Bank of Credits
(`integrations/nad`), not here.

**Status:** contracts proposed (0.2.0); not built. See [docs/prd.md](docs/prd.md).

- `contracts/ports/` — the port and the Adapter contract, copied from integration-hub
- `contracts/openapi.yaml` — read-only exchanges view
- `src/` — format writers and readers (CSV, ELMO XML, EDC JSON-LD)
- `config/env.example` — format versions and limits (partners are integration-hub connections)
- `tests/` — golden files per format, validated against the published schemas
