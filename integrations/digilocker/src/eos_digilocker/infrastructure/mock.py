"""Mock mode: a stateful stand-in for DigiLocker's issuer and requester APIs that answers in the shapes of the
Requester API Specification v1.12 (docs/prd.md, "Sandbox and mock"). It runs behind httpx.MockTransport, so mock
mode and the tests make no network call. It checks what DigiLocker checks: the Push URI HMAC and the age of ts,
PKCE S256 on the token exchange, a bearer token on the file APIs, and the file HMAC it sends back.

Not a sandbox: it proves the adapter's own logic and wire format, not DigiLocker's behaviour. Until sandbox access
is granted, treat the field names marked in docs/prd.md as "not verified" as assumptions."""

from __future__ import annotations

import base64
import hashlib
import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import parse_qs, unquote

import httpx

from ..domain.rules import file_hmac, push_hmac

PUSH_ORDER = ["clientid", "digilockerid", "uri", "doctype", "description", "docid", "issuedate", "validfrom",
              "validto", "action", "ts"]  # fmt: skip
STALE_AFTER_S = 1800  # DigiLocker refuses a ts older than 30 minutes


def _json(status: int, body: dict) -> httpx.Response:
    return httpx.Response(status, json=body)


def _form(request: httpx.Request) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(request.content.decode()).items()}


