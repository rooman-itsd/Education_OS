# Changelog — payment-sbiepay

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- The redirect page (`GET /payments/{reference}/redirect`) sets its own Content-Security-Policy: its one
  inline script by a per-page nonce (the `onload` attribute is gone), and `form-action 'self' https:` plus
  the `return_url` or gateway origin when it is plain HTTP (local development). The API host's default
  `default-src 'none'` (platform/api-gateway) would otherwise block the auto-submit and leave the payer on a
  blank page (review of PR 363). `form-action` is not narrowed to the gateway's origin: browsers enforce it on
  the redirects that follow the POST, and the mock callback redirects to `return_url` while the gateway may
  redirect to bank or 3-D Secure pages (second review of PR 363).
- The redirect page sends `Referrer-Policy: strict-origin-when-cross-origin` in place of the host's
  `no-referrer`, so the POST to the gateway carries the merchant's origin as `Referer` and `Origin`
  (aggregators may check them against the registered domain).
- Module scaffolded.
- Contracts: payments, gateway callback, verify, refunds, reconciliation, merchant account;
  events for succeeded, failed, expired, refunded payments and reconciliation mismatches; permissions and roles.
- PRD (`docs/prd.md`).
- Frontend (`frontend/`, package `@eos/payment-sbiepay`): the Finance Staff widget `payment-sbiepay.reconciliation`
  (#335) shows today's succeeded, settled, pending and failed payments with their amounts, the latest run's mismatches
  and when the day was last reconciled, with loading, empty and error-with-retry states, and its tests.
- Adapter implementation (`src/eos_payment_sbiepay`):
  - payments with idempotent start, redirect page, gateway callback with double verification, verify, refunds;
  - reconciliation runs and the daily summary for the Finance Staff widget; merchant account;
  - events in the same transaction as each change; signed `notify_url` notifications with retry;
  - scheduled sweep for expired and abandoned payments; mock gateway for development and tests.
- Tests, including the cross-tenant leak test.
- Contracts: `Payment` gains `id`; `ReconciliationRun` gains `organisation_id`.
- Config: `PAYMENT_SBIEPAY_MODE` accepts `mock` for development. It defaults to `sandbox`, so mock is never chosen by accident.
  `sandbox` and `live` require `PAYMENT_SBIEPAY_CALLBACK_BASE_URL`.
- One open payment per caller source, enforced by a partial unique index as well as by the service.
- Alembic chain (`db/`, revision `psb_0001`) with its own version table and the `tenant_isolation` policy on Postgres.
  The migration test checks that the chain matches the models and downgrades cleanly.
- Fixes from review:
  - concurrent refunds are serialised by a row lock, and unsettled (`requested`) refunds count against the balance;
  - subscription payments cannot be refunded by an organisation (`403`);
  - `purpose` must match its calling module (`422`);
  - an expired payment the gateway confirms becomes `succeeded`;
  - status changes are compare-and-set, so racing callers publish once;
  - reconciliation works outside a request (scheduler);
  - one gateway error no longer stops the sweep;
  - a request delivers only its own payment's notifications;
  - date-times always carry `+00:00`;
  - a negative cursor answers `400` and a token without a subject `401`.
- Enabled in `apps/backend/config/modules.enabled.yaml` (`integrations:`), mounted at `/api/v1/payment-sbiepay`; CI now
  installs it, runs its tests and migrates its chain on Postgres. The README says who reaches it (profile and plan) and
  what works without gateway settings.
