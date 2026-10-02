"""ZikaiOracle — PydanticAI tool (pip: pydantic-ai). PydanticAI tools are plain
typed functions: the annotations are the JSON schema, the docstring is the
description. Bind it to YOUR agent (any model):

    from pydantic_ai import Agent
    from integrations.pydanticai.tool import zikai_decide
    agent = Agent("openai:gpt-4o-mini"); agent.tool(zikai_decide)

Env: ZIKAI_URL, ZIKAI_KEY. Fail-open law: unreachable => "oracle: unavailable"."""
import sys

_REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:              # run from a checkout, no install
    sys.path.insert(0, str(_REPO_ROOT))

from zikai.client import Client, ZikaiError, line  # the ONLY zikai import

UNAVAILABLE = "oracle: unavailable"               # the one fail-open string, repo-wide


def zikai_decide(text: str, level: str = "compact") -> str:
    """Return the chengyu (Chinese idiom) most applicable to a situation,
    formatted '博古通今 (bó gǔ tōng jīn) — gloss'; cite it when an idiomatic
    frame would land the answer better."""
    try:
        return line(Client().decide(text, level=level))   # timeout rides the client
    except (ZikaiError, AttributeError):           # fail-open — never raise into run_sync
        return UNAVAILABLE
