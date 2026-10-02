"""zikai.client — the ONE place that knows how to talk to a zikai endpoint.

Every adapter (git hook, alert shim, receipt header, the dashboard's JS
sibling, austin's zk CLI + skill + stop-hook) imports this and nothing else.
Contract: two env vars — ZIKAI_URL, ZIKAI_KEY. stdlib-only, one retry, one
timeout. If you are adding a helper here, it is formatting: put it in the
adapter. If an adapter is duplicating a request shape, it is wrong: call home.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_TIMEOUT = 8.0


class ZikaiError(Exception):
    """Transport/protocol failure. status = HTTP code or None (network)."""

    def __init__(self, msg, status=None):
        super().__init__(msg)
        self.status = status


class Client:
    def __init__(self, base_url: str | None = None, key: str | None = None,
                 timeout: float = DEFAULT_TIMEOUT):
        self.base = (base_url or os.environ.get("ZIKAI_URL",
                                                "http://127.0.0.1:8077")
                     ).rstrip("/")
        self.key = key or os.environ.get("ZIKAI_KEY", "")
        self.timeout = timeout

    # -- verbs (the whole surface) ------------------------------------
    def healthz(self) -> dict:
        return self._get("/healthz")

    def stats(self) -> dict:
        return self._get("/stats")

    def decide(self, text: str, level: str = "compact",
               extras: list[str] | None = None, trace: bool = False,
               decider: str | None = None) -> dict:
        body = {"text": text, "level": level, "trace": trace}
        if extras:
            body["extras"] = extras
        if decider:
            body["decider"] = decider
        return self._post("/decide", body)

    def idiom(self, slug: str, level: str = "full") -> dict:
        return self._get(f"/idioms/{slug}?level={level}")

    # -- one transport, once ------------------------------------------
    def _request(self, method: str, path: str, body: dict | None) -> dict:
        req = urllib.request.Request(self.base + path, method=method)
        req.add_header("content-type", "application/json")
        if self.key:
            req.add_header("x-api-key", self.key)
        data = json.dumps(body).encode() if body is not None else None
        try:
            with urllib.request.urlopen(req, data,
                                        timeout=self.timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raise ZikaiError(f"{method} {path} -> {e.code}", e.code) from None
        except Exception as e:  # URLError, timeout, json, …
            raise ZikaiError(f"{method} {path}: {e.__class__.__name__}") from None

    def _get(self, path: str) -> dict:
        return self._request("GET", path, None)

    def _post(self, path: str, body: dict) -> dict:
        try:
            return self._request("POST", path, body)
        except ZikaiError as e:
            if e.status is None:      # network flake only; HTTP 4xx is a verdict
                return self._request("POST", path, body)  # one retry
            raise


def line(result: dict) -> str:
    """THE formatting helper for hooks: '博古通今 (bó gǔ tōng jīn) — gloss'.
    Single-sourced on purpose: git trailer, alert title, receipt block and CLI
    one-liners all render through here. Adapter-specific decoration stays in
    the adapter."""
    i = result.get("idiom") or {}
    hanzi = i.get("hanzi") or i.get("slug") or "?"
    pin = i.get("pinyin") or ""
    gloss = (i.get("meaning") or "").strip().split(". ")[0]
    suffix = " [lexical]" if str(result.get("decider", "")).endswith("+fallback") else ""
    return f"{hanzi} ({pin}) — {gloss}{suffix}"
