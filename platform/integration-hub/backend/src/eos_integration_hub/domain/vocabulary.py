"""The hub's fixed vocabulary, as contracts/openapi.yaml and contracts/ports/adapter.yaml define it. Tests compare
every tuple here with the contract, so a change starts in the contract."""

from __future__ import annotations

import re

MODULE = "integration-hub"

PORTS = (
    "certificate-issuance",
    "academic-records",
    "regulatory-submission",
    "meetings",
    "wearable-data",
    "inter-institution-records",
)
MODES = ("mock", "sandbox", "live")
CREATE_MODES = ("mock", "sandbox")  # live is reached through POST /connections/{id}/mode
HEALTH_STATUSES = ("not_checked", "healthy", "degraded", "unreachable", "auth_failed")
CHECK_STATUSES = ("healthy", "degraded", "unreachable", "auth_failed")  # what an adapter's healthcheck may answer
LINK_STATUSES = ("pending", "active", "expired", "revoked", "error")
DELIVERY_STATUSES = (
    "queued",
    "in_progress",
    "succeeded",
    "retry_scheduled",
    "failed",
    "dead_lettered",
    "manual_action_required",
    "rejected_inbound",
)
AUTH_KINDS = (
    "none",
    "api_key",
    "oauth2_client_credentials",
    "oauth2_authorization_code",
    "jwt_shared_secret",
    "hmac_shared_secret",
)
LINK_SCOPES = ("organisation", "person")
INBOUND_KINDS = ("webhook", "provider_request")
DIRECTIONS = ("outbound", "inbound")
CREDENTIAL_SOURCES = ("admin", "oauth")

# contracts/ports/adapter.yaml error_codes: one vocabulary for every adapter, each with a fixed retryable flag.
ERROR_CODES: dict[str, bool] = {
    "not_configured": False,
    "auth_failed": False,
    "consent_required": False,
    "invalid_request": False,
    "not_found": False,
    "conflict": False,
    "rejected": False,
    "unsupported": False,
    "manual_action_required": False,
    "throttled": True,
    "transport_unavailable": True,
    "provider_error": True,
}

# Bounds on what the API and the adapters hand us, so bad input is a 4xx or a recorded error, never a 500.
NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,60}$")  # adapter and provider ids
CREDENTIAL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
CHANNEL_RE = re.compile(r"^[a-z][a-z0-9-]{1,40}$")
CONNECTION_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")
OPERATION_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
CALLER_MODULE_RE = re.compile(r"^[a-z][a-z0-9-]{1,60}$")
MAX_DISPLAY_NAME = 120
MAX_REASON = 500
MAX_PURPOSE = 200
MAX_URL = 2048
MAX_CREDENTIAL_VALUE = 16384
MAX_IDEMPOTENCY_KEY = 200
MAX_CALLER_REFERENCE = 200
MAX_PROVIDER_REFERENCE = 200
MAX_DEDUPE_KEY = 200
MAX_DETAIL = 500
MAX_SUBJECT = 200
