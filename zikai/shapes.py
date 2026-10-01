"""Response shaping — one hydrator, several verbosity levels.

  level=full     complete hydrated record (+requested extras)
  level=compact  the decision essentials + one-line meaning
  level=text     a single formatted sentence/line for chat UIs
  level=slug     just the pinyin slug (machine-to-machine)
"""
from __future__ import annotations

CORE = ("slug", "hanzi", "pinyin", "meaning", "theme", "url")
META = ("term_code", "literal", "meaning_metaphoric", "origin",
        "example_en", "example_zh", "related", "faq", "title",
        "date_modified")


def hydrate(record: dict, level: str = "full",
           extras: list[str] | None = None,
           related_resolved: bool = False, corpus: dict | None = None
           ) -> dict:
    """Pick fields by level; extras force-include specific meta fields."""
    level = (level or "full").lower()
    extras = set(extras or [])
    if level == "slug":
        return {"slug": record.get("slug")}
    if level == "text":
        return {"text": format_line(record)}
    out: dict = {k: record.get(k) for k in CORE if record.get(k) is not None}
    if level == "compact":
        out["confidence_hint"] = record.get("_rank_pool")
        for e in extras:
            if e in record:
                out[e] = record[e]
        return out
    # full
    for k in META:
        if record.get(k) is not None:
            out[k] = record[k]
    for e in extras:
        if e in record:
            out[e] = record[e]
    if related_resolved and corpus:
        out["related_idioms"] = [
            {k: corpus.get(s, {}).get(k) for k in ("slug", "hanzi", "meaning")}
            for s in (record.get("related") or [])[:5] if s in corpus]
    return out


def format_line(record: dict) -> str:
    hanzi = record.get("hanzi") or ""
    py = record.get("pinyin") or ""
    meaning = record.get("meaning") or ""
    slug = record.get("slug") or ""
    if hanzi:
        return f"{hanzi} ({py}) — {meaning} [{slug}]"
    return f"{meaning} [{slug}]"
