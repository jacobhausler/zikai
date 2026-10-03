"""zikai — the never-finished-study idiom decision service.

Maps the chineseidioms.com corpus into a shallow clustered decision tree
(theme -> cluster -> idiom, max 2 questions deep) and serves it behind a
decisions-style API with pluggable decider adapters (OpenAI, Anthropic,
OpenAI-compatible endpoints incl. laya/sglang/together/fireworks/groq,
or a zero-key lexical decider).
"""
try:  # package metadata is the SINGLE source; the string can never lag a release
    from importlib.metadata import version as _pkg_version
    __version__ = _pkg_version("zikai")
except Exception:  # running from source without install metadata
    __version__ = "0.0.0+unknown"
