"""Decider adapters — the pluggable "decider model" layer.

A decider is any model that, given the input text + a routing question +
labelled options, returns the chosen option's value (or None). The decision
API never depends on a vendor: adapters normalize to one shape and
normalize the answer back. A failed remote call returns value=None and the
engine falls back to the lexical decider for that node — one flaky vendor
never fails the request.

Resolution order for decider="auto": laya/OpenAI-compatible base_url ->
openai -> anthropic -> lexical (zero-key, always available).
"""
from __future__ import annotations

import re
import time

import httpx

from .config import Settings
from .tree import dice, _words


class Decision:
    def __init__(self, value: str | None, confidence: float = 0.0,
                 raw: str = "", adapter: str = "", latency_ms: int = 0,
                 error: str | None = None):
        self.value, self.confidence, self.raw = value, confidence, raw
        self.adapter, self.latency_ms, self.error = adapter, latency_ms, error


def _options_block(options: list[dict]) -> str:
    lines = []
    for o in options:
        hint = f" — {o['hint']}" if o.get("hint") else ""
        lines.append(f"- {o['value']}: {o['label']}{hint}")
    return "\n".join(lines)


def _prompt(text: str, question: str, options: list[dict]) -> str:
    return ("You are a decision node in a routing tree. Choose the single "
            "best option for the INPUT. Answer with ONLY the option value, "
            "nothing else.\n\n"
            f"Question: {question}\n\nOptions:\n{_options_block(options)}\n\n"
            f"INPUT:\n<<<\n{text}\n>>>")


def _extract_choice(reply: str, options: list[dict]) -> str | None:
    """Vendor-agnostic answer parsing: exact value, JSON, label, Dice."""
    if not reply:
        return None
    t = reply.strip().lower()
    vals = [o["value"].lower() for o in options]
    if t in vals:
        return options[vals.index(t)]["value"]
    m = re.search(r'"value"\s*:\s*"([^"]+)"', t)
    if m and m.group(1).lower() in vals:
        return options[vals.index(m.group(1).lower())]["value"]
    for o, v in zip(options, vals):
        if o["label"].lower() == t:
            return o["value"]
    # first option value/label appearing as a whole token in the reply
    for o, v in zip(options, vals):
        if re.search(rf'(^|[^a-z0-9-]){re.escape(v)}([^a-z0-9-]|$)', t):
            return o["value"]
    scored = sorted(((dice(_words(t), _words(o["label"])), o["value"])
                     for o in options), reverse=True)
    if scored and scored[0][0] >= 0.34:
        return scored[0][1]
    return None


class BaseAdapter:
    name = "base"

    def decide(self, text: str, question: str,
               options: list[dict]) -> Decision:
        raise NotImplementedError

    def expand(self, text: str) -> list[str]:
        """Optional recall hop: semantic keyword expansion of the input.
        Remote adapters override; default = no expansion."""
        return []


