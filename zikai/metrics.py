"""Tiny self-reported metrics for the obs rails (three-rule pattern input).

Exposition at GET /metrics (Prometheus text format). Counters are process
totals; the *staleness* of zikai_last_decide_unix and the *absence* of the
scrape target itself are what the alert rules watch — a dead writer's last
count stays green forever, so value alone is never the proof.
"""
from __future__ import annotations

import time

START = time.time()
_DECIDES = 0          # successful decisions
_ERRORS = 0           # decisions that raised
_LATENCY_SUM = 0.0    # seconds, over _DECIDES
_LAST_DECIDE = 0.0    # unix ts of the last successful decide
_CORPUS_SIZE = 0


def note_decide(dt: float) -> None:
    global _DECIDES, _LATENCY_SUM, _LAST_DECIDE
    _DECIDES += 1
    _LATENCY_SUM += dt
    _LAST_DECIDE = time.time()


def note_error() -> None:
    global _ERRORS
    _ERRORS += 1


def set_corpus(n: int) -> None:
    global _CORPUS_SIZE
    _CORPUS_SIZE = n


def exposition() -> str:
    avg = (_LATENCY_SUM / _DECIDES) if _DECIDES else 0.0
    lines = [
        "# TYPE zikai_uptime_seconds gauge",
        f"zikai_uptime_seconds {time.time() - START:.3f}",
        "# TYPE zikai_decides_total counter",
        f"zikai_decides_total {_DECIDES}",
        "# TYPE zikai_decide_errors_total counter",
        f"zikai_decide_errors_total {_ERRORS}",
        "# TYPE zikai_decide_latency_seconds_total counter",
        f"zikai_decide_latency_seconds_total {_LATENCY_SUM:.6f}",
        "# TYPE zikai_decide_latency_seconds_avg gauge",
        f"zikai_decide_latency_seconds_avg {avg:.6f}",
        "# TYPE zikai_last_decide_unix gauge",
        f"zikai_last_decide_unix {_LAST_DECIDE:.3f}",
        "# TYPE zikai_corpus_idioms gauge",
        f"zikai_corpus_idioms {_CORPUS_SIZE}",
    ]
    return "\n".join(lines) + "\n"
