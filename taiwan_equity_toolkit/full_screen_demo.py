"""
full_screen_demo.py — Canonical end-to-end example.

Runs the full framework on a single stock and prints a clean memo.
Use this as a template for the agent's typical single-name screening workflow.

Usage:
    export FINMIND_TOKEN="your_token"
    python full_screen_demo.py                # defaults to 2330 (TSMC)
    python full_screen_demo.py 2317           # Hon Hai
"""

from __future__ import annotations

import argparse
import sys

from taiwan_equity_toolkit import (
    FinMindClient,
    mass_triage,
    gate3,
    gate65,
    memo,
    workstream_a,
)
from taiwan_equity_toolkit.config import load_token
from taiwan_equity_toolkit.states import Status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stock_id", nargs="?", default="2330", help="Target stock code")
    parser.add_argument("--book", type=str, default="",
                        help="Comma-separated current book for correlation check")
    parser.add_argument("--size-ntd", type=float, default=None,
                        help="Intended position size in NT$ (for liquidity/execution check)")
    args = parser.parse_args()

    stock_id = args.stock_id
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

    # ── Workstream A ──────────────────────────────────────
    print("──── Workstream A: Industry / Macro ────")
    wa = workstream_a.run(client, stock_id=stock_id)
    print(f"status={wa.status.value} | cluster={wa.cluster or 'unclustered'}")
    print(
        "chain="
        f"{wa.chain_position.source or 'none'} | "
        f"node={wa.chain_position.node or 'n/a'} | "
        f"usable_peers={wa.peer_alignment.usable_peer_count}"
    )
    if wa.tsmc_anchor.tsmc_revenue_yoy is not None:
        print(f"tsmc_yoy={wa.tsmc_anchor.tsmc_revenue_yoy:.2f}%")
    if wa.notes:
        print("notes:")
        for note in wa.notes:
            print(f"  - {note}")
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
        workstream_a_notes="\n".join(
            [
                f"Status: {wa.status.value}",
                f"Cluster: {wa.cluster or 'unclustered'}",
                f"Chain source: {wa.chain_position.source or 'none'}",
                f"Usable peer count: {wa.peer_alignment.usable_peer_count}",
                "Notes:",
                *[f"- {note}" for note in wa.notes],
            ]
        ),
        entry_architecture_notes=g65.summary(),
        verdict="(pending — fill in judgment gates)",
    )
    print(m.render())


if __name__ == "__main__":
    main()
