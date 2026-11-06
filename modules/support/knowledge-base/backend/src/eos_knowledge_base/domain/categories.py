"""Category tree rules (PRD flow 1): two levels only, names unique among siblings, a category holding published articles
cannot be deactivated. Pure Python."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import DomainRuleError


@dataclass(frozen=True)
class Node:
    id: str
    parent_id: str | None
    name: str
    position: int


def check_parent(category_id: str | None, parent: Node | None, has_children: bool) -> None:
    """409 when the result would have a third level: the parent is itself a sub-category, or a category that has
    sub-categories is moved under another one. A category cannot be its own parent."""
    if parent is None:
        return
    if category_id is not None and parent.id == category_id:
        raise DomainRuleError("third_level", "a category cannot be its own parent", kind="conflict", field="parent_id")
    if parent.parent_id is not None:
        raise DomainRuleError(
            "third_level", "the parent is itself a sub-category; only two levels", kind="conflict", field="parent_id"
        )
    if has_children:
        raise DomainRuleError(
            "third_level",
            "a category with sub-categories cannot become a sub-category; only two levels",
            kind="conflict",
            field="parent_id",
        )


def check_unique_name(name: str, siblings: list[Node], category_id: str | None = None) -> None:
    """409 "Name already used under this parent" (ignoring case and surrounding spaces)."""
    key = name.strip().casefold()
    if any(s.name.strip().casefold() == key and s.id != category_id for s in siblings):
        raise DomainRuleError(
            "name_taken", "a category with this name exists under this parent", kind="conflict", field="name"
        )


def check_deactivatable(published_articles: int) -> None:
    """409 "Category holds published articles" (a top-level category counts its sub-categories' articles too)."""
    if published_articles:
        raise DomainRuleError(
            "category_in_use", f"the category holds {published_articles} published article(s)", kind="conflict"
        )


def tree_order(nodes: list[Node]) -> list[Node]:
    """Display order: top-level categories by position then name, each followed by its sub-categories in the same
    order. A sub-category whose parent is not in `nodes` follows the top level."""
    key = lambda n: (n.position, n.name.casefold(), n.id)  # noqa: E731
    ids = {n.id for n in nodes}
    tops = sorted((n for n in nodes if n.parent_id is None), key=key)
    out: list[Node] = []
    for top in tops:
        out.append(top)
        out.extend(sorted((n for n in nodes if n.parent_id == top.id), key=key))
    out.extend(sorted((n for n in nodes if n.parent_id is not None and n.parent_id not in ids), key=key))
    return out
