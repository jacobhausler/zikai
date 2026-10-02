---
description: Ask 子開 which 成語 the current situation deserves
allowed-tools: Bash(*/tools/zk*)
---

Run the oracle on this situation and cite it.

`!`../../tools/zk decide "$ARGUMENTS"` ``

Rules (the practice, not decoration):
- Cite the line as returned: `成語 (pīnyīn) — gloss`, plus the `decider:`
  line verbatim. `+fallback` / `+judge_lexical` / `[lexical]` are honest
  data about who cooked — never trim, never normalize, never re-word.
- If stdout is `oracle: unavailable`: say exactly that and move on. Do
  NOT substitute an idiom you remember. An un-idiom'd answer is fine; a
  hallucinated one is the only failure.
- If the returned idiom is visibly wrong for the situation, that's a
  finding: re-run with `--trace` and quote the shortlist — 吾斯之未能信,
  the oracle earns trust by showing where it isn't yet trustworthy.

Usage: `/zikai the reranker kept stealing near-synonyms from the judge`
