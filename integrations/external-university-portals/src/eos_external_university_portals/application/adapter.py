"""The Adapter contract (contracts/ports/adapter.yaml) and the inter-institution-records port, for exchange of academic
records with partner institutions: PDF and CSV files, EMREX ELMO XML and Europass EDC.

integration-hub finds `get_adapter` by the `eos.integration_adapters` entry point and calls the operations below with
a Context. Every operation returns a Result (output or error) and never raises. Each partner is one connection: its
settings arrive in the Context. The hub injects the platform/documents and platform/notification clients; until it
does, only mock mode runs, on in-memory ones. In mock and sandbox nothing is delivered; only live sends.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eos_core.db import SessionLocal
from eos_core.tenant import organisation_scope
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..domain.port import MODES, Context, Result, fail, ok
from ..infrastructure.config import Settings
from ..infrastructure.documents import Courier, DocumentStore, MemoryCourier, MemoryDocumentStore
from . import schema, service
from .csvmapping import mapping_issues
from .formats.csvfmt import COLUMNS
from .service import CHANNELS, PROVIDER_FORMATS, Partner

PORT = "inter-institution-records"
PORT_VERSION = 1
UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
TITLES = {
    "file": "File exchange (PDF and CSV)",
    "elmo": "EMREX ELMO XML",
    "edc": "Europass Digital Credentials (JSON-LD)",
}

_FORMAT_LIST = {
    "type": "array",
    "maxItems": 4,
    "items": {"type": "string", "enum": ["pdf", "csv", "elmo_xml", "edc_jsonld"]},
}
SETTINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "partner_id": {"type": "string", "pattern": r"^[A-Za-z0-9._-]{1,60}$"},
        "name": {"type": "string", "minLength": 1, "maxLength": 200},
        "country": {"type": "string", "pattern": r"^[A-Z]{2}$"},
        "institution_code": {"type": "string", "minLength": 1, "maxLength": 60},
        "formats_out": _FORMAT_LIST,
        "formats_in": _FORMAT_LIST,
        "channel": {"type": "string", "enum": list(CHANNELS)},
        "email": {"type": "string", "pattern": r"^[^@\s]{1,64}@[^@\s]{1,189}$"},
        "portal_url": {"type": "string", "pattern": r"^https?://[^\s]{1,490}$"},
        "csv_mapping": {"type": "object"},
        "grade_conversion": {"type": "object"},
        "credit_conversion": {"type": "object"},
    },
    "required": ["partner_id", "country", "channel"],
    "additionalProperties": False,
}


def _module_version() -> str:
    """module.yaml's version, so describe() and the manifest cannot drift."""
    for parent in Path(__file__).resolve().parents:
        manifest = parent / "module.yaml"
        if manifest.is_file():
            m = re.search(r"^version:\s*([0-9][^\s#]*)", manifest.read_text(), re.M)
            if m:
                return m.group(1)
    return "0.0.0"


