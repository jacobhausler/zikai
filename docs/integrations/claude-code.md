# Claude Code

Copy the skill and the command adapter into Claude Code's user dirs — plain
copies, no edits:

```sh
mkdir -p ~/.claude/skills/zikai ~/.claude/commands
cp skills/zikai/SKILL.md ~/.claude/skills/zikai/SKILL.md
cp adapters/claude-code/zikai-command.md ~/.claude/commands/zikai.md
```

The skills copy registers the oracle as an Agent Skill; the adapter registers
the `/zikai <situation>` slash command (its frontmatter already gates
`Bash(*/tools/zk*)`). Env: `ZIKAI_URL` (default `http://127.0.0.1:8077`) and
`ZIKAI_KEY`, exported in the shell Claude Code's Bash tool runs in.

Smoke test: `/zikai He bragged to the master` → one `成語 (pīnyīn) — gloss
[slug]` line plus `decider:` verbatim, exit 0.
