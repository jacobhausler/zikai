"""ZikaiOracle — LangChain/LangGraph tool: one @tool binds into a ReAct chain or
a LangGraph ToolNode identically. Env: ZIKAI_URL, ZIKAI_KEY. Fail-open law:
unreachable oracle => "oracle: unavailable", never a raise into the chain."""
import sys

_REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:              # run from a checkout, no install
    sys.path.insert(0, str(_REPO_ROOT))

from langchain_core.tools import tool

from zikai.client import Client, ZikaiError, line  # the ONLY zikai import

UNAVAILABLE = "oracle: unavailable"               # the one fail-open string, repo-wide


@tool("zikai_decide")
def zikai_decide(text: str, level: str = "compact") -> str:
    """Return the chengyu (Chinese idiom) most applicable to the given situation,
    formatted '博古通今 (bó gǔ tōng jīn) — gloss'. Call it when an answer would
    land better with an idiomatic frame."""
    try:
        return line(Client().decide(text, level=level))   # timeout rides the client
    except (ZikaiError, AttributeError):           # fail-open — garnish dropped
        return UNAVAILABLE
