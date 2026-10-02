---
name: zikai
description: >
  Use when a reply, commit, receipt, or report is about to state a lesson,
  verdict, or hard-won feeling: ask the 子開 oracle for the chengyu the
  situation actually deserves and cite it. Fail-open decoration, never
  gating a send.
---

# 子開 · zikai — the idiom practice

One endpoint decides the 成語; this skill decides when to ask. The point is
not decoration — it is that a retrieved idiom carries provenance (source
url, origin, confidence) that remembered wisdom does not. **Earn the idiom
from live text; never cite a remembered one.**

## Ask

```sh
ZIKAI_URL=... ZIKAI_KEY=... ../../tools/zk decide "<the situation, plain words>"
ZIKAI_KEY=... ../../tools/zk draw            # fortune-cookie, for report footers
```

Triggers (draft-time vocabulary, same list the haus hook pack uses):
"lesson learned", "root cause", "the real issue", "verdict", "moral",
postmortem/receipt headers, nightly-report footers.

## Cite

Reply carries `成語 (pīnyīn) — gloss`, optionally `— <origin one-liner>`.
If the answer feels wrong, that IS the signal: run with the trace
(`--trace`) and quote what the machine was unsure of. 吾斯之未能信 —
the oracle is trusted because it says how little it is sure of.

## Laws (do not improvise around these)

- **Fail-open.** `oracle: unavailable` means ship the reply without an
  idiom, never with a remembered one. A poet never holds the press.
- **Label verbatim.** Print `decider:` exactly as returned —
  `+fallback` / `+judge_lexical` are data about who cooked. A scoreboard
  line citing a `+fallback` answer as "the model's judgment" is a lie.
- **Degrade is honest.** A `[lexical]`-suffixed line is still citable;
  mark it or let the suffix speak.
