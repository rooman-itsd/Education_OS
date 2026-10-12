# payment-sbiepay

SBIePay payment gateway adapter: start a payment, take the payer to the gateway, confirm the result by
double verification, refund, and reconcile settlements. Used by `platform/billing` (plan upgrades,
`purpose=subscription`) and `fees-accounts` (fees, `purpose=fee`). Requirements: [docs/prd.md](docs/prd.md).

- `contracts/` holds the API (`openapi.yaml`), events and permissions. Callers use only these.
- `src/eos_payment_sbiepay/` is the adapter (package `eos-payment-sbiepay`). Its layers:
  - `domain/models.py`: tables, each with `organisation_id`. Row-level security is applied by `eos_core.init_db()`.
  - `application/service.py`: the use cases and the scheduled jobs.
  - `infrastructure/gateway.py`: the gateway port, `MockGateway` and `SbiepayGateway`.
  - `infrastructure/notifier.py`: signed notifications to `notify_url`.
  - `infrastructure/config.py`: reads `PAYMENT_SBIEPAY_*`.
  - `api/router.py`: the HTTP surface, mounted at `/api/v1/payment-sbiepay`.
- `config/env.example` documents every setting.
- `tests/` covers the flow end to end on the mock gateway, plus the cross-tenant leak test.

## How a payment works

1. The caller sends `POST /payments` with its `source_module`, `source_reference`, amount, `return_url` and an optional `notify_url`. The adapter returns `{reference, payment_url, expires_at}`. While a payment for the same source is open, a second request returns `409` with that payment's session. A unique index on open payments (`uq_payment_sbiepay_open_source`) enforces this in the database too, so two simultaneous requests can't both start a payment.
2. The browser opens `payment_url`, an auto-submitting form to the gateway. The payment becomes `pending`.
3. The gateway posts its response to `POST /callbacks/sbiepay`. The adapter never trusts that response alone. It asks the gateway again (double verification), records `succeeded` or `failed`, publishes the event, and redirects the browser to `return_url?reference=...&status=...`.
4. A payment can reach `expired` in two ways:
   - its session was never opened before it ran out;
   - it stayed pending longer than `PAYMENT_SBIEPAY_PENDING_VERIFY_AFTER_MINUTES` and the gateway doesn't know it.

Final payments never change again, so repeated callbacks are harmless.

## Notifications to `notify_url`

On every final status and every successful refund, the adapter posts a `PaymentNotification` to the caller's `notify_url`:
- The body is JSON with sorted keys and no spaces.
- The header `X-Payment-Signature` carries the hex HMAC-SHA256 of the raw body, keyed with `PAYMENT_SBIEPAY_NOTIFY_SECRET`.
- A receiver must check the signature against the raw bytes and de-duplicate on `event_id`. `event_id` is the same id as the outbox event.
- If delivery fails, the adapter retries with exponential backoff, at most 6 hours apart, until it gets a 2xx answer.

## Scheduled jobs

These are plain functions that `platform/scheduler` will call. They aren't wired yet.

| Function | Suggested schedule | Does |
|---|---|---|
| `service.sweep_open_payments(db)` | every 5 minutes | Expires sessions that were never opened. Re-verifies stale pending payments. |
| `service.deliver_notifications(db)` | every minute | Retries notifications that are due. |
| `service.run_reconciliation(...)` | daily, per organisation | Compares the gateway's settlement report with fee payments. |

## Modes

`PAYMENT_SBIEPAY_MODE` takes one of three values:

- **`sandbox`** (the default) and **`live`**: use `SbiepayGateway`. Both need `PAYMENT_SBIEPAY_CALLBACK_BASE_URL`, so `payment_url` and the gateway's return URL are absolute. Without it, payment calls answer `503`. The gateway can't talk to SBIePay yet; see the limitations below.
- **`mock`**: an in-memory gateway for development and tests. The redirect form posts straight back to the callback. It must be set explicitly (`PAYMENT_SBIEPAY_MODE=mock`) and is refused unless `EOS_DEV_MODE=true`, so a missing setting never selects it.

## Running the tests

```sh
pip install -e packages/core -e packages/testing -e "integrations/payment-sbiepay[test]"
pytest integrations/payment-sbiepay
```

The tests mount only this adapter's router and issue tokens with `eos_core.security`, so they need no other module.

## Known limitations (tracked on #97)

- **The SBIePay gateway isn't implemented.** The request and response fields, the encryption, double verification, refunds and the settlement report format all come from the SBIePay merchant integration kit, which hasn't been received. AES also needs a library on the approved stack. Until then, `sandbox` and `live` answer `503`.
- **Merchant encryption keys aren't stored.** `PUT /merchant-account` with an `encryption_key` answers `501`, because keys must be stored encrypted.
- **Settlement reports uploaded through `platform/documents`** (`report_document_id`) answer `501` until the documents SDK exists.
- **No audit records are written**, because `packages/sdk` has no audit client yet. Every state change already publishes an event.
- **Reconciliation runs immediately** and returns the finished run with `202`.
  - It covers fee payments against the organisation's merchant account.
  - Reconciling subscription payments against the platform account is a platform task.
- **Days use UTC.** That applies to the summary, reconciliation and list filters.
- **Auth reads the platform token through `eos_core`** (`api/deps.py`), because an integration can't import `eos_identity`. It will move to the SDK dependency when one exists.
- **Not mounted in `apps/backend` and not run in CI yet.** Those files belong to other owners.
