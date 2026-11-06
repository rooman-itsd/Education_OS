"""Search over the module's own data (PRD open question 1: platform/search has no contract, so v1 searches here and
GET /articles?q= stays the module's search contract whatever engine comes later). Pure Python.

Every word of q must appear (ignoring case) in the title, summary, body or tags. Relevance weighs where the words
appear: title 3, tags 2, summary 2, body 1 per word. The snippet is plain text around the first match in the body
(or summary, or title), with the matched words wrapped in ** **, as Markdown bold; bodies are Markdown and HTML is
never rendered (PRD rule)."""

from __future__ import annotations

import re

SNIPPET_CHARS = 160
WEIGHTS = {"title": 3, "tags": 2, "summary": 2, "body": 1}


def terms(q: str) -> list[str]:
    """The distinct words of q, lowercased, in order."""
    seen: list[str] = []
    for word in q.casefold().split():
        if word not in seen:
            seen.append(word)
    return seen


def _fields(title: str, summary: str | None, body: str, tags: list[str]) -> dict[str, str]:
    return {
        "title": title.casefold(),
        "tags": " ".join(tags).casefold(),
        "summary": (summary or "").casefold(),
        "body": body.casefold(),
    }


def score(words: list[str], title: str, summary: str | None, body: str, tags: list[str]) -> int:
    """0 when any word is missing everywhere; otherwise the weighted relevance."""
    fields = _fields(title, summary, body, tags)
    total = 0
    for word in words:
        hit = sum(w for name, w in WEIGHTS.items() if word in fields[name])
        if not hit:
            return 0
        total += hit
    return total


def snippet(words: list[str], title: str, summary: str | None, body: str) -> str | None:
    """About SNIPPET_CHARS characters around the first match, with the words marked; None when nothing matches."""
    for text in (body, summary or "", title):
        low = text.casefold()
        positions = [low.find(w) for w in words if w in low]
        if not positions:
            continue
        start = max(0, min(positions) - SNIPPET_CHARS // 3)
        end = min(len(text), start + SNIPPET_CHARS)
        piece = " ".join(text[start:end].split())  # one line
        pattern = re.compile("|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)), re.IGNORECASE)
        piece = pattern.sub(lambda m: f"**{m.group(0)}**", piece)
        return ("…" if start > 0 else "") + piece + ("…" if end < len(text) else "")
    return None
