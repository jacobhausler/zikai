"""The decider label must stamp what RAN, not what was asked for.

Austin's self-host receipt (2026-10-02): GPU substrate down (connection
refused), yet /decide stamped `"decider": "openai_compat"` while every trace
node said `"adapter": "lexical"`. The fourth sighting of the green-counter
species: the label reported the INTENDED decider. These tests pin the honest
label across all three degrade modes.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["ZIKAI_CORPUS_PATH"] = str(ROOT / "data" / "corpus.json")
os.environ["ZIKAI_TREE_PATH"] = str(ROOT / "data" / "decision_tree.json")

from zikai.config import Settings                      # noqa: E402
from zikai.engine import Engine                        # noqa: E402
from zikai.adapters import Decision, Lexical           # noqa: E402
from zikai.tree import build_corpus, build_tree, load_records  # noqa: E402

corpus = build_corpus(load_records(ROOT / "data" / "records.jsonl"))
tree = build_tree(corpus)
TEXT = "He shows off in front of experts, a shallow display before the learned"


class FakeRemote:
    """Stand-in for openai_compat with three behaviors, one at a time."""
    name = "openai_compat"

    def __init__(self, mode):
        self.mode = mode            # "dead" | "garbage" | "good"

    def decide(self, text, question, options):
        if self.mode == "dead":     # Austin's case: transport refused
            return Decision(None, adapter=self.name, latency_ms=2,
                            error="ConnectError: connection refused")
        if self.mode == "garbage":  # answered, unusable -> silent lexical swap
            return Decision(None, raw="I cannot help", adapter=self.name,
                            latency_ms=2)
        vals = [o["value"] for o in options]
        return Decision(vals[0], adapter=self.name, latency_ms=2)

    def expand(self, text):
        return []


def engine_with(mode):
    eng = Engine(corpus, tree, Settings(require_key=False, decider="auto"), {})
    eng.adapters = {"lexical": Lexical()}
    eng.lexical = eng.adapters["lexical"]
    if mode != "lexical":
        eng.adapters["openai_compat"] = FakeRemote(mode)
    return eng


def test_dead_transport_cannot_stamp_premium_name():
    """The exact lie Austin measured: refused calls => never bare premium.
    Full truth here is triple-honest: routes fell back AND the rerank judge
    was asked into a dead transport (+judge_lexical) — every marker earned."""
    r = engine_with("dead").decide(TEXT)
    assert r["decider"] == "openai_compat+judge_lexical+fallback"
    assert r["decision_path"][0]["error"], "original error must survive the swap"
    assert all(n["adapter"] == "lexical" for n in r["decision_path"])


def test_silent_swap_without_error_still_says_fallback():
    """Answered garbage, no exception: fell_back flag carries the truth."""
    r = engine_with("garbage").decide(TEXT)
    assert r["decider"].endswith("+fallback")
    assert any(n["fell_back"] for n in r["decision_path"])


def test_healthy_remote_keeps_clean_name():
    """The fix must not punish the healthy path — clean answers, clean label."""
    r = engine_with("good").decide(TEXT)
    assert r["decider"] == "openai_compat"
    assert not any(n["fell_back"] or n["error"] for n in r["decision_path"])


def test_lexical_stays_lexical():
    """Native lexical (judge skipped by design) is not a degrade."""
    r = engine_with("lexical").decide(TEXT)
    assert r["decider"] == "lexical"
    assert "+judge_lexical" not in r["decider"]


def test_client_line_suffix_follows_honest_label():
    """client.line() decorates [lexical] iff the label ends +fallback —
    the label ordering (judge marker before fallback) preserves that."""
    from zikai.client import line
    dead = engine_with("dead").decide(TEXT)
    assert line(dead).endswith("[lexical]")
    good = engine_with("good").decide(TEXT)
    assert not line(good).endswith("[lexical]")
