"""Module settings from KNOWLEDGE_BASE_* environment keys (config/env.example). Read on every call so a deployment or
a test can change them without restarting the module. A bad value is a deployment error (ValueError), never a domain
error that an API layer could report to a caller as their own invalid request."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_REVIEW_MONTHS_KEY = "KNOWLEDGE_BASE_DEFAULT_REVIEW_MONTHS"
TOP_ARTICLES_LIMIT_KEY = "KNOWLEDGE_BASE_TOP_ARTICLES_LIMIT"
HELPFUL_MIN_VOTES_KEY = "KNOWLEDGE_BASE_HELPFUL_MIN_VOTES"

# Defaults are the values in config/env.example.
DEFAULT_DEFAULT_REVIEW_MONTHS = 12
DEFAULT_TOP_ARTICLES_LIMIT = 10
DEFAULT_HELPFUL_MIN_VOTES = 5

# GET /stats/top-articles: limit is between 1 and 50 (contract).
MIN_TOP_LIMIT, MAX_TOP_LIMIT = 1, 50
MAX_REVIEW_MONTHS = 120
MAX_MIN_VOTES = 10000


@dataclass(frozen=True)
class ModuleSettings:
    default_review_months: int
    top_articles_limit: int
    helpful_min_votes: int


def _whole(key: str, default: int, low: int, high: int) -> int:
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        raise ValueError(f"{key} must be a whole number, got {raw!r}") from None
    if not low <= value <= high:
        raise ValueError(f"{key} must be between {low} and {high}, got {raw!r}")
    return value


def load_settings() -> ModuleSettings:
    return ModuleSettings(
        default_review_months=_whole(DEFAULT_REVIEW_MONTHS_KEY, DEFAULT_DEFAULT_REVIEW_MONTHS, 1, MAX_REVIEW_MONTHS),
        top_articles_limit=_whole(TOP_ARTICLES_LIMIT_KEY, DEFAULT_TOP_ARTICLES_LIMIT, MIN_TOP_LIMIT, MAX_TOP_LIMIT),
        helpful_min_votes=_whole(HELPFUL_MIN_VOTES_KEY, DEFAULT_HELPFUL_MIN_VOTES, 1, MAX_MIN_VOTES),
    )
