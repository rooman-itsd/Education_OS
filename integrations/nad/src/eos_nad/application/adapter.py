"""The adapter the hub finds through the `eos.integration_adapters` entry point (contracts/ports/adapter.yaml).

    adapter = get_adapter()
    adapter.describe()                                   # identity, written to the hub's adapter registry
    adapter.invoke("publish_awards", context, input)     # -> {"output": {...}, "provider_reference": "..."}
                                                         #  | {"error": {"code": ..., "retryable": ..., ...}}

`invoke` never raises: every failure is an error with one of the contract's codes. A pydantic failure becomes
invalid_request and names fields only (their values may be personal data). v1.0 has the manual channel only: neither
depository's API specification is public yet, so capabilities report every API flag false."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from eos_core.db import SessionLocal
from pydantic import BaseModel, ValidationError

from .. import __version__
from ..domain.errors import AdapterError
from ..infrastructure.config import KNOWN_TEMPLATE_VERSIONS
from ..infrastructure.documents import DocumentStore
from . import batches, submissions
from .runtime import Runtime
from .schemas import (
    MAX_RECORDS,
    ConnectionSettings,
    Context,
    CorrectAwardsInput,
    GetSubmissionInput,
    PublishAwardsInput,
    PublishCreditsInput,
    RecordUploadInput,
    VerifyInput,
)

log = logging.getLogger("eos.nad")

PORT = {"port": "academic-records", "version": 1}
Handler = Callable[[Runtime, Context, Any], tuple[dict, str | None]]

OPERATIONS: dict[str, tuple[type[BaseModel], Handler]] = {
    "verify_learner_id": (VerifyInput, submissions.verify_learner_id),
    "publish_awards": (PublishAwardsInput, batches.publish_awards),
    "correct_awards": (CorrectAwardsInput, batches.correct_awards),
    "publish_credits": (PublishCreditsInput, batches.publish_credits),
    "record_manual_upload": (RecordUploadInput, submissions.record_manual_upload),
    "get_submission": (GetSubmissionInput, submissions.get_submission),
}
# Neither depository calls back and neither has an OAuth link: these Adapter-contract operations do not apply.
NOT_APPLICABLE = (
    "begin_authorisation",
    "complete_authorisation",
    "refresh_authorisation",
    "revoke_authorisation",
    "handle_provider_request",
)


def _fields(e: ValidationError) -> str:
    return ", ".join(sorted({".".join(str(p) for p in err["loc"]) or "input" for err in e.errors()}))[:300]


class NadAdapter:
    def __init__(self, runtime: Runtime | None = None):
        self.runtime = runtime or Runtime(session_factory=SessionLocal)

    def configure(self, *, documents: DocumentStore | None = None) -> None:
        """What the SDK does not provide yet: platform/documents."""
        if documents is not None:
            self.runtime.documents = documents

    # ------------------------------------------------------------ registration

    def describe(self) -> dict:
        return {
            "adapter": "nad",
            "version": __version__,
            "ports": [PORT],
            "providers": [
                {
                    "provider": "nad",
                    "title": "National Academic Depository and Academic Bank of Credits",
                    "ports": ["academic-records"],
                    "modes": ["mock", "sandbox", "live"],
                    "auth": "none",  # v1.0: upload files only; the API's auth is fixed by its specification
                    "link_scope": "organisation",
                    "inbound": [],
                    "settings_schema": ConnectionSettings.model_json_schema(),
                    "credential_names": [],
                    "platform_credential_names": [],
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
            log.exception("nad %s failed", operation)
            return {"error": AdapterError("provider_error", "internal error in the NAD adapter").to_dict()}
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
            return self._capabilities(), None
        if operation == "healthcheck":
            return self._healthcheck(ctx), None
        if operation == "verify_inbound":
            return {"verdict": "reject", "reject_status": 401}, None  # nothing here is ever called by a depository
        if operation == "parse_inbound":
            return {"notifications": []}, None
        if operation in NOT_APPLICABLE:
            raise AdapterError("unsupported", f"nad does not offer {operation}")
        raise AdapterError("unsupported", f"nad has no operation {operation}")

    def _capabilities(self) -> dict:
        cfg = self.runtime.config()
        return {
            "port": "academic-records",
            "capabilities": {
                "awards_api": False,
                "credits_api": False,
                "learner_id_verification": False,
                "status_polling": False,
                "max_rows_per_batch": MAX_RECORDS,
                "max_rows_per_file": cfg.max_rows_per_file,
            },
        }

    def _healthcheck(self, ctx: Context) -> dict:
        cfg = self.runtime.config()
        try:
            settings = self.runtime.settings(ctx)
            self.runtime.require_mode(ctx, cfg)
        except AdapterError:
            return {"status": "degraded", "detail": "the connection's settings are invalid", "expires_at": None}
        if (
            cfg.awards_template_version not in KNOWN_TEMPLATE_VERSIONS["awards"]
            or cfg.credits_template_version not in KNOWN_TEMPLATE_VERSIONS["credits"]
        ):
            return {
                "status": "degraded",
                "detail": "an upload template version is not one this adapter writes",
                "expires_at": None,
            }
        if ctx.mode != "mock" and not settings.nad_institution_id and not settings.abc_institution_id:
            return {"status": "degraded", "detail": "no institution id is set for NAD or ABC", "expires_at": None}
        return {
            "status": "healthy",
            "detail": "manual channel: upload files are prepared, no depository API is called",
            "expires_at": None,
        }


_adapter: NadAdapter | None = None


def get_adapter() -> NadAdapter:
    """Entry point `eos.integration_adapters` -> nad."""
    global _adapter
    if _adapter is None:
        _adapter = NadAdapter()
    return _adapter
