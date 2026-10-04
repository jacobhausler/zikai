"""Gate contract for the hermes oracle hook (adapters/hermes-hooks).

Used-but-not-overused is the contract; these are the gates. All offline:
the live-decide path is proven with a fake client, the real lane is proven
in the lane's own receipt. Fail-open everywhere: the hook returning None is
the correct answer for anything that isn't a clean, undecorated, discord-
sided lesson moment with a reachable oracle.
"""
import importlib.util
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "zkhook", REPO / "adapters" / "hermes-hooks" / "__init__.py")
hk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hk)

VERDICT = ("Books closed. The verdict: self-reported metadata must be derived from the "
           "execution path, not the configuration path — the standing rule after the "
           "postmortem showed the label lied while the counter stayed green. Root cause "
           "was a swallowed error; the receipt carries the number and the fix shape.")
PLAIN = "Sure — restarted the prometheus alloc, healthy in 45 seconds."


class FakeClient:
    def __init__(self, boom=False):
        self.boom = boom

    def decide(self, text, level="compact"):
        if self.boom:
            raise hk._ZikaiError("down")
        return {"idiom": {"hanzi": "刻舟求劍", "pinyin": "kè zhōu qiú jiàn",
                          "meaning": "Using outdated methods foolishly. Extra."},
                "decider": "openai_compat+fallback", "confidence": 0.1}


def setup_function(_):
    hk._client = None
    hk._client_failed = False
    os.environ.pop("ZIKAI_HOOK", None)
    try:
        from zikai.client import ZikaiError
        hk._ZikaiError = ZikaiError
    except Exception:
        sys.path.insert(0, str(REPO))
        from zikai.client import ZikaiError
        hk._ZikaiError = ZikaiError


def _with(fake):
    hk._client = fake
    hk._client_failed = False


def test_platform_and_size_gates():
    assert hk._decorate(VERDICT, platform="telegram") is None
    assert hk._decorate(VERDICT, platform="") is None
    assert hk._decorate("brief yes.", platform="discord") is None   # chatter


def test_no_moment_no_decor():
    assert hk._decorate(PLAIN + " " + "padding " * 40, platform="discord") is None


def test_already_quoted_never_double():
    assert hk._decorate(VERDICT + " 事毕矣", platform="discord") is None
    assert hk._decorate(VERDICT + "\n\n> oracle: x", platform="discord") is None


def test_kill_switch_and_dead_oracle():
    os.environ["ZIKAI_HOOK"] = "0"
    assert hk._decorate(VERDICT, platform="discord") is None
    os.environ["ZIKAI_HOOK"] = "1"
    _with(FakeClient(boom=True))            # oracle down => send clean
    assert hk._decorate(VERDICT, platform="discord") is None


def test_clean_moment_appends_verbatim():
    _with(FakeClient())
    out = hk._decorate(VERDICT, platform="discord")
    assert out is not None and out.startswith(VERDICT)
    assert "\n\n> oracle: 刻舟求劍 (kè zhōu qiú jiàn) — Using outdated methods foolishly [lexical]" in out
