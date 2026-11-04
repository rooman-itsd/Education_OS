"""Domain rules without a database: states, slugs, dates, the category tree, search and top articles."""

from datetime import date

import pytest
from eos_knowledge_base.domain import articles as rules
from eos_knowledge_base.domain import categories as tree
from eos_knowledge_base.domain import search
from eos_knowledge_base.domain.errors import DomainRuleError
from eos_knowledge_base.domain.stats import Candidate, top_articles


def code(fn, *args) -> tuple[str, str]:
    with pytest.raises(DomainRuleError) as e:
        fn(*args)
    return e.value.code, e.value.kind


def test_revision_moves():
    assert rules.submit("draft") == "in_review"
    assert code(rules.submit, "in_review") == ("no_open_draft", "conflict")
    assert code(rules.submit, None) == ("no_open_draft", "conflict")
    assert rules.give_back("in_review") == "draft"
    assert code(rules.give_back, "draft") == ("no_revision_in_review", "conflict")
    assert rules.discard("draft") == rules.discard("in_review") == "discarded"
    assert code(rules.discard, None) == ("no_open_revision", "conflict")


def test_draft_editing_rules():
    rules.check_draft_editable(None, 3)  # a new draft from revision 3
    rules.check_draft_editable("draft", None)
    assert code(rules.check_draft_editable, "in_review", None) == ("revision_in_review", "conflict")
    assert code(rules.check_draft_editable, "draft", 2) == ("draft_open", "conflict")
    assert code(rules.check_complete, {"type": "faq", "title": "Q?"}) == ("content_fields_required", "invalid")


def test_article_moves():
    rules.check_publishable("draft", "draft")
    rules.check_publishable("published", "in_review")
    assert code(rules.check_publishable, "archived", "draft") == ("article_archived", "conflict")
    assert code(rules.check_publishable, "published", None) == ("no_open_revision", "conflict")
    assert rules.archive("published") == rules.archive("draft") == "archived"
    assert code(rules.archive, "archived") == ("already_archived", "conflict")
    assert rules.restore("archived", True) == "published"
    assert rules.restore("archived", False) == "draft"
    assert code(rules.restore, "draft", False) == ("not_archived", "conflict")


def test_slugs():
    assert rules.slugify("  How do I reset my Wi-Fi password?  ") == "how-do-i-reset-my-wi-fi-password"
    assert rules.slugify("पासवर्ड") == "article"
    assert len(rules.slugify("a" * 300)) == rules.SLUG_MAX
    assert rules.with_suffix("wifi", 2) == "wifi-2"
    assert len(rules.with_suffix("a" * 120, 10)) == rules.SLUG_MAX


def test_add_months_clamps_to_the_month_and_the_calendar():
    assert rules.add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert rules.add_months(date(2026, 11, 4), 12) == date(2027, 11, 4)
    assert rules.add_months(date(9999, 6, 1), 12) == date.max


def test_stale_share_and_tags():
    assert rules.is_stale("published", date(2026, 1, 1), date(2026, 1, 2))
    assert not rules.is_stale("published", date(2026, 1, 2), date(2026, 1, 2))
    assert not rules.is_stale("draft", date(2020, 1, 1), date(2026, 1, 2))
    assert rules.helpful_share(0, 0) is None
    assert rules.helpful_share(3, 1) == 0.75
    assert rules.clean_tags([" WiFi", "wifi", "", "Network "]) == ["WiFi", "Network"]


def test_category_tree():
    top = tree.Node("t", None, "IT", 0)
    sub = tree.Node("s", "t", "Wi-Fi", 0)
    tree.check_parent(None, top, False)
    assert code(tree.check_parent, None, sub, False) == ("third_level", "conflict")
    assert code(tree.check_parent, "x", top, True) == ("third_level", "conflict")
    assert code(tree.check_parent, "t", top, False) == ("third_level", "conflict")
    assert code(tree.check_unique_name, " it ", [top]) == ("name_taken", "conflict")
    tree.check_unique_name("IT", [top], "t")  # renaming itself
    assert code(tree.check_deactivatable, 2) == ("category_in_use", "conflict")
    other = tree.Node("o", None, "Admissions", 0)
    assert [n.id for n in tree.tree_order([sub, top, other])] == ["o", "t", "s"]


def test_search_scores_and_snippets():
    words = search.terms("WiFi  wifi password")
    assert words == ["wifi", "password"]
    assert search.score(words, "WiFi help", None, "Reset the password", []) == 3 + 1
    assert search.score(words, "WiFi help", None, "nothing", []) == 0
    snip = search.snippet(["password"], "t", None, "x " * 200 + "reset the Password here" + " y" * 200)
    assert "**Password**" in snip and snip.startswith("…") and snip.endswith("…")
    assert search.snippet(["zzz"], "t", None, "body") is None


def test_top_articles_rankings():
    def c(i, views, h, n):
        return Candidate(i, i, f"T{i}", "faq", "c", "everyone", views, h, n)

    rows = [c("a", 5, 1, 0), c("b", 9, 4, 1), c("c", 0, 9, 1), c("d", 9, 0, 6)]
    assert [x["article_id"] for x in top_articles(rows, "views", 10, 5)] == ["b", "d", "a"]
    assert [x["article_id"] for x in top_articles(rows, "helpful", 10, 5)] == ["c", "b", "d"]
    assert len(top_articles(rows, "views", 1, 5)) == 1
