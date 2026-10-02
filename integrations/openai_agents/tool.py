"""ZikaiOracle — OpenAI Agents SDK function tool (pip: openai-agents). The SDK
wraps plain functions; @function_tool makes the schema from the signature and
docstring. Env: ZIKAI_URL, ZIKAI_KEY. Fail-open law: oracle down => return
"oracle: unavailable"; the run proceeds, garnish dropped, no raise."""
import sys

_REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:              # run from a checkout, no install
    sys.path.insert(0, str(_REPO_ROOT))

from agents import Agent, function_tool           # binding shown in __main__ below

from zikai.client import Client, ZikaiError, line  # the ONLY zikai import

UNAVAILABLE = "oracle: unavailable"               # the one fail-open string, repo-wide


@function_tool
def zikai_decide(text: str, level: str = "compact") -> str:
    """Return the chengyu (Chinese idiom) most applicable to a situation, e.g.
    '博古通今 (bó gǔ tōng jīn) — well-read'. Call it when an idiomatic frame
    would land the answer better."""
    try:
        return line(Client().decide(text, level=level))   # timeout rides the client
    except (ZikaiError, AttributeError):           # fail-open — never raise into the run
        return UNAVAILABLE

AGENT = Agent(name="zikai-advised", instructions="Be concise; cite zikai_decide as 成语 (pīnyīn) — gloss when it sharpens the point.", tools=[zikai_decide])
