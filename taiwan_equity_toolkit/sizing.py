"""
Mechanical sizing helpers for the V2 free-tier default path.
"""

from __future__ import annotations

from typing import Iterable

from taiwan_equity_toolkit.models import SizingBand, StrategyMode


def liquidity_cap_pct(adv_ntd: float | None) -> float:
    if adv_ntd is None:
        return 1.0
    if adv_ntd >= 5_000_000_000:
        return 8.0
    if adv_ntd >= 1_000_000_000:
        return 6.0
    if adv_ntd >= 200_000_000:
        return 4.0
    if adv_ntd >= 50_000_000:
        return 2.0
    return 0.5


def volatility_cap_pct(vol_90: float | None) -> float:
    if vol_90 is None:
        return 2.0
    if vol_90 <= 25:
        return 8.0
    if vol_90 <= 40:
        return 6.0
    if vol_90 <= 55:
        return 4.0
    if vol_90 <= 70:
        return 2.0
    return 1.0


def correlation_cap_pct(max_corr: float | None) -> float:
    if max_corr is None:
        return 6.0
    max_corr = abs(max_corr)
    if max_corr < 0.30:
        return 8.0
    if max_corr < 0.50:
        return 6.0
    if max_corr < 0.70:
        return 4.0
    if max_corr < 0.85:
        return 2.5
    return 1.5


def build_sizing_band(
    adv_ntd: float | None,
    vol_90: float | None,
    max_corr: float | None,
    strategy_mode: StrategyMode,
) -> SizingBand:
    liq_cap = liquidity_cap_pct(adv_ntd)
    vol_cap = volatility_cap_pct(vol_90)
    corr_cap = correlation_cap_pct(max_corr)

    max_pct = min(liq_cap, vol_cap, corr_cap)
    if strategy_mode == StrategyMode.QUALITY_COMPOUNDER:
        max_pct = min(max_pct + 1.0, 8.0)

    max_pct = round(max(max_pct, 0.5), 2)
    min_pct = round(min(max_pct, max(max_pct * 0.5, 0.5)), 2)
    suggested_pct = round((min_pct + max_pct) / 2, 2)
    return SizingBand(
        min_pct=min_pct,
        max_pct=max_pct,
        suggested_pct=suggested_pct,
        liquidity_cap_pct=liq_cap,
        volatility_cap_pct=vol_cap,
        correlation_cap_pct=corr_cap,
        conviction_input_required=True,
        note="Analyst conviction and variant perception still determine the final size inside this band.",
    )


def scenario_expected_irr(scenarios: Iterable[tuple[str, float, float]]) -> float:
    total_probability = 0.0
    expected = 0.0
    for _name, probability, irr in scenarios:
        total_probability += probability
        expected += probability * irr

    if round(total_probability, 6) != 1.0:
        raise ValueError(f"Scenario probabilities must sum to 1.0, got {total_probability:.6f}")
    return expected
