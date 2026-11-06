# nad: integration points

## Used

| What | How | Notes |
|---|---|---|
| platform/integration-hub | Finds this adapter by the `eos.integration_adapters` entry point (`nad = eos_nad.application.adapter:get_adapter`) and passes a context (mode, settings, secrets) with every call | The hub is built in parallel; this adapter is tested standalone against `contracts/ports/adapter.yaml` |
| platform/documents | Stores the prepared upload files; checks an acknowledgement document exists | Through the `DocumentStore` protocol (`infrastructure/documents.py`); the hub or host injects the real client with `get_adapter().configure(documents=...)`. `packages/sdk` has no documents client yet |
| NAD and ABC | Nothing is called in v1.0: no public API specification. A person uploads the file on the portal | The API channel is added by configuration once the specs and credentials arrive |

## Exposed

- The academic-records port and the Adapter contract (`contracts/ports/`).
- `GET /api/v1/nad/submissions` and `GET /api/v1/nad/submissions/{id}`, the read-only operator view (`nad:submission:read`).

## Not done here

- Events: none (`contracts/events.yaml`). The hub publishes `integration-hub.academic-record.submission-changed` from
  the results of `publish_awards`, `correct_awards`, `publish_credits` and `record_manual_upload`.
- Audit: the hub audits connection and delivery changes; the submission rows are this adapter's own record.
