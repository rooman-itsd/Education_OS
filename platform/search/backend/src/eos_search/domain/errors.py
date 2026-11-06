from __future__ import annotations


class SearchError(Exception):
    """A refusal raised by this module. `status` is the HTTP status the API answers with; `detail` is one
    sentence and never contains a query, a title or any document content."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


class EngineUnavailable(SearchError):  # noqa: N818  named for what the API says: unavailable
    """The engine is down, timed out or answered with something unusable. Always a 503, never an empty result."""

    def __init__(self, detail: str = "search is unavailable"):
        super().__init__(503, detail)


class DeclarationError(ValueError):
    """A module's contracts/searchable.yaml (or its provider) is not acceptable. Names the field, never data."""


class DocumentRejected(ValueError):  # noqa: N818
    """A provider returned a document the indexer must not store. `reason` is a short code, never content."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason
