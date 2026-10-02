# zikai — agent front door

The idiom oracle: text in → the single most applicable 成語 out, served by a
shallow clustered decision tree over the chineseidioms.com corpus.

## Install (clean machine)

```bash
python -m venv .venv && .venv/bin/pip install -e .[dev] && .venv/bin/zikai build
```

## The whole client contract — two env vars

| var | meaning |
|---|---|
| `ZIKAI_URL` | service base URL, default `http://127.0.0.1:8077` |
| `ZIKAI_KEY` | bearer key (only if the server set `ZIKAI_API_KEYS`) |

## zk verbs (`tools/zk`, stdlib-only, imports `zikai.client` and nothing else)

```bash
tools/zk decide "<situation>"   # 成語 (pīnyīn) — gloss [slug] + `decider:` verbatim
tools/zk decide --json "…"      # raw response; --trace shows the shortlist
tools/zk draw                   # random idiom for report footers
tools/zk stats                  # corpus/cluster counts
```

Copy outside the repo: invoke by absolute path (`…/zikai/tools/zk decide "…"`).

## Endpoints

| | |
|---|---|
| `POST /decide` | `{"text","level":"full|compact|text|slug","decider","extras","trace","related_resolved"}` |
| `GET /decide?q=` | same, GET-friendly (`?key=*** for health checks) |
| `POST /v1/decisions` | vendor-flavoured alias, same body |
| `GET /idioms/{slug}` · `GET /idioms?q=` | record by slug · lexical search |
| `GET /tree` · `GET /stats` · `GET /healthz` | tree as data · counts · liveness |
| `GET /` | the dashboard |

Auth: `Authorization: Bearer`, `x-api-key`, or `?key=*** against
`ZIKAI_API_KEYS` (comma-separated; unset = open).

## Fail-open contract (law)

Oracle down ⇒ `oracle: unavailable`, exit 1 — never a remembered idiom;
ship without one. Server-side: a failed vendor decider percolates nowhere,
each node falls back to lexical; the API never 500s because a vendor sneezed.
The `decider:` label prints VERBATIM (`+fallback`/`+judge_lexical` are data).

## Where to read next

- `skills/zikai/SKILL.md` — the canonical agent contract (when to ask, how to cite)
- `docs/integrations/README.md` — index of all 24 integrations
- `README.md` — quick start, provider tables, response levels
- `.env.example` — server-side config
