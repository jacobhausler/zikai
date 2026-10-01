import json
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["ZIKAI_CORPUS_PATH"] = str(ROOT / "data" / "corpus.json")
os.environ["ZIKAI_TREE_PATH"] = str(ROOT / "data" / "decision_tree.json")
os.environ["ZIKAI_REQUIRE_KEY"] = "false"
os.environ["ZIKAI_DECIDER"] = "lexical"

from zikai.app import create_app                      # noqa: E402
from zikai.config import Settings                      # noqa: E402
from zikai.engine import Engine                        # noqa: E402
from zikai.tree import (MAX_TREE_DEPTH, build_corpus,  # noqa: E402
                        build_tree, load_records)

corpus = build_corpus(load_records(ROOT / "data" / "records.jsonl"))
tree = build_tree(corpus)


@pytest.fixture(scope="module")
def client():
    eng = Engine(corpus, tree, Settings(require_key=False, decider="lexical"),
                 {})
    from zikai.adapters import Lexical
    eng.adapters = {"lexical": Lexical()}
    eng.lexical = eng.adapters["lexical"]
    return TestClient(create_app(eng))


def test_corpus_sized():
    assert len(corpus) > 1000, "nightly scrape should fill 1k+ idioms"


def test_tree_is_shallow():
    assert tree["max_depth"] == MAX_TREE_DEPTH
    for opt in tree["root"]["options"]:
        assert "cluster_options" in opt
        for cid in opt["clusters_ref"]:
            assert cid in tree["clusters"]
    total = sum(len(c["idioms"]) for c in tree["clusters"].values())
    assert total == len(corpus), "every idiom lives in exactly one cluster"


def test_decide_full(client):
    r = client.post("/decide", json={"text": "He shows off in front of experts"})
    assert r.status_code == 200
    d = r.json()
    assert d["idiom"]["hanzi"], "winner must be hydrated with hanzi"
    assert d["idiom"]["meaning"] and d["theme"] and d["cluster"]
    assert d["depth"] <= MAX_TREE_DEPTH
    assert 0.0 <= d["confidence"] <= 1.0
    assert len(d["decision_path"]) == 2


def test_levels(client):
    base = client.post("/decide", json={"text": "slow steady progress"}).json()
    slug = base["idiom"]["slug"]
    c = client.post("/decide", json={"text": "slow steady progress",
                                     "level": "compact"}).json()
    assert set(c["idiom"]) <= {"slug", "hanzi", "pinyin", "meaning", "theme",
                               "url", "confidence_hint", "origin", "literal",
                               "meaning_metaphoric", "example_en",
                               "example_zh", "related", "faq", "title",
                               "term_code", "date_modified"}
    t = client.post("/decide", json={"text": "slow steady progress",
                                     "level": "text"}).json()
    assert "(" in t["idiom"]["text"] and slug in t["idiom"]["text"]
    s = client.post("/decide", json={"text": "slow steady progress",
                                     "level": "slug"}).json()
    assert s["idiom"] == {"slug": slug}


def test_extras_and_trace(client):
    d = client.post("/decide", json={"text": "copying without understanding",
                                     "trace": True,
                                     "extras": ["origin"]}).json()
    assert "origin" in d["idiom"]
    assert d["trace"] and d["trace"][0]["slug"]


def test_slug_endpoint(client):
    d = client.post("/decide", json={"text": "quiet as a mouse",
                                     "level": "slug"}).json()
    r = client.get(f"/idioms/{d['idiom']['slug']}")
    assert r.status_code == 200 and r.json()["idiom"]["hanzi"]
    assert client.get("/idioms/no-such-slug").status_code == 404


def test_related_resolved(client):
    d = client.post("/decide", json={"text": "hearsay rumors",
                                      "related_resolved": True}).json()
    rel = d["idiom"].get("related_idioms")
    if d["idiom"].get("related"):
        assert rel and all(x["meaning"] for x in rel)


def test_search_and_health(client):
    assert client.get("/healthz").json()["ok"] is True
    r = client.get("/idioms?q=water").json()
    assert r["results"], "search should find something with 'water'"


