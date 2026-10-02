from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """All knobs via env (prefix ZIKAI_) or .env — never required at import."""

    model_config = SettingsConfigDict(env_prefix="ZIKAI_", env_file=".env",
                                      extra="ignore")

    # --- corpus -----------------------------------------------------
    corpus_path: str = str(REPO_ROOT / "data" / "corpus.json")
    tree_path: str = str(REPO_ROOT / "data" / "decision_tree.json")

    # --- service ----------------------------------------------------
    api_keys: str = ""          # comma-separated keys accepted by /decide
    api_keys_file: str = ""      # newline-separated keys (0600 pointer file)
    require_key: bool = True     # set false for local dev
    dashboard: bool = True

    # --- decider (laya-compatible OpenAI endpoint is the default) --
    # decider="openai" | "anthropic" | "openai_compat" | "lexical"
    decider: str = "auto"        # auto = first configured remote, else lexical
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_model: str = "claude-3-5-haiku-latest"
    # generic openai-compatible (laya / sglang / vllm / together / fireworks / groq)
    laya_base_url: str = ""      # e.g. http://192.168.0.122:18030/v1
    laya_api_key: str = ""       # generic bearer key for the compat endpoint
    laya_model: str = "qwen38-next"
    decision_timeout_s: float = 20.0
    # optional vendor rerank stage: "cohere_rerank" | "jina_rerank" (must
    # match a PROVIDER_PRESETS rerank row whose key env must also be set);
    # "" = off. Fail-open: a rerank miss never changes behaviour.
    rerank_transport: str = ""

    @property
    def key_set(self) -> set[str]:
        keys = {k.strip() for k in self.api_keys.split(",") if k.strip()}
        if self.api_keys_file:
            try:
                p = Path(self.api_keys_file)
                keys |= {ln.strip() for ln in p.read_text().splitlines()
                         if ln.strip() and not ln.startswith("#")}
            except OSError:
                pass  # unreadable file = no extra keys, never a crash
        return keys


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
