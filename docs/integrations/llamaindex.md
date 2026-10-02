# LlamaIndex

Placement: a `@tool`-decorated function (pip: `llama-index-core`) — schema comes from
signature + docstring; no transport code of its own:

```python
from llama_index.core.tools import tool
from zikai.client import Client, ZikaiError, line   # the ONLY zikai import

@tool("zikai_decide")
def zikai_decide(text: str, level: str = "compact") -> str:
    """Return the chengyu (Chinese idiom) most applicable to a situation, '博古通今 (bó gǔ tōng jīn) — gloss'."""
    try:
        return line(Client().decide(text, level=level))
    except (ZikaiError, AttributeError):
        return "oracle: unavailable"       # fail-open: the run proceeds ungarnished
```

Bind: `ReActAgent(tools=[zikai_decide])`. Env: `ZIKAI_URL` (default `http://127.0.0.1:8077`), `ZIKAI_KEY`.
UNVERIFIED: `llama-index-core` not installed in this venv — decorator API written from knowledge.
