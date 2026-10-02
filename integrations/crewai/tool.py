"""ZikaiOracle — CrewAI tool (pip: crewai). CrewAI tools subclass BaseTool;
name/description/args_schema come from these class fields, _run is the call.
Env: ZIKAI_URL, ZIKAI_KEY. Fail-open law: unreachable => "oracle: unavailable",
so a crew run never dies over garnish."""
import sys

_REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:              # run from a checkout, no install
    sys.path.insert(0, str(_REPO_ROOT))

from crewai.tools import BaseTool

from zikai.client import Client, ZikaiError, line  # the ONLY zikai import

UNAVAILABLE = "oracle: unavailable"               # the one fail-open string, repo-wide


class ZikaiOracle(BaseTool):
    name: str = "zikai_decide"
    description: str = ("Return the chengyu (Chinese idiom) most applicable to a situation, "
                        "formatted '博古通今 (bó gǔ tōng jīn) — gloss'. Pass the situation "
                        "as plain words in `text`; optional `level` compact|full.")

    def _run(self, text: str, level: str = "compact") -> str:
        try:
            return line(Client().decide(text, level=level))   # timeout rides the client
        except (ZikaiError, AttributeError):       # fail-open — crew run proceeds
            return UNAVAILABLE
