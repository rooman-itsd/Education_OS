from __future__ import annotations


class NotificationError(Exception):
    """A business-rule failure. `status` is the HTTP status the API layer answers with; the message never
    contains a recipient address, a variable value or a secret."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail
