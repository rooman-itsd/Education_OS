from __future__ import annotations


class HubError(Exception):
    """A business-rule failure with the HTTP status and `code` contracts/openapi.yaml names. `detail` never contains a
    credential, a token, a provider's prose or personal data: it is shown to the caller and may reach a log line."""

    def __init__(self, status: int, code: str, detail: str):
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail

    def body(self) -> dict[str, str]:
        return {"code": self.code, "detail": self.detail}


def not_found(what: str) -> HubError:
    return HubError(404, "not_found", f"{what} not found in your organisation")
