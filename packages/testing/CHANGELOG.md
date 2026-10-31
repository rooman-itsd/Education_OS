# Changelog

## Unreleased

### Fixed
- `register_and_login` no longer falls back to `eos_core.notify.sent` for the verification token: since #361 the
  mail goes through `platform/notification`, so the fallback searched a stub that never receives it and failed
  with `StopIteration`. It now reads the token from the register response (dev mode) only, and without one stops
  with a message naming `EOS_DEV_MODE=true`. `FakeNotification.emails` documents that it carries tenancy's
  approval, rejection and status mails, not the verification mail.

### Added
- Platform stubs as pytest fixtures: `fake_audit`, `fake_notification`, `fake_events`, `fake_scheduler`.
- `as_user` and `FakePrincipal` to sign a fake user in by overriding the identity dependency.
- Tests for every stub (`tests/test_stubs.py`).

## 0.1.0

### Added
- `register_and_login` and `assert_no_cross_tenant_leak`.
