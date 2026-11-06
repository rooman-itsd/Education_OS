"""The Adapter contract (contracts/ports/adapter.yaml) and the regulatory-submission port, for AISHE, NIRF and NAAC.

integration-hub finds `get_adapter` by the `eos.integration_adapters` entry point and calls the operations below with a
Context. Every operation returns a Result (output or error) and never raises: a bad input is `invalid_request`, never
a 500. The hub injects the platform/documents client; until it does, only mock mode runs, on an in-memory store.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from eos_core.db import SessionLocal
from eos_core.tenant import organisation_scope
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..domain.port import MODES, Context, Result, fail, ok
from ..infrastructure.config import Settings
from ..infrastructure.documents import DocumentStore, MemoryDocumentStore
from . import rules, service
from .catalogue import get_form

PORT = "regulatory-submission"
PORT_VERSION = 1
UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def _module_version() -> str:
    """module.yaml's version, so describe() and the manifest cannot drift."""
    for parent in Path(__file__).resolve().parents:
        manifest = parent / "module.yaml"
        if manifest.is_file():
            m = re.search(r"^version:\s*([0-9][^\s#]*)", manifest.read_text(), re.M)
            if m:
                return m.group(1)
    return "0.0.0"


_AISHE_CODE = {"type": "string", "pattern": r"^[CUS]-[0-9]{1,6}$"}
_SHORT = {"type": "string", "minLength": 1, "maxLength": 40}
PROVIDERS = {
    "aishe": (
        "AISHE (All India Survey on Higher Education)",
        {
            "institution_type": {"type": "string", "enum": ["university", "college", "standalone"]},
            "aishe_code": _AISHE_CODE,
        },
    ),
    "nirf": (
        "NIRF (National Institutional Ranking Framework)",
        {
            "nirf_institute_id": _SHORT,
            "nirf_categories": {
                "type": "array",
                "maxItems": 20,
                "items": {"type": "string", "minLength": 1, "maxLength": 40},
            },
        },
    ),
    "naac": ("NAAC (National Assessment and Accreditation Council)", {"naac_hei_id": _SHORT}),
}