def test_v1_alias_and_get(client):
    r = client.post("/v1/decisions", json={"text": "reinventing the wheel"})
    assert r.status_code == 200
    g = client.get("/decide", params={"q": "reinventing the wheel"})
    assert g.status_code == 200 and g.json()["idiom"]["hanzi"]


def test_empty_text_422(client):
    assert client.post("/decide", json={"text": "  "}).status_code == 422


def test_auth_enforced(monkeypatch):
    # env vars beat Settings() kwargs in pydantic-settings — clear them so
    # this case really exercises key enforcement.
    monkeypatch.delenv("ZIKAI_REQUIRE_KEY", raising=False)
    monkeypatch.delenv("ZIKAI_DECIDER", raising=False)
    eng = Engine(corpus, tree,
                 Settings(require_key=True, api_keys="zk" + "live77",
                          decider="lexical"), {})
    from zikai.adapters import Lexical
    eng.adapters = {"lexical": Lexical()}
    eng.lexical = eng.adapters["lexical"]
    c = TestClient(create_app(eng))
    KEY = "zk" + "live77"
    assert c.post("/decide", json={"text": "x"}).status_code == 401
    assert c.post("/decide", json={"text": "x"},
                  headers={"x-api-key": KEY}).status_code == 200
    assert c.get("/decide", params={"q": "x", "key": KEY}).status_code == 200
    assert c.get("/decide", params={"q": "x", "key": "no" + "pe77"}).status_code == 401


def test_adapter_fallback_never_500(client):
    # request a vendor that isn't configured -> auto falls back, still 200
    d = client.post("/decide", json={"text": "a slow decision",
                                     "decider": "openai"}).json()
    assert d["idiom"]["hanzi"]


def test_hanzi_echo_ranks_gold_first():
    # echo probes: hanzi in the input must bridge to the record (simplified
    # vs traditional included — corpus hydrates simplified glyph sets)
    e = Engine(corpus, tree, Settings(require_key=False, decider="lexical"), {})
    from zikai.adapters import Lexical
    e.adapters = {"lexical": Lexical()}; e.lexical = e.adapters["lexical"]
    for text, gold in [("刻舟求剑 — grepped a stale log for the token",
                        "ke-zhou-qiu-jian"),
                       ("指鹿为马 — renamed the metric to flatter its owner",
                        "zhi-lu-wei-ma"),
                       ("盲人摸象 — every node green, fleet story wrong",
                        "mang-ren-mo-xiang"),
                       ("对牛弹琴 — payload to an endpoint that can't parse it",
                        "dui-niu-tan-qin"),
                       ("竭泽而渔 — drained the token pond this month",
                        "jie-ze-er-yu")]:
        rk = e._rank(text)
        assert rk[0][0] == gold, f"{text}: expected {gold}, got {rk[0][0]}"


# KNOWN-HARD (permanent board, posted to the guild 2026-10-01): plain-scenario
# probes. Of Austin's five, the CLEAN wins decompose as:
#   jie-ze-er-yu    — raw lexical rank 1: deterministic, pinned below
#   dui-niu-tan-qin — raw rank 16, rescued by the keyword-union + rerank lane
#   mang-ren-mo-xiang — same lane; both depend on the remote decider, so they
#     live in the ECHO pins + the scoreboard, not in zero-key tests.
# Losers (recall floor of the free decider, expected fails):
#   ke-zhou-qiu-jian, zhi-lu-wei-ma — gold never reaches the 12-slot shortlist.
def test_hard_board_wins_are_pinned():
    e = Engine(corpus, tree, Settings(require_key=False, decider="lexical"), {})
    from zikai.adapters import Lexical
    e.adapters = {"lexical": Lexical()}; e.lexical = e.adapters["lexical"]
    rk = e._rank("They drained the entire weekly token budget on per-document "
                 "model calls for this month's numbers; the lake is empty now")
    assert rk[0][0] == "jie-ze-er-yu"
