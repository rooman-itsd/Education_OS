"""Module-local configuration: EXTERNAL_UNIVERSITY_PORTALS_*, documented in config/env.example. Read from the
environment on every call so a test or a redeploy never sees a stale value. Partners are integration-hub connections,
not configuration here."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass


def _int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, "")
    try:
        value = int(raw) if raw.strip() else default
    except ValueError:
        value = default
    return min(max(value, minimum), maximum)


@dataclass(frozen=True)
class Settings:
    link_ttl_hours: int
    max_import_bytes: int
    restricted_countries: frozenset[str]

    @classmethod
    def from_env(cls) -> Settings:
        raw = os.environ.get("EXTERNAL_UNIVERSITY_PORTALS_RESTRICTED_COUNTRIES", "")
        countries = frozenset(
            c for c in (x.strip().upper() for x in re.split(r"[,\s]+", raw)) if re.fullmatch(r"[A-Z]{2}", c)
        )
        return cls(
            link_ttl_hours=_int("EXTERNAL_UNIVERSITY_PORTALS_LINK_TTL_HOURS", 168, 1, 24 * 90),
            max_import_bytes=_int("EXTERNAL_UNIVERSITY_PORTALS_MAX_IMPORT_BYTES", 10_485_760, 1024, 104_857_600),
            restricted_countries=countries,
        )
