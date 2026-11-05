# Changelog — digilocker

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Contracts proposed (0.2.0), no code: PRD with DigiLocker's issuer and requester APIs and sources; implements the
  certificate-issuance port (copies of the hub's port files in `contracts/ports/`); Pull URI and Pull Doc channels and
  a read-only issuance view in `contracts/openapi.yaml`; no events of its own (the hub publishes port events);
  `digilocker:issuance:read` for org-admin; `config/env.example` with endpoints and the requester app.