class MockDigiLocker:
    def __init__(self, *, strict: bool = False, clock: Callable[[], datetime] = lambda: datetime.now(UTC)):
        self.strict = strict  # strict: only registered clients are known; otherwise the first secret seen is trusted
        self.clock = clock
        self.clients: dict[str, str] = {}
        self.accounts: dict[str, str] = {}  # mobile -> DigiLocker id
        self.pushed: dict[str, dict] = {}  # uri -> {action, digilockerid, ...}
        self.holders: dict[str, dict[str, dict]] = {}  # DigiLocker id -> {uri: {meta..., content}}
        self.codes: dict[str, dict] = {}  # authorization code -> {challenge, digilockerid, client_id}
        self.tokens: dict[str, dict] = {}  # access token -> {digilockerid, client_id}
        self.refresh: dict[str, dict] = {}
        self.revoked: list[str] = []
        self.requests: list[httpx.Request] = []
        self.corrupt_file_hmac = False
        self.fail_with: int | None = None  # answer every request with this HTTP status

    # ------------------------------------------------------------ test and dev helpers

    def register_client(self, client_id: str, client_secret: str) -> None:
        self.clients[client_id] = client_secret

    def add_account(self, mobile: str, digilocker_id: str) -> None:
        self.accounts[mobile] = digilocker_id
        self.holders.setdefault(digilocker_id, {})

    def add_file(self, digilocker_id: str, uri: str, content: bytes, *, doctype: str, issuer: str, issuerid: str,
                 description: str = "", date: str = "08/02/2019 11:32:15") -> None:  # fmt: skip
        self.holders.setdefault(digilocker_id, {})[uri] = {
            "content": content,
            "meta": {
                "name": description or uri,
                "type": "file",
                "size": str(len(content)),
                "date": date,
                "parent": "",
                "mime": ["application/pdf"],
                "uri": uri,
                "doctype": doctype,
                "description": description,
                "issuerid": issuerid,
                "issuer": issuer,
            },
        }

    def grant_code(self, digilocker_id: str, client_id: str, code_challenge: str) -> str:
        """What the person's browser does at DigiLocker: log in, consent, and come back with a code."""
        code = secrets.token_urlsafe(16)
        self.codes[code] = {"challenge": code_challenge, "digilockerid": digilocker_id, "client_id": client_id}
        return code

    # ------------------------------------------------------------ the transport

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler))

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail_with:
            return _json(self.fail_with, {"error": "mock_failure"})
        path = request.url.path
        route = path.split("/public", 1)[-1] if "/public" in path else path
        if route == "/account/1/pushuri" and request.method == "POST":
            return self._push(request)
        if route == "/account/2/verify" and request.method == "POST":
            return self._verify(request)
        if route == "/oauth2/1/token" and request.method == "POST":
            return self._token(request)
        if route == "/oauth2/1/revoke" and request.method == "POST":
            return self._revoke(request)
        if route == "/oauth2/2/files/issued" and request.method == "GET":
            return self._issued(request)
        if route == "/oauth2/1/pull/pulldocument" and request.method == "POST":
            return self._pull(request)
        if route.startswith("/oauth2/1/file/") and request.method == "GET":
            return self._file(request, unquote(route.removeprefix("/oauth2/1/file/")))
        return _json(404, {"error": "unknown_route"})

    def _push(self, request: httpx.Request) -> httpx.Response:
        f = _form(request)
        client_id = f.get("clientid", "")
        secret = self.clients.get(client_id)
        if secret is None:
            return _json(401, {"error": "invalid_client"})
        expected = push_hmac(secret, [f.get(k, "") for k in PUSH_ORDER])
        if f.get("hmac") != expected:
            return _json(401, {"error": "invalid_hmac"})
        try:
            age = self.clock().timestamp() - int(f["ts"])
        except (KeyError, ValueError):
            return _json(400, {"error": "invalid_ts"})
        if age > STALE_AFTER_S or age < -STALE_AFTER_S:
            return _json(400, {"error": "invalid_ts"})
        if f.get("action") not in ("A", "U", "D") or not f.get("uri") or not f.get("digilockerid"):
            return _json(400, {"error": "invalid_request"})
        self.pushed[f["uri"]] = {k: f.get(k, "") for k in PUSH_ORDER}
        return httpx.Response(200)

    def _verify(self, request: httpx.Request) -> httpx.Response:
        f = _form(request)
        secret = self.clients.get(f.get("clientid", ""))
        if secret is None:
            return _json(401, {"error": "invalid_client"})
        if f.get("hmac") != push_hmac(secret, [f.get("clientid", ""), f.get("mobile", ""), f.get("ts", "")]):
            return _json(401, {"error": "invalid_hmac"})
        account = self.accounts.get(f.get("mobile", ""))
        return _json(200, {"status": "found", "digilockerid": account} if account else {"status": "notfound"})

    def _issue_tokens(self, digilocker_id: str, client_id: str) -> dict:
        access, refresh = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
        self.tokens[access] = {"digilockerid": digilocker_id, "client_id": client_id}
        self.refresh[refresh] = {"digilockerid": digilocker_id, "client_id": client_id}
        # The real response also carries the person's name, date of birth and an Aadhaar flag; the adapter drops them.
        return {
            "access_token": access,
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "",
            "refresh_token": refresh,
            "digilockerid": digilocker_id,
            "name": "Mock Holder",
            "dob": "01012000",
            "gender": "M",
            "eaadhaar": "N",
            "new_account": "N",
            "reference_key": secrets.token_hex(8),
        }

    def _token(self, request: httpx.Request) -> httpx.Response:
        f = _form(request)
        client_id = f.get("client_id", "")
        secret = self.clients.get(client_id)
        if secret is None or f.get("client_secret") != secret:
            return _json(401, {"error": "invalid_client"})
        if f.get("grant_type") == "authorization_code":
            grant = self.codes.pop(f.get("code", ""), None)
            if grant is None or grant["client_id"] != client_id:
                return _json(400, {"error": "invalid_grant"})
            verifier = f.get("code_verifier", "")
            digest = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            if digest != grant["challenge"]:
                return _json(400, {"error": "invalid_grant"})
            return _json(200, self._issue_tokens(grant["digilockerid"], client_id))
        if f.get("grant_type") == "refresh_token":
            grant = self.refresh.pop(f.get("refresh_token", ""), None)
            if grant is None or grant["client_id"] != client_id:
                return _json(400, {"error": "invalid_grant"})
            return _json(200, self._issue_tokens(grant["digilockerid"], client_id))
        return _json(400, {"error": "unsupported_grant_type"})

    def _revoke(self, request: httpx.Request) -> httpx.Response:
        f = _form(request)
        secret = self.clients.get(f.get("client_id", ""))
        if secret is None or f.get("client_secret") != secret:
            return _json(401, {"error": "invalid_client"})
        token = f.get("token", "")
        self.tokens.pop(token, None)
        self.refresh.pop(token, None)
        self.revoked.append(token)
        return httpx.Response(200, json={})

    def _holder(self, request: httpx.Request) -> tuple[str, dict] | None:
        auth = request.headers.get("authorization", "")
        grant = self.tokens.get(auth.removeprefix("Bearer ").strip()) if auth.startswith("Bearer ") else None
        return (grant["digilockerid"], grant) if grant else None

    def _issued(self, request: httpx.Request) -> httpx.Response:
        holder = self._holder(request)
        if holder is None:
            return _json(401, {"error": "invalid_token"})
        return _json(200, {"items": [f["meta"] for f in self.holders.get(holder[0], {}).values()]})

    def _file(self, request: httpx.Request, uri: str) -> httpx.Response:
        holder = self._holder(request)
        if holder is None:
            return _json(401, {"error": "invalid_token"})
        found = self.holders.get(holder[0], {}).get(uri)
        if found is None:
            return _json(404, {"error": "not_found"})
        client_secret = self.clients[holder[1]["client_id"]]
        mac = file_hmac(client_secret, found["content"])
        if self.corrupt_file_hmac:
            mac = "0" * 64
        return httpx.Response(200, content=found["content"], headers={"content-type": "application/pdf", "hmac": mac})

    def _pull(self, request: httpx.Request) -> httpx.Response:
        holder = self._holder(request)
        if holder is None:
            return _json(401, {"error": "invalid_token"})
        f = _form(request)
        for uri, found in self.holders.get(holder[0], {}).items():
            if found["meta"]["doctype"] == f.get("doctype") and found["meta"]["issuerid"] == f.get("orgid"):
                return _json(200, {"uri": uri})
        return _json(404, {"error": "not_found"})
