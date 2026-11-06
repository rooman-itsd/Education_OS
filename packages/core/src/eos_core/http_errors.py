"""Shared HTTP error behaviour, installed once by the host app (`install_error_handlers`) so every module gets it.

FastAPI answers a failed validation with a 422 whose `detail` quotes the offending input back. Python's JSON parser
accepts `NaN`, `Infinity`, `-Infinity` and numbers too big for a float (`1e999`, read as infinity), and a string
can hold a lone surrogate ("\\ud800"); the response writer then cannot encode those values and the request ends in a
500. The handler below answers such a request with the same 422 and the same `detail` shape, quoting the offending
value as text instead. Any other validation error is answered exactly as FastAPI would."""

from __future__ import annotations

import math
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _bad_text(s: str) -> bool:
    try:
        s.encode("utf-8")
    except UnicodeEncodeError:
        return True
    return False


def _clean(value: Any) -> Any:
    """`value` with every non-finite float and every unencodable string replaced by its text (repr), recursively."""
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, str):
        return value if not _bad_text(value) else value.encode("unicode_escape").decode("ascii")
    if isinstance(value, dict):
        return {_clean(k) if isinstance(k, str) else k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    return value


async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    detail = jsonable_encoder(exc.errors())
    try:
        return JSONResponse(status_code=422, content={"detail": detail})
    except (ValueError, UnicodeEncodeError):
        return JSONResponse(status_code=422, content={"detail": _clean(detail)})


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, request_validation_handler)
