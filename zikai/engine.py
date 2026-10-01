"""The decision engine: walk the shallow tree, hydrate the winner.

Flow: text -> Q1 theme -> Q2 cluster -> retrieve-then-rerank pick. The two
routing questions are guidance (provenance + boost); the shortlist is
retrieved over the whole corpus so a wrong turn at Q2 can never evict the
right idiom before the decider sees it. Depth capped at MAX_TREE_DEPTH:
the rerank is a scoring stage, not a third question.
"""
from __future__ import annotations

import hashlib
import time
import uuid

from .adapters import BaseAdapter, Lexical, resolve_adapter
from .config import Settings
from .tree import MAX_TREE_DEPTH, cgram_sim, chargrams, dice, load_json, words


class Engine:
    def __init__(self, corpus: dict[str, dict], tree: dict,
                 settings: Settings, adapters: dict[str, BaseAdapter]):
        self.corpus = corpus
        self.tree = tree
        self.settings = settings
        self.adapters = adapters
        self.lexical: BaseAdapter = adapters.get("lexical") or Lexical()
        self._by_id = {o["value"]: o for o in tree["root"]["options"]}

    # ------------------------------------------------------------------
    def decide(self, text: str, decider: str | None = None,
               trace: bool = False) -> dict:
        t0 = time.time()
        adapter = resolve_adapter(decider, self.settings, self.adapters)

        theme_opt, d1 = self._route(
            text, adapter, self.tree["root"]["question"],
            self.tree["root"]["options"], self._by_id)
        cl_opts = theme_opt["cluster_options"]
        valid = {o["value"]: o for o in cl_opts}
        _cluster, d2 = self._route(
            text, adapter, theme_opt["cluster_question"], cl_opts, valid)

        members = self.tree["clusters"][d2["answer"]]["idioms"]
        boost = {s for cid in theme_opt["clusters_ref"]
                 for s in self.tree["clusters"][cid]["idioms"]} | set(members)
        ranked = self._candidates(text, adapter, boost)
        winner_slug, confidence, ranked = self._final_pick(
            text, adapter, ranked, members)

        out = {
            "id": f"dec_{uuid.uuid4().hex[:12]}",
            "input_digest": hashlib.sha256(text.encode()).hexdigest()[:16],
            "decision_path": [d1, d2],
            "depth": MAX_TREE_DEPTH,
            "cluster": d2["answer"],
            "theme": theme_opt["label"],
            "confidence": confidence,
            "runner_ups": [s for s, _ in ranked[1:4]],
            "decider": adapter.name if not (d1["error"] or d2["error"])
                       else f"{adapter.name}+fallback",
            "latency_ms": int((time.time() - t0) * 1000),
        }
        record = dict(self.corpus.get(winner_slug, {"slug": winner_slug}))
        record["_rank_pool"] = {"cluster": d2["answer"], "pool_size": len(members)}
        out["idiom"] = record
        if trace:
            out["trace"] = [{"slug": s, "score": round(sc, 3)}
                            for s, sc in ranked[:12]]
        return out

    # ------------------------------------------------------------------
    def _route(self, text, adapter, question, options, valid):
        """One routing node; a vendor sneeze degrades to lexical and never
        500s or derails."""
        d = adapter.decide(text, question, options)
        if d.value not in valid:
            d = self.lexical.decide(text, question, options)
            if d.value not in valid:
                d.value = sorted(valid)[0]
        return valid[d.value], {"question": question, "answer": d.value,
                                "adapter": d.adapter,
                                "latency_ms": d.latency_ms, "error": d.error}

    def _candidates(self, text: str, adapter: BaseAdapter,
                    boost: set[str], n: int = 16) -> list[tuple[str, float]]:
        """Shortlist = round-robin interleave of the RAW lexical rank and
        the keyword-EXPANDED rank (remote adapters only). The union can only
        add recall; a lucky expansion can never evict the raw winner. Merge
        order is kept — re-sorting by raw score sinks keyword-discovered
        candidates right back out of the shortlist."""
        ranks = [self._rank(text, boost=boost)]
        keywords: list[str] = []
        if adapter.name != "lexical":
            try:
                keywords = adapter.expand(text)[:10]
            except Exception:  # noqa: BLE001 — optional recall hop
                keywords = []
        if keywords:
            ranks.append(self._rank(
                text + " " + " ".join(keywords), boost=boost))
        merged: dict[str, float] = {}
        its = [iter(r) for r in ranks]
        while len(merged) < n:
            before = len(merged)
            for it in its:
                for s, sc in it:
                    if s not in merged:
                        merged[s] = sc
                        break
            if len(merged) == before:
                break
        return list(merged.items())

    def _final_pick(self, text: str, adapter: BaseAdapter,
                    ranked: list[tuple[str, float]],
                    members: list[str]) -> tuple[str, float, list]:
        """One rerank call over the shortlist (remote adapters only)."""
        if not ranked:
            return (members[0] if members else ""), 0.0, []
        shortlist = ranked[:12]
        if adapter.name == "lexical":
            return shortlist[0][0], round(shortlist[0][1], 3), ranked
        opts = [{"value": slug,
                 "label": f"{r.get('hanzi','')} {r.get('pinyin','')} — {r.get('meaning','')}",
                 "hint": f"literal: {r.get('literal') or r.get('meaning')}"}
                for slug, _ in shortlist if (r := self.corpus.get(slug))]
        d = adapter.decide(
            text,
            "Which single idiom best fits the INPUT? Judge by meaning fit, "
            "not word overlap. Answer with ONLY the slug value.", opts)
        if d.value in {s for s, _ in shortlist}:
            reordered = ([t for t in shortlist if t[0] == d.value]
                         + [t for t in shortlist if t[0] != d.value])
            return d.value, max(round(shortlist[0][1], 3), 0.45), \
                reordered + ranked[len(shortlist):]
        return shortlist[0][0], round(shortlist[0][1], 3), ranked

    # ------------------------------------------------------------------
    def _rank(self, text: str, boost: set[str] | None = None) -> list[tuple[str, float]]:
        tw, tc = words(text), chargrams(text)
        scored = []
        for s in self.corpus:
            r = self.corpus[s]
            blob = " ".join(str(r.get(k) or "") for k in
                            ("meaning", "literal", "meaning_metaphoric",
                             "theme", "origin"))
            score = (0.5 * dice(tw, words(blob))
                     + 0.3 * cgram_sim(tc, blob)
                     + (0.15 if s in text.lower() else 0.0)
                     + (0.05 if boost and s in boost else 0.0))
            scored.append((s, score))
        scored.sort(key=lambda t: (-t[1], t[0]))
        return scored


def load_engine(settings: Settings) -> Engine:
    from .adapters import build_adapters
    return Engine(load_json(settings.corpus_path),
                  load_json(settings.tree_path),
                  settings, build_adapters(settings))
