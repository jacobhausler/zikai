# OpenCode

Placement (native Agent Skills): project `.opencode/skills/zikai/SKILL.md`; OpenCode also reads the Claude-compatible `.claude/skills/…`, the agent-agnostic `.agents/skills/…`, and global `~/.config/opencode/skills/…`.
Install — one copy, no edits (frontmatter `name`+`description` already within spec, dir name matches):

```sh
mkdir -p .opencode/skills/zikai && cp skills/zikai/SKILL.md .opencode/skills/zikai/SKILL.md
```

OpenCode lists the skill in its `skill` tool and loads the body on demand.
Env: `ZIKAI_URL` (default `http://127.0.0.1:8077`), `ZIKAI_KEY`.
Smoke test: load the `zikai` skill, then `tools/zk decide "He bragged to the master"` → one line `成語 (pīnyīn) — gloss [slug]` + `decider:` verbatim.
