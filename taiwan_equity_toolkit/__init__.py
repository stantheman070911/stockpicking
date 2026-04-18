"""
Taiwan Equity Toolkit — Pre-trade screening infrastructure for the Stock Selection Framework.

Designed for use by an AI agent (or human analyst) to execute the framework's gates
with deterministic, citable outputs. ~80% of the mechanical work is pre-built so
the agent spends tokens on judgment, not arithmetic.

Quick start:
    from taiwan_equity_toolkit import FinMindClient, mass_triage, gate3, gate65, workstream_a
    from taiwan_equity_toolkit.config import load_token

    client = FinMindClient(token=load_token())

    # The canonical pipeline
    triage_result = mass_triage.run(client, stock_id='2330')
    if triage_result.status != "failed":
        g3 = gate3.run(client, stock_id='2330')
        if g3.verdict == "Pass":
            wa = workstream_a.run(client, '2330')
            g65 = gate65.run(client, '2330', existing_book=['2317', '2454'])

Module layout:
    config       — Thresholds, weights, token loader
    client       — FinMind API wrapper (sync + async batch)
    parsers      — FinMind long-format → wide-format converters
    metrics      — Derived financial ratios with source tagging
    mass_triage  — Triage Filter (cheap screens before Gate 3)
    universe     — Top-200 universe builder + annotative sector tilt
    workstream_a — Industry / macro context (replaces Gate 4 + Gate 5)
    gate3        — Forensic Quality scorecard + hard-fail overrides
    gate65       — Entry Architecture evaluator
    memo         — Structured output formatting
"""

from taiwan_equity_toolkit import (
    config, client, parsers, metrics,
    mass_triage, universe, gate3, gate65, memo,
    workstream_a,
)
from taiwan_equity_toolkit.client import FinMindClient
from taiwan_equity_toolkit.metrics import Metric

__version__ = "0.2.0"

__all__ = [
    "FinMindClient",
    "Metric",
    "config",
    "client",
    "parsers",
    "metrics",
    "mass_triage",
    "universe",
    "workstream_a",
    "gate3",
    "gate65",
    "memo",
]
