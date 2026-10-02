"""tools/zk rides the same client: one core, CLI spin.

Pins the two laws the CLI exists to enforce: the decider label prints
VERBATIM (never normalized), and a down endpoint yields
`oracle: unavailable` — never a remembered idiom.
"""
import os
import subprocess
import sys
import threading
import time

import pytest
import uvicorn

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZK = os.path.join(REPO, "tools", "zk")


@pytest.fixture(scope="module")
def lane():
    # same shape as test_adapters' lane: deterministic lexical, no key
    os.environ["ZIKAI_LAYA_BASE_URL"] = ""
    os.environ["ZIKAI_REQUIRE_KEY"] = "false"
    from zikai.app import create_app
    app = create_app()
    port = 8299
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


def _run(args, url):
    env = dict(os.environ, ZIKAI_URL=url, ZIKAI_KEY="", PYTHONPATH=REPO)
    return subprocess.run([sys.executable, ZK, *args], capture_output=True,
                          text=True, env=env, timeout=30)


def test_zk_decide_verbatim_label(lane):
    r = _run(["decide", "the plan looked fine until the rain"], lane)
    assert r.returncode == 0, r.stderr
    lines = r.stdout.strip().splitlines()
    assert any(l.startswith("decider: ") for l in lines)
    # label is raw engine output, byte-identical to the client's field
    from zikai.client import Client
    raw = Client(base_url=lane, key="").decide(
        "the plan looked fine until the rain", level="compact")["decider"]
    assert f"decider: {raw}" in r.stdout        # verbatim: not trimmed, not mapped


def test_zk_unavailable_never_remembers(lane):
    r = _run(["decide", "anything"], "http://127.0.0.1:9")
    assert r.returncode == 1
    assert r.stdout.strip() == "oracle: unavailable"
