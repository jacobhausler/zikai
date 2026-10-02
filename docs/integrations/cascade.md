# Cascade (Windsurf)

Placement (native skills): workspace `.devin/skills/zikai/SKILL.md` (legacy `.windsurf/skills/…` still read); globals `~/.codeium/windsurf/skills/…` or `~/.config/devin/skills/…`. Frontmatter needs only `name`+`description` — the canonical skill carries both.
Install — one copy, no edits:

```sh
mkdir -p .devin/skills/zikai && cp skills/zikai/SKILL.md .devin/skills/zikai/SKILL.md
```

`@zikai` forces the skill; the body loads on demand.
Env: `ZIKAI_URL` (default `http://127.0.0.1:8077`), `ZIKAI_KEY` in the shell Windsurf's terminal inherits.
Smoke test: `@zikai`, then `tools/zk decide "He bragged to the master"` → one line `成語 (pīnyīn) — gloss [slug]` + `decider:` verbatim.
