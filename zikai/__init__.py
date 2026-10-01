"""zikai — the never-finished-study idiom decision service.

Maps the chineseidioms.com corpus into a shallow clustered decision tree
(theme -> cluster -> idiom, max 2 questions deep) and serves it behind a
decisions-style API with pluggable decider adapters (OpenAI, Anthropic,
OpenAI-compatible endpoints incl. laya/sglang/together/fireworks/groq,
or a zero-key lexical decider).
"""
__version__ = "0.1.0"
