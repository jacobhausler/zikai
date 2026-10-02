#!/usr/bin/env python3
"""zikai git hook — the commit poem.

prepare-commit-msg: reads the message git is about to use (arg $1) plus the
STAGED diffstat, asks the oracle, and appends one line:

    Zikai: 刻舟求劍 (kè zhōu qiú jiàn) — seeking by a stale mark [lexical]

install:  ln -sf ../../adapters/git-prepare-commit-msg/zikai-prepare-commit-msg.sh .git/hooks/prepare-commit-msg
env:      ZIKAI_URL ZIKAI_KEY (the whole contract); ZIKAI_HOOK=0 disables per-call.
Why prepare-commit-msg and not post-commit: decorating before the commit
object exists rewrites nothing (no hash churn, no pushed-history lies) and
cannot recurse into a hook loop. Failure policy: any error == no poem, commit
proceeds; the poet never holds the press (3s timeout, silent silence).
"""
import os
import subprocess
import sys

def main(argv: list[str]) -> int:
    if os.environ.get("ZIKAI_HOOK", "1") == "0":
        return 0
    msgfile = argv[0] if argv else ""
    if not msgfile or not os.path.exists(msgfile):
        return 0
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    try:
        from zikai.client import Client, ZikaiError, line
        msg = open(msgfile, encoding="utf-8").read()
        if "Zikai:" in msg:          # amend-safe idempotence
            return 0
        def git(*a):
            # stat is a garnish, not a dependency: an image with no git
            # binary (slim containers) must still get a poem from the
            # message alone — the message is decidable text by itself.
            try:
                return subprocess.run(
                    ["git", *a], capture_output=True, text=True, timeout=5
                ).stdout
            except Exception:
                return ""
        stat = git("diff", "--cached", "--stat")[:400]
        text = (msg + "\n" + stat).strip()
        if len(msg.strip()) < 4:      # empty/editor-open invocation: skip
            return 0
        try:
            r = Client(timeout=3.0).decide(text[:2000], level="compact")
        except ZikaiError:
            return 0                  # endpoint down => commit uncommented
        with open(msgfile, "a", encoding="utf-8") as f:
            if not msg.endswith("\n"):
                f.write("\n")
            f.write("\nZikai: " + line(r) + "\n")
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
