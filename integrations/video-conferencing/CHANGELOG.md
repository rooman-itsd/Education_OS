# Changelog — video-conferencing

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Contracts proposed (0.2.0), no code: PRD for Zoom, Microsoft Teams (Graph), Webex and self-hosted Jitsi with sources;
  implements the meetings port (copies of the hub's port files in `contracts/ports/`); webhook verification for each
  provider and a read-only meetings view in `contracts/openapi.yaml`; no events of its own;
  `video-conferencing:meeting:read` for org-admin; `config/env.example`.
