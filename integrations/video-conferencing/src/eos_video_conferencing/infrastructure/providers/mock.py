"""Mock mode (the default in development and CI): the provider's API is replaced by an in-process stand-in that makes no
network call and creates nothing anywhere. Verification, parsing and the authorisation URLs are the real provider's, since
they need no network; Jitsi's rooms and tokens are real too, because they never needed an account."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator
from datetime import timedelta

from ...domain.context import Context
from ...domain.models import CreateMeeting, UpdateMeeting
from .base import Created, InboundRequest, Participant, Provider, ProviderEvent, RecordingFile, Ref

MOCK_RECORDING = b"mock recording bytes"


class MockProvider(Provider):
    def __init__(self, inner: Provider) -> None:
        super().__init__(inner.cfg, inner.http, inner.clock)
        self.inner = inner
        self.id, self.title, self.auth = inner.id, inner.title, inner.auth

    def create(self, ctx: Context, spec: CreateMeeting, host_user: str) -> Created:
        if self.inner.id == "jitsi":
            return self.inner.create(ctx, spec, host_user)
        pid = "mock-" + hashlib.sha256(f"{ctx.organisation_id}:{spec.meeting_key}".encode()).hexdigest()[:10]
        url = f"https://mock.{self.inner.id}.example/j/{pid}"
        return Created(
            pid,
            url,
            None if self.inner.id == "teams" else f"{url}?role=host",
            None if self.inner.id == "teams" else "mock-pass",
            [],
            host_user_id=host_user,
        )

    def update(self, ctx: Context, ref: Ref, change: UpdateMeeting, host_user: str | None) -> Created | None:
        return self.inner.update(ctx, ref, change, host_user) if self.inner.id == "jitsi" else None

    def cancel(self, ctx: Context, ref: Ref) -> None:
        return None

    def attendance(self, ctx: Context, ref: Ref) -> tuple[list[Participant], None]:
        if self.inner.id == "jitsi":
            return self.inner.attendance(ctx, ref)  # unsupported, as in live
        start = ref.starts_at
        return [
            Participant(
                "student@example.invalid", "Mock Student", "attendee", [(start, start + timedelta(minutes=30))], 1800
            )
        ], None

    def recordings(self, ctx: Context, ref: Ref) -> list[RecordingFile]:
        if self.inner.id == "jitsi":
            return self.inner.recordings(ctx, ref)
        return [
            RecordingFile(
                "mock-rec-1", "video", ref.starts_at, ref.starts_at + timedelta(minutes=30), len(MOCK_RECORDING)
            )
        ]

    def download(self, ctx: Context, ref: Ref, rec: RecordingFile) -> tuple[Iterator[bytes], Callable[[], None]]:
        if self.inner.id == "jitsi":
            return self.inner.download(ctx, ref, rec)
        return iter([MOCK_RECORDING]), lambda: None

    def mint(self, *a, **k):
        return self.inner.mint(*a, **k)

    def healthcheck(self, ctx: Context) -> dict:
        return {"status": "healthy", "detail": "mock mode: no provider was called", "expires_at": None}

    def begin_authorisation(
        self, ctx: Context, state: str, code_challenge: str, redirect_uri: str, scope_hint: list
    ) -> str:
        return f"https://mock.{self.inner.id}.example/authorize?state={state}"

    def complete_authorisation(self, ctx: Context, code: str, code_verifier: str, redirect_uri: str) -> dict:
        return {"secrets": {"access_token": "mock-access-token", "refresh_token": "mock-refresh-token"}, "provider_subject": "mock-account",
                "granted_scopes": [], "expires_at": (self.clock() + timedelta(hours=1)).isoformat()}  # fmt: skip

    def refresh_authorisation(self, ctx: Context) -> dict:
        return {"secrets": {"access_token": "mock-access-token", "refresh_token": "mock-refresh-token"}, "expires_at": (self.clock() + timedelta(hours=1)).isoformat()}  # fmt: skip

    def revoke_authorisation(self, ctx: Context) -> bool:
        return True

    def verify_inbound(self, ctx: Context | None, req: InboundRequest) -> dict:
        return self.inner.verify_inbound(ctx, req)

    def parse_inbound(self, ctx: Context | None, req: InboundRequest) -> list[ProviderEvent]:
        return self.inner.parse_inbound(ctx, req)

    def ensure_subscription(self, ctx: Context, existing):
        if existing is not None:
            return {**existing, "expires_at": self.clock() + timedelta(days=3)}
        return {
            "subscription_id": "mock-subscription",
            "expires_at": self.clock() + timedelta(days=3),
            "resource": "mock",
            "nonce": "0" * 32,
        }
