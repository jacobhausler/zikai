#!/usr/bin/env python3
"""zk-quote — the oracle header for haus-docs receipts and postmortems.

Usage:
    zk-quote.py "what actually happened, one honest sentence"   # prints blockquote
    zk-quote.py --file notes.txt                                # from a file
    echo "..." | zk-quote.py                                    # from stdin

Prints the standard opening block for a receipt, decided by the oracle:

    > 未雨绸缪 (wèi yǔ chóu móu) — bind the windows before the rain.
    > — zikai · slug wei-yu-chou-mou · decider <@haus-exec>

Paste it under the receipt title (or let the docs lane prepend it). This is
the practice half of the ask: an estate that quotes an idiom at every
postmortem is an estate that reads its postmortems.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("text", nargs="?", default="")
    ap.add_argument("--file", default="")
    ap.add_argument("--level", default="full")
    ap.add_argument("--trace", action="store_true")
    a = ap.parse_args()
    text = a.text or (open(a.file).read() if a.file else
                      sys.stdin.read() if not sys.stdin.isatty() else "")
    text = text.strip()
    if not text:
        print("usage: zk-quote.py \"<situation>\" | --file f | < f", file=sys.stderr)
        return 2
    from zikai.client import Client, ZikaiError, line
    try:
        r = Client().decide(text[:4000], level="compact", trace=a.trace)
    except ZikaiError as e:
        print(f"zk-quote: oracle unreachable ({e}) — write your own proverb",
              file=sys.stderr)
        return 1
    i = r["idiom"]
    print(f"> {line(r)}")
    print(f"> — zikai · {i.get('slug')} · "
          f"{r.get('decider')} · conf {r.get('confidence')}")
    if a.trace and r.get("trace"):
        tops = ", ".join(t["slug"] for t in r["trace"][:5])
        print(f"> shortlist: {tops}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
