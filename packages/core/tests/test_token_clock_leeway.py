"""Tokens tolerate a small clock difference (CLOCK_LEEWAY_SECONDS) on iat and exp, and no more.

Without it a token issued a moment "in the future" by a clock that was just stepped (NTP, a VM or Docker host
resuming) or by another process is refused as "not yet valid (iat)" on its very first use."""

from __future__ import annotations

import time

import jwt
import pytest
from eos_core.security import CLOCK_LEEWAY_SECONDS, decode_token
from eos_core.settings import settings


def _token(iat_offset: int, exp_offset: int) -> str:
    now = int(time.time())
    claims = {"sub": "u1", "org": "o1", "iat": now + iat_offset, "exp": now + exp_offset}
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def test_the_leeway_is_small():
    assert 0 < CLOCK_LEEWAY_SECONDS <= 60


def test_a_token_issued_a_few_seconds_ahead_is_accepted():
    assert decode_token(_token(iat_offset=CLOCK_LEEWAY_SECONDS - 10, exp_offset=3600))["sub"] == "u1"


def test_a_token_issued_well_ahead_is_still_refused():
    with pytest.raises(jwt.ImmatureSignatureError):
        decode_token(_token(iat_offset=CLOCK_LEEWAY_SECONDS + 60, exp_offset=3600))


def test_a_token_just_expired_is_accepted_within_the_leeway_and_refused_after_it():
    assert decode_token(_token(iat_offset=-3600, exp_offset=-(CLOCK_LEEWAY_SECONDS - 10)))["sub"] == "u1"
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(_token(iat_offset=-3600, exp_offset=-(CLOCK_LEEWAY_SECONDS + 60)))
