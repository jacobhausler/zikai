# Integrations

One oracle, many harnesses. The canonical contract lives in
`skills/zikai/SKILL.md` — never duplicate it; every integration below either
points at that file or copies it verbatim into the harness's native skill
directory. Nothing here needs new code: the whole surface is one stdlib CLI
(`tools/zk`, importing `zikai.client` and nothing else) and two env vars.

**Env vars (the whole config):** `ZIKAI_URL` (default
`http://127.0.0.1:8077`) and `ZIKAI_KEY`, exported in whatever shell the
agent's tools run in. The server side of keying is `ZIKAI_API_KEYS` /
`ZIKAI_REQUIRE_KEY` in `.env.example`.

**The zk verbs:** `tools/zk decide "<situation>"` (one line: 成語 (pīnyīn) —
gloss [slug] + `decider:` label verbatim; `--json` for the raw response,
`--trace` to see the shortlist), `tools/zk draw` (random idiom for report
footers), `tools/zk stats` (corpus/cluster counts).

**Smoke test, identical everywhere:**
`tools/zk decide "He bragged to the master"` → one line
`成語 (pīnyīn) — gloss [slug]` plus `decider:` printed verbatim, exit 0.
Down endpoint prints `oracle: unavailable`, exit 1 — fail-open: ship without
an idiom, never with a remembered one.

**Copied outside the repo** (global skill dirs): the skill's relative
`tools/zk` reference assumes the repo layout, so invoke it by absolute path
instead — `path/to/zikai/tools/zk decide "…"` (stdlib-only, no install).

This folder covers Hermes, Pi, Claude Code, Codex, OpenClaw, Gemini CLI,
Cursor, GitHub Copilot, OpenCode, Cline, Cascade/Windsurf, Amp, and the SDK /
chat-protocol lane; the 1.0 pass keeps the full index current below and in
`AGENTS.md`.
