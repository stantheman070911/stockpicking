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

from taiwan_equity_toolkit import (
    FinMindClient,
    mass_triage,
    gate3,
    gate65,
    peers,
    value_chain,
    memo,
)
from taiwan_equity_toolkit.config import INDUSTRY_ANCHORS, load_token
from taiwan_equity_toolkit.states import Status


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

    # ── Triage ────────────────────────────────────────────
    print("──── Triage Filter ────")
    tr = mass_triage.run(client, stock_id=stock_id, intended_position_ntd=intended)
    print(tr.summary())
    print()

    if tr.status == Status.FAILED:
        print("⛔ Triage failed — screen stops here.")
        sys.exit(0)
    if tr.status == Status.MANUAL_REVIEW_REQUIRED:
        print("⚠ Triage requires analyst review — continuing with caution.\n")

    # ── Gate 3 ────────────────────────────────────────────
    print("──── Gate 3: Forensic Quality ────")
    g3 = gate3.run(client, stock_id=stock_id)
    print(g3.memo())
    print()

    if g3.hard_fail_triggered:
        print("⛔ Gate 3 hard-fail override triggered — screen stops here.")
        sys.exit(0)
    if g3.verdict == "Fail":
        print("⛔ Gate 3 failed on score — screen stops here.")
        sys.exit(0)

    # ── Gate 4 / Gate 5: Peer + value chain ───────────────
    peer_cmp = None
    if peer_list:
        print("──── Gate 4: Cross-Source (Peer) Validation ────")
        peer_cmp = peers.compare(client, candidate=stock_id, peers=peer_list)
        print(peer_cmp.summary())
        print()

    print("──── Gate 5: Value Chain Positioning ────")
    chain = value_chain.analyze(client, stock_id=stock_id)
    print(chain.summary())
    print()

    # ── Gate 6.5 ──────────────────────────────────────────
    print("──── Gate 6.5: Entry Architecture ────")
    g65 = gate65.run(
        client,
        stock_id=stock_id,
        existing_book=book,
        intended_position_ntd=intended,
    )
    print(g65.summary())
    print()

    # ── Memo ──────────────────────────────────────────────
    print("══════════════════════════════════════════════════")
    print("  Composed memo (Gates 1, 2, 6, 7 require judgment;")
    print("  fill those in based on your view)")
    print("══════════════════════════════════════════════════")
    m = memo.FullScreenMemo(
        stock_id=stock_id,
        triage=tr,
        gate3=g3,
        peer_comparison=peer_cmp,
        value_chain_notes=chain.summary(),
        entry_architecture_notes=g65.summary(),
        verdict="(pending — fill in judgment gates)",
    )
    print(m.render())


if __name__ == "__main__":
    main()
