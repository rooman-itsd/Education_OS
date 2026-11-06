"""What every operation needs besides its input: a tenant-scoped database session, platform/documents, the HTTP
client for the mode, the clock. Injected, so the adapter runs alone in tests (module standard)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from ..domain.errors import AdapterError
from ..infrastructure import config as config_module
from ..infrastructure.client import DigiLockerClient
from ..infrastructure.documents import DocumentStore, InMemoryDocuments
from ..infrastructure.mock import MockDigiLocker
from .schemas import ConnectionSettings, Context

MOCK_BASE_URL = "https://mock.digilocker.invalid/public"


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
    mock: MockDigiLocker = field(default_factory=MockDigiLocker)
    http_factory: Callable[[], httpx.Client] = field(default=lambda: httpx.Client())  # noqa: E731
    clock: Callable[[], datetime] = _now

    def config(self) -> config_module.Config:
        return config_module.load()

    def settings(self, ctx: Context) -> ConnectionSettings:
        try:
            return ConnectionSettings.model_validate(ctx.settings)
        except ValueError as e:
            raise AdapterError("not_configured", "the connection's settings are missing or invalid") from e

    def require_mode(self, ctx: Context, cfg: config_module.Config) -> None:
        if ctx.mode == "mock" and not cfg.dev_mode:
            raise AdapterError("not_configured", "mock mode is refused unless EOS_DEV_MODE=true")
        if ctx.mode != "mock" and not cfg.base_url(ctx.mode):
            raise AdapterError("not_configured", f"no DigiLocker base URL is configured for {ctx.mode} mode")

    def pepper(self, ctx: Context, cfg: config_module.Config) -> str:
        if cfg.search_key_pepper:
            return cfg.search_key_pepper
        if ctx.mode == "mock":
            return "mock-search-key-pepper"
        raise AdapterError("not_configured", "DIGILOCKER_SEARCH_KEY_PEPPER is not set")

    def documents_for(self, ctx: Context) -> DocumentStore:
        if isinstance(self.documents, UnconfiguredDocuments) and ctx.mode == "mock":
            self.documents = InMemoryDocuments()  # dev only: nothing durable is promised in mock mode
        return self.documents

    def client(self, ctx: Context, cfg: config_module.Config) -> DigiLockerClient:
        self.require_mode(ctx, cfg)
        timeout = float(cfg.http_timeout_s)
        if ctx.deadline is not None:
            deadline = ctx.deadline if ctx.deadline.tzinfo else ctx.deadline.replace(tzinfo=UTC)
            remaining = (deadline - self.clock()).total_seconds()
            if remaining <= 0:
                raise AdapterError("transport_unavailable", "the call's deadline has passed")
            timeout = min(timeout, remaining)
        if ctx.mode == "mock":
            return DigiLockerClient(
                self.mock.client(),
                MOCK_BASE_URL,
                timeout_s=timeout,
                clock=self.clock,
                push_max_age_s=cfg.push_max_age_s,
            )
        return DigiLockerClient(
            self.http_factory(), cfg.base_url(ctx.mode), timeout_s=timeout, clock=self.clock,
            push_max_age_s=cfg.push_max_age_s,
        )  # fmt: skip

    def trust_mock_client(self, ctx: Context, client_id: str, client_secret: str) -> None:
        """Mock mode only: the first secret seen for a client id is the one the simulator accepts, so a developer
        can use any credentials. A strict simulator (tests) is never auto-registered."""
        if ctx.mode == "mock" and not self.mock.strict:
            self.mock.clients.setdefault(client_id, client_secret)

    def requester(self, ctx: Context, cfg: config_module.Config) -> tuple[str, str]:
        pair = cfg.requester(ctx.mode)
        if pair is None and ctx.mode == "mock":
            pair = ("mock-requester", "mock-requester-secret")
        if pair is None:
            raise AdapterError("not_configured", "Rooman's DigiLocker requester app is not configured for this mode")
        self.trust_mock_client(ctx, *pair)
        return pair

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
