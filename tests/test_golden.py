"""Golden set: scenario -> expected verdict, lexical decider only (zero
keys, same law as the rest of the suite). CI gate for recall (a corpus or
alias edit that drops a gold idiom out of the top spot fails here) and
for calibration (mundane input must come back no_fit, not a confident
hallucinated decoration)."""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["ZIKAI_DECIDER"] = "lexical"

from zikai.config import Settings                     # noqa: E402
from zikai.engine import Engine                       # noqa: E402
from zikai.tree import build_corpus, build_tree, load_records  # noqa: E402

corpus = build_corpus(load_records(ROOT / "data" / "records.jsonl"))
tree = build_tree(corpus)
FLOOR = Settings().no_fit_floor

CASES = [json.loads(ln) for ln in
         (ROOT / "tests" / "golden.jsonl").read_text().splitlines()
         if ln.strip()]


@pytest.fixture(scope="module")
def eng():
    from zikai.adapters import Lexical
    return Engine(corpus, tree, Settings(require_key=False, decider="lexical"),
                  {"lexical": Lexical()})


@pytest.mark.parametrize("case", CASES, ids=[c["text"][:40] for c in CASES])
def test_golden(eng, case):
    r = eng.decide(case["text"])
    if case["expect"] == "pick":
        assert r["idiom"]["slug"] == case["gold"], \
            f"pick {r['idiom']['slug']} != gold {case['gold']}"
        assert r["confidence"] >= FLOOR, \
            f"gold pick must clear the no_fit floor ({r['confidence']})"
        assert not r["no_fit"]
    else:
        assert r["no_fit"], f"mundane input must be no_fit, got conf {r['confidence']}"
