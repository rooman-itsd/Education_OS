"""Pure rules: bounded JSON, the subset of JSON Schema a provider's settings_schema uses, retry backoff and PKCE.
No framework imports."""

from __future__ import annotations

import base64
import hashlib
import json
import math
import random
import re
from datetime import datetime, timedelta

MAX_SETTINGS_BYTES = 16_384
MAX_JSON_DEPTH = 6
MAX_SCHEMA_PATTERN = 200


class RuleError(ValueError):
    """Input that breaks a rule. `code` is the contract's error code; the message names the field, never a value."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def check_json(value, *, what: str, code: str = "invalid_settings", max_bytes: int = MAX_SETTINGS_BYTES) -> None:
    """Plain, finite, bounded JSON: no NaN or Infinity, at most MAX_JSON_DEPTH deep, at most max_bytes encoded."""

    def walk(v, depth: int) -> None:
        if depth > MAX_JSON_DEPTH:
            raise RuleError(code, f"{what} is nested too deeply")
        if isinstance(v, dict):
            for k, inner in v.items():
                if not isinstance(k, str) or len(k) > 100:
                    raise RuleError(code, f"{what} has a key that is not a short string")
                walk(inner, depth + 1)
        elif isinstance(v, list):
            for inner in v:
                walk(inner, depth + 1)
        elif isinstance(v, float):
            if not math.isfinite(v):
                raise RuleError(code, f"{what} holds a number that is not finite")
        elif v is not None and not isinstance(v, str | int | bool):
            raise RuleError(code, f"{what} must be plain JSON")

    walk(value, 0)
    try:
        size = len(json.dumps(value, allow_nan=False).encode())
    except (TypeError, ValueError) as e:
        raise RuleError(code, f"{what} must be plain JSON") from e
    if size > max_bytes:
        raise RuleError(code, f"{what} is larger than {max_bytes} bytes")


_TYPES = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, int | float) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
    "null": lambda v: v is None,
}


def validate_schema(value, schema: dict | None, path: str = "settings") -> None:
    """The subset of JSON Schema a settings_schema needs: type (one or a list), enum, const, required, properties,
    additionalProperties (bool or schema), items, minLength, maxLength, pattern, minimum, maximum, minItems,
    maxItems. Anything else in the schema is ignored, so an adapter's richer schema still validates the common part.
    Raises RuleError("invalid_settings") naming the field."""
    if not isinstance(schema, dict) or not schema:
        return
    expected = schema.get("type")
    if expected is not None:
        names = expected if isinstance(expected, list) else [expected]
        if not any(_TYPES.get(n, lambda _v: True)(value) for n in names):
            raise RuleError("invalid_settings", f"{path} must be {' or '.join(map(str, names))}")
    if "enum" in schema and isinstance(schema["enum"], list) and value not in schema["enum"]:
        raise RuleError("invalid_settings", f"{path} is not one of the allowed values")
    if "const" in schema and value != schema["const"]:
        raise RuleError("invalid_settings", f"{path} is not the allowed value")
    if isinstance(value, str):
        if isinstance(schema.get("minLength"), int) and len(value) < schema["minLength"]:
            raise RuleError("invalid_settings", f"{path} is too short")
        if isinstance(schema.get("maxLength"), int) and len(value) > schema["maxLength"]:
            raise RuleError("invalid_settings", f"{path} is too long")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and len(pattern) <= MAX_SCHEMA_PATTERN:
            try:
                ok = re.search(pattern, value) is not None
            except re.error:
                ok = True  # a broken pattern in an adapter's schema is the adapter's bug, not the admin's
            if not ok:
                raise RuleError("invalid_settings", f"{path} does not have the expected format")
    if isinstance(value, int | float) and not isinstance(value, bool):
        if isinstance(schema.get("minimum"), int | float) and value < schema["minimum"]:
            raise RuleError("invalid_settings", f"{path} is below the minimum")
        if isinstance(schema.get("maximum"), int | float) and value > schema["maximum"]:
            raise RuleError("invalid_settings", f"{path} is above the maximum")
    if isinstance(value, list):
        if isinstance(schema.get("minItems"), int) and len(value) < schema["minItems"]:
            raise RuleError("invalid_settings", f"{path} has too few items")
        if isinstance(schema.get("maxItems"), int) and len(value) > schema["maxItems"]:
            raise RuleError("invalid_settings", f"{path} has too many items")
        if isinstance(schema.get("items"), dict):
            for i, item in enumerate(value):
                validate_schema(item, schema["items"], f"{path}[{i}]")
    if isinstance(value, dict):
        props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        for name in schema.get("required") or []:
            if name not in value:
                raise RuleError("invalid_settings", f"{path}.{name} is required")
        extra = schema.get("additionalProperties", True)
        for key, inner in value.items():
            if key in props:
                validate_schema(inner, props[key], f"{path}.{key}")
            elif extra is False:
                raise RuleError("invalid_settings", f"{path}.{key} is not a known setting")
            elif isinstance(extra, dict):
                validate_schema(inner, extra, f"{path}.{key}")


def backoff_s(attempt: int, *, base_s: int, max_s: int, retry_after_s: int | None = None, rng=random.random) -> int:
    """Exponential backoff with full jitter: uniform in [0, min(max_s, base_s * 2**(attempt-1))]. A provider's
    retry_after_s wins when it is longer. attempt is the attempt that just failed (1 on the first)."""
    exponent = min(max(attempt - 1, 0), 30)  # 2**30 * base is far past any cap; avoids huge integers
    ceiling = min(max_s, base_s * (2**exponent))
    delay = int(rng() * ceiling)
    if retry_after_s is not None and retry_after_s > delay:
        delay = min(retry_after_s, max_s)
    return max(delay, 1)


def next_attempt_at(now: datetime, delay_s: int) -> datetime:
    return now + timedelta(seconds=delay_s)


def fingerprint(value: str) -> str:
    """First 8 hex characters of the value's SHA-256: enough to tell two values apart, useless to recover one."""
    return hashlib.sha256(value.encode()).hexdigest()[:8]


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def pkce_challenge(verifier: str) -> str:
    """RFC 7636 S256: BASE64URL(SHA256(ASCII(code_verifier))) without padding."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
