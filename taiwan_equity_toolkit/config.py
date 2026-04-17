"""
Configuration — thresholds, weights, and tunable parameters.

Centralized so the framework's decision rules are explicit, versionable, and
tunable without hunting through logic code.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


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
# Master config bundle
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class FrameworkConfig:
    triage: TriageConfig = field(default_factory=TriageConfig)
    gate3_weights: Gate3Weights = field(default_factory=Gate3Weights)
    gate3_thresholds: Gate3Thresholds = field(default_factory=Gate3Thresholds)
    gate65: Gate65Config = field(default_factory=Gate65Config)


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
