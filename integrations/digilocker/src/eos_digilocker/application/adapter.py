"""The adapter the hub finds through the `eos.integration_adapters` entry point (contracts/ports/adapter.yaml).

    adapter = get_adapter()
    adapter.describe()                                   # identity, written to the hub's adapter registry
    adapter.invoke("issue", context, input)              # -> {"output": {...}, "provider_reference": "..."}
                                                         #  | {"error": {"code": ..., "retryable": ..., ...}}

`invoke` never raises: every failure is an error with one of the contract's codes. A pydantic failure becomes
invalid_request and names fields only (their values may be personal data). The host injects what the SDK does not
provide yet with `configure(...)`: platform/documents, the HTTP client for sandbox and live."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import httpx
from eos_core.db import SessionLocal
from pydantic import BaseModel, ValidationError

from .. import __version__
from ..domain.errors import AdapterError
from ..infrastructure.documents import DocumentStore
from ..infrastructure.mock import MockDigiLocker
from . import holder, issuing, pull
from .runtime import Runtime
from .schemas import (
    BeginAuthInput,
    CompleteAuthInput,
    ConnectionSettings,
    Context,
    FetchInput,
    GetIssuanceInput,
    IssueInput,
    ListHolderInput,
    ReplaceInput,
    WithdrawInput,
)

log = logging.getLogger("eos.digilocker")

PORT = {"port": "certificate-issuance", "version": 1}
Handler = Callable[[Runtime, Context, Any], tuple[dict, str | None]]


class _Empty(BaseModel):
    pass


# operation -> (input model, handler). Operations that need no input take an empty one.
OPERATIONS: dict[str, tuple[type[BaseModel], Handler]] = {
    "issue": (IssueInput, issuing.issue),
    "replace": (ReplaceInput, issuing.replace),
    "withdraw": (WithdrawInput, issuing.withdraw),
    "get_issuance": (GetIssuanceInput, issuing.get_issuance),
    "fetch_holder_document": (FetchInput, holder.fetch_holder_document),
    "list_holder_documents": (ListHolderInput, holder.list_holder_documents),
    "begin_authorisation": (BeginAuthInput, holder.begin_authorisation),
    "complete_authorisation": (CompleteAuthInput, holder.complete_authorisation),
    "refresh_authorisation": (_Empty, lambda rt, ctx, _i: holder.refresh_authorisation(rt, ctx)),
    "revoke_authorisation": (_Empty, lambda rt, ctx, _i: holder.revoke_authorisation(rt, ctx)),
}


def _fields(e: ValidationError) -> str:
    return ", ".join(sorted({".".join(str(p) for p in err["loc"]) or "input" for err in e.errors()}))[:300]


class DigiLockerAdapter:
    def __init__(self, runtime: Runtime | None = None):
        self.runtime = runtime or Runtime(session_factory=SessionLocal)

    def configure(
        self,
        *,
        documents: DocumentStore | None = None,
        http_factory: Callable[[], httpx.Client] | None = None,
        mock: MockDigiLocker | None = None,
    ) -> None:
        if documents is not None:
            self.runtime.documents = documents
        if http_factory is not None:
            self.runtime.http_factory = http_factory
        if mock is not None:
            self.runtime.mock = mock

    # ------------------------------------------------------------ registration

    def describe(self) -> dict:
        return {
            "adapter": "digilocker",
            "version": __version__,
            "ports": [PORT],
            "providers": [
                {
                    "provider": "digilocker",
                    "title": "DigiLocker",
                    "ports": ["certificate-issuance"],
                    "modes": ["mock", "sandbox", "live"],
                    "auth": "oauth2_authorization_code",
                    "link_scope": "person",
                    "inbound": ["provider_request"],
                    "settings_schema": ConnectionSettings.model_json_schema(),
                    "credential_names": ["issuer_api_key", "push_client_id", "push_client_secret"],
                    "platform_credential_names": [
                        "DIGILOCKER_REQUESTER_CLIENT_ID",
                        "DIGILOCKER_REQUESTER_CLIENT_SECRET",
                    ],
                }
            ],
        }

    # ------------------------------------------------------------ operations

    def invoke(self, operation: str, context: dict | Context, input: dict | None = None) -> dict:  # noqa: A002
        try:
            ctx = context if isinstance(context, Context) else Context.model_validate(context)
        except ValidationError as e:
            return {"error": AdapterError("invalid_request", f"invalid context: {_fields(e)}").to_dict()}
        try:
            output, reference = self._dispatch(operation, ctx, input or {})
        except AdapterError as e:
            return {"error": e.to_dict()}
        except ValidationError as e:
            return {"error": AdapterError("invalid_request", f"invalid input: {_fields(e)}").to_dict()}
        except Exception:  # a bug here must not become the hub's 500; it is logged and retried
            log.exception("digilocker %s failed", operation)
            return {"error": AdapterError("provider_error", "internal error in the DigiLocker adapter").to_dict()}
        result: dict = {"output": output}
        if reference:
            result["provider_reference"] = reference
        return result

    def _dispatch(self, operation: str, ctx: Context, raw: dict) -> tuple[dict, str | None]:
        rt = self.runtime
        if operation in OPERATIONS:
            model, handler = OPERATIONS[operation]
            return handler(rt, ctx, model.model_validate(raw))
        if operation == "capabilities":
            return self._capabilities(ctx), None
        if operation == "healthcheck":
            return self._healthcheck(ctx), None
        if operation == "verify_inbound":
            # DigiLocker sends no webhooks: its requests are answered by handle_provider_request.
            return {"verdict": "reject", "reject_status": 401}, None
        if operation == "parse_inbound":
            return {"notifications": []}, None
        if operation == "handle_provider_request":
            body = raw.get("raw_body")
            if isinstance(body, str):
                body = body.encode()
            if not isinstance(body, bytes | bytearray) or not isinstance(raw.get("channel"), str):
                raise AdapterError("invalid_request", "channel and raw_body are required")
            return pull.handle_provider_request(rt, ctx, raw["channel"], bytes(body)), None
        raise AdapterError("unsupported", f"digilocker has no operation {operation}")

    def _capabilities(self, ctx: Context) -> dict:
        cfg = self.runtime.config()
        settings = ConnectionSettings.model_validate(ctx.settings) if ctx.settings else None
        requester = cfg.requester(ctx.mode) is not None or ctx.mode == "mock"
        return {
            "port": "certificate-issuance",
            "capabilities": {
                "push_to_holder": bool(settings and settings.push_enabled and ctx.secrets.get("push_client_id")),
                "pull_on_demand": True,
                "replace_in_place": True,
                "holder_consent_fetch": requester,
                "doc_types": [
                    {"doc_kind": d.doc_kind, "provider_doc_type": d.doc_type}
                    for d in (settings.doc_types if settings else [])
                ],
                "max_document_bytes": cfg.max_document_bytes,
            },
        }

    def _healthcheck(self, ctx: Context) -> dict:
        cfg = self.runtime.config()
        if ctx.mode == "mock":
            return {"status": "healthy", "detail": "mock mode: no DigiLocker is called", "expires_at": None}
        try:
            self.runtime.require_mode(ctx, cfg)
            settings = ConnectionSettings.model_validate(ctx.settings)
        except (AdapterError, ValidationError):
            return {
                "status": "auth_failed",
                "detail": "the connection's settings or the deployment's URL are missing",
                "expires_at": None,
            }
        if not ctx.secrets.get("issuer_api_key"):
            return {"status": "auth_failed", "detail": "issuer_api_key is not set", "expires_at": None}
        if settings.push_enabled and not (ctx.secrets.get("push_client_id") and ctx.secrets.get("push_client_secret")):
            return {"status": "auth_failed", "detail": "push is enabled without push credentials", "expires_at": None}
        try:
            self.runtime.client(ctx, cfg).http.get(cfg.base_url(ctx.mode), timeout=float(cfg.http_timeout_s))
        except (httpx.HTTPError, AdapterError):
            return {"status": "unreachable", "detail": "DigiLocker did not answer", "expires_at": None}
        # DigiLocker documents no read-only authenticated call for an issuer, so credentials are not exercised here.
        return {
            "status": "healthy",
            "detail": "DigiLocker is reachable; credentials are checked on first use",
            "expires_at": None,
        }


_adapter: DigiLockerAdapter | None = None


def get_adapter() -> DigiLockerAdapter:
    """Entry point `eos.integration_adapters` -> digilocker."""
    global _adapter
    if _adapter is None:
        _adapter = DigiLockerAdapter()
    return _adapter
