# nad

National Academic Depository (NAD, on DigiLocker) and Academic Bank of Credits (ABC) adapter. Implements the
**academic-records** port defined by `platform/integration-hub`
([`contracts/ports/academic-records.yaml`](contracts/ports/academic-records.yaml)): lodge awards (degree, diploma,
marksheet, grade card) and corrections with NAD, lodge earned credits with ABC, keyed by the learner's APAAR / ABC id,
and verify an APAAR id where an API is offered. Without an API it prepares the depository's own CSV upload file and a
person uploads it; the port says so (`manual_action_required`).

**Status:** contracts proposed (0.2.0); not built. See [docs/prd.md](docs/prd.md).

- `contracts/ports/` — the port and the Adapter contract, copied from integration-hub
- `contracts/openapi.yaml` — read-only operator view of submissions
- `src/` — adapter implementation
- `config/env.example` — endpoints and file format versions (per-institution ids live on the hub connection)
- `tests/` — contract tests against recorded fixtures and sample upload files
