"""
full_screen_demo.py — Canonical end-to-end example.

Runs the full framework on a single stock and prints a clean memo.
Use this as a template for the agent's typical single-name screening workflow.

Usage:
    export FINMIND_TOKEN="your_token"
    python full_screen_demo.py                # defaults to 2330 (TSMC)
    python full_screen_demo.py 2317           # Hon Hai
    python full_screen_demo.py 2308 --peers 2330,2303,3711
"""

from __future__ import annotations

import argparse
import sys

from taiwan_equity_toolkit import FinMindClient, memo, value_chain
from taiwan_equity_toolkit.config import INDUSTRY_ANCHORS, load_token
from taiwan_equity_toolkit.models import StrategyMode
from taiwan_equity_toolkit.synthesis import SynthesisInputs, synthesize_candidate
from taiwan_equity_toolkit.workstream_company import run as run_company_workstream
from taiwan_equity_toolkit.workstream_industry import run as run_industry_workstream
from taiwan_equity_toolkit.workstream_setup import run as run_setup_workstream


def guess_peers(stock_id: str) -> list[str]:
    """Best-effort peer list from INDUSTRY_ANCHORS. Override with --peers."""
    for group, members in INDUSTRY_ANCHORS.items():
        if stock_id in members:
            return [m for m in members if m != stock_id]
    return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stock_id", nargs="?", default="2330", help="Target stock code")
    parser.add_argument("--peers", type=str, default="",
                        help="Comma-separated peer codes (overrides auto-detect)")
    parser.add_argument("--book", type=str, default="",
                        help="Comma-separated current book for correlation check")
    parser.add_argument("--size-ntd", type=float, default=None,
                        help="Intended position size in NT$ (for liquidity/execution check)")
    args = parser.parse_args()

    stock_id = args.stock_id
    peer_list = args.peers.split(",") if args.peers else guess_peers(stock_id)
    book = args.book.split(",") if args.book else []
    intended = args.size_ntd

    client = FinMindClient(token=load_token())

    print(f"\n╔════════════════════════════════════════════════╗")
    print(f"║  Pre-Trade Screening: {stock_id:<24} ║")
    print(f"╚════════════════════════════════════════════════╝\n")

    # API quota sanity
    try:
        usage = client.usage()
        print(f"[quota] {usage.user_count}/{usage.api_request_limit} used ({usage.utilization_pct*100:.0f}%)\n")
    except Exception as e:  # noqa: BLE001
        print(f"[quota] check skipped: {e}\n")

    print("──── Workstream A: Industry / Macro ────")
    industry = run_industry_workstream(client, stock_id=stock_id)
    print(industry.to_dict())
    print()

    print("──── Workstream B: Company Quality ────")
    company = run_company_workstream(client, stock_id=stock_id)
    print(company.to_dict())
    print()

    print("──── Workstream C: Setup / Entry ────")
    setup, extras = run_setup_workstream(client, stock_id=stock_id, existing_book=book)
    print(setup.to_dict())
    print()

    print("──── Value Chain Proxy Context ────")
    chain = value_chain.analyze(client, stock_id=stock_id, override_upstream=peer_list or None)
    print(chain.summary())
    print()

    assessment = synthesize_candidate(
        stock_id=stock_id,
        strategy_mode=StrategyMode.TACTICAL_LONG_SHORT,
        industry=industry,
        company=company,
        setup=setup,
        sizing_band=extras.get("sizing_band"),
        inputs=SynthesisInputs(),
    )

    print("══════════════════════════════════════════════════")
    print("  Composed memo (manual sections stay explicit in V2)")
    print("══════════════════════════════════════════════════")
    m = memo.FullScreenMemo(
        stock_id=stock_id,
        candidate_assessment=assessment,
        synthesis_inputs=SynthesisInputs(),
    )
    print(m.render())


if __name__ == "__main__":
    main()
