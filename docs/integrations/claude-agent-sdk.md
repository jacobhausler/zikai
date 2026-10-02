# Claude Agent SDK

Placement: an in-process MCP server (pip: `claude-agent-sdk`, `mcp`) — `@tool` +
`create_sdk_mcp_server` expose it as `mcp__zikai__decide`; the handler still only imports
`zikai.client`:

```python
from claude_agent_sdk import tool, create_sdk_mcp_server
from zikai.client import Client, ZikaiError, line   # the ONLY zikai import

@tool("zikai", "Return the chengyu most applicable to a situation, '博古通今 (bó gǔ tōng jīn) — gloss'.", {"text": str})
async def decide(args):
    try:
        return {"content": [{"type": "text", "text": line(Client().decide(args["text"]))}]}
    except (ZikaiError, AttributeError):
        return {"content": [{"type": "text", "text": "oracle: unavailable"}]}   # fail-open

zikai_server = create_sdk_mcp_server(name="zikai", tools=[decide])   # ClaudeAgentOptions(mcp_servers={"zikai": zikai_server})
```

Env: `ZIKAI_URL`, `ZIKAI_KEY`. UNVERIFIED: `claude-agent-sdk` not installed here — API names from knowledge.
