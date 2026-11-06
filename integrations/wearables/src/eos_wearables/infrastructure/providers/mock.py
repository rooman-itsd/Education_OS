"""Mock mode (the default in development and CI): the provider's API is replaced by an in-process stand-in that makes no
network call. Verification, parsing and the authorisation URLs are the real provider's, since they need no network."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta

from ...domain.context import Context
from . import base
from .base import InboundEvent, InboundRequest, Normal, Provider


class MockProvider(Provider):
    def __init__(self, inner: Provider) -> None:
        super().__init__(inner.cfg, inner.http, inner.clock)
        self.inner = inner
        for attr in (
            "id",
            "title",
            "auth",
            "link_scope",
            "inbound",
            "data_types",
            "push",
            "backfill_mode",
            "rate_limit",
            "display_to_others_allowed",
        ):
            setattr(self, attr, getattr(inner, attr))

    def capabilities(self, ctx: Context | None) -> dict:
        return self.inner.capabilities(ctx)

    def begin_authorisation(
        self, ctx: Context, state: str, code_challenge: str, redirect_uri: str, scope_hint: list
    ) -> str:
        return f"https://mock.{self.inner.id}.example/authorize?state={state}"

    def complete_authorisation(self, ctx: Context, code: str, code_verifier: str, redirect_uri: str) -> dict:
        subject = (ctx.account_link or {}).get(
            "provider_subject"
        ) or f"mock-{self.inner.id}-{(ctx.account_link or {}).get('person_id', 'athlete')}"[:80]
        return {"secrets": {"access_token": "mock-access-token", "refresh_token": "mock-refresh-token"}, "provider_subject": subject,
                "granted_scopes": [], "expires_at": (self.clock() + timedelta(hours=6)).isoformat()}  # fmt: skip

    def refresh_authorisation(self, ctx: Context) -> dict:
        return {
            "secrets": {"access_token": "mock-access-token"},
            "expires_at": (self.clock() + timedelta(hours=6)).isoformat(),
        }

    def revoke_authorisation(self, ctx: Context) -> bool:
        return True

    def pull(self, ctx: Context, data_type: str, start: date, end: date) -> list[Normal]:
        if data_type not in self.data_types:
            return self.inner.pull(ctx, data_type, start, end)  # unsupported, as in live
        out: list[Normal] = []
        src = self.inner.id
        for d in base.days(start, min(end, start + timedelta(days=30))):
            t = datetime.combine(d, time(6), tzinfo=UTC)
            if data_type == "daily_summary":
                out.append(
                    base.daily(d, f"mock-{d}", src, steps=8000, distance_m=6000.0, active_kcal=450.0, resting_hr_bpm=52)
                )
            elif data_type == "activity":
                out.append(
                    base.activity(
                        f"mock-{d}",
                        src,
                        t,
                        sport="running",
                        duration_s=2700,
                        distance_m=8000.0,
                        kcal=520.0,
                        avg_hr_bpm=150,
                        max_hr_bpm=178,
                    )
                )
            elif data_type == "sleep":
                out.append(
                    base.sleep(
                        d,
                        f"mock-{d}",
                        src,
                        t - timedelta(hours=8),
                        t,
                        total_s=28800,
                        deep_s=5400,
                        light_s=14400,
                        rem_s=6300,
                        awake_s=2700,
                        score=80,
                    )
                )
            elif data_type == "heart_rate_variability":
                out.append(base.hrv(d, f"mock-{d}", src, 62.5))
            elif data_type == "body_composition":
                out.append(base.body(t, f"mock-{d}", src, 71.5, 14.2))
        return out

    def backfill(self, ctx: Context, data_types: list[str], start: date, end: date) -> bool:
        return self.inner.backfill(ctx, data_types, start, end)

    def register_user(self, ctx: Context, person_id: str, provider_subject: str | None) -> None:
        return None

    def healthcheck(self, ctx: Context) -> dict:
        return {"status": "healthy", "detail": "mock mode: no provider was called", "expires_at": None}

    def verify_inbound(self, req: InboundRequest, link_of: Callable[[str], dict | None]) -> dict:
        return self.inner.verify_inbound(req, link_of)

    def parse_inbound(self, req: InboundRequest) -> list[InboundEvent]:
        return self.inner.parse_inbound(req)
