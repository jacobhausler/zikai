"""Adapters ride the same client: one core, three spins.

These tests pin the CONTRACT each adapter depends on (client shape + the
degrade path + the three adapter entry points importable and callable).
If the core drifts, all three adapters red here, not in someone's terminal.
"""
import json
import os
import subprocess
import sys
import threading
import time

import pytest
import uvicorn

import zikai.client as C

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def lane():
    os.environ["ZIKAI_LAYA_BASE_URL"] = ""     # deterministic lexical lane
    os.environ["ZIKAI_REQUIRE_KEY"] = "false"
    from zikai.app import create_app
    app = create_app()
    port = 8199
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
                                        log_level="error"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    deadline = time.time() + 15
    while not srv.started and time.time() < deadline:
        time.sleep(0.1)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    t.join(timeout=5)


def test_client_contract(lane):
    c = C.Client(base_url=lane, key="")
    h = c.healthz()
    assert h["ok"] and h["idioms"] > 900
    r = c.decide("I grepped the stale log for state that only lives now",
                 level="compact")
    assert r["idiom"]["slug"] and r["decision_path"]
    s = c.stats()
    assert s["idioms"] == h["idioms"]


def test_client_auth_and_retry_shape(lane, monkeypatch):
    # 4xx is a verdict (no retry); network flake retries once — verified via
    # call counting on a client pointed at a dead port.
    calls = {"n": 0}
    c = C.Client(base_url="http://127.0.0.1:1", key="", timeout=0.4)
    orig = c._request

    def spy(method, path, body):
        calls["n"] += 1
        return orig(method, path, body)
    c._request = spy
    with pytest.raises(C.ZikaiError) as e:
        c.decide("x")
    assert e.value.status is None and calls["n"] == 2   # one retry, then raise


def test_line_single_source(lane):
    r = C.Client(base_url=lane, key="").decide("the plan looked fine until the rain",
                                               level="compact")
    s = C.line(r)
    assert r["idiom"]["hanzi"] in s and r["idiom"]["pinyin"] in s


def _run(script, args, env_extra=None):
    env = dict(os.environ, PYTHONPATH=REPO, **(env_extra or {}))
    return subprocess.run([sys.executable, os.path.join(REPO, script), *args],
                          capture_output=True, text=True, env=env, timeout=30)


def test_receipt_header_adapter(lane):
    r = _run("adapters/receipt-header/zk-quote.py",
             ["we trusted the green counter and it was the counter that died"],
             {"ZIKAI_URL": lane, "ZIKAI_KEY": ""})
    assert r.returncode == 0 and "— zikai ·" in r.stdout


def test_prepare_commit_hook_adapter_silent_when_down(lane):
    msgfile = "/tmp/zk-adapt-commitmsg"
    open(msgfile, "w").write("fix: drained the pond to count the fish\n")
    r = _run("adapters/git-prepare-commit-msg/zikai-prepare-commit-msg.py",
             [msgfile], {"ZIKAI_URL": "http://127.0.0.1:1", "ZIKAI_KEY": ""})
    assert r.returncode == 0
    assert "Zikai:" not in open(msgfile).read()          # endpoint down: untouched
    open(msgfile, "w").write("fix: drained the pond to count the fish\n")
    r = _run("adapters/git-prepare-commit-msg/zikai-prepare-commit-msg.py",
             [msgfile], {"ZIKAI_URL": lane, "ZIKAI_KEY": ""})
    assert r.returncode == 0 and "Zikai:" in open(msgfile).read()
    # idempotence: second run on decorated message adds nothing
    before = open(msgfile).read()
    _run("adapters/git-prepare-commit-msg/zikai-prepare-commit-msg.py",
         [msgfile], {"ZIKAI_URL": lane, "ZIKAI_KEY": ""})
    assert open(msgfile).read() == before


def test_alert_shim_forwards_with_epigraph(lane):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "shim", os.path.join(REPO, "adapters/alertmanager-webhook/zikai-alert-shim.py"))
    assert spec and spec.loader
    shim = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shim)
    from http.server import BaseHTTPRequestHandler, HTTPServer
    got = {}

    class Cap(BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers["content-length"])
            got.update(json.loads(self.rfile.read(n)))
            self.send_response(200)
            self.end_headers()

        def log_message(self, format, *a):
            pass
    cap = HTTPServer(("127.0.0.1", 8962), Cap)
    threading.Thread(target=cap.serve_forever, daemon=True).start()
    # the shim's Client() inherits the PROCESS env — the harness contract is
    # two env vars, so set them like any harness would:
    os.environ["ZIKAI_URL"] = lane
    os.environ["ZIKAI_KEY"] = ""
    sys.argv = ["shim", "--port", "8961", "--forward", "http://127.0.0.1:8962"]
    threading.Thread(target=shim.main, daemon=True).start()
    time.sleep(0.7)
    import urllib.request
    group = {"alerts": [{"labels": {"alertname": "DiskAlmostFull",
                                    "severity": "critical"},
                         "annotations": {}}]}
    code = urllib.request.urlopen(
        urllib.request.Request("http://127.0.0.1:8961",
                               data=json.dumps(group).encode(),
                               headers={"content-type": "application/json"}),
        timeout=10).status
    time.sleep(0.4)
    assert code == 202
    epi = got.get("commonAnnotations", {}).get("zikai", "")
    # the shim decides over ITS text ("alerts firing: ..."), so pin the shape,
    # not the idiom: hanzi (pinyin) — gloss
    assert epi and "(" in epi and ")" in epi and "—" in epi
