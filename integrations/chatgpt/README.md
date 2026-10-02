# zikai as a ChatGPT integration

Two routes, neither of which is "paste your LAN URL and hope":

1. Packaged skill — take `skills/zikai/SKILL.md` (the practice, zero code),
   zip it, and upload it as a skill in ChatGPT (Settings > Apps/Skills or via
   a Project). The skill teaches the model when to cite an idiom and how —
   but the hosted model cannot call your API: ChatGPT sessions run on OpenAI
   servers, which cannot reach localhost or the LAN. Any tool call from here
   needs a publicly reachable endpoint (owner gate — public exposure of
   zikai is not enabled today).

2. Remote MCP service — same constraint: ChatGPT connectors must reach a
   public https URL. Self-host the MCP server
   (`integrations/mcp/server.py` is stdio; you would front it with an
   SSE/streamable-HTTP bridge at a public host) only if the deployment
   exposes a public endpoint.

Recommendation: the local harnesses (CLI `tools/zk`, the Claude Code
slash-command, the MCP server over stdio) are where zikai actually lives.
ChatGPT gets the skill as literacy, not as a live oracle — UNVERIFIED: skill
upload packaging (zip layout, size caps) was not exercised on a real account.
