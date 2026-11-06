"""One failure vocabulary for every provider (contracts/ports/adapter.yaml, error_codes). An AdapterError carries only
what is safe for a log line: a code from the contract, whether a retry can help, and a short detail written here,
never the provider's own text, a personal datum or a secret."""

from __future__ import annotations

RETRYABLE = {"throttled", "transport_unavailable", "provider_error"}
CODES = {
    "not_configured", "auth_failed", "consent_required", "invalid_request", "not_found", "conflict", "rejected",
    "unsupported", "manual_action_required", "throttled", "transport_unavailable", "provider_error",
}  # fmt: skip


class AdapterError(Exception):
    def __init__(
        self,
        code: str,
        detail: str,
        *,
        provider_code: str | None = None,
        retry_after_s: int | None = None,
    ) -> None:
        super().__init__(f"{code}: {detail}")
        assert code in CODES, code
        self.code = code
        self.detail = detail
        self.provider_code = provider_code
        self.retry_after_s = retry_after_s

    @property
    def retryable(self) -> bool:
        return self.code in RETRYABLE

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "retryable": self.retryable,
            "retry_after_s": self.retry_after_s,
            "detail": self.detail,
            "provider_code": self.provider_code,
        }
