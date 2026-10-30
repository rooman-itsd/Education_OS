# Changelog — payment-sbiepay

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
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
