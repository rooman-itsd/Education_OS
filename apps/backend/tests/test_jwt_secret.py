"""Security review N21: the API host refuses to start outside dev mode with the built-in development signing key or
one shorter than 32 bytes, before it mounts anything. In dev mode it starts as before."""

from dataclasses import replace

import pytest
from eos_backend import main
from eos_core.settings import DEV_JWT_SECRET, InsecureSettingsError


@pytest.mark.parametrize("key", [DEV_JWT_SECRET, "too-short-for-hs256"])
def test_outside_dev_mode_the_api_refuses_to_start_with_a_known_or_short_key(monkeypatch, key):
    monkeypatch.setattr(main, "settings", replace(main.settings, dev_mode=False, jwt_secret=key))
    with pytest.raises(InsecureSettingsError, match="EOS_JWT_SECRET"):
        main.create_app()


def test_outside_dev_mode_the_api_starts_with_a_real_key(monkeypatch):
    monkeypatch.setattr(main, "settings", replace(main.settings, dev_mode=False, jwt_secret="k" * 64))
    assert main.create_app() is not None


def test_dev_mode_starts_with_the_development_key(monkeypatch):
    monkeypatch.setattr(main, "settings", replace(main.settings, dev_mode=True, jwt_secret=DEV_JWT_SECRET))
    assert main.create_app() is not None
