"""Security review N21 (October S7 follow-up): outside dev mode the API refuses to start with a signing key anyone
could know, the built-in development key (what an unset EOS_JWT_SECRET falls back to) or one under 32 bytes."""

import secrets
from dataclasses import replace

import pytest
from eos_core.settings import DEV_JWT_SECRET, InsecureSettingsError, Settings


def test_outside_dev_mode_the_development_key_is_refused(monkeypatch):
    monkeypatch.delenv("EOS_JWT_SECRET", raising=False)
    monkeypatch.setenv("EOS_DEV_MODE", "false")
    s = Settings()
    assert s.jwt_secret == DEV_JWT_SECRET
    with pytest.raises(InsecureSettingsError, match="EOS_JWT_SECRET is unset or the built-in development key"):
        s.check_secrets()
    with pytest.raises(InsecureSettingsError):
        replace(s, jwt_secret=DEV_JWT_SECRET).check_secrets()  # set explicitly to the same value: refused too


@pytest.mark.parametrize("key", ["", "short", "x" * 31, "é" * 15])  # "é" is 2 bytes: 30 bytes
def test_outside_dev_mode_a_key_under_32_bytes_is_refused(key):
    with pytest.raises(InsecureSettingsError, match="at least 32 random bytes"):
        replace(Settings(), dev_mode=False, jwt_secret=key).check_secrets()


def test_outside_dev_mode_a_random_key_of_32_bytes_or_more_is_accepted():
    replace(Settings(), dev_mode=False, jwt_secret="x" * 32).check_secrets()
    replace(Settings(), dev_mode=False, jwt_secret=secrets.token_hex(32)).check_secrets()


def test_dev_mode_accepts_the_development_key():
    replace(Settings(), dev_mode=True, jwt_secret=DEV_JWT_SECRET).check_secrets()
    replace(Settings(), dev_mode=True, jwt_secret="short").check_secrets()
