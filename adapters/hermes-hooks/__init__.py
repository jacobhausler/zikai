"""zikai oracle hook — decorates Discord lesson/verdict replies with an idiom.

Placement law (owner 2026-10-01): this plugin is installed into ONE profile
(clankville) and the callback fires only when platform == "discord".
Used-but-not-overused gates, in order:
  1. platform guard (discord only)
  2. moment gate: the reply must read like a lesson/verdict/receipt moment
  3. already-quoted guard: any hanzi or an `oracle:` line in the reply => skip
  4. once per turn (core fires transform_llm_output once per turn_id anyway)
Fail-open by law (austin's objection, conceded): every path that isn't a
clean append returns None — the send is NEVER gated, and an idiom is never
remembered from model memory; it is decided live or it doesn't appear.
Kill switch: ZIKAI_HOOK=0 in the profile env.
"""
from __future__ import annotations

import os
import re
import sys

_MOMENT = re.compile(
    r"\b(lesson|verdict|receipt|postmortem|root cause|law\b|estate law|adopted"
    r"|green[- ]counter|standing rule|the rule (?:now|here) reads"
    r"|practice (?:is|on)|books? closed)\b|定律|守则|事毕矣|開。", re.IGNORECASE)
_HANZI = re.compile(r"[\u4e00-\u9fff]")
_ORACLED = re.compile(r"oracle:|Zikai:|— zikai ·", re.IGNORECASE)

_client = None
_client_failed = False


def _profile_env():
    """Config resolution: process env wins; else the profile's zikai-hook.json
    (0600, url+key) read at call time — so the hook works in an already-
    running gateway without an env restart. Never logs the key."""
    if os.environ.get("ZIKAI_URL"):
        return
    import json
    for p in (os.path.expandvars("$HERMES_HOME/plugins/zikai-oracle-hook/zikai-hook.json"),
              os.path.expanduser("~/.hermes/profiles/clankville/plugins/"
                                 "zikai-oracle-hook/zikai-hook.json")):
        try:
            cfg = json.load(open(p))
            os.environ.setdefault("ZIKAI_URL", cfg.get("url", ""))
            os.environ.setdefault("ZIKAI_KEY", cfg.get("key", ""))
            if os.environ.get("ZIKAI_URL"):
                return
        except Exception:
            continue


def _get_client():
    """Bootstrap zikai.client from the repo checkout — the die stays single."""
    global _client, _client_failed
    if _client is not None or _client_failed:
        return _client
    _profile_env()
    repo = os.environ.get("ZIKAI_REPO", "/home/hermes/.hermes/work/zikai")
    try:
        if repo not in sys.path:
            sys.path.insert(0, repo)
        from zikai.client import Client  # noqa: PLC0415 — lazy by design
        _client = Client(timeout=3.0)
    except Exception:
        _client_failed = True
    return _client


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
        if _HANZI.search(response_text) or _ORACLED.search(tail):
            return None                       # already quoted: never overuse
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


def register(ctx):
    ctx.register_hook("transform_llm_output", _decorate)
