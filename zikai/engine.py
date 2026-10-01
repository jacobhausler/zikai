"""The decision engine: walk the shallow tree, hydrate the winner.

Flow: text -> Q1 theme -> Q2 cluster -> intra-cluster ranking (lexical
score against the cluster's idioms; the decider model only makes the two
routing calls, the final pick is a scoring problem with the full record
available). Depth is capped at MAX_TREE_DEPTH by tree law.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid

from .adapters import BaseAdapter, Lexical, _cgram_sim, resolve_adapter
from .config import Settings
from .tree import MAX_TREE_DEPTH, Record, dice, load_json, _words


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
        path: list[dict] = []

        # Q1: theme
        q1_opts = self.tree["root"]["options"]
        d1 = adapter.decide(text, self.tree["root"]["question"], q1_opts)
        if d1.value not in self._by_id or d1.value is None:
            d1 = self.lexical.decide(text, self.tree["root"]["question"],
                                     q1_opts)
            if d1.value not in self._by_id:
                d1.value = sorted(self._by_id)[0]
                d1.adapter = d1.adapter or "lexical-default"
        theme_opt = self._by_id[d1.value]
        path.append({"node": "q1.theme", "question": self.tree["root"]["question"],
                     "answer": d1.value, "adapter": d1.adapter,
                     "latency_ms": d1.latency_ms, "error": d1.error})

        # Q2: cluster within the theme
        cl_opts = theme_opt["cluster_options"]
        d2 = adapter.decide(text, theme_opt["cluster_question"], cl_opts)
        valid = {o["value"] for o in cl_opts}
        if d2.value not in valid:
            d2 = self.lexical.decide(text, theme_opt["cluster_question"],
                                     cl_opts)
            if d2.value not in valid:
                d2.value = sorted(valid)[0]
        path.append({"node": "q2.cluster", "question": theme_opt["cluster_question"],
                     "answer": d2.value, "adapter": d2.adapter,
                     "latency_ms": d2.latency_ms, "error": d2.error})

        # final pick = retrieve-then-rerank: the two routing questions above
        # are guidance (provenance, boosts), but the shortlist is retrieved
        # over the WHOLE corpus — a slightly-off routing answer must never
        # evict the right idiom before the decider ever sees it. Remote
        # adapters get one recall hop (semantic keyword expansion of the
        # input) that widens the retrieval query; one rerank call over the
        # top candidates is a scoring stage, not a tree level.
        keywords: list[str] = []
        if adapter.name != "lexical":
            try:
                keywords = adapter.expand(text)[:10]
            except Exception:  # noqa: BLE001 — recall hop is optional
                keywords = []
        query = text if not keywords else text + " " + " ".join(keywords)
        members = self.tree["clusters"][d2.value]["idioms"]
        theme_boost = {s for cid in theme_opt["clusters_ref"]
                       for s in self.tree["clusters"][cid]["idioms"]}
        ranked_global = self._rank(query, list(self.corpus),
                                   boost=theme_boost | set(members))
        winner_slug, confidence, ranked = self._final_pick(
            text, adapter, ranked_global, members)
        runner_ups = [s for s, _ in ranked[1:4]]

        out = {
            "id": f"dec_{uuid.uuid4().hex[:12]}",
            "input_digest": hashlib.sha256(text.encode()).hexdigest()[:16],
            "decision_path": path,
            "depth": min(len(path), MAX_TREE_DEPTH),
            "cluster": d2.value,
            "theme": theme_opt["label"],
            "confidence": confidence,
            "runner_ups": runner_ups,
            "decider": adapter.name if not any(p["error"] for p in path)
                       else f"{adapter.name}+fallback",
            "latency_ms": int((time.time() - t0) * 1000),
        }
        record = dict(self.corpus.get(winner_slug, {"slug": winner_slug}))
        record["_rank_pool"] = {"cluster": d2.value, "pool_size": len(members),
                                "rank": 1 if ranked else 0}
        out["idiom"] = record
        if trace:
            out["trace"] = [{"slug": s, "score": round(sc, 3)}
                            for s, sc in ranked[:8]]
        return out

    # ------------------------------------------------------------------
    def _final_pick(self, text: str, adapter: BaseAdapter,
                    ranked: list[tuple[str, float]],
                    members: list[str]) -> tuple[str, float, list]:
        """Final pick = lexical shortlist, then (remote adapters only) ONE
        rerank call over the top candidates. This is a scoring stage, not a
        tree level — decision depth stays capped at MAX_TREE_DEPTH."""
        if not ranked:
            return (members[0] if members else ""), 0.0, []
        shortlist = ranked[:12]
        if adapter.name == "lexical" or getattr(adapter, "name", "") == "lexical":
            return shortlist[0][0], round(shortlist[0][1], 3), ranked
        opts = []
        for slug, score in shortlist:
            r = self.corpus.get(slug, {})
            opts.append({
                "value": slug,
                "label": f"{r.get('hanzi','')} {r.get('pinyin','')} — {r.get('meaning','')}",
                "hint": f"literal: {r.get('literal') or r.get('meaning')}",
            })
        d = adapter.decide(
            text,
            "Which single idiom best fits the INPUT? Judge by meaning fit, "
            "not word overlap. Answer with ONLY the slug value.", opts)
        if d.value and d.value in {s for s, _ in shortlist}:
            # rerank winner first, keep the rest for runner-ups
            reordered = [t for t in shortlist if t[0] == d.value] + \
                        [t for t in shortlist if t[0] != d.value]
            conf = max(round(shortlist[0][1], 3), 0.45)
            self._last_rerank = d
            return d.value, conf, reordered + ranked[len(shortlist):]
        self._last_rerank = d
        return shortlist[0][0], round(shortlist[0][1], 3), ranked

    # ------------------------------------------------------------------
    def _rank(self, text: str, slugs: list[str],
              boost: set[str] | None = None) -> list[tuple[str, float]]:
        tw, tc = _words(text), _chargrams(text)
        scored = []
        for s in slugs:
            r = self.corpus.get(s, {})
            blob = " ".join(str(r.get(k) or "") for k in
                            ("meaning", "literal", "meaning_metaphoric",
                             "theme", "origin"))
            score = (0.5 * dice(tw, _words(blob))
                     + 0.3 * _cgram_sim(tc, blob)
                     + (0.15 if s in text.lower() else 0.0)
                     + (0.05 if boost and s in boost else 0.0))
            scored.append((s, score))
        scored.sort(key=lambda t: (-t[1], t[0]))
        return scored


def load_engine(settings: Settings) -> Engine:
    corpus = load_json(settings.corpus_path)
    tree = load_json(settings.tree_path)
    from .adapters import build_adapters
    return Engine(corpus, tree, settings, build_adapters(settings))


def _chargrams(s: str) -> set[str]:
    s = re.sub(r"\s+", " ", s.lower())
    return {s[i:i + 3] for i in range(len(s) - 2)}
