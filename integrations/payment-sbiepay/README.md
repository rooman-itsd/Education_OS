# payment-sbiepay

SBIePay payment gateway adapter: start a payment, take the payer to the gateway, confirm the result by
double verification, refund, and reconcile settlements. Used by `platform/billing` (plan upgrades,
`purpose=subscription`) and `fees-accounts` (fees, `purpose=fee`). Requirements: [docs/prd.md](docs/prd.md).

- `contracts/` holds the API (`openapi.yaml`), events and permissions. Callers use only these.
- `src/eos_payment_sbiepay/` is the adapter (package `eos-payment-sbiepay`). Its layers:
  - `domain/models.py`: tables, each with `organisation_id` and the `tenant_isolation` row-level-security policy on Postgres.
  - `application/service.py`: the use cases and the scheduled jobs.
  - `infrastructure/gateway.py`: the gateway port, `MockGateway` and `SbiepayGateway`.
  - `infrastructure/notifier.py`: signed notifications to `notify_url`.
  - `infrastructure/config.py`: reads `PAYMENT_SBIEPAY_*`.
  - `api/router.py`: the HTTP surface, mounted at `/api/v1/payment-sbiepay`.
- `frontend/` is the Finance Staff dashboard widget (package `@eos/payment-sbiepay`); see [Frontend](#frontend).
- `config/env.example` documents every setting.
- `tests/` covers the flow end to end on the mock gateway, plus the cross-tenant leak test.

## How a payment works

1. The caller sends `POST /payments` with its `source_module`, `source_reference`, amount, `return_url` and an optional `notify_url`. The adapter returns `{reference, payment_url, expires_at}`. While a payment for the same source is open, a second request returns `409` with that payment's session. A unique index on open payments (`uq_payment_sbiepay_open_source`) enforces this in the database too, so two simultaneous requests can't both start a payment.
2. The browser opens `payment_url`, an auto-submitting form to the gateway. The payment becomes `pending`.
3. The gateway posts its response to `POST /callbacks/sbiepay`. The adapter never trusts that response alone. It asks the gateway again (double verification), records `succeeded` or `failed`, publishes the event, and redirects the browser to `return_url?reference=...&status=...`.
4. A payment can reach `expired` in two ways:
   - its session was never opened before it ran out;
   - it stayed pending longer than `PAYMENT_SBIEPAY_PENDING_VERIFY_AFTER_MINUTES` and the gateway doesn't know it.

Final payments never change again, so repeated callbacks are harmless:
- Every status change is a compare-and-set on the row. Of a callback, a verify and a sweep racing each other, only one publishes.
- The one exception is `expired` → `succeeded`. A payer may finish at the gateway after the sweep expired the session, and the gateway's confirmation wins. Consumers may therefore see `succeeded` after `expired` for the same reference.

Each purpose has one caller: `fee` must come from `fees-accounts` and `subscription` from `billing`; anything else answers `422`.

Refunds:
- They are for fee payments only. A subscription was paid into the platform account, so an organisation gets `403`.
- The payment row is locked while a refund runs.
- Refunds the gateway accepted but hasn't settled yet count against the refundable balance.

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

## In the host app

`apps/backend/config/modules.enabled.yaml` lists `payment-sbiepay` under `integrations:`, so the API mounts the router at
`/api/v1/payment-sbiepay`, and `py-setup.sh`, the API image, CI and the auto-deploy install it, run its tests and upgrade
its chain.
- **Who reaches it:** the entitlement gate treats it like a module. An organisation reaches it only when its profile and
  its plan both include `payment-sbiepay`. Every profile does, and so do the standard and premium plans; the trial plan
  doesn't, so a trial organisation gets `403 module_not_entitled`.
- **Without settings:** the API starts with no `PAYMENT_SBIEPAY_*` set, because settings are read per call. The read
  endpoints (payments, the reconciliation summary and runs) work. Starting a payment, verify, refunds and reconciliation
  runs answer `503` until the gateway settings exist (see Modes).

## Migrations

`db/` holds this adapter's own Alembic chain:
- It touches only `payment_sbiepay_*` tables.
- It records its revision in `payment_sbiepay_alembic_version`, so it shares a database with every other module's chain.
- On Postgres, the first revision (`psb_0001`) applies the `tenant_isolation` policy to every table.

```sh
cd integrations/payment-sbiepay/db
alembic upgrade head                     # uses EOS_DATABASE_URL
alembic -x url=postgresql+psycopg://... upgrade head
```

`tests/test_migrations.py` upgrades a throwaway SQLite file, checks that the schema matches the models exactly, then downgrades. Any later change to the models needs a new revision in `db/migrations/versions`.

## Running the tests

```sh
pip install -e packages/core -e packages/testing -e "integrations/payment-sbiepay[test]"
pytest integrations/payment-sbiepay
```

The tests mount only this adapter's router and issue tokens with `eos_core.security`, so they need no other module.

## Frontend

`frontend/src/widgets/index.ts` exports the dashboard widget. The Finance Staff layout in
`platform/identity/config/dashboards/finance-staff.yaml` places it, and the `integrations:` list in `apps/frontend`
registers it (a separate PR).

| Widget | Dashboard | Endpoint | Permission |
|---|---|---|---|
| `payment-sbiepay.reconciliation` | Finance Staff | `GET /reconciliation/summary` | `payment-sbiepay:payment:read` |

- **Online payments reconciliation:** today's payments through SBIePay: succeeded, settled and pending, each with its
  count and amount, and failed with its count. Under them, the latest settlement reconciliation for the day: a danger
  badge with the number of mismatches, or "No mismatches", with "Last reconciled <date, time>" in the viewer's time
  zone; "Not reconciled yet" when no run exists for the day. Read-only: runs are started through `POST /reconciliation/runs`.
- **Data:** the widget reads through `src/api/client.ts`, a hand-written typed client that the generated client will
  replace. It asks for no `date`, so the adapter summarises today in UTC (see the limitations).
- **States:** loading; empty ("No online payments today") when every count is zero and the day has no run; and error
  with a retry when trying again can help. Until the adapter is mounted, the error reads "Payment data is not available yet."
- **Tests:** `cd integrations/payment-sbiepay/frontend && pnpm test` (vitest and Testing Library), or
  `corepack pnpm --filter @eos/payment-sbiepay test` from the repo root.

## Known limitations (tracked on #97)

- **Starting a payment needs only the payer's token.** A payer could start a payment for the right module but someone else's invoice, or a different amount. Consumers must check `amount` and `source_reference` against their own record before acting on `payment-sbiepay.payment.succeeded`. Service-to-service authentication is the platform's decision (raised on #97).
- **The SBIePay gateway isn't implemented.** The request and response fields, the encryption, double verification, refunds and the settlement report format all come from the SBIePay merchant integration kit, which hasn't been received. AES also needs a library on the approved stack. Until then, `sandbox` and `live` answer `503`.
- **Merchant encryption keys aren't stored.** `PUT /merchant-account` with an `encryption_key` answers `501`, because keys must be stored encrypted.
- **Settlement reports uploaded through `platform/documents`** (`report_document_id`) answer `501` until the documents SDK exists.
- **No audit records are written**, because `packages/sdk` has no audit client yet. Every state change already publishes an event.
- **Reconciliation runs immediately** and returns the finished run with `202`.
  - It covers fee payments against the organisation's merchant account.
  - Reconciling subscription payments against the platform account is a platform task.
- **Days use UTC.** That applies to the summary, reconciliation and list filters.
- **Auth reads the platform token through `eos_core`** (`api/deps.py`), because an integration can't import `eos_identity`. It will move to the SDK dependency when one exists.
- **The reconciliation summary's default day is UTC,** while the contract says the organisation's time zone. Pass `date` to choose the day.
- **The Finance Staff widget `payment-sbiepay.reconciliation` (#376) isn't on the dashboard yet.** `apps/frontend` must read an `integrations:` list (#375) and list `payment-sbiepay` in it (a follow-up PR).
