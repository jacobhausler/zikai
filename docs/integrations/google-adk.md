# Google ADK

Placement: a `FunctionTool` (pip: `google-adk`) — ADK takes any plain callable and builds
the declaration from signature + docstring:

```python
from google.adk.tools import FunctionTool
from zikai.client import Client, ZikaiError, line   # the ONLY zikai import

def zikai_decide(text: str, level: str = "compact") -> str:
    """Return the chengyu (Chinese idiom) most applicable to a situation, '博古通今 (bó gǔ tōng jīn) — gloss'."""
    try:
        return line(Client().decide(text, level=level))
    except (ZikaiError, AttributeError):
        return "oracle: unavailable"       # fail-open: the agent run proceeds ungarnished

zikai_tool = FunctionTool(zikai_decide)    # Agent(model="gemini-2.5-flash", tools=[zikai_tool])
```

Env: `ZIKAI_URL` (default `http://127.0.0.1:8077`), `ZIKAI_KEY`.
UNVERIFIED: `google-adk` not installed in this venv — import path written from knowledge.
