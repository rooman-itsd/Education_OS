# digilocker

DigiLocker adapter. Implements the **certificate-issuance** port defined by `platform/integration-hub`
([`contracts/ports/certificate-issuance.yaml`](contracts/ports/certificate-issuance.yaml)): issue academic documents
to students' DigiLocker (Pull by default, Push where the account is known), replace and withdraw them, answer
DigiLocker's Pull URI and Pull Doc requests, and fetch a person's documents with their consent (requester OAuth, PKCE).

**Status:** contracts proposed (0.2.0); not built. See [docs/prd.md](docs/prd.md).

- `contracts/ports/` — the port and the Adapter contract, copied from integration-hub
- `contracts/openapi.yaml` — the Pull Issuer channels DigiLocker calls (served under integration-hub) and a read-only operator view
- `src/` — adapter implementation
- `config/env.example` — endpoints and Rooman's requester app (per-institution credentials live in the hub's secret store)
- `tests/` — contract tests against recorded fixtures, and against the DigiLocker sandbox when configured
