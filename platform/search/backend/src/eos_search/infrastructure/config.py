"""Module-local configuration. Keys are SEARCH_*, documented in config/env.example. Read from the environment on
every call so a test or a redeploy never sees a stale value."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEV_CURSOR_SECRET = "dev-only-search-cursor-secret-do-not-use"
MIN_SECRET_LENGTH = 32
# Hard ceilings: the contract's bounds. Configuration may lower them, never raise them.
MAX_QUERY_LENGTH = 200
MAX_PAGE_SIZE = 50
MAX_CURSOR_TTL_SECONDS = 3600


def dev_mode() -> bool:
    return os.environ.get("EOS_DEV_MODE", "true").strip().lower() == "true"


def _int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError:
        value = default
    return min(max(value, minimum), maximum)


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    return default if not raw else raw in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class SearchConfig:
    engine: str
    opensearch_url: str
    opensearch_user: str
    opensearch_password: str
    opensearch_verify_certs: bool
    opensearch_timeout_seconds: int
    index_environment: str
    index_shards: int
    index_replicas: int
    max_query_length: int
    max_page_size: int
    cursor_ttl_seconds: int
    cursor_secret: str
    reindex_batch_size: int
    reindex_max_docs_per_second: int
    job_runner: str
    redis_url: str
    index_attempts: int
    index_retry_backoff_seconds: float
    job_stale_seconds: int
    dev_mode: bool

    @classmethod
    def from_env(cls) -> SearchConfig:
        env = os.environ.get
        dev = dev_mode()
        secret = env("SEARCH_CURSOR_SECRET", "").strip()
        try:
            backoff = min(max(float(env("SEARCH_INDEX_RETRY_BACKOFF_SECONDS", "0.2")), 0.0), 30.0)
        except ValueError:
            backoff = 0.2
        return cls(
            engine=env("SEARCH_ENGINE", "memory").strip().lower() or "memory",
            opensearch_url=env("SEARCH_OPENSEARCH_URL", "http://localhost:9200").strip(),
            opensearch_user=env("SEARCH_OPENSEARCH_USER", "").strip(),
            opensearch_password=env("SEARCH_OPENSEARCH_PASSWORD", ""),
            opensearch_verify_certs=_bool("SEARCH_OPENSEARCH_VERIFY_CERTS", True),
            opensearch_timeout_seconds=_int("SEARCH_OPENSEARCH_TIMEOUT_SECONDS", 2, 1, 30),
            index_environment=env("SEARCH_INDEX_ENVIRONMENT", "dev").strip() or "dev",
            index_shards=_int("SEARCH_INDEX_SHARDS", 1, 1, 20),
            index_replicas=_int("SEARCH_INDEX_REPLICAS", 1, 0, 5),
            max_query_length=_int("SEARCH_MAX_QUERY_LENGTH", MAX_QUERY_LENGTH, 1, MAX_QUERY_LENGTH),
            max_page_size=_int("SEARCH_MAX_PAGE_SIZE", MAX_PAGE_SIZE, 1, MAX_PAGE_SIZE),
            cursor_ttl_seconds=_int("SEARCH_CURSOR_TTL_SECONDS", 300, 10, MAX_CURSOR_TTL_SECONDS),
            cursor_secret=secret or (DEV_CURSOR_SECRET if dev else ""),
            reindex_batch_size=_int("SEARCH_REINDEX_BATCH_SIZE", 500, 1, 5000),
            reindex_max_docs_per_second=_int("SEARCH_REINDEX_MAX_DOCS_PER_SECOND", 2000, 1, 1_000_000),
            job_runner=env("SEARCH_JOB_RUNNER", "inline").strip().lower() or "inline",
            redis_url=env("SEARCH_REDIS_URL", "redis://localhost:6379/0").strip(),
            index_attempts=_int("SEARCH_INDEX_ATTEMPTS", 3, 1, 10),
            index_retry_backoff_seconds=backoff,
            job_stale_seconds=_int("SEARCH_JOB_STALE_SECONDS", 3600, 60, 86_400),
            dev_mode=dev,
        )

    def validate(self) -> SearchConfig:
        """Refuse to run misconfigured: the in-memory fake outside dev mode, an unknown engine, a missing or short
        cursor secret outside dev mode. Raises RuntimeError naming the key, never a value."""
        if self.engine not in ("memory", "opensearch"):
            raise RuntimeError("SEARCH_ENGINE must be memory or opensearch")
        if self.engine == "memory" and not self.dev_mode:
            raise RuntimeError(
                "SEARCH_ENGINE=memory is refused when EOS_DEV_MODE is false: set SEARCH_ENGINE=opensearch"
            )
        if not self.dev_mode and len(self.cursor_secret) < MIN_SECRET_LENGTH:
            raise RuntimeError(f"SEARCH_CURSOR_SECRET must be at least {MIN_SECRET_LENGTH} characters outside dev mode")
        if self.job_runner not in ("inline", "arq"):
            raise RuntimeError("SEARCH_JOB_RUNNER must be inline or arq")
        return self
