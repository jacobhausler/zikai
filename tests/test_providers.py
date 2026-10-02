"""Provider presets: resolution + rerank absence, no network.

Every resolve runs against an EMPTY adapter dict so only the preset table
+ env can produce an adapter; any real HTTP would mean a wrong-side build.
"""
import pytest

from zikai.adapters import PROVIDER_PRESETS, Lexical, resolve_adapter, rerank
from zikai.config import Settings

LEXICAL = {"lexical": Lexical()}
S = Settings(decider="auto")

REMOTE_ROWS = [n for n, r in PROVIDER_PRESETS.items()
               if r[1].startswith("https://")]
LOCAL_ROWS = [n for n, r in PROVIDER_PRESETS.items()
              if r[1].startswith("http://127.") or r[1].startswith("http://localhost")]
ALIAS_ROWS = [n for n, r in PROVIDER_PRESETS.items() if not r[1]]


def test_preset_shape():
    for n, r in PROVIDER_PRESETS.items():
        assert len(r) == 4 and isinstance(r[3], tuple), n
        assert r[0], n


@pytest.mark.parametrize("name", sorted(ALIAS_ROWS))
def test_alias_rows_pick_configured_adapter(name):
    transport = PROVIDER_PRESETS[name][0]
    adapters = dict(LEXICAL, **{transport: "sentinel"})
    assert resolve_adapter(name, S, adapters) == "sentinel"


@pytest.mark.parametrize("name", sorted(ALIAS_ROWS))
def test_alias_row_unconfigured_falls_to_lexical(name):
    assert resolve_adapter(name, S, LEXICAL).name == "lexical"


@pytest.mark.parametrize("name", sorted(REMOTE_ROWS + LOCAL_ROWS))
def test_resolve_per_preset_no_network(name, monkeypatch):
    def no_net(*a, **k):
        raise AssertionError(f"network attempt: {a}")
    monkeypatch.setattr("zikai.adapters.httpx.post", no_net)
    for key in PROVIDER_PRESETS[name][3]:
        monkeypatch.delenv(key, raising=False)
    transport, _, model, envs = PROVIDER_PRESETS[name]
    key_env = [k for k in envs if k.endswith("_API_KEY")]
    buildable = (transport in ("openai_compat", "openai", "anthropic")
                 and PROVIDER_PRESETS[name][1] and model)
    remote = PROVIDER_PRESETS[name][1].startswith("https://")

    # Stage 1 — nothing configured: remote rows (and every class-less/gated
    # row) must fall to lexical, never dial the vendor. localhost rows may
    # build keyless by design (a local server needs no key; a dead one fails
    # fast per-node) — the no_net patch proves nothing dialled either way.
    assert resolve_adapter(name, S, LEXICAL).name == ("lexical" if (remote or not buildable) else name)

    # Stage 2 — configured (key env present): buildable rows resolve from
    # the preset defaults; the rest stay lexical even with a key handed them.
    if key_env:
        monkeypatch.setenv(key_env[0], "k-test")
    got = resolve_adapter(name, S, LEXICAL)
    if buildable:
        assert got.name == name
        assert got.model == PROVIDER_PRESETS[name][2]
        assert got.base_url == PROVIDER_PRESETS[name][1].rstrip("/")
    else:
        assert got.name == "lexical"


def test_classless_transports_never_route():
    # decisions/responses/rerank rows exist but have no adapter class yet:
    # they must resolve to lexical, never 500, never dial the vendor.
    for name in ("jev-typesafe", "perplexity-decisions", "openai-decisions",
                 "openai_responses", "cohere_rerank", "jina_rerank"):
        assert resolve_adapter(name, S, LEXICAL).name == "lexical"


def test_env_override_of_preset_defaults(monkeypatch):
    monkeypatch.setenv("LAYA_BASE_URL", "http://10.0.0.9:9/v1")
    monkeypatch.setenv("LAYA_MODEL", "custom-b24")
    monkeypatch.setenv("LAYA_API_KEY", "k-test")
    got = resolve_adapter("laya", S, LEXICAL)
    assert (got.base_url, got.model) == ("http://10.0.0.9:9/v1", "custom-b24")


def test_rerank_absent_by_default():
    # no env, no transport arg sense: both vendor rows return None untouched
    import os
    for k in ("CO_API_KEY", "JINA_API_KEY"):
        os.environ.pop(k, None)
    assert rerank("cohere_rerank", "q", ["a", "b"], 1.0) is None
    assert rerank("jina_rerank", "q", ["a", "b"], 1.0) is None
    assert rerank("openai", "q", ["a"], 1.0) is None          # not a reranker
    assert rerank("cohere_rerank", "q", [], 1.0) is None       # empty docs


def test_engine_rerank_off_by_default():
    from zikai.engine import Engine
    tree = {"root": {"options": [], "question": "", "cluster_options": [],
                     "clusters_ref": []}}
    e = Engine({"a": {"slug": "a", "hanzi": "一", "meaning": "one"}}, tree, S,
               dict(LEXICAL))
    sl = [("a", 0.5)]
    assert e._vendor_rerank("one", sl) is sl                   # untouched
