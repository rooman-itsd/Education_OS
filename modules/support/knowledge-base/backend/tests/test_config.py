"""KNOWLEDGE_BASE_* settings (config/env.example): defaults, overrides and refused values."""

from pathlib import Path

import pytest
from eos_knowledge_base.infrastructure import config


def test_defaults_are_the_env_example_values(monkeypatch):
    example = Path(__file__).resolve().parents[2] / "config" / "env.example"
    values = dict(
        line.split("=", 1)
        for line in example.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "=" in line
    )
    for key in values:
        monkeypatch.delenv(key, raising=False)
    s = config.load_settings()
    assert s.default_review_months == int(values[config.DEFAULT_REVIEW_MONTHS_KEY])
    assert s.top_articles_limit == int(values[config.TOP_ARTICLES_LIMIT_KEY])
    assert s.helpful_min_votes == int(values[config.HELPFUL_MIN_VOTES_KEY])


def test_overrides(monkeypatch):
    monkeypatch.setenv(config.DEFAULT_REVIEW_MONTHS_KEY, " 6 ")
    monkeypatch.setenv(config.TOP_ARTICLES_LIMIT_KEY, "50")
    monkeypatch.setenv(config.HELPFUL_MIN_VOTES_KEY, "1")
    s = config.load_settings()
    assert (s.default_review_months, s.top_articles_limit, s.helpful_min_votes) == (6, 50, 1)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        (config.DEFAULT_REVIEW_MONTHS_KEY, "soon"),
        (config.DEFAULT_REVIEW_MONTHS_KEY, "0"),
        (config.DEFAULT_REVIEW_MONTHS_KEY, "121"),
        (config.TOP_ARTICLES_LIMIT_KEY, "51"),
        (config.HELPFUL_MIN_VOTES_KEY, "0"),
    ],
)
def test_bad_values_are_deployment_errors(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match=key):
        config.load_settings()
