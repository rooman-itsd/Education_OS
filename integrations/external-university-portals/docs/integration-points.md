# external-university-portals: integration points

| Direction | With | How |
|---|---|---|
| In | integration-hub | Finds the adapter by entry point `eos.integration_adapters` / `external-university-portals`; calls `describe` once, then the Adapter and inter-institution-records operations with a `Context` (organisation, connection = one partner, provider `file`/`elmo`/`edc`, mode, settings) |
| In | examinations, enrolment-registration, admissions, student-information | Through the port via the hub: `export_records`, `send_records`, `record_manual_delivery`, `import_records`, `list_partners` |
| Out | platform/documents | Generated files are stored with `put`; a signed PDF and imported files are read with `get`, always for the calling organisation. The hub injects the client (`DocumentStore` protocol) |
| Out | platform/notification | An email with a time-limited download link (`Courier` protocol, `send_email_with_link`), live mode only. The hub injects the client |
| Out | platform/event-bus | Outbox events `external-university-portals.exchange.*`, same transaction as the change |
| Out | Partners | None in v1.0: a file, an email link, or a person uploading |
| In | operators | Read-only HTTP: `GET /exchanges`, `/exchanges/{id}` with `external-university-portals:exchange:read`; never transcript content |

Errors follow `contracts/ports/adapter.yaml`: `invalid_request` for a transcript or file that fails validation (with the
failing field paths or the reason, never values), `unsupported` for a format the provider or partner does not take, a PDF
import, signed exports and the API channel, `rejected` for a restricted country, `conflict` for a key reused for another
partner or format and for recording a delivery twice, `manual_action_required` for download and partner portal,
`transport_unavailable` (retryable) when notification cannot send.
