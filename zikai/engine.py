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
        winner_slug, confidence, ranked, judge_fell_back = self._final_pick(
            text, adapter, ranked, members)

        # The label stamps what RAN, not what was asked for (austin-exec
        # receipt, self-hosted chengyuserver): a remote adapter silently
        # replaced by lexical at any node is +fallback; a dropped rerank
        # judge is +judge_lexical. Green counter, honest message.
        label = adapter.name
        if judge_fell_back:
            label += "+judge_lexical"
        if d1["error"] or d2["error"] or d1["fell_back"] or d2["fell_back"]:
            label += "+fallback"     # ends +fallback: client's [lexical] holds

        out = {
            "id": f"dec_{uuid.uuid4().hex[:12]}",
            "input_digest": hashlib.sha256(text.encode()).hexdigest()[:16],
            "decision_path": [d1, d2],
            "depth": MAX_TREE_DEPTH,
            "cluster": d2["answer"],
            "theme": theme_opt["label"],
            "confidence": confidence,
            "runner_ups": [s for s, _ in ranked[1:4]],
            "decider": label,
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
        500s or derails. fell_back records the SILENT degrade — the model
        answered (no error) but its answer was unusable and lexical cooked
        instead; the decider label must not hide that (austin-exec find)."""
        d = adapter.decide(text, question, options)
        fell_back = False
        orig_err = d.error
        if d.value not in valid:
            fell_back = d.adapter != "lexical"
            d = self.lexical.decide(text, question, options)
            if d.value not in valid:
                d.value = sorted(valid)[0]
        return valid[d.value], {"question": question, "answer": d.value,
                                "adapter": d.adapter, "fell_back": fell_back,
                                "latency_ms": d.latency_ms,
                                "error": d.error or orig_err}

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
                    members: list[str]) -> tuple[str, float, list, bool]:
        """One rerank call over the shortlist (remote adapters only).
        Returns (slug, conf, ranked, judge_fell_back) — judge_fell_back is
        True only when the judge WAS asked and its answer was unusable;
        a by-design skip (dominant lexical signal) is not a degrade."""
        if not ranked:
            return (members[0] if members else ""), 0.0, [], False
        shortlist = ranked[:12]
        # A dominant lexical score (hanzi echo, exact slug, strong word
        # overlap) needs no judge — scores sit under ~0.2 without it, so 0.4
        # only fires on signals the decider could only contradict.
        if adapter.name == "lexical" or shortlist[0][1] >= 0.4:
            return shortlist[0][0], round(shortlist[0][1], 3), ranked, False
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
                reordered + ranked[len(shortlist):], False
        return shortlist[0][0], round(shortlist[0][1], 3), ranked, True

    # ------------------------------------------------------------------
    def _rank(self, text: str, boost: set[str] | None = None) -> list[tuple[str, float]]:
        tw, tc = words(text), chargrams(text)
        tl = text.lower()
        # CJK char-set overlap bridges hanzi-in-input echoes WITHOUT a
        # trad/simplified conversion table: shared characters score whether or
        # not the glyphs match exactly (刻舟求劍 echo vs 刻舟求剑 corpus).
        qcjk = {c for c in text if "\u4e00" <= c <= "\u9fff"}
        scored = []
        for s, r in self.corpus.items():
            blob = " ".join(str(r.get(k) or "") for k in
                            ("meaning", "literal", "meaning_metaphoric",
                             "theme", "origin", "example_en"))
            hz = r.get("hanzi")
            hz_bonus = 0.0
            if qcjk and hz:
                hzc = set(hz)
                hz_bonus = 0.8 * len(qcjk & hzc) / len(qcjk | hzc)
            score = (0.5 * dice(tw, words(blob))
                     + 0.3 * cgram_sim(tc, blob)
                     + hz_bonus
                     + (0.15 if s in tl else 0.0)
                     + (0.05 if boost and s in boost else 0.0))
            scored.append((s, score))
        scored.sort(key=lambda t: (-t[1], t[0]))
        return scored


def load_engine(settings: Settings) -> Engine:
    from .adapters import build_adapters
    return Engine(load_json(settings.corpus_path),
                  load_json(settings.tree_path),
                  settings, build_adapters(settings))
