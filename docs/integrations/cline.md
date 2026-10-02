# Cline

Placement: workspace rules — `.clinerules/zikai.md` (newer `.cline/rules/zikai.md` is equivalent; Cline combines every `.md` in either dir). Cline has no SKILL.md discovery, so the rule points at the canonical skill.
Install — save as `.clinerules/zikai.md`:

```md
## 子開 zikai idiom oracle
Read skills/zikai/SKILL.md and follow its laws. When a reply, commit, receipt, or report is about to
state a lesson or verdict, run `ZIKAI_URL=… ZIKAI_KEY=… tools/zk decide "<the situation, plain words>"`
and cite `成語 (pīnyīn) — gloss`. Fail-open on `oracle: unavailable`; print `decider:` verbatim.
```

Env: `ZIKAI_URL` (default `http://127.0.0.1:8077`), `ZIKAI_KEY` in the terminal Cline shells run in.
Smoke test: ask Cline to consult the oracle — expect `tools/zk decide "He bragged to the master"` to return one line `成語 (pīnyīn) — gloss [slug]` + `decider:`.
