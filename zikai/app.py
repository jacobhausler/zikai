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

from . import __version__
from .config import get_settings
from .engine import Engine, load_engine
from .shapes import format_line, hydrate

DASH = Path(__file__).resolve().parent.parent / "dashboard" / "index.html"


def create_app(engine: Engine | None = None) -> FastAPI:
    app = FastAPI(title="zikai · 子開", version=__version__,
                  description="Decisions API over the chineseidioms.com corpus")
    app.state.engine = engine or load_engine(settings=get_settings())
    settings = app.state.engine.settings  # auth follows the engine's config

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

    @app.get("/healthz")
    def healthz():
        e: Engine = app.state.engine
        return {"ok": True, "version": __version__,
                "idioms": len(e.corpus), "clusters": len(e.tree["clusters"]),
                "themes": len(e.tree["root"]["options"])}

    @app.post("/decide", dependencies=[Depends(auth)])
    @app.post("/v1/decisions", dependencies=[Depends(auth)])
    async def decide_api(req: Request):
        body = await req.json()
        return _decide(body.get("text"), body.get("decider"),
                       body.get("level", "full"), body.get("extras"),
                       bool(body.get("trace")),
                       bool(body.get("related_resolved")))

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
        e: Engine = app.state.engine
        if len(text) > 8000:
            text = text[:8000]
        result = e.decide(text, decider=decider, trace=trace)
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