class ExternalUniversityPortalsAdapter:
    name = "external-university-portals"

    def __init__(
        self,
        documents: DocumentStore | None = None,
        courier: Courier | None = None,
        session_factory: Callable[[], Session] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._injected_documents = documents is not None
        self._injected_courier = courier is not None
        self.documents: DocumentStore = documents or MemoryDocumentStore()
        self.courier: Courier = courier or MemoryCourier()
        self.session_factory = session_factory or SessionLocal
        self.clock = clock or (lambda: datetime.now(UTC).replace(microsecond=0))

    # ------------------------------------------------------------ registration

    def describe(self) -> dict:
        return {
            "adapter": self.name,
            "version": _module_version(),
            "ports": [{"port": PORT, "version": PORT_VERSION}],
            "providers": [
                {
                    "provider": provider,
                    "title": TITLES[provider],
                    "ports": [PORT],
                    "modes": list(MODES),
                    "auth": "none",
                    "link_scope": "organisation",
                    "inbound": [],
                    "settings_schema": SETTINGS_SCHEMA,
                    "credential_names": [],
                    "platform_credential_names": [],
                }
                for provider in PROVIDER_FORMATS
            ],
        }

    # ------------------------------------------------------------ plumbing

    def _guard(self, ctx: Any, *, needs_documents: bool = False) -> tuple[Partner | None, Result | None]:
        """The checks every operation shares: a usable context and a valid partner connection. Never raises. The
        hub's context is read as attributes from here on; Context.of only checks it carries the context's fields."""
        ctx = Context.of(ctx)
        if ctx is None:
            return None, fail("invalid_request", "missing context")
        if not isinstance(ctx.organisation_id, str) or not UUID_RE.fullmatch(ctx.organisation_id):
            return None, fail("invalid_request", "organisation_id must be a uuid")
        if ctx.mode not in MODES:
            return None, fail("invalid_request", "mode must be mock, sandbox or live")
        if ctx.provider not in PROVIDER_FORMATS:
            return None, fail("not_configured", "no such provider here: file, elmo or edc")
        if needs_documents and ctx.mode != "mock" and not self._injected_documents:
            return None, fail("not_configured", "no platform/documents client: only mock mode runs without one")
        settings = ctx.settings if isinstance(ctx.settings, dict) else None
        if settings is None:
            return None, fail("not_configured", "the connection has no settings")
        issues: list[dict] = []
        schema.check(SETTINGS_SCHEMA, settings, "", issues)
        issues += mapping_issues(settings, COLUMNS)
        if issues:
            return None, fail(
                "not_configured", f"connection settings are invalid at {issues[0]['path'] or '$'} ({issues[0]['code']})"
            )
        return Partner(
            partner_id=settings["partner_id"],
            country=settings["country"],
            channel=settings["channel"],
            name=settings.get("name"),
            institution_code=settings.get("institution_code"),
            formats_out=tuple(settings.get("formats_out", ())),
            formats_in=tuple(settings.get("formats_in", ())),
            email=settings.get("email"),
            portal_url=settings.get("portal_url"),
            csv_mapping=dict(settings.get("csv_mapping", {})),
            grade_conversion=dict(settings.get("grade_conversion", {})),
            credit_conversion=dict(settings.get("credit_conversion", {})),
        ), None

    @contextmanager
    def _db(self, ctx: Context):
        db = self.session_factory()
        db.info["organisation_id"] = ctx.organisation_id
        try:
            with organisation_scope(ctx.organisation_id):
                yield db
        finally:
            db.close()

    def _run(self, ctx: Context, fn: Callable[[Session], Result]) -> Result:
        try:
            with self._db(ctx) as db:
                return fn(db)
        except SQLAlchemyError:
            return fn_failed()

    # ------------------------------------------------------------ Adapter contract

    def capabilities(self, ctx: Context) -> Result:
        _, err = self._guard(ctx)
        return err or ok({"port": PORT, "capabilities": service.capabilities(ctx.provider)})

    def healthcheck(self, ctx: Context) -> Result:
        """No partner API is called in v1.0 and nothing is held, so a connection is always healthy."""
        _, err = self._guard(ctx)
        return err or ok(
            {"status": "healthy", "detail": "no partner is contacted; nothing to authenticate", "expires_at": None}
        )

    def begin_authorisation(self, ctx: Context, **_: Any) -> Result:
        return fail("unsupported", "partners in this release need no authorisation")

    complete_authorisation = refresh_authorisation = revoke_authorisation = begin_authorisation

    def verify_inbound(self, ctx: Context, **_: Any) -> Result:
        return ok({"verdict": "reject", "reject_status": 404})  # no partner calls back in v1.0

    def parse_inbound(self, ctx: Context, **_: Any) -> Result:
        return ok({"notifications": []})

    def handle_provider_request(self, ctx: Context, **_: Any) -> Result:
        return ok({"status": 404, "content_type": "text/plain", "body": b""})

    # ------------------------------------------------------------ inter-institution-records port

    def list_partners(self, ctx: Context) -> Result:
        partner, err = self._guard(ctx)
        return err or service.list_partners(partner, ctx.provider)

    def export_records(
        self,
        ctx: Context,
        *,
        exchange_key: Any,
        partner_id: Any,
        format: Any,
        transcript: Any,
        document_id: Any = None,
        caller: Any = None,
    ) -> Result:
        partner, err = self._guard(ctx, needs_documents=True)
        if err:
            return err
        return self._run(
            ctx,
            lambda db: service.export_records(
                db, self.documents, Settings.from_env(), partner, provider=ctx.provider,
                organisation_id=ctx.organisation_id, connection_id=ctx.connection_id, exchange_key=exchange_key,
                partner_id=partner_id, format=format, transcript=transcript, document_id=document_id,
                clock=self.clock(), secrets=ctx.secrets, caller=caller,
            ),
        )  # fmt: skip

    def send_records(self, ctx: Context, *, exchange_id: Any, message: Any = None) -> Result:
        partner, err = self._guard(ctx)
        if err:
            return err
        courier = self.courier if (self._injected_courier or ctx.mode == "mock") else None
        return self._run(
            ctx,
            lambda db: service.send_records(
                db,
                Settings.from_env(),
                partner,
                courier,
                mode=ctx.mode,
                exchange_id=exchange_id,
                message=message,
                clock=self.clock(),
            ),
        )

    def record_manual_delivery(
        self, ctx: Context, *, exchange_id: Any, delivered_on: Any, delivered_by: Any, partner_reference: Any
    ) -> Result:
        partner, err = self._guard(ctx)
        if err:
            return err
        return self._run(
            ctx,
            lambda db: service.record_manual_delivery(
                db, organisation_id=ctx.organisation_id, partner=partner, exchange_id=exchange_id,
                delivered_on=delivered_on, delivered_by=delivered_by, partner_reference=partner_reference,
                today=self.clock().date(),
            ),
        )  # fmt: skip

    def import_records(
        self, ctx: Context, *, exchange_key: Any, partner_id: Any, format: Any, document_id: Any, caller: Any = None
    ) -> Result:
        partner, err = self._guard(ctx, needs_documents=True)
        if err:
            return err
        return self._run(
            ctx,
            lambda db: service.import_records(
                db, self.documents, Settings.from_env(), partner, provider=ctx.provider,
                organisation_id=ctx.organisation_id, connection_id=ctx.connection_id, exchange_key=exchange_key,
                partner_id=partner_id, format=format, document_id=document_id, caller=caller,
            ),
        )  # fmt: skip


def fn_failed() -> Result:
    return fail("provider_error", "the database failed; try again")


_ADAPTER: ExternalUniversityPortalsAdapter | None = None


def get_adapter() -> ExternalUniversityPortalsAdapter:
    """The entry point (`eos.integration_adapters`, name external-university-portals). One instance per process."""
    global _ADAPTER
    if _ADAPTER is None:
        _ADAPTER = ExternalUniversityPortalsAdapter()
    return _ADAPTER
