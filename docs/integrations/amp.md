# Amp (Sourcegraph)

Placement (native): Amp searches `.agents/skills/zikai/SKILL.md`, `.claude/skills/…`, `.amp/skills/…`, and globals like `~/.config/amp/skills/…` — and always includes repo-root `AGENTS.md`, so the front door covers you even without a copy.
Install — one copy into the agent-agnostic project dir:

```sh
mkdir -p .agents/skills/zikai && cp skills/zikai/SKILL.md .agents/skills/zikai/SKILL.md
```

Env: `ZIKAI_URL` (default `http://127.0.0.1:8077`), `ZIKAI_KEY` — Amp's thread tools inherit the shell environment.
Smoke test: `tools/zk decide "He bragged to the master"` → one line `成語 (pīnyīn) — gloss [slug]` + `decider:` verbatim; `oracle: unavailable` (exit 1) is fail-open — ship without an idiom.
