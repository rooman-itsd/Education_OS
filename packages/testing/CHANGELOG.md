# Changelog

## Unreleased

### Added
- Platform stubs as pytest fixtures: `fake_audit`, `fake_notification`, `fake_events`, `fake_scheduler`.
- `as_user` and `FakePrincipal` to sign a fake user in by overriding the identity dependency.
- Tests for every stub (`tests/test_stubs.py`).

## 0.1.0

### Added
- `register_and_login` and `assert_no_cross_tenant_leak`.
