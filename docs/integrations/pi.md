# Pi

Placement is native: Pi implements the Agent Skills standard and discovers
skills from `~/.pi/agent/skills/`, `~/.agents/skills/` (global) and
`.pi/skills/`, `.agents/skills/` (project, walking up to the git root).

Install — one copy, no edits:

```sh
mkdir -p .agents/skills/zikai
cp skills/zikai/SKILL.md .agents/skills/zikai/SKILL.md
```

Pi lists the skill at startup (see `/hotkeys`) and registers it as
`/skill:zikai`; the agent also loads it on demand from its description. To
reuse an existing Claude/Codex install, add `"skills": ["~/.claude/skills"]`
(or `~/.codex/skills`) to `~/.pi/agent/settings.json` instead of copying.

Env: `ZIKAI_URL` (default `http://127.0.0.1:8077`), `ZIKAI_KEY`.

Smoke test: `tools/zk decide "He bragged to the master"` → one
`成語 (pīnyīn) — gloss [slug]` line plus `decider:`, exit 0.
