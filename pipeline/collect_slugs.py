#!/usr/bin/env python3
"""Collect idiom slugs + lastmod from chineseidioms.com sitemaps.

Discovery law: the sitemap is the authoritative list (the rendered
dictionary page only shows 263 entries); new pages surface here first on
nightly runs.
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.request

BASE = "https://www.chineseidioms.com"
SITEMAPS = [f"{BASE}/sitemap/{i}.xml" for i in (0, 1, 2, 3, 4, 5, 6, 7)]
UA = "zikai-sync/0.1 (research mirror; contact: jacob@hausler.cc)"


def get(url: str) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    entries: dict[str, str] = {}
    seen_sitemaps = 0
    for sm in SITEMAPS:
        xml = get(sm)
        if not xml:
            continue
        seen_sitemaps += 1
        for m in re.finditer(
                r"<url>\s*<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>",
                xml):
            url, lm = m.group(1), m.group(2)
            mm = re.match(r"https://www\.chineseidioms\.com/blog/([a-z0-9-]+)$",
                          url)
            if mm:
                entries[mm.group(1)] = lm
    if not entries:
        print("[slugs] ERROR: no sitemaps yielded entries", flush=True)
        return 1
    json.dump(entries, open(args.out, "w"), indent=0, sort_keys=True)
    print(f"[slugs] {len(entries)} slugs from {seen_sitemaps} sitemaps -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
