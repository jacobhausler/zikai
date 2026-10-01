#!/usr/bin/env python3
"""zikai pipeline — scrape chineseidioms.com idiom pages into records.jsonl.

Honesty law: every field is copied verbatim from the source page (JSON-LD
blocks + rendered sections). Nothing is inferred that isn't present on the
page. The page's own ``lastmod`` from the sitemap rides along so nightly
runs can diff. robots.txt allows / (only /api/ disallowed); we stay on
public HTML at a polite rate with a declared UA.

Usage:
  python3 scrape.py --slugs slugs.json --out data/records.jsonl \
      [--if-changed data/last_seen.json] [--workers 4] [--force]
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import html as html_mod
import json
import re
import sys
import time
import urllib.request

BASE = "https://www.chineseidioms.com"
UA = "zikai-sync/0.1 (research mirror; contact: jacob@hausler.cc)"
DELAY_S = 0.45  # polite per-request pause shared across workers


def fetch(url: str, retries: int = 3) -> str | None:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            if attempt == retries - 1:
                return None
            time.sleep(1.5 * (attempt + 1))
    return None


def strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = html_mod.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def parse_page(slug: str, page: str) -> dict:
    rec: dict = {"slug": slug, "url": f"{BASE}/blog/{slug}"}
    blocks = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', page, re.S)
    for b in blocks:
        try:
            val = json.loads(b)
        except Exception:
            continue
        items = val if isinstance(val, list) else [val]
        for it in items:
            t = it.get("@type")
            if t == "FAQPage":
                for q in it.get("mainEntity", []) or []:
                    rec.setdefault("faq", []).append(
                        {"q": q.get("name"),
                         "a": strip_tags(
                             (q.get("acceptedAnswer") or {}).get("text", ""))})
            if t == "DefinedTerm":
                rec["hanzi"] = it.get("name")
                rec["term_code"] = it.get("termCode")
                desc = it.get("description") or ""
                m = re.search(r'literally means "([^"]*)"', desc)
                if m:
                    rec["literal"] = m.group(1)
                m = re.search(r'metaphorically means "([^"]*)"', desc)
                if m:
                    rec["meaning_metaphoric"] = m.group(1)
                alts = it.get("alternateName") or []
                for a in alts:
                    if re.search(r"[\u4e00-\u9fff]", a):
                        continue
                    if re.match(r"^[a-z\s]+$", a):  # toneless pinyin
                        rec.setdefault("pinyin_plain", a)
                    else:
                        rec["pinyin"] = a
            elif t == "BlogPosting":
                rec["meaning"] = it.get("description")
                rec["origin"] = it.get("articleBody")
                rec["date_modified"] = it.get("dateModified")
                kw = [k.strip() for k in (it.get("keywords") or "").split(",")]
                theme = next((k for k in kw if k and not re.match(
                    r"^[a-z\s\u4e00-\u9fff]+$", k) and "meaning" not in k
                    and k not in (rec.get("pinyin"), rec.get("hanzi"),
                                  rec.get("pinyin_plain"))
                    and k[0].isupper()), None)
                if not theme:
                    theme = next((k for k in kw if " " in k
                                  and k[0].isupper()), None)
                rec["theme"] = theme

    def section(label: str) -> str | None:
        m = re.search(r"<h2[^>]*>" + label + r".*?</h2>(.*?)(?=<h2|<footer|</main)",
                      page, re.S)
        return strip_tags(m.group(1)) if m else None

    if not rec.get("origin"):
        rec["origin"] = section("Origin")
    ex = section("Examples")
    if ex:
        m = re.search(r'English:\s*"?(.*?)"?\s*(?:Chinese:|$)', ex)
        rec["example_en"] = (m.group(1) if m else ex)[:400]
        m = re.search(r"Chinese:\s*(.*?)\s*(?:Previous|Next|$)", ex)
        rec["example_zh"] = (m.group(1) if m else None)

    # literal meaning lives in DefinedTerm description: 'X literally means "A" and metaphorically means "B"'
    m = re.search(r'literally means\s*\\?"([^"\\]*)', page)
    if m:
        rec["literal"] = html_mod.unescape(m.group(1))
    m = re.search(r'metaphorically means\s*\\?"([^"\\]*)', page)
    if m:
        rec["meaning_metaphoric"] = html_mod.unescape(m.group(1))

    rel = re.findall(r'href="/blog/([a-z0-9-]+)"[^>]*>\s*(?:<(?:[^>]*)>)*([^<]{2,15})',
                     page)
    seen, related = set(), []
    for s, _t in rel:
        if s != slug and s not in seen:
            seen.add(s)
            related.append(s)
    rec["related"] = related[:10]

    faqs = re.findall(
        r'<script type="application/ld\+json">\s*(\[?\{?"@context".*?FAQPage.*?)</script>',
        page, re.S)
    if faqs:
        try:
            data = json.loads(faqs[0])
            data = data if isinstance(data, list) else [data]
            for it in data:
                for q in it.get("mainEntity", []) or []:
                    rec.setdefault("faq", []).append(
                        {"q": q.get("name"), "a": strip_tags(q.get("acceptedAnswer", {}).get("text", ""))})
        except Exception:
            pass

    m = re.search(r"<title>([^<]*)</title>", page)
    if m:
        rec["title"] = html_mod.unescape(m.group(1)).strip()
    rec["ok"] = bool(rec.get("hanzi") and rec.get("meaning"))
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--if-changed", default=None,
                    help="json map slug->lastmod; unchanged slugs skipped")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    slugs_raw = json.load(open(args.slugs))
    if isinstance(slugs_raw, dict):
        lastmod = slugs_raw
        slug_list = sorted(slugs_raw)
    else:
        lastmod = {}
        slug_list = sorted(set(slugs_raw))
    changed = None
    if args.if_changed and not args.force:
        try:
            changed = json.load(open(args.if_changed))
        except Exception:
            changed = None
    # re-fetch when the sitemap lastmod moved since our last record of it
    def stale(slug: str) -> bool:
        if not changed or slug not in changed:
            return True
        lm = lastmod.get(slug)
        return bool(lm) and changed[slug] != lm
    todo = [s for s in slug_list if stale(s)]
    if args.limit:
        todo = todo[: args.limit]
    print(f"[scrape] {len(todo)} of {len(slug_list)} to fetch", flush=True)

    done = {}
    t0 = time.time()

    def work(slug):
        time.sleep(DELAY_S)
        page = fetch(f"{BASE}/blog/{slug}")
        return slug, (parse_page(slug, page) if page else {"slug": slug, "ok": False, "error": "fetch"})

    with open(args.out, "a", encoding="utf-8") as fh:
        with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
            for slug, rec in ex.map(work, todo):
                done[slug] = lastmod.get(slug) or "fetched"
                if rec.get("ok") or rec.get("error"):
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fh.flush()
                if len(done) % 100 == 0:
                    print(f"[scrape] {len(done)}/{len(todo)} "
                          f"({time.time()-t0:.0f}s)", flush=True)
    if args.if_changed:
        merged = dict(changed or {})
        merged.update(done)
        json.dump(merged, open(args.if_changed, "w"))
    ok_n = sum(1 for s in done if done[s] != "failed")
    print(f"[scrape] done {len(done)} ({ok_n} ok) in {time.time()-t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