class OpenAICompat(BaseAdapter):
    """Any chat-completions-compatible endpoint: OpenAI, laya, sglang,
    vllm, together, fireworks, groq, ollama..."""

    def __init__(self, base_url: str, api_key: str, model: str,
                 timeout: float, name: str = "openai_compat"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.name = name

    def decide(self, text: str, question: str, options: list[dict]) -> Decision:
        reply, err, ms = self._chat(_prompt(text, question, options))
        if err:
            return Decision(None, adapter=self.name, latency_ms=ms, error=err)
        return Decision(_extract_choice(reply, options), raw=reply[:120],
                        adapter=self.name, latency_ms=ms)

    def expand(self, text: str) -> list[str]:
        reply, err, _ = self._chat(
            "Give 6-10 lower-case English keywords/synonyms that a classical "
            "Chinese idiom (chengyu) would allegorically encode for this "
            "INPUT. Answer with ONLY a comma-separated list, no sentences.\n\n"
            f"INPUT:\n<<<\n{text}\n>>>")
        if not reply:
            return []
        words = [w.strip().lower() for w in reply.replace("\n", ",").split(",")]
        return [w for w in words if re.fullmatch(r"[a-z][a-z\- ]{1,24}", w)][:10]

    def _chat(self, prompt: str) -> tuple[str, str | None, int]:
        t0 = time.time()
        base = {"model": self.model, "temperature": 0, "max_tokens": 320,
                "messages": [{"role": "user", "content": prompt}]}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = dict(base, chat_template_kwargs={"enable_thinking": False})
        try:
            try:
                r = httpx.post(f"{self.base_url}/chat/completions", json=body,
                               headers=headers, timeout=self.timeout)
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                # vendors that reject chat_template_kwargs (OpenAI et al)
                if e.response.status_code not in (400, 422):
                    raise
                r = httpx.post(f"{self.base_url}/chat/completions", json=base,
                               headers=headers, timeout=self.timeout)
                r.raise_for_status()
            msg = r.json()["choices"][0]["message"]
            reply = (msg.get("content") or msg.get("reasoning")
                     or msg.get("reasoning_content") or "")
        except Exception as e:  # noqa: BLE001 — engine falls back, never 500
            return "", f"{type(e).__name__}: {e}"[:200], int((time.time() - t0) * 1000)
        return reply, None, int((time.time() - t0) * 1000)


class Anthropic(BaseAdapter):
    name = "anthropic"

    def __init__(self, base_url: str, api_key: str, model: str,
                 timeout: float):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def decide(self, text: str, question: str, options: list[dict]) -> Decision:
        t0 = time.time()
        try:
            r = httpx.post(f"{self.base_url}/v1/messages",
                           headers={"x-api-key": self.api_key,
                                    "anthropic-version": "2023-06-01",
                                    "content-type": "application/json"},
                           json={"model": self.model, "max_tokens": 24,
                                 "temperature": 0,
                                 "messages": [{"role": "user",
                                               "content": _prompt(
                                                   text, question, options)}]},
                           timeout=self.timeout)
            r.raise_for_status()
            reply = "".join(b.get("text", "") for b in r.json()["content"])
        except Exception as e:  # noqa: BLE001
            return Decision(None, adapter=self.name,
                            latency_ms=int((time.time() - t0) * 1000),
                            error=f"{type(e).__name__}: {e}"[:200])
        return Decision(_extract_choice(reply, options), raw=reply[:120],
                        adapter=self.name,
                        latency_ms=int((time.time() - t0) * 1000))

    def expand(self, text: str) -> list[str]:
        t0 = time.time()
        try:
            r = httpx.post(
                f"{self.base_url}/v1/messages",
                headers={"x-api-key": self.api_key,
                         "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": self.model, "max_tokens": 200, "temperature": 0,
                      "messages": [{"role": "user", "content":
                                    "Give 6-10 lower-case English "
                                    "keywords/synonyms that a classical "
                                    "Chinese idiom (chengyu) would "
                                    "allegorically encode for this INPUT. "
                                    "Answer with ONLY a comma-separated "
                                    f"list.\n\nINPUT:\n<<<\n{text}\n>>>"}]},
                timeout=self.timeout)
            r.raise_for_status()
            reply = "".join(b.get("text", "") for b in r.json()["content"])
        except Exception:  # noqa: BLE001
            return []
        words = [w.strip().lower() for w in reply.replace("\n", ",").split(",")]
        return [w for w in words
                if re.fullmatch(r"[a-z][a-z\- ]{1,24}", w)][:10]


class Lexical(BaseAdapter):
    """Zero-key fallback: word-set + character n-gram Dice similarity of the
    text against every option label+hint. Keeps the API fully testable and
    gives cheap endpoints a floor to beat."""

    name = "lexical"

    def decide(self, text: str, question: str, options: list[dict]) -> Decision:
        tw, tc = _words(text), _chargrams(text)
        best, best_s = None, -1.0
        for o in options:
            blob = (f"{o.get('label','')} {o.get('hint','')} "
                    f"{' '.join(o.get('exemplars', []))}")
            s = 0.55 * dice(tw, _words(blob)) + 0.45 * _cgram_sim(tc, blob)
            if s > best_s:
                best, best_s = o, s
        if best is None:
            return Decision(None, adapter=self.name)
        return Decision(best["value"], confidence=round(best_s, 3),
                        raw=best.get("label", ""), adapter=self.name)


def _chargrams(s: str) -> set[str]:
    s = re.sub(r"\s+", " ", s.lower())
    return {s[i:i + 3] for i in range(len(s) - 2)}


def _cgram_sim(q: set[str], blob: str) -> float:
    b = _chargrams(blob)
    if not q or not b:
        return 0.0
    return len(q & b) / len(q | b)


def build_adapters(settings: Settings) -> dict[str, BaseAdapter]:
    a: dict[str, BaseAdapter] = {}
    if settings.laya_base_url:
        a["openai_compat"] = OpenAICompat(settings.laya_base_url,
                                          settings.laya_api_key,
                                          settings.laya_model,
                                          settings.decision_timeout_s)
    if settings.openai_api_key:
        a["openai"] = OpenAICompat(settings.openai_base_url,
                                   settings.openai_api_key,
                                   settings.openai_model,
                                   settings.decision_timeout_s, name="openai")
    if settings.anthropic_api_key:
        a["anthropic"] = Anthropic(settings.anthropic_base_url,
                                   settings.anthropic_api_key,
                                   settings.anthropic_model,
                                   settings.decision_timeout_s)
    a["lexical"] = Lexical()
    return a


_ALIAS = {"laya": "openai_compat", "sglang": "openai_compat",
          "vllm": "openai_compat", "ollama": "openai_compat",
          "together": "openai", "groq": "openai", "fireworks": "openai",
          "deepseek": "openai_compat", "openrouter": "openai"}


def resolve_adapter(requested: str | None, settings: Settings,
                    adapters: dict[str, BaseAdapter]) -> BaseAdapter:
    if requested:
        key = _ALIAS.get(requested.lower(), requested.lower())
        if key in adapters:
            return adapters[key]
        # requested but unconfigured -> fall through to auto (never 500)
    mode = settings.decider
    if mode != "auto" and mode in adapters:
        return adapters[mode]
    for k in ("openai_compat", "openai", "anthropic", "lexical"):
        if k in adapters:
            return adapters[k]
    return adapters["lexical"]
