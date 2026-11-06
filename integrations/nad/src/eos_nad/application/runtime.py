"""What every operation needs besides its input: a tenant-scoped database session, platform/documents, the clock.
Injected, so the adapter runs alone in tests (module standard). v1.0 makes no outbound call to NAD or ABC, so there
is no HTTP client here: the API channel is added with the depositories' specs (docs/prd.md)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ..domain.errors import AdapterError
from ..infrastructure import config as config_module
from ..infrastructure.documents import DocumentStore, InMemoryDocuments
from .schemas import ConnectionSettings, Context


class UnconfiguredDocuments:
    """Until the host wires platform/documents, only mock mode (dev) has a store."""

    def get(self, organisation_id: str, document_id: str) -> bytes | None:
        raise AdapterError("not_configured", "platform/documents is not connected to this adapter")

    def put(self, organisation_id: str, *, filename: str, content_type: str, content: bytes) -> str:
        raise AdapterError("not_configured", "platform/documents is not connected to this adapter")


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Runtime:
    session_factory: Callable[[], Session]
    documents: DocumentStore = field(default_factory=UnconfiguredDocuments)
    clock: Callable[[], datetime] = _now

    def config(self) -> config_module.Config:
        return config_module.load()

    def settings(self, ctx: Context) -> ConnectionSettings:
        try:
            return ConnectionSettings.model_validate(ctx.settings)
        except ValueError as e:
            raise AdapterError("not_configured", "the connection's settings are invalid") from e

    def require_mode(self, ctx: Context, cfg: config_module.Config) -> None:
        if ctx.mode == "mock" and not cfg.dev_mode:
            raise AdapterError("not_configured", "mock mode is refused unless EOS_DEV_MODE=true")

    def pepper(self, ctx: Context, cfg: config_module.Config) -> str:
        if cfg.apaar_hash_pepper:
            return cfg.apaar_hash_pepper
        if ctx.mode == "mock":
            return "mock-apaar-hash-pepper"
        raise AdapterError("not_configured", "NAD_APAAR_HASH_PEPPER is not set")

    def institution_id(self, ctx: Context, settings: ConnectionSettings, depository: str) -> str:
        """The institution's id on NAD (awards) or ABC (credits). Outside mock mode a missing one is a connection
        that cannot produce a file the depository would accept."""
        value = settings.nad_institution_id if depository == "nad" else settings.abc_institution_id
        if value:
            return value
        if ctx.mode == "mock":
            return f"MOCK-{depository.upper()}-INSTITUTION"
        raise AdapterError("not_configured", f"the connection has no {depository}_institution_id")

    def documents_for(self, ctx: Context) -> DocumentStore:
        if isinstance(self.documents, UnconfiguredDocuments) and ctx.mode == "mock":
            self.documents = InMemoryDocuments()  # dev only: nothing durable is promised in mock mode
        return self.documents

    @contextmanager
    def db(self, ctx: Context) -> Iterator[Session]:
        session = self.session_factory()
        session.info["organisation_id"] = str(ctx.organisation_id)
        try:
            yield session
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()
