"""The Adapter contract's error vocabulary (contracts/ports/adapter.yaml, error_codes). Every failure leaves the
adapter as an AdapterError with one of these codes; provider text never does."""

from __future__ import annotations

RETRYABLE = {
    "not_configured": False,
    "auth_failed": False,
    "consent_required": False,
    "invalid_request": False,
    "not_found": False,
    "conflict": False,
    "rejected": False,
    "unsupported": False,
    "manual_action_required": False,
    "throttled": True,
    "transport_unavailable": True,
    "provider_error": True,
}


class AdapterError(Exception):
    def __init__(
        self,
        code: str,
        detail: str,
        *,
        provider_code: str | None = None,
        retry_after_s: int | None = None,
    ):
        if code not in RETRYABLE:
            raise ValueError(f"unknown error code {code}")
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.provider_code = provider_code
        self.retry_after_s = retry_after_s

    @property
    def retryable(self) -> bool:
        return RETRYABLE[self.code]

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "retryable": self.retryable,
            "retry_after_s": self.retry_after_s,
            "detail": self.detail,
            "provider_code": self.provider_code,
        }
