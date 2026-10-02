#!/usr/bin/env python3
"""zikai alert shim — Alertmanager webhook -> alert with an idiom epigraph.

Small stdlib HTTP receiver: Alertmanager posts its group here, we ask the
oracle to name the group's *condition*, then forward the alert to ntfy with
one epigraph line the whole team reads before the runbook:

    隔靴搔痒 (gé xuē sāo yǎng) — scratching through the boot: indirect effort

Run:  ZIKAI_URL=... ZIKAI_KEY=... NTFY=.../alerts FORWARDER_TOKEN=... \
      python3 zikai-alert-shim.py --port 8951 --forward http://ntfy-alertmanager:8080
If you don't want a forwarder, --forward is optional: the shim publishes
directly to ntfy itself (title carries the idiom; body carries the group).

Why: the pager is the one message humans always read — a single line of
成語 makes the fleet's failure weather legible as a *type*, not an instance.
The shim NEVER eats an alert: oracle down => the forward goes out uncommented.
"""
import argparse
import json
import os
import sys
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _forward(url: str, payload: dict) -> bool:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"content-type": "application/json"})
    tok = os.environ.get("FORWARDER_TOKEN", "")
    if tok:
        req.add_header("authorization", "Basic " + tok)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return 200 <= r.status < 300
    except Exception:
        return False


class Handler(BaseHTTPRequestHandler):
    opts: argparse.Namespace

    def log_message(self, format, *a):  # noqa: A002 (stdlib name) — quiet
        pass

    def do_POST(self):  # noqa: N802 (stdlib name)
        try:
            n = int(self.headers.get("content-length", 0))
            group = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            self.send_response(400); self.end_headers(); return

        names = sorted({a["labels"].get("alertname", "?")
                        for a in group.get("alerts", [])})
        sev = min((a["labels"].get("severity", "info")
                   for a in group.get("alerts", [])),
                  key=lambda s: ["info", "warning", "critical"].index(s)
                  if s in ("info", "warning", "critical") else 2,
                  default="info")
        text = "alerts firing: " + ", ".join(names[:6])
        epigraph = ""
        try:
            from zikai.client import Client, line
            r = Client(timeout=4.0).decide(text, level="compact")
            epigraph = line(r)
        except Exception:
            pass  # no poem, no problem: the alert itself must survive

        title = f"[{sev}] {names[0] if names else 'alert-group'}"
        body = (epigraph + "\n\n" if epigraph else "") + text
        ok = True
        if self.opts.forward:
            group.setdefault("commonAnnotations", {})
            if epigraph:
                group["commonAnnotations"]["zikai"] = epigraph
            ok = _forward(self.opts.forward, group)
        elif self.opts.ntfy:
            req = urllib.request.Request(
                self.opts.ntfy.rstrip("/") + "/alerts",
                data=body.encode(),
                headers={"Title": title, "Tags": "warning" if sev == "critical" else "information"})
            tok = os.environ.get("NTFY_TOKEN", "")
            if tok:
                req.add_header("Authorization", "Bearer " + tok)
            try:
                ok = urllib.request.urlopen(req, timeout=5).status < 300
            except Exception:
                ok = False
        self.send_response(202 if ok else 502)
        self.end_headers()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8951)
    ap.add_argument("--forward", default="", help="AM-bridge webhook URL (preferred)")
    ap.add_argument("--ntfy", default="", help="direct ntfy base URL (fallback)")
    Handler.opts = ap.parse_args()
    HTTPServer(("0.0.0.0", Handler.opts.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
