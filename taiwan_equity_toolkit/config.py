"""
Configuration — thresholds, weights, and tunable parameters.

Centralized so the framework's decision rules are explicit, versionable, and
tunable without hunting through logic code.
"""

import os
from dataclasses import dataclass, field
from typing import FrozenSet, Optional


# ──────────────────────────────────────────────────────────────────────────
# FinMind API
# ──────────────────────────────────────────────────────────────────────────

FINMIND_BASE_URL = "https://api.finmindtrade.com/api/v4"
FINMIND_USER_INFO_URL = "https://api.web.finmindtrade.com/v2/user_info"
RATE_LIMIT_PER_HOUR = 600  # with token
DEFAULT_TIMEOUT_SEC = 30
MAX_RETRIES = 3
RETRY_BACKOFF_SEC = 2.0


def load_token() -> str:
    """Load FinMind token from env var FINMIND_TOKEN. Raise if missing."""
    token = os.environ.get("FINMIND_TOKEN")
    if not token:
        raise RuntimeError(
            "FINMIND_TOKEN environment variable is not set. "
            "Export it before running, e.g. `export FINMIND_TOKEN=your_token`."
        )
    return token


# ──────────────────────────────────────────────────────────────────────────
# Triage Filter thresholds
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class TriageConfig:
    # Liquidity
    min_adv_ntd: float = 50_000_000          # NT$ 50M average daily dollar volume
    adv_lookback_days: int = 20
    position_max_pct_of_adv: float = 0.10    # intended position ≤ 10% of ADV

    # Financial sanity
    max_quarters_stale: int = 1              # latest financial statement within 1 quarter
    monthly_revenue_collapse_yoy: float = -0.30  # -30% YoY = disqualify (unless shorting)

    # Price history cleanliness
    corporate_action_lookback_months: int = 24

    # Peer outlier
    peer_return_lookback_days: int = 90


# ──────────────────────────────────────────────────────────────────────────
# Gate 3 Forensic Quality scorecard
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class Gate3Weights:
    """Scorecard weights summing to 100."""
    operating_quality: int = 25
    balance_sheet_survival: int = 35
    ownership_market_structure: int = 20
    derivatives_capital_structure: int = 10
    data_integrity: int = 10

    def total(self) -> int:
        return (
            self.operating_quality
            + self.balance_sheet_survival
            + self.ownership_market_structure
            + self.derivatives_capital_structure
            + self.data_integrity
        )


@dataclass
class Gate3Thresholds:
    # Verdict thresholds
    pass_threshold: int = 80            # ≥ 80 → Pass
    conditional_threshold: int = 65     # 65–79 → Conditional Watchlist

    # 3A. Operating Quality
    cfo_to_ni_healthy: float = 0.8      # CFO/NI ≥ 0.8 is healthy
    cfo_to_ni_warning: float = 0.5      # CFO/NI < 0.5 for 4+ qtrs = hard-fail
    cfo_to_ni_warning_qtrs: int = 4
    min_gross_margin_stability: float = 0.02  # stdev of GM over 8 qtrs ≤ 2pp = stable

    # 3B. Balance Sheet & Cash Survival
    interest_coverage_min: float = 2.0        # EBIT/Interest ≥ 2x is baseline
    interest_coverage_hardfail: float = 2.0   # below this + debt wall = hard-fail
    net_debt_to_ebitda_warning: float = 3.0   # above 3x flags leverage concern
    net_debt_to_ebitda_hardfail: float = 5.0  # above 5x + no growth = disqualifying
    current_ratio_min: float = 1.0
    cash_to_short_term_debt_min: float = 1.0
    debt_wall_months: int = 12                # debt maturing within 12 months

    # 3C. Ownership & Market Structure
    institutional_flow_lookback_days: int = 60
    foreign_ownership_ceiling_buffer: float = 0.05  # within 5pp of limit = crowded

    # Hard-fail override flags
    require_no_repeat_dilution: bool = True
    require_no_governance_red_flags: bool = True


