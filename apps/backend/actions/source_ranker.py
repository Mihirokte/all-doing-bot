"""Source ranking and confidence for evidence-first deep search responses."""
from __future__ import annotations

import re
from typing import Any, List, Tuple

# Entry-like: has content, source (url), optional metadata
EntryLike = Any


def _domain(url: str) -> str:
    if not url or not url.strip():
        return ""
    s = url.strip().lower()
    for prefix in ("https://", "http://", "//"):
        if s.startswith(prefix):
            s = s[len(prefix) :].lstrip("/")
            break
    return s.split("/")[0].split(":")[0] if s else ""


def score_entry(entry: EntryLike, query: str) -> float:
    """
    Score a single entry by relevance, freshness cues, and content completeness.
    Higher is better.
    """
    content = (getattr(entry, "content", "") or "").strip()
    source = (getattr(entry, "source", "") or "").strip()
    if not content and not source:
        return 0.0

    score = 0.0
    q_lower = query.lower()
    words = [w for w in re.split(r"[\s,]+", q_lower) if len(w) > 1]

    # Relevance: query terms in content/source
    combined = (content + " " + source).lower()
    for w in words[:10]:
        if w in combined:
            score += 1.0
    if words:
        score += 2.0 * (min(len(words), 5) / 5.0)

    # Content completeness: longer substantive content
    content_len = len(content)
    if content_len >= 500:
        score += 2.0
    elif content_len >= 200:
        score += 1.0
    elif content_len >= 80:
        score += 0.5

    # Freshness cues in text
    freshness = ("2025", "2026", "today", "recent", "latest", "new", "announced", "released")
    if any(c in combined for c in freshness):
        score += 1.0

    # Has valid URL
    if source.startswith("http"):
        score += 1.0

    return max(0.0, score)


def rank_entries(entries: List[EntryLike], query: str, top_n: int = 5) -> List[Tuple[EntryLike, float]]:
    """Score and rank entries; return top_n (entry, score) sorted by score descending."""
    scored = [(e, score_entry(e, query)) for e in entries]
    scored.sort(key=lambda x: -x[1])
    return scored[:top_n]


def confidence_from_scores(scores: List[float], min_evidence: int = 2) -> str:
    """
    Compute confidence level from list of evidence scores.
    Returns 'high' | 'medium' | 'low'.
    """
    if not scores:
        return "low"
    n = len(scores)
    avg = sum(scores) / n
    strong = sum(1 for s in scores if s >= 4.0)

    if n >= min_evidence and (avg >= 4.0 or strong >= 2):
        return "high"
    if n >= 1 and avg >= 2.0:
        return "medium"
    return "low"


def evidence_bullets(ranked: List[Tuple[EntryLike, float]], max_bullets: int = 5) -> List[Tuple[str, str]]:
    """
    From ranked (entry, score) list, produce (claim, url) bullets for evidence-first response.
    claim = short one-line summary from content/title; url = source.
    """
    bullets: List[Tuple[str, str]] = []
    seen_urls: set[str] = set()

    for entry, _ in ranked[:max_bullets]:
        content = (getattr(entry, "content", "") or "").strip()
        source = (getattr(entry, "source", "") or "").strip()
        if not source or source in seen_urls:
            continue
        seen_urls.add(source)

        # Extract title from content (e.g. **title**\n\nsnippet)
        claim = content
        if content.startswith("**") and "**" in content[2:]:
            end = content.find("**", 2)
            title = content[2:end].strip()
            rest = content[end + 2 :].strip().lstrip("\n")
            if title:
                claim = title
            if rest and len(rest) > 20:
                snippet = " ".join(rest.split())[:120].rstrip()
                if snippet:
                    claim = claim + " — " + snippet if claim != title else snippet
        else:
            claim = " ".join(content.split())[:150].rstrip()
        if not claim:
            claim = source
        bullets.append((claim, source))

    return bullets
