"""Open WebUI tool: ask zikai (子開) to name your situation.

Native Tool plugin (Open-WebUI/tools convention): a class with a `valve` and a
`pipe` callable. Import it in Settings > Tools. Requires ZIKAI_URL and
ZIKAI_KEY in the Open WebUI server env; stdlib-only, one request, timeout.
The response carries `decider` — what actually ran; trust it over the poem.
"""
import json
import os
import urllib.request

URL = os.environ.get("ZIKAI_URL", "http://127.0.0.1:8077").rstrip("/")
KEY = os.environ.get("ZIKAI_KEY", "")


class ZikaiTools:
    def valves(self):
        return {}

    def pipe(self, body: str, model: str = None, __body__: dict = None):
        req = urllib.request.Request(
            URL + "/decide",
            data=json.dumps({"text": body, "level": "compact"}).encode(),
            headers={"content-type": "application/json", "x-api-key": KEY})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                d = json.loads(r.read().decode())
        except Exception:
            return "zikai unavailable"          # fail-open: chat proceeds
        i = d.get("idiom") or {}
        yield (f"{i.get('hanzi', '?')} ({i.get('pinyin', '')}) — "
               f"{i.get('meaning', '')} [decider: {d.get('decider', '?')}]")
