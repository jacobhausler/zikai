"""FastAPI app — decisions-API-compliant endpoints + cute dashboard.

Endpoints
  POST /decide            {text, level?, decider?, extras?, trace?}
  GET  /decide?q=...&key=***   same, GET-friendly (dashboard/health checks)
  POST /v1/decisions      alias kept vendor-flavoured; body == /decide
  GET  /idioms/{slug}     hydrated record by slug
  GET  /idioms?q=...      lexical search over the corpus
  GET  /tree              the clustered decision tree (data, not code)
  GET  /stats             corpus + tree stats + freshness
  GET  /healthz           liveness
  GET  /                  dashboard
"""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from . import __version__, metrics
from .config import get_settings
from .engine import Engine, load_engine
from .shapes import format_line, hydrate

DASH = Path(__file__).resolve().parent.parent / "dashboard" / "index.html"


def create_app(engine: Engine | None = None) -> FastAPI:
    app = FastAPI(title="zikai · 子開", version=__version__,
                  description="Decisions API over the chineseidioms.com corpus")
    app.state.engine = engine or load_engine(settings=get_settings())
    settings = app.state.engine.settings  # auth follows the engine's config
    metrics.set_corpus(len(app.state.engine.corpus))

    class Auth:
        """Explicit callable dependency — settings bound on the instance,
        never in a closure (testability + one obvious lookup path)."""

        def __init__(self, settings):
            self.settings = settings

        def __call__(self, authorization: str | None = Header(default=None),
                     x_api_key: str | None = Header(default=None,
                                                    alias="x-api-key"),
                     key: str | None = Query(default=None)):
            s = self.settings
            if not s.require_key or not s.api_keys.strip():
                return
            supplied = None
            if authorization and authorization.lower().startswith("bearer "):
                supplied = authorization[7:].strip()
            supplied = supplied or x_api_key or key
            if supplied not in s.key_set:
                raise HTTPException(401, "invalid or missing API key")

    auth = Auth(settings)

    # --- hot-reload: the nightly rebuild lands new files in place; pick them
    # up without a restart. Checked at most every 5s on the decide path.
    import os as _os
    import threading as _threading
    import time as _time
    _paths = [settings.corpus_path, settings.tree_path]
    _mt = [_os.stat(p).st_mtime if _os.path.exists(p) else 0 for p in _paths]
    _lock = _threading.Lock()
    _last_check = [0.0]

    def _maybe_reload():
        now = _time.monotonic()
        if now - _last_check[0] < 5:
            return
        _last_check[0] = now
        fresh = [_os.stat(p).st_mtime if _os.path.exists(p) else 0
                 for p in _paths]
        if fresh != _mt:
            with _lock:
                try:
                    eng = load_engine(settings)
                    app.state.engine = eng
                    metrics.set_corpus(len(eng.corpus))
                    _mt[:] = fresh
                except Exception:
                    pass  # keep serving the last good corpus, never 500

    @app.get("/healthz")
    def healthz():
        _maybe_reload()  # throttled by its own 5s clock; probes see fresh counts
        e: Engine = app.state.engine
        return {"ok": True, "version": __version__,
                "idioms": len(e.corpus), "clusters": len(e.tree["clusters"]),
                "themes": len(e.tree["root"]["options"])}

    @app.get("/metrics", include_in_schema=False)
    def scrape():
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(metrics.exposition(),
                                 media_type="text/plain; version=0.0.4")


    @app.post("/decide", dependencies=[Depends(auth)])
    @app.post("/v1/decisions", dependencies=[Depends(auth)])
    async def decide_api(req: Request):
        body = await req.json()
        # The engine's model calls are blocking httpx (~27s on a loaded lane).
        # Run them in the threadpool so the event loop never pins — an async
        # decide would time out every concurrent request behind a slow call.
        from fastapi.concurrency import run_in_threadpool
        return await run_in_threadpool(
            _decide, body.get("text"), body.get("decider"),
            body.get("level", "full"), body.get("extras"),
            bool(body.get("trace")), bool(body.get("related_resolved")))

    @app.get("/decide", dependencies=[Depends(auth)])
    def decide_get(q: str = Query(..., min_length=1),
                   decider: str | None = None, level: str = "full",
                   extras: str | None = None, trace: bool = False,
                   related: bool = False):
        return _decide(q, decider, level,
                       extras.split(",") if extras else None, trace, related)

    def _decide(text: str | None, decider: str | None,
                level: str, extras: list[str] | None, trace: bool,
                related_resolved: bool):
        if not text or not text.strip():
            raise HTTPException(422, "text is required")
        _maybe_reload()
        e: Engine = app.state.engine
        if len(text) > 8000:
            text = text[:8000]
        import time as _t
        t0 = _t.perf_counter()
        try:
            result = e.decide(text, decider=decider, trace=trace)
        except Exception:
            metrics.note_error()
            raise
        metrics.note_decide(_t.perf_counter() - t0)
        result["idiom"] = hydrate(result["idiom"], level=level,
                                  extras=extras,
                                  related_resolved=related_resolved,
                                  corpus=e.corpus)
        result["level"] = level
        return JSONResponse(result)

    @app.get("/idioms/{slug}", dependencies=[Depends(auth)])
    def idiom_by_slug(slug: str, level: str = "full",
                      related: bool = False):
        e: Engine = app.state.engine
        rec = e.corpus.get(slug)
        if not rec:
            raise HTTPException(404, f"no idiom slug {slug!r}")
        out = hydrate(dict(rec), level=level, related_resolved=related,
                      corpus=e.corpus)
        if level == "text":
            out = {"text": format_line(rec)}
        return {"slug": slug, "idiom": out}

    @app.get("/idioms", dependencies=[Depends(auth)])
    def idiom_search(q: str = Query(..., min_length=1), limit: int = 8):
        e: Engine = app.state.engine
        ql = q.lower()
        scored = []
        for slug, r in e.corpus.items():
            hay = " ".join(str(r.get(k) or "") for k in
                           ("slug", "hanzi", "pinyin", "meaning", "literal",
                            "theme")).lower()
            if ql in hay or (len(ql) > 3 and ql in r.get("slug", "").lower()):
                scored.append({k: r.get(k) for k in
                               ("slug", "hanzi", "pinyin", "meaning", "theme",
                                "url")})
            if len(scored) >= max(50, limit):
                break
        return {"query": q, "results": scored[:limit], "count": len(scored)}

    @app.get("/tree")
    def tree():
        return app.state.engine.tree

    @app.get("/stats")
    def stats():
        e: Engine = app.state.engine
        return {"version": __version__, "idioms": len(e.corpus),
                "themes": {o["label"]: len(o["clusters_ref"])
                           for o in e.tree["root"]["options"]},
                "clusters": {cid: len(c["idioms"])
                            for cid, c in e.tree["clusters"].items()},
                "max_depth": e.tree["max_depth"],
                "adapters_configured": sorted(e.adapters)}

    @app.get("/", include_in_schema=False)
    def dashboard():
        if not settings.dashboard or not DASH.exists():
            return JSONResponse({"service": "zikai", "version": __version__,
                                 "endpoints": [r.path for r in app.routes
                                               if hasattr(r, "path")]})
        return HTMLResponse(DASH.read_text(encoding="utf-8"))

    return app
