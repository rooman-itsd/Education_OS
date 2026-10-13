# Changelog — payment-sbiepay

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contracts: payments, gateway callback, verify, refunds, reconciliation, merchant account;
  events for succeeded, failed, expired, refunded payments and reconciliation mismatches; permissions and roles.
- PRD (`docs/prd.md`).
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
