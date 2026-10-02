# Hermes

Placement is native: Hermes discovers Agent Skills as
`~/.hermes/skills/<name>/SKILL.md` (house) or
`~/.hermes/profiles/<profile>/skills/<name>/SKILL.md` (per-profile), and the
agent loads one with `skill_view(name)`.

Install — one copy, no edits (the frontmatter already carries `name: zikai` +
`description`):

```sh
mkdir -p ~/.hermes/skills/zikai
cp skills/zikai/SKILL.md ~/.hermes/skills/zikai/SKILL.md
```

The skill then appears in `skills_list`; the description's trigger vocabulary
("lesson learned", "verdict", receipt headers) is what makes the agent load it.

Env: `ZIKAI_URL` (default `http://127.0.0.1:8077`), `ZIKAI_KEY` — exported in
the shell Hermes tools run in.

Smoke test: `ZIKAI_URL=… ZIKAI_KEY=… tools/zk decide "He bragged to the
master"` → one `成語 (pīnyīn) — gloss [slug]` line plus `decider:` verbatim.