# ──────────────────────────────────────────────────────────────────────────
# Gate 6.5 Entry Architecture thresholds
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class Gate65Config:
    realized_vol_lookback_short: int = 30
    realized_vol_lookback_long: int = 90
    beta_lookback_days: int = 90
    correlation_hardfail: float = 0.85      # > 0.85 with existing holding = same position
    correlation_warning: float = 0.70
    meme_daily_vol_threshold: float = 0.20  # ±20% daily = unmanageable

    valuation_high_percentile: float = 0.80  # above 80th %ile of 5y history = stretched
    valuation_low_percentile: float = 0.20   # below 20th %ile = attractive


# ──────────────────────────────────────────────────────────────────────────
# V2 — Free-tier policy & premium dataset detection
# ──────────────────────────────────────────────────────────────────────────

# Datasets that require FinMind Backer/Sponsor membership. Path A (free-tier
# default) never calls these; they are surfaced only through
# taiwan_equity_toolkit.adapters.premium.
#
# Sourced from Finmind.md tier notes (Backer / Sponsor markers). Keep this set
# as the single source of truth — client.is_premium() consults it before every
# HTTP call so free-tier runs fail loudly instead of silently 400-ing.
PREMIUM_DATASETS: FrozenSet[str] = frozenset({
    # Chain-of-supply & macro (Backer/Sponsor)
    "TaiwanStockIndustryChain",
    "TaiwanBusinessIndicator",
    # Trading-state overlays
    "TaiwanStockDispositionSecuritiesPeriod",
    "TaiwanStockSuspended",
    # Convertible bond family (all four)
    "TaiwanStockConvertibleBondDaily",
    "TaiwanStockConvertibleBondDailyOverview",
    "TaiwanStockConvertibleBondDetail",
    "TaiwanStockConvertibleBondInstitutionalInvestorsBuySell",
    # Broker-branch / government flow
    "TaiwanStockTradingDailyReport",
    "TaiwanStockTradingDailyReportSecIdAgg",
    "TaiwanstockGovernmentBankBuySell",
    # Market-value / holding distributions
    "TaiwanStockMarketValue",
    "TaiwanStockMarketValueWeek",
    "TaiwanStockMarketValueMonth",
    "TaiwanStockHoldingSharesPer",
    # Tick / intraday / alt-frequency price series
    "TaiwanStockKBar",
    "TaiwanStockPriceTick",
    "TaiwanStockWeekPrice",
    "TaiwanStockMonthPrice",
    "TaiwanStockEvery5SecondsIndex",
    "TaiwanStock10Year",
    # Large-trader derivatives OI
    "TaiwanFuturesOpenInterestLargeTraders",
    "TaiwanOptionOpenInterestLargeTraders",
    # Sentiment
    "CnnFearGreedIndex",
})


@dataclass
class FreeTierPolicy:
    """Gates whether the client may call premium datasets.

    Default is strict free-tier — premium datasets raise PremiumDatasetRequired
    before the HTTP call, so the pipeline never silently 400s on a tier-locked
    endpoint. Flip `allow_premium_adapters` to True only when a Backer/Sponsor
    token is active (wired through adapters/premium in Phase 10).
    """
    allow_premium_adapters: bool = False
    strict: bool = True  # raise on premium call when adapters disabled