def _settings_schema(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": [], "additionalProperties": False}


class GovernmentPortalsAdapter:
    name = "government-portals"

    def __init__(
        self,
        documents: DocumentStore | None = None,
        session_factory: Callable[[], Session] | None = None,
    ) -> None:
        self._injected_documents = documents is not None
        self.documents: DocumentStore = documents or MemoryDocumentStore()
        self.session_factory = session_factory or SessionLocal

    # ------------------------------------------------------------ registration

    def describe(self) -> dict:
        return {
            "adapter": self.name,
            "version": _module_version(),
            "ports": [{"port": PORT, "version": PORT_VERSION}],
            "providers": [
                {
                    "provider": provider,
                    "title": title,
                    "ports": [PORT],
                    "modes": list(MODES),
                    "auth": "none",
                    "link_scope": "organisation",
                    "inbound": [],
                    "settings_schema": _settings_schema(props),
                    "credential_names": [],
                    "platform_credential_names": [],
                }
                for provider, (title, props) in PROVIDERS.items()
            ],
        }

    # ------------------------------------------------------------ plumbing

    def _guard(self, ctx: Any, *, needs_documents: bool = False, form_code: Any = None) -> Result | None:
        """The checks every operation shares. A failure here is returned, never raised."""
        if not isinstance(ctx, Context):
            return fail("invalid_request", "missing context")
        if not isinstance(ctx.organisation_id, str) or not UUID_RE.fullmatch(ctx.organisation_id):
            return fail("invalid_request", "organisation_id must be a uuid")
        if ctx.mode not in MODES:
            return fail("invalid_request", "mode must be mock, sandbox or live")
        if ctx.provider not in PROVIDERS:
            return fail("not_configured", "no such provider here: aishe, nirf or naac")
        issues: list[dict] = []
        rules.check_schema(_settings_schema(PROVIDERS[ctx.provider][1]), ctx.settings, "", issues)
        if issues:
            return fail("not_configured", f"connection settings are invalid at {issues[0]['path'] or '$'}")
        if needs_documents and ctx.mode != "mock" and not self._injected_documents:
            return fail("not_configured", "no platform/documents client: only mock mode runs without one")
        if isinstance(form_code, str) and (spec := get_form(form_code)) and spec.authority != ctx.provider:
            return fail("unsupported", f"the {ctx.provider} connection does not offer this form")
        return None

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
            return fail("provider_error", "the database failed; try again")

    # ------------------------------------------------------------ Adapter contract

    def capabilities(self, ctx: Context) -> Result:
        if (err := self._guard(ctx)) is not None:
            return err
        return ok({"port": PORT, "capabilities": service.capabilities(Settings.from_env())})

    def healthcheck(self, ctx: Context) -> Result:
        """Nothing is sent to a portal and nothing is held, so a connection is always healthy (docs/prd.md)."""
        if (err := self._guard(ctx)) is not None:
            return err
        return ok(
            {"status": "healthy", "detail": "no portal is contacted; nothing to authenticate", "expires_at": None}
        )

    def begin_authorisation(self, ctx: Context, **_: Any) -> Result:
        return fail("unsupported", "these portals use the institution's own login, which is never stored")

    complete_authorisation = refresh_authorisation = revoke_authorisation = begin_authorisation

    def verify_inbound(self, ctx: Context, **_: Any) -> Result:
        return ok({"verdict": "reject", "reject_status": 404})  # no portal calls back

    def parse_inbound(self, ctx: Context, **_: Any) -> Result:
        return ok({"notifications": []})

    def handle_provider_request(self, ctx: Context, **_: Any) -> Result:
        return ok({"status": 404, "content_type": "text/plain", "body": b""})

    # ------------------------------------------------------------ regulatory-submission port

    def list_forms(self, ctx: Context) -> Result:
        if (err := self._guard(ctx)) is not None:
            return err
        return service.list_forms(Settings.from_env(), authority=ctx.provider)

    def validate(self, ctx: Context, *, form_code: Any, period: Any, data: Any) -> Result:
        if (err := self._guard(ctx, form_code=form_code)) is not None:
            return err
        return service.validate(Settings.from_env(), form_code, period, data)

    def prepare_package(
        self,
        ctx: Context,
        *,
        package_key: Any,
        form_code: Any,
        period: Any,
        data: Any,
        evidence: Any = None,
        caller: Any = None,
    ) -> Result:
        if (err := self._guard(ctx, needs_documents=True, form_code=form_code)) is not None:
            return err
        return self._run(
            ctx,
            lambda db: service.prepare_package(
                db,
                self.documents,
                Settings.from_env(),
                organisation_id=ctx.organisation_id,
                package_key=package_key,
                form_code=form_code,
                period=period,
                data=data,
                evidence=evidence,
                caller=caller,
            ),
        )

    def submit(self, ctx: Context, *, package_id: Any) -> Result:
        if (err := self._guard(ctx)) is not None:
            return err
        return self._run(ctx, lambda db: service.submit(db, package_id=package_id))

    def record_manual_submission(
        self,
        ctx: Context,
        *,
        package_id: Any,
        submitted_on: Any,
        submitted_by: Any,
        portal_reference: Any,
        acknowledgement_document_id: Any = None,
    ) -> Result:
        if (err := self._guard(ctx, needs_documents=True)) is not None:
            return err
        return self._run(
            ctx,
            lambda db: service.record_manual_submission(
                db,
                self.documents,
                organisation_id=ctx.organisation_id,
                package_id=package_id,
                submitted_on=submitted_on,
                submitted_by=submitted_by,
                portal_reference=portal_reference,
                acknowledgement_document_id=acknowledgement_document_id,
            ),
        )

    def get_package(self, ctx: Context, *, package_id: Any) -> Result:
        if (err := self._guard(ctx)) is not None:
            return err
        return self._run(ctx, lambda db: service.get_package(db, package_id))


_ADAPTER: GovernmentPortalsAdapter | None = None


def get_adapter() -> GovernmentPortalsAdapter:
    """The entry point (`eos.integration_adapters`, name government-portals). One instance per process."""
    global _ADAPTER
    if _ADAPTER is None:
        _ADAPTER = GovernmentPortalsAdapter()
    return _ADAPTER
