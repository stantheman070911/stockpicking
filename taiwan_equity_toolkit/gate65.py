"""
Gate 6.5 — Entry Architecture.

Tactical: is today the right day to enter, at this price, at this size?

One function: `run(client, stock_id, existing_book=...)` → Gate65Result.

Gate 6 (strategic portfolio fit) is a judgment call the agent makes; Gate 6.5
is mechanical and therefore automatable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from taiwan_equity_toolkit.client import FinMindClient
from taiwan_equity_toolkit.config import DEFAULT_CONFIG, Gate65Config
from taiwan_equity_toolkit import metrics


@dataclass
class Gate65Check:
    layer: str               # "6.5A", "6.5B", "6.5C", "6.5D"
    name: str
    result: str              # "Green", "Yellow", "Red"
    detail: str
    metric: Optional[metrics.Metric] = None


@dataclass
class Gate65Result:
    stock_id: str
    verdict: str             # "Enter Now" | "Stagger / Scale In" | "Wait for Setup" | "Reject for Book Fit"
    checks: list[Gate65Check] = field(default_factory=list)
    green_count: int = 0
    yellow_count: int = 0
    red_count: int = 0
    correlations: dict[str, float] = field(default_factory=dict)  # stock_id → correlation

    def summary(self) -> str:
        lines = [f"# Gate 6.5 — Entry Architecture: {self.stock_id}"]
        lines.append(f"Verdict: {self.verdict}  "
                     f"(Green {self.green_count} / Yellow {self.yellow_count} / Red {self.red_count})")
        lines.append("")
        current_layer = None
        for c in self.checks:
            if c.layer != current_layer:
                lines.append(f"## {c.layer}")
                current_layer = c.layer
            mark = {"Green": "✓", "Yellow": "⚠", "Red": "✗"}.get(c.result, "·")
            lines.append(f"  {mark} {c.name}: {c.detail}")
        if self.correlations:
            lines.append("")
            lines.append("## Correlation to existing book (90d returns)")
            for sid, corr in sorted(self.correlations.items(), key=lambda x: -abs(x[1])):
                lines.append(f"  - {sid}: {corr:+.2f}")
        return "\n".join(lines)


def _per_history(per_df: pd.DataFrame) -> Optional[pd.Series]:
    """Return PER time series (sorted by date)."""
    if per_df.empty or "PER" not in per_df.columns:
        return None
    df = per_df.sort_values("date").copy()
    df["PER"] = pd.to_numeric(df["PER"], errors="coerce")
    return df.set_index("date")["PER"].dropna()


def run(
    client: FinMindClient,
    stock_id: str,
    existing_book: Optional[list[str]] = None,
    intended_position_ntd: Optional[float] = None,
    cfg: Optional[Gate65Config] = None,
) -> Gate65Result:
    """
    Evaluate entry architecture for a single stock.

    Args:
        client: Authenticated FinMindClient
        stock_id: Target stock
        existing_book: List of stock IDs already held, for correlation check
        intended_position_ntd: For liquidity check
        cfg: Optional threshold override
    """
    cfg = cfg or DEFAULT_CONFIG.gate65
    result = Gate65Result(stock_id=stock_id, verdict="(pending)")

    today = datetime.today()
    price_start = (today - timedelta(days=400)).strftime("%Y-%m-%d")
    per_start = (today - timedelta(days=5 * 365)).strftime("%Y-%m-%d")

    # Fetch
    price_df = client.price_adj(stock_id, price_start)
    raw_price_df = client.price(stock_id, (today - timedelta(days=60)).strftime("%Y-%m-%d"))
    per_df = client.per(stock_id, per_start)

    # ───── 6.5A. Valuation & Expectation Gap ─────
    per_series = _per_history(per_df)
    if per_series is not None and len(per_series) >= 252:  # ~1y of data
        latest_per = per_series.iloc[-1]
        pct_rank = (per_series <= latest_per).mean()  # 0–1 percentile within history
        if pct_rank >= cfg.valuation_high_percentile:
            r = "Red"
            d = f"PER {latest_per:.1f}x is at {pct_rank*100:.0f}th percentile of 5y history (stretched)"
        elif pct_rank <= cfg.valuation_low_percentile:
            r = "Green"
            d = f"PER {latest_per:.1f}x is at {pct_rank*100:.0f}th percentile (attractive)"
        else:
            r = "Yellow"
            d = f"PER {latest_per:.1f}x at {pct_rank*100:.0f}th percentile (fair/neutral)"
        result.checks.append(Gate65Check("6.5A", "Valuation location (PER vs 5y history)", r, d))
    else:
        result.checks.append(Gate65Check(
            "6.5A", "Valuation location", "Yellow",
            "Insufficient PER history (need ≥1y)"
        ))

    # ───── 6.5B. Volatility & Correlation ─────
    vol_30 = metrics.realized_vol(price_df, lookback=cfg.realized_vol_lookback_short)
    vol_90 = metrics.realized_vol(price_df, lookback=cfg.realized_vol_lookback_long)

    if vol_30.value is not None:
        if vol_30.value > cfg.meme_daily_vol_threshold * 100 * (252 ** 0.5) / 5:  # rough meme-vol proxy
            r = "Red"
        elif vol_30.value > 60:
            r = "Yellow"
        else:
            r = "Green"
        result.checks.append(Gate65Check(
            "6.5B", "Realized vol (30d, annualized)", r,
            f"{vol_30.value:.1f}% — " + ("elevated" if r != "Green" else "manageable"),
            metric=vol_30
        ))
    else:
        result.checks.append(Gate65Check("6.5B", "Realized vol (30d)", "Yellow", "data unavailable"))

    if vol_90.value is not None:
        result.checks.append(Gate65Check(
            "6.5B", "Realized vol (90d, annualized)", "Green" if vol_90.value < 50 else "Yellow",
            f"{vol_90.value:.1f}%", metric=vol_90
        ))

    # Correlation to existing book
    if existing_book:
        book_ids = [b for b in existing_book if b != stock_id]
        if book_ids:
            book_prices = client.get_multi("TaiwanStockPriceAdj", book_ids, price_start)
            max_corr = 0.0
            max_corr_id = None
            for sid, df in book_prices.items():
                if df.empty:
                    continue
                corr_m = metrics.correlation_to_series(price_df, df, lookback=90)
                if corr_m.value is not None:
                    result.correlations[sid] = corr_m.value
                    if abs(corr_m.value) > abs(max_corr):
                        max_corr = corr_m.value
                        max_corr_id = sid

            if max_corr_id is not None:
                if abs(max_corr) >= cfg.correlation_hardfail:
                    r = "Red"
                    d = f"Max corr {max_corr:+.2f} with {max_corr_id} ≥ {cfg.correlation_hardfail} — same position in risk terms"
                elif abs(max_corr) >= cfg.correlation_warning:
                    r = "Yellow"
                    d = f"Max corr {max_corr:+.2f} with {max_corr_id} — material overlap"
                else:
                    r = "Green"
                    d = f"Max corr {max_corr:+.2f} with {max_corr_id} — diversifying"
                result.checks.append(Gate65Check("6.5B", "Correlation to existing book", r, d))
            else:
                result.checks.append(Gate65Check(
                    "6.5B", "Correlation to existing book", "Yellow",
                    "Could not compute correlations"
                ))
    else:
        result.checks.append(Gate65Check(
            "6.5B", "Correlation to existing book", "Yellow",
            "No existing book provided — skipped"
        ))

    # ───── 6.5C. Liquidity & Execution ─────
    adv = metrics.adv_ntd(raw_price_df, lookback=20)
    if adv.value is not None:
        if intended_position_ntd is not None:
            pct = intended_position_ntd / adv.value
            if pct > 0.10:
                r = "Red"
                d = f"Position {pct*100:.1f}% of ADV (NT${adv.value:,.0f}) > 10% — exit will move market"
            elif pct > 0.05:
                r = "Yellow"
                d = f"Position {pct*100:.1f}% of ADV (NT${adv.value:,.0f}) — scale in tranches"
            else:
                r = "Green"
                d = f"Position {pct*100:.1f}% of ADV (NT${adv.value:,.0f}) — executable"
        else:
            r = "Green" if adv.value >= 50_000_000 else "Yellow"
            d = f"ADV NT${adv.value:,.0f} (20d)"
        result.checks.append(Gate65Check("6.5C", "Liquidity (ADV)", r, d, metric=adv))
    else:
        result.checks.append(Gate65Check("6.5C", "Liquidity (ADV)", "Red", "ADV unavailable"))

    # Price-limit regime check
    try:
        pl_df = client.get("TaiwanStockPriceLimit", stock_id,
                           (today - timedelta(days=7)).strftime("%Y-%m-%d"))
        if not pl_df.empty and "limit_up" in pl_df.columns:
            latest_pl = pl_df.sort_values("date").iloc[-1]
            if latest_pl["limit_up"] == 0 or latest_pl["limit_down"] == 0:
                r = "Yellow"
                d = "No daily price limit (leveraged/inverse ETF or emerging stock) — special handling"
            else:
                r = "Green"
                d = f"Standard ±10% limit regime (up {latest_pl['limit_up']:.2f}, down {latest_pl['limit_down']:.2f})"
            result.checks.append(Gate65Check("6.5C", "Price-limit regime", r, d))
    except Exception as e:  # noqa: BLE001
        result.checks.append(Gate65Check("6.5C", "Price-limit regime", "Yellow", f"check errored: {e}"))

    # ───── 6.5D. Crowding & Catalyst Proximity ─────
    # Disposition period check (if currently dispositioned, flag)
    try:
        disp = client.get("TaiwanStockDispositionSecuritiesPeriod", stock_id,
                          (today - timedelta(days=90)).strftime("%Y-%m-%d"))
        if not disp.empty and "period_end" in disp.columns:
            today_str = today.strftime("%Y-%m-%d")
            current = disp[(disp["period_start"] <= today_str) & (disp["period_end"] >= today_str)]
            if not current.empty:
                result.checks.append(Gate65Check(
                    "6.5D", "Disposition status", "Red",
                    f"Currently on disposition list — entry restricted"
                ))
            else:
                result.checks.append(Gate65Check(
                    "6.5D", "Disposition status", "Green",
                    "Not on active disposition"
                ))
        else:
            result.checks.append(Gate65Check("6.5D", "Disposition status", "Green", "No disposition record"))
    except Exception as e:  # noqa: BLE001
        result.checks.append(Gate65Check("6.5D", "Disposition status", "Yellow", f"check errored: {e}"))

    # Crowding via margin balance trajectory (60d)
    try:
        mgn = client.margin_short(stock_id, (today - timedelta(days=90)).strftime("%Y-%m-%d"))
        if not mgn.empty and "MarginPurchaseTodayBalance" in mgn.columns and len(mgn) >= 20:
            df = mgn.sort_values("date").tail(60)
            first = df.iloc[0]["MarginPurchaseTodayBalance"]
            last = df.iloc[-1]["MarginPurchaseTodayBalance"]
            if first and first > 0:
                change_pct = (last - first) / first * 100
                if change_pct > 30:
                    r = "Red"
                    d = f"Margin balance +{change_pct:.0f}% in 60d — retail crowded"
                elif change_pct > 10:
                    r = "Yellow"
                    d = f"Margin balance +{change_pct:.0f}% in 60d — building"
                elif change_pct < -10:
                    r = "Green"
                    d = f"Margin balance {change_pct:.0f}% in 60d — weak hands shaking out"
                else:
                    r = "Green"
                    d = f"Margin balance {change_pct:+.0f}% in 60d — stable"
                result.checks.append(Gate65Check("6.5D", "Margin crowding (60d)", r, d))
    except Exception as e:  # noqa: BLE001
        result.checks.append(Gate65Check("6.5D", "Margin crowding", "Yellow", f"check errored: {e}"))

    # Tally
    for c in result.checks:
        if c.result == "Green":
            result.green_count += 1
        elif c.result == "Yellow":
            result.yellow_count += 1
        elif c.result == "Red":
            result.red_count += 1

    # Verdict
    if result.red_count >= 2:
        result.verdict = "Reject for Book Fit" if any(
            "Correlation" in c.name and c.result == "Red" for c in result.checks
        ) else "Wait for Setup"
    elif result.red_count == 1:
        result.verdict = "Wait for Setup"
    elif result.yellow_count >= 3:
        result.verdict = "Stagger / Scale In"
    else:
        result.verdict = "Enter Now"

    return result
