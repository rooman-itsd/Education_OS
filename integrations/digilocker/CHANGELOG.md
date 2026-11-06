# Changelog — digilocker

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- 0.3.0, built on the draft contracts: the adapter (`eos.integration_adapters` entry point) with issue, replace, withdraw,
  get_issuance (Pull by default, Push where the account is known, never Aadhaar), the Pull URI and Pull Doc channels
  (keyhash, timestamp tolerance, name and date of birth with hashed search keys), requester OAuth with PKCE S256,
  `list_holder_documents` and `fetch_holder_document` with the file HMAC verified; mock mode (simulator on
  `httpx.MockTransport`) and recorded fixtures; own schema `digilocker_*` with RLS and its own Alembic chain; the
  read-only `GET /issuances` view; docs and `DIGILOCKER_SEARCH_KEY_PEPPER` in `config/env.example`.
- Contracts proposed (0.2.0), no code: PRD with DigiLocker's issuer and requester APIs and sources; implements the
  certificate-issuance port (copies of the hub's port files in `contracts/ports/`); Pull URI and Pull Doc channels and
  a read-only issuance view in `contracts/openapi.yaml`; no events of its own (the hub publishes port events);
  `digilocker:issuance:read` for org-admin; `config/env.example` with endpoints and the requester app.
