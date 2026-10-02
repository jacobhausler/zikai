#!/usr/bin/env python3
"""zikai MCP server (子開) — stdio, stdlib-only, MINIMAL SUBSET of the
modelcontextprotocol baseline: initialize, ping, notifications/*, and the
tools surface (tools/list, tools/call) over newline-delimited JSON-RPC 2.0.
No resources, no prompts, no sampling — the whole point is one tool.

One tool: zikai_decide(text, level?) -> the idiom that names the situation,
delegating to zikai.client (the ONLY transport code that exists). Fail-open:
oracle down => a text result saying so + isError, never a crashed server.

Run:  ZIKAI_URL=... ZIKAI_KEY=... python3 server.py   (spawned by the client)
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

TOOL = {
    "name": "zikai_decide",
    "description": "Ask the 子開 oracle which Chinese idiom names this situation. "
                   "Pass the situation as plain text; the answer is one idiom, "
                   "with pinyin, gloss, and the decider that actually ran.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "the situation, in a sentence"},
            "level": {"type": "string", "enum": ["slug", "text", "compact", "full"],
                      "description": "how much of the idiom record to return"},
        },
        "required": ["text"],
    },
}

SERVER = {"name": "zikai", "version": "0.0.1"}
PROTOCOL = "2024-11-05"


def call(req):
    """One tools/call: delegate to zikai.client; never raise."""
    args = (req.get("params") or {}).get("arguments") or {}
    try:
        from zikai.client import Client, line
        text = str(args.get("text", ""))
        level = args.get("level", "compact")
        d = Client().decide(text, level=level)
        body = line(d)
        if level == "full":
            body += "\n" + json.dumps(d, ensure_ascii=False, indent=2)
        return {"content": [{"type": "text", "text": body}]}
    except Exception as e:
        return {"content": [{"type": "text",
                             "text": f"zikai unavailable: {e.__class__.__name__}"}],
                "isError": True}


def handle(req):
    m = req.get("method")
    if m == "initialize":
        return {"protocolVersion": PROTOCOL, "capabilities": {"tools": {}},
                "serverInfo": SERVER}
    if m == "ping":
        return {}
    if m == "tools/list":
        return {"tools": [TOOL]}
    if m == "tools/call":
        return call(req)
    if m.startswith("notifications/"):
        return None                      # notifications get no response
    return {"_err": (-32601, f"method not found: {m}")}


def main():
    for ln in sys.stdin:                 # newline-delimited JSON-RPC 2.0
        ln = ln.strip()
        if not ln:
            continue
        try:
            req = json.loads(ln)
        except json.JSONDecodeError:
            out = {"jsonrpc": "2.0", "id": None,
                   "error": {"code": -32700, "message": "parse error"}}
        else:
            try:
                res = handle(req)
            except Exception as e:       # a tool must never kill the pipe
                res = {"_err": (-32603, e.__class__.__name__)}
            rid = req.get("id")
            if res is None or (rid is None and "_err" not in res):
                continue                 # notification: no reply at all
            out = {"jsonrpc": "2.0", "id": rid}
            if "_err" in res:
                out["error"] = {"code": res["_err"][0], "message": res["_err"][1]}
            else:
                out["result"] = res
        sys.stdout.write(json.dumps(out) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
