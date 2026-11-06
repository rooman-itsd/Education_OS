"""Module-local configuration: GOVERNMENT_PORTALS_*, documented in config/env.example. Read from the environment on
every call so a test or a redeploy never sees a stale value. This adapter holds no credentials of any kind."""

from __future__ import annotations

import os
from dataclasses import dataclass

# The format cycles this release knows. A cycle not listed here is refused, never replaced by last year's format
# (docs/prd.md, "Forms catalogue"). A new cycle is a new adapter release with golden files.
SUPPORTED_FORMATS: dict[str, tuple[str, ...]] = {
    "aishe": ("2025-26",),
    "nirf": ("2026",),
    "naac": ("2025",),
}


def _int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.environ.get(name, "")
    try:
        value = int(raw) if raw.strip() else default
    except ValueError:
        value = default
    return max(value, minimum)


@dataclass(frozen=True)
class Settings:
    aishe_format: str
    nirf_format: str
    naac_format: str
    max_evidence_file_bytes: int
    max_package_bytes: int

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            aishe_format=os.environ.get("GOVERNMENT_PORTALS_AISHE_FORMAT", "2025-26").strip(),
            nirf_format=os.environ.get("GOVERNMENT_PORTALS_NIRF_FORMAT", "2026").strip(),
            naac_format=os.environ.get("GOVERNMENT_PORTALS_NAAC_FORMAT", "2025").strip(),
            max_evidence_file_bytes=_int("GOVERNMENT_PORTALS_MAX_EVIDENCE_FILE_BYTES", 5_242_880),
            max_package_bytes=_int("GOVERNMENT_PORTALS_MAX_PACKAGE_BYTES", 524_288_000),
        )

    def format_for(self, authority: str) -> str:
        return {"aishe": self.aishe_format, "nirf": self.nirf_format, "naac": self.naac_format}[authority]

    def supported(self, authority: str) -> bool:
        return self.format_for(authority) in SUPPORTED_FORMATS[authority]
