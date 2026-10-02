# GitHub Copilot

Placement: repository custom instructions — `.github/copilot-instructions.md` (read on every request in repo context). Copilot has no SKILL.md runtime, so the body points at the canonical skill.
Install: save as `.github/copilot-instructions.md` in a checkout of the zikai repo:

```md
## 子開 zikai idiom oracle
When a reply, commit, receipt, or report is about to state a lesson or verdict: run
`ZIKAI_URL=… ZIKAI_KEY=… tools/zk decide "<the situation, plain words>"` and cite
`成語 (pīnyīn) — gloss`. Full contract: skills/zikai/SKILL.md.
Fail-open on `oracle: unavailable`; print `decider:` verbatim — `+fallback` is data, not decoration.
```

Smoke test: `tools/zk decide "He bragged to the master"` → one line `成語 (pīnyīn) — gloss [slug]` + `decider:`, exit 0.
