# government-portals: integration points

| Direction | With | How |
|---|---|---|
| In | integration-hub | Finds the adapter by entry point `eos.integration_adapters` / `government-portals`; calls `describe` once, then the Adapter and regulatory-submission operations with a `Context` (organisation, connection, provider `aishe`/`nirf`/`naac`, mode, settings) |
| In | regulatory-reports, iqac-accreditation | Through the port via the hub: `prepare_package`, `record_manual_submission`, `get_package` |
| Out | platform/documents | Generated files are stored with `put`; evidence and acknowledgements are read with `get`, always for the calling organisation. The hub injects the client (`DocumentStore` protocol in `infrastructure/documents.py`) |
| Out | platform/event-bus | Outbox events `government-portals.package.prepared` and `.filed`, same transaction as the change |
| Out | AISHE, NIRF, NAAC | None. A person files with the institution's own login |
| In | operators | Read-only HTTP: `GET /forms`, `/packages`, `/packages/{id}` with `government-portals:package:read` |

Errors follow `contracts/ports/adapter.yaml`: `unsupported` for an unknown form or a cycle without a format,
`invalid_request` for malformed arguments, `conflict` for recording twice or re-preparing a filed package,
`manual_action_required` for `submit`, `not_found` for another organisation's package.

An invalid *data set* is not an error: `prepare_package` returns `status: invalid` with the issues and keeps the
package row, so the caller can show what to fix (the port's output lists `invalid` as a status).
