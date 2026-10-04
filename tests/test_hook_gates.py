"""Gate contract for the hermes oracle hook (adapters/hermes-hooks).

Used-but-not-overused is the contract; these are the gates. All offline:
live-decide paths run through a fake client, lane liveness through a fake
probe. Fail-open everywhere: None is the correct answer for anything that
isn't a clean, undecorated, discord-sided lesson moment with a reachable
oracle. Portability laws (austin's install receipt 2026-10-04): the pointer
file resolves beside the plugin's own file, HERMES_HOME overrides, and no
estate's profile name may ever be hardcoded in the adapter.
"""
import importlib.util
import inspect
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "zkhook", REPO / "adapters" / "hermes-hooks" / "__init__.py")
hk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hk)

from zikai.client import ZikaiError  # noqa: E402

VERDICT = ("Books closed. The verdict: self-reported metadata must be derived from the "
           "execution path, not the configuration path — the standing rule after the "
           "postmortem showed the label lied while the counter stayed green. Root cause "
           "was a swallowed error; the receipt carries the number and the fix shape.")
PLAIN = ("Sure — restarted the prometheus alloc and it came back healthy in about "
         "forty-five seconds; both probes look fine on the dashboards now, nothing else.")


class FakeClient:
    def __init__(self, boom=False):
        self.boom = boom

    def decide(self, text, level="compact"):
        if self.boom:
            raise ZikaiError("down")
        return {"idiom": {"hanzi": "刻舟求劍", "pinyin": "kè zhōu qiú jiàn",
                          "meaning": "Using outdated methods foolishly. Extra."},
                "decider": "openai_compat+fallback", "confidence": 0.1}


def setup_function(_):
    hk._client = None
    hk._client_failed = False
    for k in ("ZIKAI_HOOK", "ZIKAI_URL", "ZIKAI_KEY", "ZIKAI_REPO", "HERMES_HOME"):
        os.environ.pop(k, None)


def _with(fake):
    hk._client = fake
    hk._client_failed = False


def test_platform_and_size_gates():
    assert hk._decorate(VERDICT, platform="telegram") is None
    assert hk._decorate(VERDICT, platform="") is None
    assert hk._decorate("brief yes.", platform="discord") is None   # chatter


def test_no_moment_no_decor():
    assert hk._decorate(PLAIN, platform="discord") is None


def test_decided_style_quote_never_double():
    _with(FakeClient())
    assert hk._decorate(VERDICT + "\n\n> oracle: x", platform="discord") is None
    assert hk._decorate(
        VERDICT + "\nAs the ledger reads: 刻舟求劍 (kè zhōu qiú jiàn) — wrong die.",
        platform="discord") is None


def test_plain_hanzi_in_prose_still_decorates():
    """Austin's over-suppression catch: hanzi as a term in prose is not a
    quote — the moment still earns its decided epigraph."""
    _with(FakeClient())
    out = hk._decorate(VERDICT + " The 系統 view: boundaries are the feature.",
                       platform="discord")
    assert out is not None and out.startswith(VERDICT)
    assert "\n\n> oracle: 刻舟求劍 (kè zhōu qiú jiàn) — Using outdated methods foolishly [lexical]" in out


def test_kill_switch_and_dead_oracle():
    os.environ["ZIKAI_HOOK"] = "0"
    assert hk._decorate(VERDICT, platform="discord") is None
    os.environ["ZIKAI_HOOK"] = "1"
    _with(FakeClient(boom=True))            # oracle down => send clean
    assert hk._decorate(VERDICT, platform="discord") is None


def test_config_resolves_beside_plugin_never_other_estate():
    src = inspect.getsource(hk)
    assert "clankville" not in src, "adapter must not hardcode any estate's profile"
    assert "homelab" not in src
    cands = hk._config_candidates()
    assert str(cands[0]).endswith("hermes-hooks/zikai-hook.json"), cands[0]
    os.environ["HERMES_HOME"] = "/tmp/fake-hermes"
    assert str(hk._config_candidates()[1]) == (
        "/tmp/fake-hermes/plugins/zikai-oracle-hook/zikai-hook.json")


def test_unconfigured_is_deaf_not_silent_default_port():
    """Austin's nastiest species: fail-open that can't tell 'no moment' from
    'can't find my config'. Unconfigured must refuse the client (no ride on
    Client's 127.0.0.1:8077 fallback) and the armed line must SAY deaf+down."""
    hk._config_candidates = lambda: [Path("/nonexistent/zikai-hook.json")]
    assert _get_client_fresh() is None
    line = hk._armed_line()
    assert "DEAF" in line and ("MISSING" in line) and "lane=DOWN" in line


def test_armed_line_reports_live_lane():
    os.environ["ZIKAI_URL"] = "http://lane.invalid"
    hk._reachable = lambda url: True       # fake the lane
    assert "client=ok" in hk._armed_line() and "lane=up" in hk._armed_line()
    hk._reachable = lambda url: False
    assert "lane=DOWN" in hk._armed_line()  # enabled-but-deaf announces itself


def test_hook_budget_is_measured_not_inherited():
    """3s was an inherited guess; the GPU lane answers in 17–32s (5 samples).
    Default budget must clear the server's decide cap, and both overrides
    (env, pointer file) must be honored."""
    assert hk._decide_budget({}) >= 35.0
    assert hk._decide_budget({"timeout": 5}) == 5.0
    os.environ["ZIKAI_HOOK_TIMEOUT_S"] = "12"
    assert hk._decide_budget({}) == 12.0
    os.environ["ZIKAI_HOOK_TIMEOUT_S"] = "garbage"
    assert hk._decide_budget({}) >= 35.0    # garbage falls back, never 0


def _get_client_fresh():
    hk._client = None
    hk._client_failed = False
    return hk._get_client()