# ──────────────────────────────────────────────────────────────────────────
# V2 — Workstream B (Company Quality) thresholds & weights
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class WorkstreamBThresholds:
    """Thresholds for the 10-item red-flag screen (Stage 1).

    CFO/NI is a flag, not a hard reject — downgrade from Gate 3's
    cfo_to_ni_warning_qtrs hard-fail (report §3 p.86, §5.3).
    """
    # Red-flag cutoffs (Stage 1)
    cfo_to_ni_flag: float = 0.8
    cfo_to_ni_flag_qtrs: int = 4
    director_pledge_flag_pct: float = 0.50       # director share pledging > 50%
    related_party_rev_flag_pct: float = 0.30     # related-party revenue > 30%
    debt_wall_months: int = 18                    # proxy: ST/LT ratio + IC<2x
    historical_dilution_flag_pct: float = 0.15   # 3y cumulative dilution > 15%
    dilution_lookback_years: int = 3
    roe_trajectory_lookback_years: int = 3
    roe_trajectory_collapse_pct: float = 0.30    # ROE -30% over 3y = flag
    interest_coverage_flag: float = 2.0
    auditor_change_lookback_years: int = 3

    # Two-stage gate trigger
    deep_forensic_trigger_count: int = 2          # ≥ 2 flags → Stage 2

    # Stage 2 (deep forensic) verdict thresholds — reweighted (no CB)
    pass_threshold: int = 80
    conditional_threshold: int = 65


@dataclass
class WorkstreamBScoreWeights:
    """Scorecard weights for Stage 2 deep forensic — summing to 100.

    Rationale (Phase 5 plan + report §7):
    - Gate 3's derivatives/CB sub-layer is removed from default scoring (CB is
      now a premium adapter + manual review, not a scoring input).
    - That 10-pt slice redistributes: +5 to balance-sheet-survival (now 40) and
      +5 to data-integrity (now 15).
    - Operating quality stays 25; ownership-subset stays 20 (the rest of the
      ownership work lives in Workstream C, not here).
    """
    operating_quality: int = 25
    balance_sheet_survival: int = 40
    ownership_capital_structure: int = 20
    data_integrity: int = 15

    def total(self) -> int:
        return (
            self.operating_quality
            + self.balance_sheet_survival
            + self.ownership_capital_structure
            + self.data_integrity
        )


# ──────────────────────────────────────────────────────────────────────────
# V2 — Workstream C (Setup / Positioning / Entry) config
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class WorkstreamCConfig:
    """Entry architecture + positioning thresholds.

    Correlation no longer hard-rejects. Report §5.10 / §7.5 downgraded the 0.85
    hard cutoff to "document and justify if > 0.7". We surface flags, never
    kill a candidate on correlation alone.
    """
    # Volatility panel
    realized_vol_lookback_short: int = 30
    realized_vol_lookback_long: int = 90
    meme_daily_vol_threshold: float = 0.20

    # Correlation documentation (no hard reject — demoted per report §5.10)
    correlation_review_trigger: float = 0.70     # flag for manual_review
    correlation_document_threshold: float = 0.85  # always document; never reject

    # Valuation panel
    valuation_high_percentile: float = 0.80
    valuation_low_percentile: float = 0.20

    # Liquidity / crowding
    institutional_flow_lookback_days: int = 60
    margin_balance_lookback_days: int = 60
    foreign_ownership_ceiling_buffer: float = 0.05

    # TXO put/call ratio overlay (conditional — not_assessed if no listed opt)
    txo_pcr_lookback_days: int = 20


# ──────────────────────────────────────────────────────────────────────────
# V2 — Sizing caps (mechanical — analyst supplies conviction)
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class SizingCaps:
    """Mechanical caps on position size.

    The user-confirmed hybrid: Python computes mechanical caps (vol, liquidity,
    correlation, suggested band); analyst supplies conviction tier + final
    size within the band. This dataclass is BOTH the config (default band +
    cap parameters) and the return type (compute_sizing_caps populates it).
    """
    # Band bounds (% of AUM)
    band_low_pct: float = 0.005    # 0.5% floor
    band_high_pct: float = 0.04    # 4% ceiling

    # Volatility-based cap — inverse to realized vol
    vol_lookback_days: int = 90
    vol_cap_target: float = 0.02   # target portfolio vol contribution

    # Liquidity cap — intended ≤ X% of ADV
    liquidity_cap_pct_of_adv: float = 0.10
    adv_lookback_days: int = 20

    # Correlation cap — reduce size when covariance contribution above
    correlation_cap_trigger: float = 0.70
    correlation_penalty_pct: float = 0.50  # halve size on hit


