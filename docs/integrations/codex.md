# Codex

Codex CLI reads `AGENTS.md` (global `~/.codex/AGENTS.md`, plus the project
root). No skill loader — one paragraph in the project `AGENTS.md` is the
install:

```sh
mkdir -p .agents/skills && cp -r skills/zikai .agents/skills/zikai
cat >> AGENTS.md <<'EOF'
When a reply/commit/receipt is about to state a lesson or verdict, read
.agents/skills/zikai/SKILL.md and follow it: ask `tools/zk decide "<situation>"`,
cite the returned line verbatim, fail-open on `oracle: unavailable`.
EOF
```

(`.agents/skills/` is just a folder holding the skill as data — Codex has no
native skills dir; UNVERIFIED if newer builds discover it natively.)

Env: `ZIKAI_URL` (default `http://127.0.0.1:8077`), `ZIKAI_KEY` in Codex's
shell tool.

Smoke test: `tools/zk decide "He bragged to the master"` → one
`成語 (pīnyīn) — gloss [slug]` line plus `decider:` verbatim, exit 0.
