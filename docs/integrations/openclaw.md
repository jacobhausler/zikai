# OpenClaw

OpenClaw's skill-discovery layout is UNVERIFIED from this repo's sources
(community harness variant): drop the skill as data wherever OpenClaw keeps
its instruction files and reference it from its AGENTS.md-equivalent.

```sh
mkdir -p .agents/skills && cp -r skills/zikai .agents/skills/zikai
echo 'Before any reply/commit/receipt states a lesson or verdict, read
.agents/skills/zikai/SKILL.md and follow it: `tools/zk decide "<situation>"`,
cite verbatim, fail-open on `oracle: unavailable`.' >> AGENTS.md   # adjust path to OpenClaw's instructions file
```

Env: `ZIKAI_URL` (default `http://127.0.0.1:8077`), `ZIKAI_KEY`.

Smoke test: `tools/zk decide "He bragged to the master"` → one
`成語 (pīnyīn) — gloss [slug]` line plus `decider:` verbatim, exit 0.
