# 子開 zikai — the idiom oracle

> 子使漆雕開仕。對曰：「吾斯之未能信。」子說。
> *The Master urged Qidiao Kai to take office. "I have not yet made my
> study trustworthy," he replied — and the Master was pleased.* (Analects 5.20)
>
> 是故學然後知不足。*Only after studying does one know one's own gap.* (學記, Book of Rites)

This service is named after 子開 (Qidiao Kai, 漆雕開), the disciple who
declined a government post rather than answer before he was ready. An oracle
named for a man who refused premature answers: the `confidence` field and the
trace mode are that refusal encoded — the service always tells you how little
it is sure of.

**zikai** maps the [chineseidioms.com](https://www.chineseidioms.com) chengyu
corpus (1072 idioms, hydrated) into a **shallow clustered decision tree**
and serves it behind a **decisions-style API**: text in → the single most
applicable idiom out, fully hydrated (hanzi, pinyin, literal + metaphoric
meaning, origin, examples, FAQ, related idioms).

## Why shallow (the design law)

Every extra tree level is a latency tax and an error multiplication. Two
model calls — *theme*, then *cluster* — then the final pick is a
**retrieval+rerank scoring stage**, not a third question. Routing answers
guide (boost) retrieval but can never evict the right idiom before the
decider sees it: the shortlist is retrieved over the whole corpus, widened
by one semantic keyword-expansion hop from the decider.

```
text ──Q1 theme──► 5 themes ──Q2 cluster──► 43 clusters
     └► keyword expansion ─► global lexical retrieval (top-12) ─► decider rerank ─► winner
                                                          depth capped at 2
```

## Quick start

```bash
python -m venv .venv && .venv/bin/pip install -e .[dev]
zikai build                # records.jsonl -> corpus.json + decision_tree.json
zikai serve --port 8077    # API + dashboard at http://localhost:8077/
zikai decide "He bragged to the master" --level text
pytest                     # 12 tests, zero keys required (lexical decider)
```

## Endpoints

| | |
|---|---|
| `POST /decide` | `{"text": "...", "level": "full\|compact\|text\|slug", "decider": "...", "extras": ["origin"], "trace": true, "related_resolved": true}` |
| `GET /decide?q=` | same, GET-friendly (`?key=*** for health checks) |
| `POST /v1/decisions` | vendor-flavoured alias, same body |
| `GET /idioms/{slug}` | hydrated record by slug (`?level=`, `?related=true`) |
| `GET /idioms?q=` | lexical search (hanzi/pinyin/meaning/slug) |
| `GET /tree` | the clustered decision tree as data |
| `GET /stats` · `GET /healthz` | corpus/adapter stats, liveness |
| `GET /` | the dashboard |

Auth: any of `Authorization: Bearer`, `x-api-key`, or `?key=*** compared
against `ZIKAI_API_KEYS` (comma-separated). Leave it unset to run open.

## Decider adapters (the trendy-API adapter layer)

One normalized shape — *(text, question, options) → value* — vendors
pluggable at request time (`"decider": "..."`) or by env:

- `openai` — OpenAI chat completions (`ZIKAI_OPENAI_API_KEY`)
- `anthropic` — Messages API (`ZIKAI_ANTHROPIC_API_KEY`)
- `openai_compat` — **any** chat-completions endpoint: laya, sglang, vLLM,
  deepseek, openrouter (`ZIKAI_LAYA_BASE_URL=http://host:18030/v1`)
- `together` / `groq` / `fireworks` — aliases over the OpenAI adapter
- `lexical` — zero-key character/word Dice fallback. **A failed vendor call
  percolates nowhere: each node falls back to lexical, so the API never
  returns 500 because a vendor sneezed.**

```bash
export ZIKAI_LAYA_BASE_URL=http://192.168.0.122:18030/v1  # zero-cent substrate
export ZIKAI_OPENAI_API_KEY=***                            # premium rerank lane
export ZIKAI_API_KEYS=zk-public-1,zk-partner-2             # keys YOU accept
```

## Response levels

- `full` — everything: hanzi, pinyin, literal + metaphoric meaning, origin,
  examples (en/zh), FAQ, related slugs, term code, source URL, provenance
  (`decision_path`, `cluster`, `runner_ups`, `confidence`, `latency_ms`)
- `compact` — decision essentials
- `text` — one line: `按部就班 (àn bù jiù bān) — Follow established procedures [slug]`
- `slug` — machine-to-machine minimal
- `extras:["origin","faq"]` force-include any meta field;
  `related_resolved:true` hydrates related slugs into `{slug,hanzi,meaning}`.

## Nightly mapping refresh

`pipeline/` is robots.txt-respecting (only `/api/` is disallowed),
lastmod-incremental, 0.45s/request politeness, UA-declared.

```bash
zikai nightly --push    # resync sitemaps → scrape changed → rebuild → git push data
```

The data artifacts (`corpus.json`, `decision_tree.json`, `records.jsonl`)
are committed with date-stamped snapshot commits so the mapping history is
reviewable per-night. Schedule with cron/systemd:

```cron
17 5 * * * cd /path/to/zikai && .venv/bin/zikai nightly --push >> data/nightly.log 2>&1
```

## Dashboard

`GET /` — rice-paper + vermillion, seal-script 開 stamp, vertical hanzi
card, one-click test situations, near-miss drilldown, session history,
random **抽一句 Draw**, grove search by hanzi/pinyin/meaning, raw-JSON
copy, `Ctrl/Cmd+Enter` to decide. No build step, one HTML file, no CDN.

## Repo layout

```
zikai/            app.py (API) engine.py (tree walk) adapters.py (vendor layer)
                  tree.py (cluster build) shapes.py (levels) config.py cli.py
pipeline/         collect_slugs.py (sitemap) scrape.py (hydrating scraper)
data/             records.jsonl corpus.json decision_tree.json (refreshed nightly)
dashboard/        index.html
tests/            12 tests, no keys needed
```

## Honesty notes

- Corpus fields are copied verbatim from source JSON-LD/rendered sections;
  the service never invents metadata. Source attribution rides in every
  record (`url`, `term_code`).
- `confidence` is the lexical score of the winner, floored at 0.45 when a
  remote decider confirmed the pick — an honest instrument, not a probability.
- Self-tested eval: 4/7 on a adversarial near-synonym probe set with the
  free local rerank; premium keys lift the rerank lane. Trace mode exposes
  the whole shortlist when you want to judge the machine's judgment.

*子開: 學然後知不足 — the answer is the beginning of the study, not the end.*
