"""DigiLocker's HTTP APIs: Push URI and account verify (issuer), and the Requester OAuth and file APIs. Paths and
fields follow the Requester API Specification v1.12 as cited in docs/prd.md. The HTTP client is injected, so tests
and mock mode never touch the network. Provider text never leaves this module: failures become AdapterError with
the contract's code and DigiLocker's own machine code as provider_code."""

from __future__ import annotations

import hmac
import re
from collections.abc import Callable
from datetime import UTC, date, datetime
from urllib.parse import quote, urlencode

import httpx

from ..domain.errors import AdapterError
from ..domain.rules import file_hmac, push_hmac

STALE_TS_CODES = {"invalid_ts", "stale_ts", "ts_expired", "timestamp_expired"}
_CODE = re.compile(r"^[A-Za-z0-9_.-]{1,40}$")
MAX_RETRY_AFTER_S = 3600


def ddmmyyyy(value: date | None) -> str:
    return value.strftime("%d%m%Y") if value else ""


def _provider_code(response: httpx.Response) -> str:
    """DigiLocker's own error code when the body carries a well-formed one, else the HTTP status."""
    try:
        body = response.json()
        code = body.get("error") if isinstance(body, dict) else None
    except ValueError:
        code = None
    return code if isinstance(code, str) and _CODE.match(code) else str(response.status_code)


def raise_for_response(response: httpx.Response, *, token_call: bool = False) -> None:
    """The PRD's error mapping. token_call: a 401 on a call made with a person's token means their consent is gone
    (expired or revoked) rather than that our credentials are wrong."""
    status = response.status_code
    if status < 400:
        return
    code = _provider_code(response)
    if code in STALE_TS_CODES:
        raise AdapterError("provider_error", "DigiLocker refused the timestamp as stale", provider_code=code)
    if status in (401, 403):
        if token_call:
            raise AdapterError("consent_required", "the person's DigiLocker consent has expired", provider_code=code)
        raise AdapterError("auth_failed", "DigiLocker refused the credentials", provider_code=code)
    if status == 404:
        raise AdapterError("not_found", "DigiLocker has no such document", provider_code=code)
    if status == 429:
        try:
            after = min(max(int(response.headers.get("retry-after", "")), 1), MAX_RETRY_AFTER_S)
        except ValueError:
            after = None
        raise AdapterError("throttled", "DigiLocker rate limited the request", provider_code=code, retry_after_s=after)
    if status >= 500:
        raise AdapterError("provider_error", "DigiLocker failed to answer", provider_code=code)
    raise AdapterError("invalid_request", "DigiLocker refused the request as invalid", provider_code=code)


