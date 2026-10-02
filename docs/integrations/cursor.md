# Cursor

Placement: `.cursor/rules/zikai.mdc` (plain `.md` there is ignored); repo-root `AGENTS.md` is also read and serves as the front door.
Install: save this as `.cursor/rules/zikai.mdc` in a checkout of the zikai repo, so `skills/zikai/SKILL.md` and `tools/zk` resolve:

```mdc
---
description: When a reply, commit, receipt, or report is about to state a lesson or verdict, consult the 子開 oracle and cite the chengyu it returns.
alwaysApply: false
---
Read skills/zikai/SKILL.md and follow its laws: run `ZIKAI_URL=… ZIKAI_KEY=… tools/zk decide "<the situation, plain words>"`, cite `成語 (pīnyīn) — gloss`, fail-open on `oracle: unavailable`, print `decider:` verbatim.
```

Smoke test: `tools/zk decide "He bragged to the master"` → one line `成語 (pīnyīn) — gloss [slug]` + `decider:` verbatim, exit 0; `oracle: unavailable` (exit 1) is fail-open — never a remembered idiom.
