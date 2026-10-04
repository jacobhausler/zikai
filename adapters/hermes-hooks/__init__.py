"""zikai oracle hook — decorates Discord lesson/verdict replies with an idiom.

Placement law (owner 2026-10-04): installed into ONE profile per estate, and
the callback fires only when platform == "discord".
Used-but-not-overused gates, in order:
  1. platform guard (discord only)
  2. moment gate: the reply must read like a lesson/verdict/receipt moment
  3. already-quoted guard: an `oracle:`/`Zikai:` line anywhere, or a quoted
     idiom of the shape 成語 (pinyin) — near the tail => skip. (Bare hanzi in
     the BODY does NOT suppress: a post that uses a hanzi term in prose still
     deserves a decided epigraph — only a DECIDED-STYLE quote means it rode.)
  4. once per turn (core fires transform_llm_output once per turn_id anyway)
Fail-open by law (austin's objection, conceded): every path that isn't a
clean append returns None — the send is NEVER gated, and an idiom is never
remembered from model memory; it is decided live or it doesn't appear.
Kill switch: ZIKAI_HOOK=0 in the profile env.

Config law (austin's install receipt 2026-10-04): NOTHING on this estate's
paths is a default. The pointer file `zikai-hook.json` is read from the
plugin's OWN directory first (Path(__file__).parent), then
$HERMES_HOME/plugins/zikai-oracle-hook/. Keys: url, key, repo. The armed line
printed at register() says where config was found — decoration-shaped
vaporware must announce itself at install time, not fail-open silently.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

_MOMENT = re.compile(
    r"\b(lesson|verdict|receipt|postmortem|root cause|law\b|estate law|adopted"
    r"|green[- ]counter|standing rule|the rule (?:now|here) reads"
    r"|practice (?:is|on)|books? closed)\b|定律|守则|事毕矣|開。", re.IGNORECASE)
# a quote has already rode if it looks like the oracle's own product shape
_QUOTED_TAIL = re.compile(r"[\u4e00-\u9fff]{2,}\s*\([^)]*\)\s*—")
_ORACLED = re.compile(r"oracle:|Zikai:|— zikai ·", re.IGNORECASE)

_client = None
_client_failed = False


def _config_candidates():
    """Where zikai-hook.json may live, in trust order. NEVER a hardcoded
    other-profile path (austin's law): a copied plugin resolves beside itself."""
    here = Path(__file__).resolve().parent
    cands = [here / "zikai-hook.json"]
    hh = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    cands.append(Path(hh) / "plugins" / "zikai-oracle-hook" / "zikai-hook.json")
    return cands


def _load_cfg():
    """First readable pointer file wins; {} means 'not configured'."""
    if os.environ.get("ZIKAI_URL"):
        return {}                      # process env is already authoritative
    import json
    for p in _config_candidates():
        try:
            cfg = json.load(open(p))
            if cfg.get("url"):
                return cfg
        except Exception:
            continue
    return {}


def _get_client(cfg=None):
    """Bootstrap zikai.client — the die stays single. Import order: installed
    package first, then an explicit `repo` from env/pointer file. No estate
    path is ever the default (austin's finding #2)."""
    global _client, _client_failed
    if _client is not None or _client_failed:
        return _client
    cfg = cfg if cfg is not None else _load_cfg()
    if cfg.get("url"):
        os.environ.setdefault("ZIKAI_URL", cfg["url"])
    if cfg.get("key"):
        os.environ.setdefault("ZIKAI_KEY", cfg["key"])
    if not os.environ.get("ZIKAI_URL"):
        _client_failed = True
        return None                    # unconfigured: no silent 127.0.0.1 default
                                       # (austin #1 — Client's fallback port is
                                       # a lie the hook must never ride quietly)
    try:
        from zikai.client import Client  # noqa: PLC0415 — installed first
    except Exception:
        repo = os.environ.get("ZIKAI_REPO") or cfg.get("repo")
        if not repo:
            _client_failed = True
            return None                # not installed and not pointed: armed-nothing
        if repo not in sys.path:
            sys.path.insert(0, repo)
        try:
            from zikai.client import Client  # noqa: PLC0415 — from pointer repo
        except Exception:
            _client_failed = True
            return None
    _client = Client(timeout=_decide_budget(cfg))
    return _client


def _decide_budget(cfg) -> float:
    """Hook latency budget = the lane's decide cap + transport margin, both
    measured (owner's sizing law): GPU answers ran 17–32s live; the server
    caps decide at ZIKAI_DECISION_TIMEOUT_S*nodes + overhead ≈ 32.2s, so the
    honest default is 40s (one decide + a hair; the client's single network
    retry can stack a second try, so the effective ceiling is 2x this).
    Pointer file `timeout` or ZIKAI_HOOK_TIMEOUT_S override. 3s was the
    inherited guess that made the hook silent-vapor."""
    raw = os.environ.get("ZIKAI_HOOK_TIMEOUT_S") or cfg.get("timeout") or 40.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 40.0


def _decorate(response_text: str, **_ignored):
    try:
        if os.environ.get("ZIKAI_HOOK", "1") == "0":
            return None
        # platform arrives as a hook kwarg from turn_finalizer
        if _ignored.get("platform") != "discord":
            return None
        if not response_text or len(response_text) < 200:
            return None                       # chatter is not a verdict
        tail = response_text[-1200:]
        if _ORACLED.search(response_text) or _QUOTED_TAIL.search(tail):
            return None                       # a quote already rode: no double
        if not _MOMENT.search(tail):
            return None                       # not a lesson moment
        c = _get_client()
        if c is None:
            return None                       # oracle unreachable: send clean
        from zikai.client import line, ZikaiError  # noqa: PLC0415
        try:
            r = c.decide(tail[:1500], level="compact")
        except ZikaiError:
            return None                       # never a remembered idiom
        return response_text + "\n\n> oracle: " + line(r)
    except Exception:
        return None                           # the poet never holds the press


def _reachable(url: str) -> bool:
    """One-shot /healthz probe for the ARMED LINE only — decide() never probes."""
    try:
        import urllib.request
        with urllib.request.urlopen(url.rstrip("/") + "/healthz", timeout=1.5) as r:
            return r.status == 200
    except Exception:
        return False


def _armed_line() -> str:
    """register()'s self-report: config source, client, lane liveness. An
    enabled-but-deaf hook must announce itself at arm time, not print green."""
    cfg = _load_cfg()
    if os.environ.get("ZIKAI_URL"):
        src = "env"
    elif cfg:
        src = next((str(p) for p in _config_candidates()
                    if p.exists() and json_url(p)), "MISSING")
    else:
        src = "MISSING (no url; hook no-ops)"
    url = os.environ.get("ZIKAI_URL") or (cfg.get("url") or "?")
    try:
        ok = _get_client(cfg) is not None
    except Exception:
        ok = False
    url = os.environ.get("ZIKAI_URL", url)
    live = ok and url != "?" and _reachable(url)
    return (f"[zikai-oracle-hook] armed: config={src} url={url} "
            f"client={'ok' if ok else 'DEAF (fail-open no-op)'} "
            f"lane={'up' if live else 'DOWN'}")


def register(ctx):
    print(_armed_line(), file=sys.stderr)
    ctx.register_hook("transform_llm_output", _decorate)


def json_url(p):
    import json
    try:
        return bool(json.load(open(p)).get("url"))
    except Exception:
        return False