class DigiLockerClient:
    def __init__(
        self,
        http: httpx.Client,
        base_url: str,
        *,
        timeout_s: float = 15.0,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        push_max_age_s: int = 60,
    ):
        self.http = http
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.clock = clock
        self.push_max_age_s = push_max_age_s

    def _send(self, method: str, path: str, *, timeout_s: float | None = None, **kwargs) -> httpx.Response:
        try:
            return self.http.request(method, f"{self.base_url}{path}", timeout=timeout_s or self.timeout_s, **kwargs)
        except httpx.InvalidURL as e:
            raise AdapterError("invalid_request", "the request URL is not valid") from e
        except httpx.HTTPError as e:  # timeouts, connection and TLS failures
            raise AdapterError(
                "transport_unavailable", "DigiLocker is unreachable", provider_code=type(e).__name__
            ) from e

    # ------------------------------------------------------------ issuer: Push URI and account verify

    def push_uri(
        self,
        *,
        client_id: str,
        client_secret: str,
        digilocker_id: str,
        uri: str,
        doc_type: str,
        description: str,
        doc_id: str,
        issue_date: date,
        valid_from: date | None,
        valid_to: date | None,
        action: str,
    ) -> None:
        """POST /account/1/pushuri. The request is signed with a fresh ts; one that took longer than
        push_max_age_s to build and send is refused here rather than by DigiLocker."""
        built = self.clock()
        fields = {
            "clientid": client_id,
            "digilockerid": digilocker_id,
            "uri": uri,
            "doctype": doc_type,
            "description": description,
            "docid": doc_id,
            "issuedate": ddmmyyyy(issue_date),
            "validfrom": ddmmyyyy(valid_from),
            "validto": ddmmyyyy(valid_to),
            "action": action,
            "ts": str(int(built.timestamp())),
        }
        fields["hmac"] = push_hmac(client_secret, [fields[k] for k in fields])
        if (self.clock() - built).total_seconds() > self.push_max_age_s:
            raise AdapterError("provider_error", "the push request went stale before it was sent")
        raise_for_response(self._send("POST", "/account/1/pushuri", data=fields))

    def find_account(self, *, client_id: str, client_secret: str, mobile: str) -> str | None:
        """POST /account/2/verify: the DigiLocker id for a mobile number, or None when there is no account. The
        number is sent once and never kept."""
        ts = str(int(self.clock().timestamp()))
        fields = {"clientid": client_id, "mobile": mobile, "ts": ts}
        fields["hmac"] = push_hmac(client_secret, [fields[k] for k in fields])
        response = self._send("POST", "/account/2/verify", data=fields)
        raise_for_response(response)
        try:
            body = response.json()
        except ValueError as e:
            raise AdapterError("provider_error", "DigiLocker answered with something unreadable") from e
        account = body.get("digilockerid") if isinstance(body, dict) else None
        found = isinstance(body, dict) and str(body.get("status", "")).lower() in ("1", "found", "true", "y")
        if found and isinstance(account, str) and re.fullmatch(r"[A-Za-z0-9._-]{1,100}", account):
            return account
        return None

    # ------------------------------------------------------------ requester: OAuth

    def authorize_url(self, params: dict[str, str]) -> str:
        return f"{self.base_url}/oauth2/1/authorize?{urlencode(params)}"

    def _json(self, response: httpx.Response, *, token_call: bool = False) -> dict:
        raise_for_response(response, token_call=token_call)
        try:
            body = response.json()
        except ValueError as e:
            raise AdapterError("provider_error", "DigiLocker answered with something unreadable") from e
        if not isinstance(body, dict):
            raise AdapterError("provider_error", "DigiLocker answered with something unexpected")
        return body

    def token(self, data: dict[str, str]) -> dict:
        """POST /oauth2/1/token (authorization_code or refresh_token grant)."""
        response = self._send("POST", "/oauth2/1/token", data=data)
        code = _provider_code(response)
        if response.status_code in (400, 401) and code != "invalid_client":
            # a refused code or refresh token: the person must consent again
            raise AdapterError("consent_required", "DigiLocker refused the code or refresh token", provider_code=code)
        return self._json(response)

    def revoke(self, data: dict[str, str]) -> None:
        raise_for_response(self._send("POST", "/oauth2/1/revoke", data=data))

    # ------------------------------------------------------------ requester: files

    def files_issued(self, access_token: str) -> list[dict]:
        response = self._send("GET", "/oauth2/2/files/issued", headers={"Authorization": f"Bearer {access_token}"})
        items = self._json(response, token_call=True).get("items", [])
        return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []

    def pull_document(self, access_token: str, params: dict[str, str]) -> str:
        """POST /oauth2/1/pull/pulldocument: ask the issuer for a document by search parameters, with the consent
        text DigiLocker shows the person. Returns the URI."""
        response = self._send(
            "POST", "/oauth2/1/pull/pulldocument", data=params, headers={"Authorization": f"Bearer {access_token}"}
        )
        uri = self._json(response, token_call=True).get("uri")
        if not isinstance(uri, str) or not uri:
            raise AdapterError("not_found", "the issuer returned no document for that search")
        return uri

    def file(self, access_token: str, uri: str, client_secret: str, max_bytes: int) -> tuple[bytes, bool]:
        """GET /oauth2/1/file/{uri}. Returns (content, integrity_verified). The HMAC header is the SHA-256 HMAC of
        the content keyed by our client secret; a file without it, or with a wrong one, is never kept."""
        response = self._send(
            "GET", f"/oauth2/1/file/{quote(uri, safe='')}", headers={"Authorization": f"Bearer {access_token}"}
        )
        raise_for_response(response, token_call=True)
        content = response.content
        if len(content) > max_bytes:
            raise AdapterError("invalid_request", "the document is larger than this deployment accepts")
        presented = (response.headers.get("hmac") or "").strip().lower()
        if not presented or not hmac.compare_digest(file_hmac(client_secret, content), presented):
            raise AdapterError(
                "provider_error", "the document failed DigiLocker's integrity check", provider_code="hmac_mismatch"
            )
        return content, True
