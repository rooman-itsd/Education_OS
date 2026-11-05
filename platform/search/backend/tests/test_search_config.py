"""Configuration: the in-memory fake is refused outside dev mode, secrets are required there, bounds only lower."""

import pytest
from eos_search.infrastructure.config import DEV_CURSOR_SECRET, SearchConfig
from eos_search.infrastructure.engine import create_engine
from eos_search.infrastructure.memory_engine import InMemoryEngine


def test_dev_defaults_run_on_the_memory_engine():
    config = SearchConfig.from_env().validate()
    assert config.engine == "memory" and config.cursor_secret == DEV_CURSOR_SECRET and config.dev_mode
    assert isinstance(create_engine(), InMemoryEngine)


def test_the_memory_engine_is_refused_when_dev_mode_is_off(monkeypatch):
    monkeypatch.setenv("EOS_DEV_MODE", "false")
    with pytest.raises(RuntimeError, match="memory"):
        create_engine()


def test_outside_dev_mode_a_cursor_secret_is_required(monkeypatch):
    monkeypatch.setenv("EOS_DEV_MODE", "false")
    monkeypatch.setenv("SEARCH_ENGINE", "opensearch")
    with pytest.raises(RuntimeError, match="SEARCH_CURSOR_SECRET"):
        SearchConfig.from_env().validate()
    monkeypatch.setenv("SEARCH_CURSOR_SECRET", "short")
    with pytest.raises(RuntimeError, match="SEARCH_CURSOR_SECRET"):
        SearchConfig.from_env().validate()
    monkeypatch.setenv("SEARCH_CURSOR_SECRET", "s" * 32)
    assert SearchConfig.from_env().validate().cursor_secret == "s" * 32


@pytest.mark.parametrize("key, value", [("SEARCH_ENGINE", "solr"), ("SEARCH_JOB_RUNNER", "cron")])
def test_unknown_choices_are_refused(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(RuntimeError, match=key):
        SearchConfig.from_env().validate()


def test_bounds_can_be_lowered_but_not_raised_and_garbage_falls_back(monkeypatch):
    monkeypatch.setenv("SEARCH_MAX_QUERY_LENGTH", "50")
    monkeypatch.setenv("SEARCH_MAX_PAGE_SIZE", "500")
    monkeypatch.setenv("SEARCH_CURSOR_TTL_SECONDS", "not-a-number")
    monkeypatch.setenv("SEARCH_INDEX_RETRY_BACKOFF_SECONDS", "nope")
    monkeypatch.setenv("SEARCH_INDEX_ATTEMPTS", "-3")
    config = SearchConfig.from_env()
    assert config.max_query_length == 50 and config.max_page_size == 50
    assert config.cursor_ttl_seconds == 300 and config.index_retry_backoff_seconds == 0.2 and config.index_attempts == 1
