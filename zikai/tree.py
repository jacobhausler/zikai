"""Corpus + shallow clustered decision tree.

The tree is deliberately SHALLOW (max 2 decider questions + 1 final pick
inside a cluster) — every extra level is a latency tax and an error
multiplication; a decider model at each level is only worth it while each
question genuinely halves the field. Data facts, not vibes, set the
clusters: they are built from the corpus itself and rebuilt nightly.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

MAX_TREE_DEPTH = 2  # law: theme question, cluster question (final pick is intra-cluster ranking, not a tree level)


def _stem(w: str) -> str:
    for suf in ("ies", "es", "s", "ing", "ed", "ly", "ment", "ness"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            base = w[:-len(suf)]
            if suf == "ies":
                base += "y"
            return base
    return w


def _words(s: str | None) -> set[str]:
    if not s:
        return set()
    s = s.lower()
    s = re.sub(r"[^a-z\s'\-]", " ", s)
    return {_stem(w) for w in s.split()
            if len(w) > 2 and _stem(w) not in _STOP}


_STOP = set(
    "the a an and or of to in is are was were it its this that with for from "
    "when you your their his her who whom what which does did have has had not "
    "about into over under more most some such other others being been they them "
    "there here than then both each can could will would shall should may might "
    "must because while where before after above below up down out off very too "
    "also only just then through during between because people person one two "
    "something someone something nothing everything means meaning phrase used "
    "idiom chinese say saying describes describe situation situations".split())


def dice(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return 2 * len(a & b) / (len(a) + len(b))


class Record(dict):
    __getattr__ = dict.get


def load_records(path: str | Path) -> list[Record]:
    out: dict[str, Record] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        # last write wins: nightly appends refreshed records for changed slugs
        if r.get("ok") and r.get("slug"):
            out[r["slug"]] = Record(r)
    return list(out.values())


def build_corpus(records: list[Record]) -> dict:
    """Flat slug->record corpus plus a lexical index for the fallback decider."""
    corpus: dict[str, dict] = {}
    for r in records:
        corpus[r["slug"]] = {k: v for k, v in r.items() if k != "ok"}
    return corpus


def _tokens_for(r: dict) -> set[str]:
    return _words(r.get("meaning")) | _words(r.get("literal")) | _words(
        (r.get("origin") or "")[:400]) | _words(r.get("meaning_metaphoric"))


def _label_cluster(rows: list[dict], taken: set[str]) -> tuple[str, list[str]]:
    freq: dict[str, int] = {}
    toks = {r["slug"]: _tokens_for(r) for r in rows}
    for r in rows:
        for w in toks[r["slug"]]:
            freq[w] = freq.get(w, 0) + 1
    top = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    label_words = [w for w, c in top[:3] if c >= 2] or [w for w, _ in top[:3]]
    for w in label_words:
        taken.add(w)
    core = set(label_words)
    exemplars = sorted(rows, key=lambda r: (-len(toks[r["slug"]] & core),
                                            r["slug"]))[:2]
    return ", ".join(label_words), [r["slug"] for r in exemplars]


def build_tree(corpus: dict[str, dict]) -> dict:
    """theme -> clusters -> idioms. Deterministic; no RNG."""
    themes: dict[str, list[dict]] = {}
    for slug, r in corpus.items():
        themes.setdefault(r.get("theme") or "Uncategorized", []).append(
            {"slug": slug, **r})
    for t in themes:
        themes[t].sort(key=lambda r: r["slug"])  # determinism

    tree = {
        "version": 1,
        "max_depth": MAX_TREE_DEPTH,
        "root": {
            "id": "q0.theme",
            "kind": "question",
            "question": ("Which domain of life does the input text mainly "
                         "deal with? Pick the single closest option."),
            "options": [],
        },
        "clusters": {},
    }

    for theme, rows in sorted(themes.items()):
        key = re.sub(r"[^a-z0-9]+", "-", theme.lower()).strip("-")
        clusters = _cluster_theme(rows)
        taken: set[str] = set()
        opts = []
        for ci, members in enumerate(clusters):
            label, exemplars = _label_cluster(members, taken)
            cid = f"{key}--c{ci}"
            tree["clusters"][cid] = {
                "theme": theme,
                "idioms": [m["slug"] for m in
                           sorted(members, key=lambda r: r["slug"])],
            }
            opts.append({
                "value": cid,
                "label": label or f"{theme} cluster {ci}",
                "hint": "; ".join(
                    f"{m.get('meaning')}" for m in exemplars_slugs(
                        exemplars, corpus, 2)),
                "exemplars": exemplars,
            })
        tree["root"]["options"].append({
            "value": key,
            "label": theme,
            "hint": f"{len(rows)} idioms",
            "clusters_ref": [o["value"] for o in opts],
            "cluster_question": (
                f"Within “{theme}”, which situation is closest to the input?"),
            "cluster_options": opts,
        })
    return tree


def exemplars_slugs(slugs: list[str], corpus: dict, n: int) -> list[dict]:
    out = []
    for s in slugs[:n]:
        r = corpus.get(s)
        if r:
            out.append({"slug": s, "meaning": r.get("meaning")})
    return out


def _cluster_theme(rows: list[dict]) -> list[list[dict]]:
    """Deterministic clustering; target 10-25 idioms per cluster so the Q2
    option list stays decidable for a small model."""
    k = max(3, min(9, round(len(rows) / 15) or 3))
    return _greedy_cluster(rows, k)


def _greedy_cluster(rows: list[dict], k: int) -> list[list[dict]]:
    """Deterministic greedy centroid clustering over word-set vectors."""
    rows = sorted(rows, key=lambda r: r["slug"])
    toks = {r["slug"]: _tokens_for(r) for r in rows}
    # seeds: farthest-point traversal (deterministic tiebreak by slug)
    seeds: list[dict] = [rows[0]]
    while len(seeds) < min(k, len(rows)):
        best, best_d = None, -1.0
        for r in rows:
            if any(r is s for s in seeds):
                continue
            d = min(dice(toks[r["slug"]], toks[s["slug"]]) for s in seeds)
            if d > best_d + 1e-9:
                best, best_d = r, d
        seeds.append(best)
    buckets: dict[int, list[dict]] = {i: [] for i in range(len(seeds))}
    for r in rows:
        best_i, best_score = 0, -1.0
        for i, s in enumerate(seeds):
            d = dice(toks[r["slug"]], toks[s["slug"]])
            if d > best_score:
                best_i, best_score = i, d
        buckets[best_i].append(r)
    return [b for b in buckets.values() if b]


def save_json(obj, path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8")


def load_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
