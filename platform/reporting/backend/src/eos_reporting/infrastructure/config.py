"""Configuration loader for reporting service."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ReportingSettings:
    execution_retention_days: int = 90
    max_page_size: int = 100
    seed_standard_reports: bool = True


def load_settings() -> ReportingSettings:
    """Load reporting settings from environment variables."""
    return ReportingSettings(
        execution_retention_days=int(os.environ.get("REPORTING_EXECUTION_RETENTION_DAYS", "90")),
        max_page_size=int(os.environ.get("REPORTING_MAX_PAGE_SIZE", "100")),
        seed_standard_reports=os.environ.get("REPORTING_SEED_STANDARD_REPORTS", "true").lower() in ("true", "1", "yes"),
    )