# ──────────────────────────────────────────────────────────────────────────
# V2 — Sell discipline (Freeman-Shor archetypes)
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class SellDisciplineArchetypes:
    """Defaults for the three Freeman-Shor archetypes.

    - Assassin: cut quickly on thesis breakage (event-driven).
    - Hunter: average down with discipline (value).
    - Connoisseur: let winners run (quality-compounder).
    Forced −20% drawdown review trigger applies to all three.
    """
    drawdown_review_trigger_pct: float = -0.20   # force review at -20%

    # Assassin
    assassin_max_loss_pct: float = -0.10
    assassin_time_stop_months: int = 3

    # Hunter
    hunter_max_averaging_down_mult: float = 1.5   # ≤ 1.5× initial size total
    hunter_time_stop_months: int = 12

    # Connoisseur
    connoisseur_target_runout_pct: float = 1.50   # let winners run to 150% of target
    connoisseur_deadmoney_months: int = 12


# ──────────────────────────────────────────────────────────────────────────
# V2 — Macro context (free-tier substitute for 景氣對策信號)
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class MacroContextConfig:
    """Free-tier macro backdrop inputs (replaces removed 景氣對策信號).

    Uses InterestRate (FED), GovernmentBondsYield (UST 2Y / 10Y spread),
    CrudeOilPrices (WTI), and TaiwanExchangeRate (USD) — all free-tier.
    Report §5.11 / §7.4: 景氣對策信號 is OUT of scoring and timing.
    """
    fed_rate_lookback_days: int = 180
    ust_curve_short: str = "UST_2Y"
    ust_curve_long: str = "UST_10Y"
    oil_lookback_days: int = 180
    twd_lookback_days: int = 180


# ──────────────────────────────────────────────────────────────────────────
# Master config bundle
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class FrameworkConfig:
    triage: TriageConfig = field(default_factory=TriageConfig)
    gate3_weights: Gate3Weights = field(default_factory=Gate3Weights)
    gate3_thresholds: Gate3Thresholds = field(default_factory=Gate3Thresholds)
    gate65: Gate65Config = field(default_factory=Gate65Config)
    # V2 additions (legacy fields above kept until their consumers are deleted
    # in Phases 2, 3, 4, 5).
    free_tier: FreeTierPolicy = field(default_factory=FreeTierPolicy)
    workstream_b_thresholds: WorkstreamBThresholds = field(default_factory=WorkstreamBThresholds)
    workstream_b_weights: WorkstreamBScoreWeights = field(default_factory=WorkstreamBScoreWeights)
    workstream_c: WorkstreamCConfig = field(default_factory=WorkstreamCConfig)
    sizing: SizingCaps = field(default_factory=SizingCaps)
    sell_discipline: SellDisciplineArchetypes = field(default_factory=SellDisciplineArchetypes)
    macro: MacroContextConfig = field(default_factory=MacroContextConfig)


DEFAULT_CONFIG = FrameworkConfig()


# ──────────────────────────────────────────────────────────────────────────
# Taiwan-specific metadata
# ──────────────────────────────────────────────────────────────────────────

# Common industry peer anchors (can be extended / loaded from TaiwanStockIndustryChain)
INDUSTRY_ANCHORS = {
    "foundry": ["2330", "2303", "6770"],           # TSMC, UMC, PSMC
    "osat": ["2308", "3711", "6239", "2449"],       # ASE, ASE Tech, Powertech, KYEC (approx; verify)
    "ic_design": ["2454", "3034", "3443"],          # MediaTek, Novatek, GlobalWafers (adjust)
    "server_odm": ["2317", "2382", "3231", "2324"], # Hon Hai, Quanta, Wistron, Compal
    "financials": ["2881", "2882", "2884", "2886"], # Fubon, Cathay, Mega, Mega Holdings
    "shipping": ["2603", "2609", "2615"],           # Evergreen, Yang Ming, Wan Hai
}
