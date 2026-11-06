# nad

National Academic Depository (NAD, on DigiLocker) and Academic Bank of Credits (ABC) adapter. Implements the
**academic-records** port defined by `platform/integration-hub`
([`contracts/ports/academic-records.yaml`](contracts/ports/academic-records.yaml)): lodge awards (degree, diploma,
marksheet, grade card) and corrections with NAD, lodge earned credits with ABC, keyed by the learner's APAAR / ABC id,
and verify an APAAR id where an API is offered.

**Status:** built (0.3.0) against the draft contracts. v1.0 ships the **manual channel**: neither depository's API
specification is public, so the adapter validates the batch and writes the depository's own CSV upload file, and a
person uploads it (`manual_action_required`). `verify_learner_id` answers `unverifiable`. See [docs/prd.md](docs/prd.md).

## How the hub uses it

```python
# eos_nad.application.adapter:get_adapter, found by entry point
adapter = entry_point("eos.integration_adapters", "nad")()
adapter.describe()  # identity, ports, providers
result = adapter.invoke("publish_awards", context, input)
# {"output": ..., "provider_reference": ...} or {"error": {"code": ..., "retryable": ...}}
```

`invoke` never raises. Operations: `publish_awards`, `correct_awards`, `publish_credits`, `record_manual_upload`,
`get_submission`, `verify_learner_id`, `capabilities`, `healthcheck`, `verify_inbound` (always rejects: nothing calls
us), `parse_inbound`. The OAuth operations and `handle_provider_request` are `unsupported`.

## The manual channel

1. `publish_awards` or `publish_credits` validates every record. Any invalid record refuses the whole batch with
   `row_errors` (`row`, `field`, `code`; status `rejected`; nothing is written or lodged). Codes: `missing`, `invalid`,
   `out_of_range`, `duplicate`, `already_lodged`, `mismatch`, `too_many_courses`, `apaar_missing`, `apaar_invalid`.
2. A valid batch is written as CSV (UTF-8, CRLF, template version 1; format in `eos_nad/domain/rules.py`), split at
   `NAD_MAX_ROWS_PER_FILE`, stored in platform/documents, and returned as `upload_files` with the `steps` to sign in to
   the portal, upload, choose the template and publish.
3. A person uploads the file, then `record_manual_upload` records the date, who, the portal's reference and optionally
   the acknowledgement document; the submission becomes `uploaded_manually`.
4. `correct_awards` takes records that name the `award_number` they correct, for the same learner, and writes the same
   file with `M` in MARKS REC STATUS (new records carry `N`). A correction for an award that was not lodged is
   `not_found`.

The same `batch_key` with the same batch answers from the record; with another batch it is a conflict.

## Modes

`mock` (default in dev and CI, refused unless `EOS_DEV_MODE=true`), `sandbox` and `live` all use the manual channel,
because there is nothing to call: NAD and ABC have no public sandbox and no public API. `sandbox` and `live` need the
institution's ids on the connection (below) and `NAD_APAAR_HASH_PEPPER`; mock fills development defaults.

## Configuration

Deployment keys are in [config/env.example](config/env.example). Per-institution connection settings, entered on the hub:

| Kind | Name | Notes |
|---|---|---|
| setting | `nad_institution_id` | From the NAD account (written to every award row) |
| setting | `abc_institution_id` | From the ABC registration (written to every credit row) |
| setting | `institution_name` | Optional; the name NAD's template shows, defaults to the NAD institution id |
| setting | `award_templates` | `[{award_kind, template_code, programme_level}]`: the certificate template per award kind |

No secret is needed until the API channel exists.

## What is mocked, and until which approval

Nothing is mocked: the manual channel is the real v1.0 behaviour. What does not exist yet: the API channel (awards, credits,
status polling) and APAAR verification, until NAD, ABC and API Setu share their specifications and grant access (see
the PRD's external dependencies). The CSV columns are **template version 1**, built from the column examples in NAD
guidance (PRD, "The award CSV"); the depositories' own templates sit behind each institution's login, so the first
institution to register compares them and, if they differ, the columns change under a new template version
(`NAD_AWARDS_CSV_TEMPLATE_VERSION`, `NAD_CREDITS_CSV_TEMPLATE_VERSION`) with a new golden file.

## Tests

`tests/` runs with no network and no other module: golden-file tests of every upload file (awards, corrections, credits,
split files), row validation by code, idempotency and conflicts, corrections, manual upload recording, `unverifiable`
verification, tenancy (cross-tenant leak, organisation_id and policies on every table), the Alembic chain, and the
Adapter contract.

- `contracts/ports/` the port and the Adapter contract, copied from integration-hub
- `contracts/openapi.yaml` the read-only operator view
- `docs/data-model.md`, `docs/integration-points.md`
