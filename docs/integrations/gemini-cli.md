# Gemini CLI

Gemini CLI reads `GEMINI.md` context files and project slash commands from
TOML files in `.gemini/commands/`. Copy the skill as data, add one TOML:

```sh
mkdir -p .agents/skills .gemini/commands
cp -r skills/zikai .agents/skills/zikai
printf 'description: Ask 子開 which 成語 the situation deserves\nprompt: Read .agents/skills/zikai/SKILL.md and follow it for: {{args}}\n' > .gemini/commands/zikai.toml
```

That gives `/zikai <situation>`; the skill copy is the contract. Env:
`ZIKAI_URL` (default `http://127.0.0.1:8077`), `ZIKAI_KEY`. (TOML command
schema from Gemini CLI docs knowledge — UNVERIFIED against a live build.)

Smoke test: `tools/zk decide "He bragged to the master"` → one
`成語 (pīnyīn) — gloss [slug]` line plus `decider:` verbatim, exit 0.
