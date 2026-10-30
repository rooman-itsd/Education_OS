"""HTTP surface of contracts/openapi.yaml, mounted at /api/v1/messaging-providers.

apps/backend does not mount it yet: wiring a router into the host is the host's change, as it is for
payment-sbiepay.

POST /webhooks/{provider} is not served. The only provider is SMTP, and SMTP reports nothing by webhook, so there
is no vendor payload to verify or normalise until a provider that does (SES, SendGrid) exists.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..application import providers as service
from ..application.providers import OperatorError
from .deps import Principal, require

router = APIRouter(tags=["messaging-providers"])

READ = "messaging-providers:provider:read"
ADMIN = "platform:messaging-providers:admin"


class SendTestRequest(BaseModel):
    to: str = Field(min_length=1, max_length=320)  # RFC 5321's longest address


def _err(e: OperatorError) -> HTTPException:
    return HTTPException(e.status, str(e))


@router.get("/providers")
def list_providers(p: Principal = Depends(require(READ))):
    return service.list_providers()


@router.get("/providers/{provider}/health")
def provider_health(provider: str, p: Principal = Depends(require(READ))):
    try:
        return service.check_health(provider)
    except OperatorError as e:
        raise _err(e) from e


@router.post("/providers/{provider}/test", status_code=202)
def send_test_message(provider: str, body: SendTestRequest, p: Principal = Depends(require(ADMIN))):
    try:
        return service.send_test(provider, to=body.to, actor=p.user_id)
    except OperatorError as e:
        raise _err(e) from e
