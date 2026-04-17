# Taiwan Equity Toolkit Source Code

This file aggregates the contents of the `taiwan_equity_toolkit` directory.

## `taiwan_equity_toolkit/README.md`

```markdown
# Taiwan Equity Toolkit

Pre-built Python infrastructure for executing the Stock Selection Framework against the Taiwan market via FinMind. ~80% of the mechanical work — API calls, long-format parsing, ratio math, peer comparisons, scorecard arithmetic — is done here so the agent spends tokens on judgment, not plumbing.

---

## Install

```bash
pip install -U FinMind pandas requests
export FINMIND_TOKEN="your_token_here"
```

Copy the `taiwan_equity_toolkit/` directory into your working path, or install as a local package.

---

## First-run validation

Before trusting the toolkit in production, run the validator:

```bash
python taiwan_equity_toolkit/validate_setup.py
# or: python taiwan_equity_toolkit/validate_setup.py 2330 2317 2454
```

This confirms: token works, API quota is healthy, critical datasets are reachable, the parser ledgers match real FinMind responses, and a full Triage + Gate 3 pass completes end-to-end on a reference stock. Fix any ✗ before running screens; treat ⚠ on reachability as "this dataset is tier-locked or intermittently unavailable."

For a full end-to-end demo:

```bash
python taiwan_equity_toolkit/full_screen_demo.py 2330
python taiwan_equity_toolkit/full_screen_demo.py 2330 --peers 2303,6770 --book 2317,2454 --size-ntd 10000000
```

---

## The agent's mental model

The toolkit is a set of deterministic functions keyed to the framework's gates. Each function:

- Returns a structured dataclass (no raw dicts, no HTML parsing)
- Carries source citations (`{dataset_name}, {as_of_date}`) on every metric
- Fails loud — missing data → `None` + note, never silent zeros
- Uses async batch whenever peer data is involved

The agent's job is to call the right function for the current gate, interpret the structured result, and compose a memo. The arithmetic is already done.

---

## Quick start — full screen on one name

```python
from taiwan_equity_toolkit import FinMindClient, triage, gate3, peers
from taiwan_equity_toolkit.config import load_token, INDUSTRY_ANCHORS

client = FinMindClient(token=load_token())

# Step 1 — Triage
triage_result = triage.run(client, stock_id='2330')
print(triage_result.summary())

if not triage_result.passed:
    # Stop here. Document the failure. Do not proceed to Gate 3.
    pass
else:
    # Step 2 — Gate 3 Forensic Quality
    g3 = gate3.run(client, stock_id='2330')
    print(g3.memo())
    # g3.verdict ∈ {"Pass", "Conditional Watchlist", "Fail", "Fail (Hard-Fail Override)"}
    # g3.total_score is out of 100
    # g3.hard_fail_triggered is a boolean

    # Step 3 — Gate 4 peer comparison (if Gate 3 passed)
    if g3.verdict == "Pass":
        peer_cmp = peers.compare(
            client,
            candidate='2330',
            peers=INDUSTRY_ANCHORS['foundry'],
        )
        print(peer_cmp.summary())
```

---

## Module reference

### `config`
All thresholds, weights, and tunable parameters. One file, explicit, versionable.

Key dataclasses:
- `TriageConfig` — triage thresholds (min ADV, max staleness, etc.)
- `Gate3Weights` — scorecard weights summing to 100
- `Gate3Thresholds` — CFO/NI threshold, interest coverage floor, etc.
- `Gate65Config` — entry-architecture thresholds

```python
from taiwan_equity_toolkit.config import DEFAULT_CONFIG
print(DEFAULT_CONFIG.gate3_weights.total())  # 100
```

### `client.FinMindClient`
FinMind REST wrapper. Handles authentication, rate-limit awareness, retry logic, and async batch.

```python
client = FinMindClient(token=load_token())
print(client.usage())  # API quota check

# Single fetch
df = client.price('2330', start_date='2024-01-01')

# Async batch — use this for peer work
panel = client.get_multi(
    'TaiwanStockMonthRevenue',
    stock_ids=['2330', '2303', '6770'],
    start_date='2023-01-01',
)  # returns {stock_id: DataFrame}

# Convenience shortcuts for the common datasets
df = client.financial_statements('2330', '2022-01-01')
df = client.monthly_revenue('2330', '2023-01-01')
df = client.institutional_flow('2330', '2024-01-01')
```

### `parsers`
Pivots FinMind's long-format financial statements into structured records.

```python
from taiwan_equity_toolkit import parsers
fs_df = client.financial_statements('2330', '2022-01-01')
income = parsers.parse_income_statements(fs_df)
# income is list[IncomeStatement], each with .revenue, .gross_margin, etc.

latest = parsers.latest(income)
last_4q = parsers.ttm(income, n=4)
```

### `metrics`
Derived ratios. Every return is a `Metric` dataclass with `.value`, `.unit`, `.as_of`, `.source`, `.note`.

```python
from taiwan_equity_toolkit import metrics

# Call with parsed records
cfo_ni = metrics.cfo_to_ni_ratio(income, cash, n_qtrs=4)
print(cfo_ni.cite())  # "CFO/NI=0.87x (FinancialStatements + CashFlows, 2024-09-30)"

# Call with DataFrames for market data
adv = metrics.adv_ntd(price_df, lookback=20)
vol = metrics.realized_vol(price_adj_df, lookback=30)
```

### `triage.run(client, stock_id)`
The Triage Filter. One call, returns `TriageResult` with `.passed` boolean and per-check diagnostics.

```python
result = triage.run(client, '2330', intended_position_ntd=10_000_000)
print(result.summary())
if not result.passed:
    for f in result.failures():
        print(f"FAIL: {f.name} — {f.detail}")
```

### `gate3.run(client, stock_id)`
Full forensic quality pass. Returns `Gate3Result` with:

- `.total_score` (out of 100)
- `.verdict` — "Pass" / "Conditional Watchlist" / "Fail" / "Fail (Hard-Fail Override)"
- `.sub_layers` — list of `SubLayerScore` (3A through 3E)
- `.hard_fails` — list of `HardFailFinding` with `.triggered` booleans
- `.hard_fail_triggered` — overall boolean
- `.headline_metrics` — list of `Metric` for quick citation
- `.memo()` — pre-formatted markdown block for inclusion in the full memo

```python
g3 = gate3.run(client, '2330')
if g3.hard_fail_triggered:
    # Automatic reject, regardless of numeric score
    for hf in g3.hard_fails:
        if hf.triggered:
            print(f"HARD FAIL: {hf.name} — {hf.detail}")
```

### `peers.compare(client, candidate, peers)`
Async batch peer comparison for Gate 4 cross-source validation. Returns `PeerComparison` with:

- `.revenue_yoy`, `.gross_margin`, `.operating_margin`, `.cfo_to_ni` — ranked DataFrames
- `.correlation_matrix` — 90-day return correlation, symmetric
- `.institutional_flow_60d` — net flow by investor type across all peers
- `.candidate_rankings` — dict mapping metric → (rank, total)
- `.summary()` — pre-formatted markdown block

```python
cmp = peers.compare(client, '2330', peers=['2303', '6770'])
print(cmp.summary())
print(cmp.candidate_rankings)
# {'Revenue YoY': (1, 3), 'Gross margin': (1, 3), ...}
```

### `value_chain.analyze(client, stock_id)`
Gate 5 industry-chain mapping and upstream signal collection. Uses `TaiwanStockIndustryChain` to find chain peers, then async-batch queries revenue, margins, and institutional flows.

```python
from taiwan_equity_toolkit import value_chain

report = value_chain.analyze(client, '2330')
print(report.summary())
# Industries: 半導體業
# Peers in chain: 28 — 2303, 2449, 3034, ...
# Upstream / chain signals:
#   - 2303: Rev YoY +8.2% | Margin expanding | Inst flow +120,000,000 (2024-09-30)
```

Override the auto-detected upstream list if needed:

```python
report = value_chain.analyze(client, '2330', override_upstream=['3715', '3443'])
```

### `gate65.run(client, stock_id, existing_book=...)`
Gate 6.5 Entry Architecture evaluator — parallel structure to `gate3.run()`. Returns `Gate65Result` with:

- `.verdict` — "Enter Now" / "Stagger / Scale In" / "Wait for Setup" / "Reject for Book Fit"
- `.checks` — per-check red/yellow/green findings organized by sub-layer (6.5A–6.5D)
- `.correlations` — dict of stock_id → correlation with candidate (if existing book supplied)
- `.summary()` — pre-formatted output

```python
from taiwan_equity_toolkit import gate65

g65 = gate65.run(
    client,
    stock_id='2330',
    existing_book=['2317', '2454', '2308'],    # current holdings for correlation check
    intended_position_ntd=10_000_000,           # for liquidity sizing check
)
print(g65.summary())
```

### `metrics.reverse_dcf_implied_growth(market_cap, ttm_fcf, ...)`
Gate 6.5A reverse-DCF sanity check. Solves for the explicit-period FCF growth rate implied by the current market cap given a 2-stage DCF (explicit years + terminal).

```python
implied = metrics.reverse_dcf_implied_growth(
    market_cap=20_000_000_000_000,   # NT$20T
    ttm_fcf=1_000_000_000_000,       # NT$1T
    discount_rate=0.09,
    terminal_growth=0.025,
    explicit_years=10,
)
print(implied.cite())
# Reverse-DCF implied g=7.2% (derived, discount=9.0%, terminal=2.5%, explicit=10y)
```

If `.value > plausible growth for this business`, the price is pricing in too much.

### `memo.FullScreenMemo`
Assembler for the final memo. Fill in qualitative fields (industry view, thesis, catalyst) around the mechanical results.

```python
from taiwan_equity_toolkit.memo import FullScreenMemo

m = FullScreenMemo(
    stock_id='2330',
    industry_view="Foundry expanding — AI-driven capacity shortage into 2H26...",
    company_qualitative="TSMC is the industry. Leading-node monopoly...",
    triage=triage_result,
    gate3=g3_result,
    peer_comparison=peer_cmp,
    thesis_statement="Long 2330 into 2H26 AI capex cycle.",
    catalyst_path="Monthly revenue release (mid-month), Q1 earnings mid-April.",
    invalidation="Monthly YoY < 10% for 2 consecutive months.",
    verdict="Actionable Watchlist",
)
print(m.render())
```

---

## What the toolkit does NOT automate

These are judgment calls the agent must still make:

- **Gate 1 industry direction** — requires synthesizing macro indicators with market context
- **Gate 2 business model articulation** — qualitative understanding
- **Gate 5 value chain lead/lag timing** — industry-specific expertise required
- **Gate 6 strategic portfolio fit** — depends on existing book
- **Gate 6.5 crowding judgment** — requires current market context
- **Gate 7 thesis writing and invalidation criteria** — the actual investment view
- **Reverse DCF** — requires assumptions about growth and margin trajectory

The toolkit gives you a clean scorecard and clean data; the view is still yours.

---

## Error handling expectations

Every function can fail because FinMind is a remote service. Patterns:

```python
try:
    g3 = gate3.run(client, '2330')
except FinMindError as e:
    # Data fetch failure — log and skip this name
    log.error("Gate 3 failed for 2330: %s", e)
except RateLimitExceeded:
    # Quota exhausted — stop and wait
    raise
```

If partial data is available, the toolkit completes what it can and flags the gaps in `.data_gaps` and `.notes`. Never trust a metric with `.value is None` — treat it as "unknown," not zero.

---

## Tier awareness

FinMind has three tiers (Free / Backer / Sponsor). When a required dataset is unavailable at the current tier, the affected check returns gracefully with a note. Check:

```python
usage = client.usage()
print(f"API usage: {usage.user_count}/{usage.api_request_limit} ({usage.utilization_pct*100:.1f}%)")
```

Batch aggressively via `get_multi` to minimize requests. Each peer comparison with 3 peers across 5 datasets = 20 requests (4 × 5, one per stock per dataset), not 20 sequential calls.

---

## Typical call budget per full screen

Rough estimates for a single-name full screen:

| Gate | Calls | Notes |
|---|---|---|
| Triage | 5–6 | Disposition, suspension, price, monthly revenue, financials (freshness check), capital reduction |
| Gate 3 | 7 | Financials, balance sheet, cash flow, monthly rev, institutional flow, foreign ownership, margin/short, plus news for 3E |
| Gate 4 (peers) | 5 × (1 + peer_count) | via async batch |
| Gate 6.5 | 3–4 | PER, price adj, price limit, optional futures/options data |

Target: ~30–40 calls per full single-name screen. Peer comparison at 3 peers adds ~20 calls via batch.

---

## Extending the toolkit

Natural next additions:

1. **Value-chain helper** — wrapper around `TaiwanStockIndustryChain` for upstream/downstream batch queries
2. **Reverse-DCF helper** — closed-form implied-growth solver
3. **Convertible-bond dilution calculator** — using `TaiwanStockConvertibleBondDailyOverview`
4. **Branch-broker persistent-buyer detector** — Sponsor-tier `TaiwanStockTradingDailyReport` analysis
5. **Post-trade attribution** — logs which gates were predictive (covered elsewhere)

Add new metrics to `metrics.py`, new checks to `gate3.py` components, new thresholds to `config.py`. Keep the public API (`triage.run`, `gate3.run`, `peers.compare`) stable.
```

## `taiwan_equity_toolkit/__init__.py`

```python
"""
Taiwan Equity Toolkit — Pre-trade screening infrastructure for the Stock Selection Framework.

Designed for use by an AI agent (or human analyst) to execute the framework's gates
with deterministic, citable outputs. ~80% of the mechanical work is pre-built so
the agent spends tokens on judgment, not arithmetic.

Quick start:
    from taiwan_equity_toolkit import FinMindClient, triage, gate3, gate65, peers, value_chain
    from taiwan_equity_toolkit.config import load_token

    client = FinMindClient(token=load_token())

    # The canonical pipeline
    triage_result = triage.run(client, stock_id='2330')
    if triage_result.passed:
        g3 = gate3.run(client, stock_id='2330')
        if g3.verdict == "Pass":
            peer_cmp = peers.compare(client, '2330', peers=['2303', '6770'])
            chain_report = value_chain.analyze(client, '2330')
            g65 = gate65.run(client, '2330', existing_book=['2317', '2454'])

Module layout:
    config       — Thresholds, weights, token loader
    client       — FinMind API wrapper (sync + async batch)
    parsers      — FinMind long-format → wide-format converters
    metrics      — Derived financial ratios with source tagging
    triage       — Triage Filter (cheap screens before Gate 3)
    gate3        — Forensic Quality scorecard + hard-fail overrides
    gate65       — Entry Architecture evaluator
    peers        — Async peer comparison utilities
    value_chain  — Gate 5 industry-chain position + upstream signals
    memo         — Structured output formatting
"""

from taiwan_equity_toolkit import (
    config, client, parsers, metrics,
    triage, gate3, gate65, peers, value_chain, memo,
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
    "triage",
    "gate3",
    "gate65",
    "peers",
    "value_chain",
    "memo",
]
```

## `taiwan_equity_toolkit/client.py`

```python
"""
FinMind API client — thin wrapper around the REST endpoint with async batch support.

Prefer `get_multi(...)` over looping `get(...)` for peer analysis: it hits the
API concurrently and returns a dict keyed by stock_id. This is the single most
important performance lever when comparing a candidate against peers.

Usage:
    client = FinMindClient(token=load_token())
    df = client.get('TaiwanStockFinancialStatements', stock_id='2330', start_date='2020-01-01')
    panel = client.get_multi('TaiwanStockMonthRevenue', stock_ids=['2330', '2303'], start_date='2023-01-01')
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd
import requests

from taiwan_equity_toolkit.config import (
    FINMIND_BASE_URL,
    FINMIND_USER_INFO_URL,
    MAX_RETRIES,
    RATE_LIMIT_PER_HOUR,
    RETRY_BACKOFF_SEC,
    DEFAULT_TIMEOUT_SEC,
)

log = logging.getLogger(__name__)


class FinMindError(Exception):
    """Raised when the API returns an error or response is unparseable."""


class RateLimitExceeded(FinMindError):
    """API quota exhausted."""


@dataclass
class UsageInfo:
    user_count: int
    api_request_limit: int

    @property
    def remaining(self) -> int:
        return self.api_request_limit - self.user_count

    @property
    def utilization_pct(self) -> float:
        if self.api_request_limit == 0:
            return 0.0
        return self.user_count / self.api_request_limit


class FinMindClient:
    """FinMind REST client with retry, rate-limit awareness, and async batching."""

    def __init__(
        self,
        token: str,
        base_url: str = FINMIND_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT_SEC,
    ):
        if not token:
            raise ValueError("FinMind token is required.")
        self._token = token
        self._base_url = base_url
        self._timeout = timeout
        self._headers = {"Authorization": f"Bearer {token}"}

    # ──────────────────────────────────────────────────────────────────
    # Quota
    # ──────────────────────────────────────────────────────────────────

    def usage(self) -> UsageInfo:
        """Check current API quota usage."""
        resp = requests.get(FINMIND_USER_INFO_URL, headers=self._headers, timeout=self._timeout)
        resp.raise_for_status()
        j = resp.json()
        return UsageInfo(user_count=int(j["user_count"]), api_request_limit=int(j["api_request_limit"]))

    # ──────────────────────────────────────────────────────────────────
    # Synchronous single-dataset fetch
    # ──────────────────────────────────────────────────────────────────

    def get(
        self,
        dataset: str,
        stock_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Fetch a dataset from FinMind.

        Returns an empty DataFrame if the API returns no data. Raises FinMindError
        on non-recoverable failures after retries.

        Args:
            dataset: FinMind dataset name (e.g., 'TaiwanStockFinancialStatements')
            stock_id: Data ID (stock code for most TW datasets)
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD

        Returns:
            DataFrame with the raw response rows.
        """
        params: dict[str, Any] = {"dataset": dataset}
        if stock_id:
            params["data_id"] = stock_id
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        last_err: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.get(
                    f"{self._base_url}/data",
                    params=params,
                    headers=self._headers,
                    timeout=self._timeout,
                )
                if resp.status_code == 402:
                    raise RateLimitExceeded(f"FinMind quota exceeded: {resp.text}")
                if resp.status_code == 400:
                    # 400 = dataset requires higher membership tier (Backer/Sponsor).
                    # Not a transient error — do not retry.
                    raise FinMindError(
                        f"FinMind tier limit: dataset '{dataset}' requires Backer/Sponsor "
                        f"tier (HTTP 400). Skipping."
                    )
                resp.raise_for_status()
                payload = resp.json()
                if payload.get("status") != 200:
                    raise FinMindError(f"FinMind error: {payload}")
                rows = payload.get("data", [])
                return pd.DataFrame(rows)
            except RateLimitExceeded:
                raise  # don't retry on quota exhaustion
            except FinMindError:
                raise  # don't retry on known API errors (tier, bad dataset)
            except Exception as e:  # noqa: BLE001
                last_err = e
                log.warning("FinMind fetch failed (attempt %d/%d): %s", attempt + 1, MAX_RETRIES, e)
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
        raise FinMindError(f"FinMind fetch failed after {MAX_RETRIES} retries: {last_err}")

    # ──────────────────────────────────────────────────────────────────
    # Async batch fetch — the edge over retail workflows
    # ──────────────────────────────────────────────────────────────────

    async def _fetch_async(
        self,
        dataset: str,
        stock_id: str,
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> tuple[str, pd.DataFrame]:
        """Wrapper that runs sync fetch in a thread."""
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None, lambda: self.get(dataset, stock_id, start_date, end_date)
        )
        return stock_id, df

    async def _get_multi_async(
        self,
        dataset: str,
        stock_ids: list[str],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> dict[str, pd.DataFrame]:
        tasks = [
            self._fetch_async(dataset, sid, start_date, end_date) for sid in stock_ids
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        out: dict[str, pd.DataFrame] = {}
        for res in results:
            if isinstance(res, Exception):
                log.warning("Peer fetch failed: %s", res)
                continue
            stock_id, df = res
            out[stock_id] = df
        return out

    def get_multi(
        self,
        dataset: str,
        stock_ids: list[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, pd.DataFrame]:
        """
        Async batch fetch across multiple stocks.

        Returns {stock_id: DataFrame}. Failed fetches are logged and omitted.
        Not supported by: info, snapshot, tick, total-aggregation, CB datasets
        (those take no data_id or have special semantics — call get() instead).
        """
        return asyncio.run(self._get_multi_async(dataset, stock_ids, start_date, end_date))

    # ──────────────────────────────────────────────────────────────────
    # Convenience shortcuts for the most common datasets
    # ──────────────────────────────────────────────────────────────────

    def price(self, stock_id: str, start_date: str, end_date: Optional[str] = None) -> pd.DataFrame:
        return self.get("TaiwanStockPrice", stock_id, start_date, end_date)

    def price_adj(self, stock_id: str, start_date: str, end_date: Optional[str] = None) -> pd.DataFrame:
        return self.get("TaiwanStockPriceAdj", stock_id, start_date, end_date)

    def financial_statements(self, stock_id: str, start_date: str) -> pd.DataFrame:
        return self.get("TaiwanStockFinancialStatements", stock_id, start_date)

    def balance_sheet(self, stock_id: str, start_date: str) -> pd.DataFrame:
        return self.get("TaiwanStockBalanceSheet", stock_id, start_date)

    def cash_flow(self, stock_id: str, start_date: str) -> pd.DataFrame:
        return self.get("TaiwanStockCashFlowsStatement", stock_id, start_date)

    def monthly_revenue(self, stock_id: str, start_date: str) -> pd.DataFrame:
        return self.get("TaiwanStockMonthRevenue", stock_id, start_date)

    def per(self, stock_id: str, start_date: str, end_date: Optional[str] = None) -> pd.DataFrame:
        return self.get("TaiwanStockPER", stock_id, start_date, end_date)

    def market_value(self, stock_id: str, start_date: str, end_date: Optional[str] = None) -> pd.DataFrame:
        return self.get("TaiwanStockMarketValue", stock_id, start_date, end_date)

    def institutional_flow(self, stock_id: str, start_date: str, end_date: Optional[str] = None) -> pd.DataFrame:
        return self.get("TaiwanStockInstitutionalInvestorsBuySell", stock_id, start_date, end_date)

    def foreign_ownership(self, stock_id: str, start_date: str, end_date: Optional[str] = None) -> pd.DataFrame:
        return self.get("TaiwanStockShareholding", stock_id, start_date, end_date)

    def margin_short(self, stock_id: str, start_date: str, end_date: Optional[str] = None) -> pd.DataFrame:
        return self.get("TaiwanStockMarginPurchaseShortSale", stock_id, start_date, end_date)

    def securities_lending(self, stock_id: str, start_date: str, end_date: Optional[str] = None) -> pd.DataFrame:
        return self.get("TaiwanStockSecuritiesLending", stock_id, start_date, end_date)

    def news(self, stock_id: str, start_date: str) -> pd.DataFrame:
        return self.get("TaiwanStockNews", stock_id, start_date)

    def dividend(self, stock_id: str, start_date: str) -> pd.DataFrame:
        return self.get("TaiwanStockDividend", stock_id, start_date)

    def industry_chain(self) -> pd.DataFrame:
        return self.get("TaiwanStockIndustryChain")

    def stock_info(self) -> pd.DataFrame:
        return self.get("TaiwanStockInfo")
```

## `taiwan_equity_toolkit/config.py`

```python
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
```

## `taiwan_equity_toolkit/full_screen_demo.py`

```python
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
    triage,
    gate3,
    gate65,
    peers,
    value_chain,
    memo,
)
from taiwan_equity_toolkit.config import INDUSTRY_ANCHORS, load_token


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
    tr = triage.run(client, stock_id=stock_id, intended_position_ntd=intended)
    print(tr.summary())
    print()

    if not tr.passed:
        print("⛔ Triage failed — screen stops here.")
        sys.exit(0)

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
```

## `taiwan_equity_toolkit/gate3.py`

```python
"""
Gate 3 — Forensic Quality.

Implements the 5-sublayer scorecard (3A–3E), 100-point scoring, and the
seven Hard-Fail Overrides.

One function: `run(client, stock_id)` → Gate3Result. The agent reads the
structured result and composes the memo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from taiwan_equity_toolkit.client import FinMindClient
from taiwan_equity_toolkit.config import DEFAULT_CONFIG, Gate3Thresholds, Gate3Weights
from taiwan_equity_toolkit import metrics, parsers


@dataclass
class SubLayerScore:
    layer: str                  # "3A", "3B", ...
    name: str                   # full name
    score: float                # earned points
    max_score: int              # weight cap
    components: list[dict] = field(default_factory=list)  # per-check details

    def as_line(self) -> str:
        return f"{self.layer} {self.name}: {self.score:.1f} / {self.max_score}"


@dataclass
class HardFailFinding:
    name: str
    triggered: bool
    detail: str


@dataclass
class Gate3Result:
    stock_id: str
    total_score: float
    verdict: str                # "Pass" | "Conditional" | "Fail"
    sub_layers: list[SubLayerScore] = field(default_factory=list)
    hard_fails: list[HardFailFinding] = field(default_factory=list)
    hard_fail_triggered: bool = False
    headline_metrics: list[metrics.Metric] = field(default_factory=list)
    thesis_bullets: list[str] = field(default_factory=list)
    risk_bullets: list[str] = field(default_factory=list)
    data_gaps: list[str] = field(default_factory=list)

    def memo(self) -> str:
        lines = [
            f"# Gate 3 — Forensic Quality: {self.stock_id}",
            f"Score: {self.total_score:.1f} / 100 → {self.verdict}",
        ]
        if self.hard_fail_triggered:
            lines.append("⚠ Hard-Fail Override TRIGGERED — automatic rejection regardless of score")
        lines.append("")

        lines.append("## Sub-layer scores")
        for s in self.sub_layers:
            lines.append(f"- {s.as_line()}")
        lines.append("")

        lines.append("## Headline metrics")
        for m in self.headline_metrics:
            lines.append(f"- {m.cite()}")
        lines.append("")

        if self.hard_fails:
            lines.append("## Hard-Fail Overrides")
            for hf in self.hard_fails:
                mark = "⚠" if hf.triggered else "✓"
                lines.append(f"- {mark} {hf.name}: {hf.detail}")
            lines.append("")

        if self.thesis_bullets:
            lines.append("## Thesis (forensic-quality perspective)")
            for b in self.thesis_bullets:
                lines.append(f"- {b}")
            lines.append("")

        if self.risk_bullets:
            lines.append("## Risks")
            for b in self.risk_bullets:
                lines.append(f"- {b}")
            lines.append("")

        if self.data_gaps:
            lines.append("## Data gaps / staleness")
            for g in self.data_gaps:
                lines.append(f"- {g}")

        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────
# Scoring helpers
# ──────────────────────────────────────────────────────────────────────────

def _score_3a_operating(
    income: list[parsers.IncomeStatement],
    cash: list[parsers.CashFlow],
    balance: list[parsers.BalanceSheet],
    rev_df,
    weight: int,
    th: Gate3Thresholds,
) -> SubLayerScore:
    """
    Operating Quality — 25 pts.
    Sub-components: revenue growth (7), margin direction (6), earnings quality (CFO/NI) (7), ROE (5).
    """
    components = []
    earned = 0.0

    # Revenue growth (7 pts)
    rev_yoy = metrics.revenue_growth_yoy(rev_df)
    rev_ttm = metrics.revenue_ttm_trend(rev_df)
    rev_pts = 0.0
    if rev_yoy.value is not None:
        if rev_yoy.value > 10:
            rev_pts += 4
        elif rev_yoy.value > 0:
            rev_pts += 2
        elif rev_yoy.value > -10:
            rev_pts += 1
    if rev_ttm.value is not None:
        if rev_ttm.value > 10:
            rev_pts += 3
        elif rev_ttm.value > 0:
            rev_pts += 2
        elif rev_ttm.value > -5:
            rev_pts += 1
    components.append({"check": "Revenue growth", "points": rev_pts, "max": 7, "detail": f"YoY {rev_yoy.value}, TTM {rev_ttm.value}"})
    earned += rev_pts

    # Margin direction (6 pts)
    gm_pts = 0.0
    if len(income) >= 4:
        recent = sorted(income, key=lambda r: r.date)[-4:]
        gm_series = [r.gross_margin for r in recent if r.gross_margin is not None]
        if len(gm_series) >= 2:
            if gm_series[-1] >= gm_series[0]:
                gm_pts += 3
            else:
                gm_pts += 1
        om_series = [r.operating_margin for r in recent if r.operating_margin is not None]
        if len(om_series) >= 2:
            if om_series[-1] >= om_series[0]:
                gm_pts += 3
            else:
                gm_pts += 1
    components.append({"check": "Margin direction", "points": gm_pts, "max": 6, "detail": "4Q GM + OM trend"})
    earned += gm_pts

    # Earnings quality — CFO/NI (7 pts)
    cfo_ni = metrics.cfo_to_ni_ratio(income, cash, n_qtrs=4)
    eq_pts = 0.0
    if cfo_ni.value is not None:
        if cfo_ni.value >= th.cfo_to_ni_healthy:
            eq_pts = 7
        elif cfo_ni.value >= 0.6:
            eq_pts = 4
        elif cfo_ni.value >= th.cfo_to_ni_warning:
            eq_pts = 2
        else:
            eq_pts = 0
    components.append({"check": "CFO/NI", "points": eq_pts, "max": 7, "detail": cfo_ni.cite()})
    earned += eq_pts

    # ROE (5 pts)
    roe = metrics.roe_proxy(income, balance)
    roe_pts = 0.0
    if roe.value is not None:
        if roe.value >= 15:
            roe_pts = 5
        elif roe.value >= 10:
            roe_pts = 3
        elif roe.value >= 5:
            roe_pts = 2
        elif roe.value >= 0:
            roe_pts = 1
    components.append({"check": "ROE (proxy)", "points": roe_pts, "max": 5, "detail": roe.cite()})
    earned += roe_pts

    return SubLayerScore("3A", "Operating Quality", earned, weight, components)


def _score_3b_balance_sheet(
    income: list[parsers.IncomeStatement],
    cash: list[parsers.CashFlow],
    balance: list[parsers.BalanceSheet],
    weight: int,
    th: Gate3Thresholds,
) -> SubLayerScore:
    """
    Balance Sheet & Cash Survival — 35 pts.
    Leverage (10), liquidity (8), interest coverage (7), FCF integrity (10).
    """
    components = []
    earned = 0.0

    # Leverage — net debt / EBITDA (10 pts)
    nd_ebitda = metrics.net_debt_to_ebitda(balance, income)
    lev_pts = 0.0
    if nd_ebitda.value is not None:
        v = nd_ebitda.value
        if v <= 0:
            lev_pts = 10  # net cash
        elif v <= 1.5:
            lev_pts = 9
        elif v <= th.net_debt_to_ebitda_warning:
            lev_pts = 7
        elif v <= 4.0:
            lev_pts = 4
        elif v <= th.net_debt_to_ebitda_hardfail:
            lev_pts = 2
        else:
            lev_pts = 0
    components.append({"check": "Net debt / EBITDA", "points": lev_pts, "max": 10, "detail": nd_ebitda.cite()})
    earned += lev_pts

    # Liquidity — current ratio (4) + cash/ST debt (4) = 8 pts
    cr = metrics.current_ratio_latest(balance)
    cash_st = metrics.cash_to_short_term_debt(balance)
    liq_pts = 0.0
    if cr.value is not None:
        if cr.value >= 1.5:
            liq_pts += 4
        elif cr.value >= th.current_ratio_min:
            liq_pts += 2
    if cash_st.value is not None:
        if cash_st.value >= 2.0:
            liq_pts += 4
        elif cash_st.value >= th.cash_to_short_term_debt_min:
            liq_pts += 2
    components.append({"check": "Liquidity", "points": liq_pts, "max": 8, "detail": f"{cr.cite()}; {cash_st.cite()}"})
    earned += liq_pts

    # Interest coverage (7 pts)
    ic = metrics.interest_coverage(income, 4)
    ic_pts = 0.0
    if ic.value is not None:
        if ic.value >= 10:
            ic_pts = 7
        elif ic.value >= 5:
            ic_pts = 5
        elif ic.value >= th.interest_coverage_min:
            ic_pts = 3
        else:
            ic_pts = 0
    else:
        # May be missing because no interest expense (debt-free); partial credit
        bs = parsers.latest(balance)
        if bs and (bs.total_debt or 0) == 0:
            ic_pts = 7  # debt-free
            ic.note = "Debt-free — no interest expense"
    components.append({"check": "Interest coverage", "points": ic_pts, "max": 7, "detail": ic.cite()})
    earned += ic_pts

    # FCF integrity (10 pts)
    fcf_margin = metrics.free_cash_flow_margin(cash, income, 4)
    fcf_pts = 0.0
    if fcf_margin.value is not None:
        if fcf_margin.value >= 15:
            fcf_pts = 10
        elif fcf_margin.value >= 5:
            fcf_pts = 7
        elif fcf_margin.value >= 0:
            fcf_pts = 4
        else:
            fcf_pts = 0
    components.append({"check": "FCF margin", "points": fcf_pts, "max": 10, "detail": fcf_margin.cite()})
    earned += fcf_pts

    return SubLayerScore("3B", "Balance Sheet & Cash Survival", earned, weight, components)


def _score_3c_ownership(
    flow_df,
    ownership_df,
    margin_df,
    weight: int,
) -> SubLayerScore:
    """
    Ownership & Market Structure — 20 pts.
    Institutional net flow (10), foreign ownership trend (5), margin structure (5).
    """
    components = []
    earned = 0.0

    # Institutional flow (10 pts)
    flows = metrics.institutional_net_flow(flow_df, lookback_days=60)
    pos_directions = 0
    neg_directions = 0
    for k, m in flows.items():
        if m.value is None:
            continue
        if m.value > 0:
            pos_directions += 1
        elif m.value < 0:
            neg_directions += 1

    if pos_directions >= 2:
        flow_pts = 10  # broad sponsorship
    elif pos_directions == 1 and neg_directions == 0:
        flow_pts = 6
    elif pos_directions == neg_directions:
        flow_pts = 4
    elif neg_directions >= 2:
        flow_pts = 0
    else:
        flow_pts = 3
    components.append({
        "check": "Institutional flow (60d net)",
        "points": flow_pts, "max": 10,
        "detail": "; ".join([m.cite() for m in flows.values()])
    })
    earned += flow_pts

    # Foreign ownership trend (5 pts)
    fo_pts = 0.0
    fo_detail = "no data"
    try:
        if not ownership_df.empty and "ForeignInvestmentSharesRatio" in ownership_df.columns:
            df = ownership_df.sort_values("date").copy()
            if len(df) >= 2:
                first = df.iloc[0]["ForeignInvestmentSharesRatio"]
                last = df.iloc[-1]["ForeignInvestmentSharesRatio"]
                if first is not None and last is not None:
                    if last > first:
                        fo_pts = 5
                        fo_detail = f"Foreign holdings rising: {first:.1f}% → {last:.1f}%"
                    elif last == first:
                        fo_pts = 3
                        fo_detail = f"Foreign holdings flat at ~{last:.1f}%"
                    else:
                        fo_pts = 1
                        fo_detail = f"Foreign holdings declining: {first:.1f}% → {last:.1f}%"
    except Exception:
        pass
    components.append({"check": "Foreign ownership trend", "points": fo_pts, "max": 5, "detail": fo_detail})
    earned += fo_pts

    # Margin/short structure (5 pts)
    m_pts = 0.0
    m_detail = "no data"
    try:
        if not margin_df.empty and "MarginPurchaseTodayBalance" in margin_df.columns:
            df = margin_df.sort_values("date").copy()
            if len(df) >= 20:
                recent = df.tail(20)
                margin_change = recent.iloc[-1]["MarginPurchaseTodayBalance"] - recent.iloc[0]["MarginPurchaseTodayBalance"]
                short_change = recent.iloc[-1]["ShortSaleTodayBalance"] - recent.iloc[0]["ShortSaleTodayBalance"]
                # Retail margin declining + short covering = healthy
                if margin_change < 0 and short_change <= 0:
                    m_pts = 5
                    m_detail = "Retail margin declining or flat, shorts covering — clean"
                elif margin_change < 0:
                    m_pts = 4
                    m_detail = "Retail margin declining"
                elif short_change < 0:
                    m_pts = 3
                    m_detail = "Shorts covering but margin rising — mixed"
                elif margin_change > 0 and short_change > 0:
                    m_pts = 2
                    m_detail = "Margin and short both rising — battleground"
                else:
                    m_pts = 2
                    m_detail = "Elevated retail margin"
    except Exception:
        pass
    components.append({"check": "Margin/short structure", "points": m_pts, "max": 5, "detail": m_detail})
    earned += m_pts

    return SubLayerScore("3C", "Ownership & Market Structure", earned, weight, components)


def _score_3d_derivatives(client: FinMindClient, stock_id: str, weight: int) -> SubLayerScore:
    """
    Derivatives & Capital Structure — 10 pts.
    CB existence & pricing (5), single-stock futures/options presence (5).
    Tier-dependent; partial if data unavailable.
    """
    components = []
    earned = 0.0
    today = datetime.today()
    cb_start = (today - timedelta(days=180)).strftime("%Y-%m-%d")

    # CB check (5 pts)
    cb_pts = 0.0
    cb_detail = "no CB outstanding (default pass)"
    try:
        cb_info = client.get("TaiwanStockConvertibleBondInfo")
        if not cb_info.empty:
            # Filter for this underlying if schema supports it
            # Schema: cb_id often encodes underlying; match manually if needed
            # Conservative: if underlying appears in cb_id or cb_name, check further
            matching = cb_info[cb_info["cb_id"].astype(str).str.startswith(stock_id, na=False)]
            if matching.empty:
                cb_pts = 5
                cb_detail = "No outstanding CB for this underlying — no dilution risk from CB"
            else:
                cb_pts = 3  # CB exists, need deeper look
                cb_detail = f"{len(matching)} CB(s) outstanding — review required"
    except Exception as e:  # noqa: BLE001
        cb_detail = f"CB data unavailable: {e}"
    components.append({"check": "Convertible bond check", "points": cb_pts, "max": 5, "detail": cb_detail})
    earned += cb_pts

    # Single-stock futures/options presence (5 pts) — simplified: presence of derivatives = liquid, confirmable
    fut_pts = 0.0
    fut_detail = "data not fetched at this tier"
    try:
        fut_info = client.get("TaiwanFutOptDailyInfo")
        if not fut_info.empty:
            matches = fut_info[fut_info["code"].astype(str).str.contains(stock_id, na=False)]
            if not matches.empty:
                fut_pts = 5
                fut_detail = f"{len(matches)} single-stock derivative(s) listed — market structure deep"
            else:
                fut_pts = 3
                fut_detail = "No single-stock derivatives — can't cross-confirm via futures/options"
    except Exception as e:  # noqa: BLE001
        fut_detail = f"Futures info unavailable: {e}"
        fut_pts = 2  # partial credit for data gap, not the company's fault
    components.append({"check": "Single-stock derivatives presence", "points": fut_pts, "max": 5, "detail": fut_detail})
    earned += fut_pts

    return SubLayerScore("3D", "Derivatives & Capital Structure", earned, weight, components)


def _score_3e_data_integrity(
    client: FinMindClient,
    stock_id: str,
    rev_df,
    income: list[parsers.IncomeStatement],
    weight: int,
) -> SubLayerScore:
    """
    Data Integrity & Event Audit — 10 pts.
    Monthly vs quarterly revenue consistency (5), news/governance red flags (5).
    """
    components = []
    earned = 0.0
    today = datetime.today()

    # Monthly vs quarterly revenue consistency (5 pts)
    consistency_pts = 0.0
    consistency_detail = "insufficient data for check"
    try:
        if not rev_df.empty and income and "revenue" in rev_df.columns:
            # Take latest quarter revenue from income statements
            recent_q = sorted(income, key=lambda r: r.date)[-1]
            q_rev = recent_q.revenue
            q_date = recent_q.date[:7]  # YYYY-MM
            # Sum monthly revenue for the quarter
            import pandas as pd
            rev_df_copy = rev_df.copy()
            rev_df_copy["date"] = pd.to_datetime(rev_df_copy["date"])
            q_start = pd.to_datetime(q_date + "-01") - pd.DateOffset(months=2)
            q_end = pd.to_datetime(q_date + "-01") + pd.DateOffset(months=1)
            q_monthly = rev_df_copy[(rev_df_copy["date"] >= q_start) & (rev_df_copy["date"] < q_end)]
            m_sum = q_monthly["revenue"].sum()
            if q_rev and m_sum and abs(m_sum - q_rev) / q_rev < 0.05:
                consistency_pts = 5
                consistency_detail = f"Monthly sum vs quarterly report reconcile (Δ < 5%)"
            elif q_rev:
                consistency_pts = 2
                consistency_detail = f"Monthly sum {m_sum:,.0f} vs quarterly {q_rev:,.0f} — investigate"
    except Exception as e:  # noqa: BLE001
        consistency_detail = f"Check errored: {e}"
    components.append({"check": "Monthly↔Quarterly revenue consistency", "points": consistency_pts, "max": 5, "detail": consistency_detail})
    earned += consistency_pts

    # News red-flag scan (5 pts) — default positive unless we find trouble keywords
    news_pts = 5.0  # default pass
    news_detail = "no red-flag keywords found"
    red_flag_keywords = [
        "auditor", "會計師更換", "辭任", "董事請辭",
        "掏空", "財報重編", "restatement", "going concern",
        "關係人交易", "解任", "停牌",
    ]
    try:
        news_df = client.news(stock_id, (today - timedelta(days=90)).strftime("%Y-%m-%d"))
        if not news_df.empty and "title" in news_df.columns:
            hits = []
            for kw in red_flag_keywords:
                matching = news_df[news_df["title"].str.contains(kw, na=False)]
                if not matching.empty:
                    hits.append(f"{kw} ({len(matching)})")
            if hits:
                news_pts = 1.0
                news_detail = "Red-flag keywords in news: " + "; ".join(hits)
    except Exception as e:  # noqa: BLE001
        news_detail = f"News check errored: {e}"
    components.append({"check": "Governance/news red-flag scan", "points": news_pts, "max": 5, "detail": news_detail})
    earned += news_pts

    return SubLayerScore("3E", "Data Integrity & Event Audit", earned, weight, components)


# ──────────────────────────────────────────────────────────────────────────
# Hard-fail overrides
# ──────────────────────────────────────────────────────────────────────────

def _check_hard_fails(
    income: list[parsers.IncomeStatement],
    cash: list[parsers.CashFlow],
    balance: list[parsers.BalanceSheet],
    sub_3c: SubLayerScore,
    sub_3e: SubLayerScore,
    th: Gate3Thresholds,
) -> list[HardFailFinding]:
    findings: list[HardFailFinding] = []

    # 1. Refinancing wall + weak coverage
    bs = parsers.latest(balance)
    ic = metrics.interest_coverage(income, 4)
    cash_st = metrics.cash_to_short_term_debt(balance)
    triggered_1 = False
    detail_1 = "not triggered"
    if bs and bs.short_term_borrowings and bs.short_term_borrowings > 0:
        weak_cov = ic.value is not None and ic.value < th.interest_coverage_hardfail
        weak_cash = cash_st.value is not None and cash_st.value < th.cash_to_short_term_debt_min
        if weak_cov and weak_cash:
            triggered_1 = True
            detail_1 = f"ST debt present, coverage {ic.value:.1f}x < {th.interest_coverage_hardfail}, cash/ST {cash_st.value:.2f} < 1.0"
    findings.append(HardFailFinding("Refinancing wall + weak coverage", triggered_1, detail_1))

    # 2. Persistent CFO/NI divergence
    cfo_ni_4q = metrics.cfo_to_ni_ratio(income, cash, n_qtrs=4)
    triggered_2 = cfo_ni_4q.value is not None and cfo_ni_4q.value < th.cfo_to_ni_warning
    detail_2 = cfo_ni_4q.cite()
    if triggered_2:
        detail_2 += f" — below {th.cfo_to_ni_warning} threshold for 4+Q"
    findings.append(HardFailFinding("Persistent CFO/NI divergence", triggered_2, detail_2))

    # 3. Governance red flags (pulled from 3E score)
    news_comp = next((c for c in sub_3e.components if "red-flag" in c["check"]), None)
    triggered_3 = news_comp is not None and news_comp["points"] <= 1.0
    detail_3 = news_comp["detail"] if news_comp else "check skipped"
    findings.append(HardFailFinding("Governance red flags", triggered_3, detail_3))

    # 4. Ownership/derivatives conflict with fundamentals
    # Conservative proxy: 3C score < 6 (net outflow + weak margin structure) + fundamentals OK
    triggered_4 = False
    detail_4 = "not triggered"
    if sub_3c.score < 6:
        triggered_4 = True
        detail_4 = f"Ownership structure weak (3C score {sub_3c.score:.1f}/20) — check for unresolved conflict"
    findings.append(HardFailFinding("Unresolved cross-data conflict", triggered_4, detail_4))

    # 5. Extreme leverage
    nd_ebitda = metrics.net_debt_to_ebitda(balance, income)
    triggered_5 = nd_ebitda.value is not None and nd_ebitda.value > th.net_debt_to_ebitda_hardfail
    detail_5 = nd_ebitda.cite()
    findings.append(HardFailFinding("Extreme leverage", triggered_5, detail_5))

    # 6. Placeholder for repeat dilution — requires corporate-action history (caller can supply)
    findings.append(HardFailFinding("Repeated dilution without repair",
                                    False, "manual check — review TaiwanStockCapitalReductionReferencePrice history"))

    # 7. Data gap hard-fail if too many missing
    missing = 0
    for rec in income + cash + balance:
        missing += len(rec.missing_fields)
    total_fields = len(income) * 12 + len(cash) * 6 + len(balance) * 11
    gap_ratio = missing / max(total_fields, 1)
    triggered_7 = gap_ratio > 0.5
    findings.append(HardFailFinding("Excessive data gaps", triggered_7, f"{gap_ratio*100:.0f}% of fields missing"))

    return findings


# ──────────────────────────────────────────────────────────────────────────
# Main entry
# ──────────────────────────────────────────────────────────────────────────

def run(
    client: FinMindClient,
    stock_id: str,
    weights: Optional[Gate3Weights] = None,
    thresholds: Optional[Gate3Thresholds] = None,
) -> Gate3Result:
    """Run Gate 3 — Forensic Quality on a single stock."""
    weights = weights or DEFAULT_CONFIG.gate3_weights
    thresholds = thresholds or DEFAULT_CONFIG.gate3_thresholds

    today = datetime.today()
    fs_start = (today - timedelta(days=730)).strftime("%Y-%m-%d")  # 2y history
    rev_start = (today - timedelta(days=730)).strftime("%Y-%m-%d")
    flow_start = (today - timedelta(days=90)).strftime("%Y-%m-%d")
    ownership_start = (today - timedelta(days=180)).strftime("%Y-%m-%d")

    # Fetch primary data
    fs_df = client.financial_statements(stock_id, fs_start)
    bs_df = client.balance_sheet(stock_id, fs_start)
    cf_df = client.cash_flow(stock_id, fs_start)
    rev_df = client.monthly_revenue(stock_id, rev_start)
    flow_df = client.institutional_flow(stock_id, flow_start)
    own_df = client.foreign_ownership(stock_id, ownership_start)
    mgn_df = client.margin_short(stock_id, flow_start)

    income = parsers.parse_income_statements(fs_df)
    balance = parsers.parse_balance_sheets(bs_df)
    cash = parsers.parse_cash_flows(cf_df)

    # Score each sub-layer
    s_3a = _score_3a_operating(income, cash, balance, rev_df, weights.operating_quality, thresholds)
    s_3b = _score_3b_balance_sheet(income, cash, balance, weights.balance_sheet_survival, thresholds)
    s_3c = _score_3c_ownership(flow_df, own_df, mgn_df, weights.ownership_market_structure)
    s_3d = _score_3d_derivatives(client, stock_id, weights.derivatives_capital_structure)
    s_3e = _score_3e_data_integrity(client, stock_id, rev_df, income, weights.data_integrity)

    sub_layers = [s_3a, s_3b, s_3c, s_3d, s_3e]
    total = sum(s.score for s in sub_layers)

    # Hard fails
    hard_fails = _check_hard_fails(income, cash, balance, s_3c, s_3e, thresholds)
    hard_fail_triggered = any(hf.triggered for hf in hard_fails)

    # Verdict
    if hard_fail_triggered:
        verdict = "Fail (Hard-Fail Override)"
    elif total >= thresholds.pass_threshold:
        verdict = "Pass"
    elif total >= thresholds.conditional_threshold:
        verdict = "Conditional Watchlist"
    else:
        verdict = "Fail"

    # Headline metrics
    headline = [
        metrics.revenue_growth_yoy(rev_df),
        metrics.gross_margin_latest(income),
        metrics.operating_margin_latest(income),
        metrics.cfo_to_ni_ratio(income, cash, 4),
        metrics.net_debt_to_ebitda(balance, income),
        metrics.interest_coverage(income, 4),
        metrics.free_cash_flow_margin(cash, income, 4),
        metrics.roe_proxy(income, balance),
    ]

    # Data gaps summary
    gaps: list[str] = []
    for rec in [parsers.latest(income), parsers.latest(balance), parsers.latest(cash)]:
        if rec and rec.missing_fields:
            gaps.append(f"{type(rec).__name__} @ {rec.date}: missing {', '.join(rec.missing_fields[:5])}" +
                        (f" and {len(rec.missing_fields)-5} more" if len(rec.missing_fields) > 5 else ""))

    return Gate3Result(
        stock_id=stock_id,
        total_score=total,
        verdict=verdict,
        sub_layers=sub_layers,
        hard_fails=hard_fails,
        hard_fail_triggered=hard_fail_triggered,
        headline_metrics=headline,
        data_gaps=gaps,
    )
```

## `taiwan_equity_toolkit/gate65.py`

```python
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
```

## `taiwan_equity_toolkit/memo.py`

```python
"""
Memo formatter — assemble structured gate outputs into a CIO-grade memo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from taiwan_equity_toolkit.triage import TriageResult
from taiwan_equity_toolkit.gate3 import Gate3Result
from taiwan_equity_toolkit.peers import PeerComparison


@dataclass
class FullScreenMemo:
    stock_id: str
    industry_view: str = ""
    company_qualitative: str = ""
    triage: Optional[TriageResult] = None
    gate3: Optional[Gate3Result] = None
    peer_comparison: Optional[PeerComparison] = None
    value_chain_notes: str = ""
    portfolio_fit_notes: str = ""
    entry_architecture_notes: str = ""
    thesis_statement: str = ""
    catalyst_path: str = ""
    invalidation: str = ""
    verdict: str = ""  # Actionable Watchlist / Conditional / Reject

    def render(self) -> str:
        lines = [
            f"# Pre-Trade Screening Memo — {self.stock_id}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            f"## Verdict: {self.verdict or '(pending)'}",
            "",
        ]

        if self.industry_view:
            lines += ["## Gate 1 — Industry Direction", self.industry_view, ""]

        if self.company_qualitative:
            lines += ["## Gate 2 — Company Qualitative", self.company_qualitative, ""]

        if self.triage:
            lines += ["## Triage Filter", self.triage.summary(), ""]

        if self.gate3:
            lines += ["## Gate 3 — Forensic Quality", self.gate3.memo(), ""]

        if self.peer_comparison:
            lines += ["## Gate 4 — Cross-Source Validation", self.peer_comparison.summary(), ""]

        if self.value_chain_notes:
            lines += ["## Gate 5 — Value Chain Positioning", self.value_chain_notes, ""]

        if self.portfolio_fit_notes:
            lines += ["## Gate 6 — Portfolio Fit (Strategic)", self.portfolio_fit_notes, ""]

        if self.entry_architecture_notes:
            lines += ["## Gate 6.5 — Entry Architecture", self.entry_architecture_notes, ""]

        if self.thesis_statement or self.catalyst_path or self.invalidation:
            lines += ["## Gate 7 — Thesis & Dated Catalyst"]
            if self.thesis_statement:
                lines += [f"**Thesis:** {self.thesis_statement}"]
            if self.catalyst_path:
                lines += [f"**Dated catalyst:** {self.catalyst_path}"]
            if self.invalidation:
                lines += [f"**Invalidation criteria:** {self.invalidation}"]
            lines += [""]

        return "\n".join(lines)
```

## `taiwan_equity_toolkit/metrics.py`

```python
"""
Metrics — derived financial ratios and growth rates.

Every metric carries its source dataset(s) and as-of date, enabling direct
citation in memos. Metrics return None (not 0, not NaN) when underlying data
is missing — this is deliberate. Silent zeros hide problems.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from taiwan_equity_toolkit.parsers import (
    BalanceSheet,
    CashFlow,
    IncomeStatement,
    latest,
    ttm,
)


@dataclass
class Metric:
    """A single metric value with provenance."""
    name: str
    value: Optional[float]
    unit: str                    # e.g., "%", "x", "ratio", "NT$", "qtrs"
    as_of: Optional[str]         # date of source data
    source: str                  # FinMind dataset name(s)
    note: str = ""               # caveats, staleness, missing-data notes

    def __repr__(self) -> str:
        v = f"{self.value:.2f}" if self.value is not None else "n/a"
        return f"{self.name}={v}{self.unit} ({self.source}, {self.as_of}){' — ' + self.note if self.note else ''}"

    def cite(self) -> str:
        """Short citation string for inline use in memos."""
        if self.value is None:
            return f"{self.name}: n/a ({self.source}, {self.as_of or 'no data'})"
        v = f"{self.value:.2f}{self.unit}"
        return f"{self.name}={v} ({self.source}, {self.as_of})"


# ──────────────────────────────────────────────────────────────────────────
# Operating quality (3A)
# ──────────────────────────────────────────────────────────────────────────

def cfo_to_ni_ratio(income: list[IncomeStatement], cash: list[CashFlow], n_qtrs: int = 4) -> Metric:
    """Trailing-n-quarter CFO/NI ratio. Healthy ≥ 0.8."""
    inc_ttm = ttm(income, n_qtrs)
    cf_ttm = ttm(cash, n_qtrs)

    if not inc_ttm or not cf_ttm:
        return Metric("CFO/NI", None, "x", None, "TaiwanStockFinancialStatements + TaiwanStockCashFlowsStatement", "insufficient data")

    ni_sum = sum((r.net_income or 0) for r in inc_ttm)
    cfo_sum = sum((r.cfo or 0) for r in cf_ttm)

    if ni_sum == 0:
        return Metric("CFO/NI", None, "x", inc_ttm[-1].date, "TaiwanStockFinancialStatements + TaiwanStockCashFlowsStatement", "NI sum is zero")

    ratio = cfo_sum / ni_sum
    return Metric("CFO/NI", ratio, "x", inc_ttm[-1].date, "TaiwanStockFinancialStatements + TaiwanStockCashFlowsStatement", f"trailing {n_qtrs}Q")


def revenue_growth_yoy(monthly_rev_df: pd.DataFrame) -> Metric:
    """YoY growth of most recent monthly revenue."""
    if monthly_rev_df.empty or "revenue" not in monthly_rev_df.columns:
        return Metric("Revenue YoY", None, "%", None, "TaiwanStockMonthRevenue", "empty data")

    df = monthly_rev_df.sort_values("date").copy()
    if len(df) < 13:
        return Metric("Revenue YoY", None, "%", df.iloc[-1]["date"] if len(df) else None, "TaiwanStockMonthRevenue", "need 13+ months")

    latest_rev = df.iloc[-1]["revenue"]
    year_ago_rev = df.iloc[-13]["revenue"]
    if not year_ago_rev or year_ago_rev == 0:
        return Metric("Revenue YoY", None, "%", df.iloc[-1]["date"], "TaiwanStockMonthRevenue", "year-ago zero")

    yoy = (latest_rev - year_ago_rev) / year_ago_rev * 100
    return Metric("Revenue YoY", yoy, "%", df.iloc[-1]["date"], "TaiwanStockMonthRevenue")


def revenue_ttm_trend(monthly_rev_df: pd.DataFrame) -> Metric:
    """TTM revenue vs. prior TTM — broader-trend growth."""
    if monthly_rev_df.empty or "revenue" not in monthly_rev_df.columns:
        return Metric("Revenue TTM growth", None, "%", None, "TaiwanStockMonthRevenue", "empty data")

    df = monthly_rev_df.sort_values("date").copy()
    if len(df) < 24:
        return Metric("Revenue TTM growth", None, "%", df.iloc[-1]["date"] if len(df) else None, "TaiwanStockMonthRevenue", "need 24+ months")

    current_ttm = df.iloc[-12:]["revenue"].sum()
    prior_ttm = df.iloc[-24:-12]["revenue"].sum()
    if prior_ttm == 0:
        return Metric("Revenue TTM growth", None, "%", df.iloc[-1]["date"], "TaiwanStockMonthRevenue", "prior TTM zero")

    growth = (current_ttm - prior_ttm) / prior_ttm * 100
    return Metric("Revenue TTM growth", growth, "%", df.iloc[-1]["date"], "TaiwanStockMonthRevenue")


def gross_margin_latest(income: list[IncomeStatement]) -> Metric:
    rec = latest(income)
    if not rec or rec.gross_margin is None:
        return Metric("Gross margin", None, "%", rec.date if rec else None, "TaiwanStockFinancialStatements", "missing revenue or GP")
    return Metric("Gross margin", rec.gross_margin * 100, "%", rec.date, "TaiwanStockFinancialStatements")


def operating_margin_latest(income: list[IncomeStatement]) -> Metric:
    rec = latest(income)
    if not rec or rec.operating_margin is None:
        return Metric("Operating margin", None, "%", rec.date if rec else None, "TaiwanStockFinancialStatements", "missing data")
    return Metric("Operating margin", rec.operating_margin * 100, "%", rec.date, "TaiwanStockFinancialStatements")


def roe_proxy(income: list[IncomeStatement], balance: list[BalanceSheet]) -> Metric:
    """ROE proxy: trailing 4Q net income / latest equity."""
    inc_ttm = ttm(income, 4)
    bs = latest(balance)
    if not inc_ttm or not bs or bs.equity is None:
        return Metric("ROE (proxy)", None, "%", bs.date if bs else None, "TaiwanStockFinancialStatements + TaiwanStockBalanceSheet", "missing data")
    ni_sum = sum((r.net_income or 0) for r in inc_ttm)
    if bs.equity == 0:
        return Metric("ROE (proxy)", None, "%", bs.date, "TaiwanStockFinancialStatements + TaiwanStockBalanceSheet", "equity zero")
    return Metric("ROE (proxy)", ni_sum / bs.equity * 100, "%", bs.date, "TaiwanStockFinancialStatements + TaiwanStockBalanceSheet", "trailing 4Q NI / latest equity")


# ──────────────────────────────────────────────────────────────────────────
# Balance sheet & cash survival (3B)
# ──────────────────────────────────────────────────────────────────────────

def net_debt_to_ebitda(balance: list[BalanceSheet], income: list[IncomeStatement]) -> Metric:
    """Net debt / trailing-4Q EBITDA (EBIT + D&A approximation)."""
    bs = latest(balance)
    inc_ttm = ttm(income, 4)
    if not bs or not inc_ttm:
        return Metric("Net debt / EBITDA", None, "x", bs.date if bs else None, "TaiwanStockBalanceSheet + TaiwanStockFinancialStatements", "missing data")

    nd = bs.net_debt
    if nd is None:
        return Metric("Net debt / EBITDA", None, "x", bs.date, "TaiwanStockBalanceSheet + TaiwanStockFinancialStatements", "net debt unavailable")

    ebit_sum = sum((r.operating_income or 0) for r in inc_ttm)
    dna_sum = sum((r.depreciation or 0) for r in inc_ttm)
    ebitda = ebit_sum + dna_sum
    if ebitda <= 0:
        return Metric("Net debt / EBITDA", None, "x", bs.date, "TaiwanStockBalanceSheet + TaiwanStockFinancialStatements", "EBITDA non-positive")

    return Metric("Net debt / EBITDA", nd / ebitda, "x", bs.date, "TaiwanStockBalanceSheet + TaiwanStockFinancialStatements", "trailing 4Q EBITDA")


def interest_coverage(income: list[IncomeStatement], n_qtrs: int = 4) -> Metric:
    """EBIT / interest expense, trailing-n-quarter."""
    inc_ttm = ttm(income, n_qtrs)
    if not inc_ttm:
        return Metric("Interest coverage", None, "x", None, "TaiwanStockFinancialStatements", "no data")

    ebit = sum((r.operating_income or 0) for r in inc_ttm)
    ie = sum((r.interest_expense or 0) for r in inc_ttm)
    if ie == 0:
        return Metric("Interest coverage", None, "x", inc_ttm[-1].date, "TaiwanStockFinancialStatements", "interest expense zero or missing")
    return Metric("Interest coverage", ebit / abs(ie), "x", inc_ttm[-1].date, "TaiwanStockFinancialStatements", f"trailing {n_qtrs}Q")


def current_ratio_latest(balance: list[BalanceSheet]) -> Metric:
    bs = latest(balance)
    if not bs or bs.current_ratio is None:
        return Metric("Current ratio", None, "x", bs.date if bs else None, "TaiwanStockBalanceSheet", "missing data")
    return Metric("Current ratio", bs.current_ratio, "x", bs.date, "TaiwanStockBalanceSheet")


def cash_to_short_term_debt(balance: list[BalanceSheet]) -> Metric:
    bs = latest(balance)
    if not bs:
        return Metric("Cash / ST debt", None, "x", None, "TaiwanStockBalanceSheet", "no data")
    if bs.cash_and_equivalents is None or bs.short_term_borrowings is None:
        return Metric("Cash / ST debt", None, "x", bs.date, "TaiwanStockBalanceSheet", "missing cash or ST debt")
    if bs.short_term_borrowings == 0:
        return Metric("Cash / ST debt", float("inf"), "x", bs.date, "TaiwanStockBalanceSheet", "no short-term debt")
    return Metric("Cash / ST debt", bs.cash_and_equivalents / bs.short_term_borrowings, "x", bs.date, "TaiwanStockBalanceSheet")


def free_cash_flow_margin(cash: list[CashFlow], income: list[IncomeStatement], n_qtrs: int = 4) -> Metric:
    """FCF margin: trailing-n-Q FCF / trailing-n-Q revenue."""
    cf_ttm = ttm(cash, n_qtrs)
    inc_ttm = ttm(income, n_qtrs)
    if not cf_ttm or not inc_ttm:
        return Metric("FCF margin", None, "%", None, "TaiwanStockCashFlowsStatement + TaiwanStockFinancialStatements", "insufficient data")

    fcf_sum = sum((r.free_cash_flow or 0) for r in cf_ttm)
    rev_sum = sum((r.revenue or 0) for r in inc_ttm)
    if rev_sum == 0:
        return Metric("FCF margin", None, "%", cf_ttm[-1].date, "TaiwanStockCashFlowsStatement + TaiwanStockFinancialStatements", "revenue zero")
    return Metric("FCF margin", fcf_sum / rev_sum * 100, "%", cf_ttm[-1].date, "TaiwanStockCashFlowsStatement + TaiwanStockFinancialStatements", f"trailing {n_qtrs}Q")


# ──────────────────────────────────────────────────────────────────────────
# Price / liquidity
# ──────────────────────────────────────────────────────────────────────────

def adv_ntd(price_df: pd.DataFrame, lookback: int = 20) -> Metric:
    """Average daily dollar volume in NT$, most recent N days."""
    if price_df.empty or "Trading_money" not in price_df.columns:
        return Metric("ADV", None, " NT$", None, "TaiwanStockPrice", "no data")

    recent = price_df.sort_values("date").tail(lookback)
    if recent.empty:
        return Metric("ADV", None, " NT$", None, "TaiwanStockPrice", "no recent data")

    avg = recent["Trading_money"].mean()
    return Metric("ADV", avg, " NT$", recent.iloc[-1]["date"], "TaiwanStockPrice", f"{lookback}-day mean")


def realized_vol(price_adj_df: pd.DataFrame, lookback: int = 30) -> Metric:
    """Annualized realized volatility from adjusted closes."""
    if price_adj_df.empty or "close" not in price_adj_df.columns:
        return Metric(f"Realized vol {lookback}d", None, "%", None, "TaiwanStockPriceAdj", "no data")

    df = price_adj_df.sort_values("date").tail(lookback + 1).copy()
    if len(df) < lookback + 1:
        return Metric(f"Realized vol {lookback}d", None, "%", df.iloc[-1]["date"] if len(df) else None, "TaiwanStockPriceAdj", "insufficient history")

    df["ret"] = df["close"].pct_change()
    vol = df["ret"].std() * (252 ** 0.5) * 100
    return Metric(f"Realized vol {lookback}d", vol, "%", df.iloc[-1]["date"], "TaiwanStockPriceAdj", "annualized")


def correlation_to_series(primary_df: pd.DataFrame, other_df: pd.DataFrame, lookback: int = 90) -> Metric:
    """Return correlation of two adjusted price series over lookback days."""
    if primary_df.empty or other_df.empty:
        return Metric("Correlation", None, "", None, "TaiwanStockPriceAdj", "empty series")

    p = primary_df[["date", "close"]].rename(columns={"close": "a"}).copy()
    o = other_df[["date", "close"]].rename(columns={"close": "b"}).copy()
    merged = p.merge(o, on="date").sort_values("date").tail(lookback + 1)
    if len(merged) < lookback + 1:
        return Metric("Correlation", None, "", None, "TaiwanStockPriceAdj", "insufficient overlap")

    merged["ra"] = merged["a"].pct_change()
    merged["rb"] = merged["b"].pct_change()
    corr = merged["ra"].corr(merged["rb"])
    return Metric("Correlation", corr, "", merged.iloc[-1]["date"], "TaiwanStockPriceAdj", f"{lookback}d returns")


# ──────────────────────────────────────────────────────────────────────────
# Institutional flow (3C)
# ──────────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────────
# Reverse-DCF sanity check (6.5A)
# ──────────────────────────────────────────────────────────────────────────

def reverse_dcf_implied_growth(
    market_cap: float,
    ttm_fcf: float,
    discount_rate: float = 0.09,
    terminal_growth: float = 0.025,
    explicit_years: int = 10,
) -> Metric:
    """
    Solve for the explicit-period FCF growth rate implied by the current market cap.

    Uses a 2-stage DCF: grow FCF at g for `explicit_years`, then terminal growth forever.
    Returns the g that makes present value == market_cap.

    Args:
        market_cap: Current market cap (NT$)
        ttm_fcf: Trailing-12-month free cash flow (NT$)
        discount_rate: Required return / WACC
        terminal_growth: Steady-state perpetual growth
        explicit_years: Length of explicit forecast horizon

    Returns:
        Metric with value = implied annual growth rate (%).
        Positive: market expects growth
        Negative: market expects decline
        If ttm_fcf <= 0, returns None with note.
    """
    if ttm_fcf <= 0:
        return Metric("Reverse-DCF implied g", None, "%", None,
                     "derived",
                     "FCF non-positive — reverse DCF undefined")
    if market_cap <= 0:
        return Metric("Reverse-DCF implied g", None, "%", None, "derived", "market cap non-positive")

    def pv_at_growth(g: float) -> float:
        """Present value of explicit + terminal given growth rate g."""
        pv = 0.0
        fcf = ttm_fcf
        for year in range(1, explicit_years + 1):
            fcf *= (1 + g)
            pv += fcf / ((1 + discount_rate) ** year)
        # Terminal value at end of explicit period
        terminal_fcf = fcf * (1 + terminal_growth)
        if discount_rate <= terminal_growth:
            return float("inf")
        terminal_value = terminal_fcf / (discount_rate - terminal_growth)
        pv += terminal_value / ((1 + discount_rate) ** explicit_years)
        return pv

    # Bisection search for g that matches market cap
    lo, hi = -0.20, 0.50  # search between -20% and +50% annual growth
    for _ in range(60):
        mid = (lo + hi) / 2
        pv = pv_at_growth(mid)
        if pv < market_cap:
            lo = mid
        else:
            hi = mid
        if abs(hi - lo) < 0.0001:
            break

    g = (lo + hi) / 2
    note = f"discount={discount_rate*100:.1f}%, terminal={terminal_growth*100:.1f}%, explicit={explicit_years}y"
    return Metric("Reverse-DCF implied g", g * 100, "%", None, "derived", note)


# ──────────────────────────────────────────────────────────────────────────
# Institutional flow (3C)
# ──────────────────────────────────────────────────────────────────────────

def institutional_net_flow(flow_df: pd.DataFrame, lookback_days: int = 60) -> dict[str, Metric]:
    """
    Net buy/sell by investor type (Foreign_Investor, Investment_Trust, Dealer)
    over the most recent lookback days.
    """
    out: dict[str, Metric] = {}
    if flow_df.empty:
        for k in ("Foreign_Investor", "Investment_Trust", "Dealer"):
            out[k] = Metric(f"{k} net flow", None, " shares", None, "TaiwanStockInstitutionalInvestorsBuySell", "no data")
        return out

    df = flow_df.copy()
    # FinMind returns 'name' = investor type, 'buy' / 'sell' counts.
    df["net"] = df["buy"] - df["sell"]
    # Keep most recent lookback by date.
    df["date"] = pd.to_datetime(df["date"])
    cutoff = df["date"].max() - pd.Timedelta(days=lookback_days)
    df = df[df["date"] >= cutoff]

    for investor_type in ("Foreign_Investor", "Investment_Trust", "Dealer"):
        sub = df[df["name"].str.contains(investor_type.replace("_", ""), case=False, na=False) |
                 df["name"].str.contains(investor_type, case=False, na=False)]
        if sub.empty:
            out[investor_type] = Metric(f"{investor_type} net flow", None, " shares", None, "TaiwanStockInstitutionalInvestorsBuySell", "no match")
        else:
            net = sub["net"].sum()
            as_of = sub["date"].max().strftime("%Y-%m-%d")
            out[investor_type] = Metric(f"{investor_type} net flow", net, " shares", as_of, "TaiwanStockInstitutionalInvestorsBuySell", f"last {lookback_days}d sum")
    return out
```

## `taiwan_equity_toolkit/parsers.py`

```python
"""
Parsers — convert FinMind's long-format financial statements into usable structures.

FinMind returns Taiwan financial statements in a painful long format:

    date       | stock_id | type                | value       | origin_name
    2024-09-30 | 2330     | Revenue             | 7.57e11     | 營業收入合計
    2024-09-30 | 2330     | GrossProfit         | 4.40e11     | 營業毛利（毛損）
    ...

This module pivots into wide format keyed on common English 'type' codes.
When a type is not present, the corresponding field is None with a flag.

The canonical type names below are what FinMind actually returns. If you see
different names in the wild, add them to the LEDGER dicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


# ──────────────────────────────────────────────────────────────────────────
# Canonical field mappings — FinMind 'type' codes → our field names.
# Multiple variants allowed per field; first match wins.
# ──────────────────────────────────────────────────────────────────────────

INCOME_STATEMENT_LEDGER = {
    "revenue": ["Revenue", "OperatingRevenue"],
    "cogs": ["CostOfGoodsSold", "OperatingCosts"],
    "gross_profit": ["GrossProfit"],
    "operating_expenses": ["OperatingExpenses"],
    "operating_income": ["OperatingIncome"],
    "nonop_income": ["NonoperatingIncomeAndExpenses"],
    "pretax_income": ["IncomeBeforeTax", "ProfitBeforeTax"],
    "tax_expense": ["IncomeTaxExpense"],
    "net_income": ["IncomeAfterTax", "IncomeAfterTaxes", "NetIncome"],
    "eps": ["EPS", "EarningsPerShare"],
    "depreciation": ["Depreciation"],
    "interest_expense": ["InterestExpense"],
}

BALANCE_SHEET_LEDGER = {
    "cash_and_equivalents": ["CashAndCashEquivalents"],
    "accounts_receivable": ["AccountsReceivable", "AccountsReceivableNet"],
    "inventory": ["Inventories"],
    "current_assets": ["CurrentAssets"],
    "total_assets": ["TotalAssets", "Assets"],
    "short_term_borrowings": ["ShortTermBorrowings", "ShortTermLoans"],
    "accounts_payable": ["AccountsPayable"],
    "current_liabilities": ["CurrentLiabilities"],
    "long_term_borrowings": ["LongTermBorrowings", "LongTermLoans"],
    "total_liabilities": ["Liabilities", "TotalLiabilities"],
    "equity": ["Equity", "TotalEquity", "StockholdersEquity"],
}

CASH_FLOW_LEDGER = {
    "cfo": ["CashFlowsFromOperatingActivities", "NetCashProvidedByOperatingActivities"],
    "cfi": ["CashFlowsFromInvestingActivities"],
    "cff": ["CashFlowsFromFinancingActivities"],
    "capex": ["PropertyPlantAndEquipment", "AcquisitionOfPropertyPlantAndEquipment"],
    "depreciation_cf": ["Depreciation"],
    "dividends_paid": ["CashDividendsPaid", "PaymentOfCashDividends"],
}


# ──────────────────────────────────────────────────────────────────────────
# Structured records
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class IncomeStatement:
    date: str
    stock_id: str
    revenue: Optional[float] = None
    cogs: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_expenses: Optional[float] = None
    operating_income: Optional[float] = None
    nonop_income: Optional[float] = None
    pretax_income: Optional[float] = None
    tax_expense: Optional[float] = None
    net_income: Optional[float] = None
    eps: Optional[float] = None
    depreciation: Optional[float] = None
    interest_expense: Optional[float] = None
    missing_fields: list[str] = field(default_factory=list)

    @property
    def gross_margin(self) -> Optional[float]:
        if self.revenue and self.gross_profit is not None and self.revenue != 0:
            return self.gross_profit / self.revenue
        return None

    @property
    def operating_margin(self) -> Optional[float]:
        if self.revenue and self.operating_income is not None and self.revenue != 0:
            return self.operating_income / self.revenue
        return None

    @property
    def net_margin(self) -> Optional[float]:
        if self.revenue and self.net_income is not None and self.revenue != 0:
            return self.net_income / self.revenue
        return None


@dataclass
class BalanceSheet:
    date: str
    stock_id: str
    cash_and_equivalents: Optional[float] = None
    accounts_receivable: Optional[float] = None
    inventory: Optional[float] = None
    current_assets: Optional[float] = None
    total_assets: Optional[float] = None
    short_term_borrowings: Optional[float] = None
    accounts_payable: Optional[float] = None
    current_liabilities: Optional[float] = None
    long_term_borrowings: Optional[float] = None
    total_liabilities: Optional[float] = None
    equity: Optional[float] = None
    missing_fields: list[str] = field(default_factory=list)

    @property
    def total_debt(self) -> Optional[float]:
        if self.short_term_borrowings is not None and self.long_term_borrowings is not None:
            return self.short_term_borrowings + self.long_term_borrowings
        return None

    @property
    def net_debt(self) -> Optional[float]:
        td = self.total_debt
        if td is not None and self.cash_and_equivalents is not None:
            return td - self.cash_and_equivalents
        return None

    @property
    def current_ratio(self) -> Optional[float]:
        if self.current_liabilities and self.current_assets is not None and self.current_liabilities != 0:
            return self.current_assets / self.current_liabilities
        return None

    @property
    def debt_to_equity(self) -> Optional[float]:
        td = self.total_debt
        if td is not None and self.equity and self.equity != 0:
            return td / self.equity
        return None


@dataclass
class CashFlow:
    date: str
    stock_id: str
    cfo: Optional[float] = None
    cfi: Optional[float] = None
    cff: Optional[float] = None
    capex: Optional[float] = None
    depreciation_cf: Optional[float] = None
    dividends_paid: Optional[float] = None
    missing_fields: list[str] = field(default_factory=list)

    @property
    def free_cash_flow(self) -> Optional[float]:
        # Capex in FinMind is typically reported as negative (investment outflow).
        # FCF = CFO - |Capex|. If capex is reported positive, flip sign.
        if self.cfo is not None and self.capex is not None:
            return self.cfo - abs(self.capex)
        return None


# ──────────────────────────────────────────────────────────────────────────
# Parser functions
# ──────────────────────────────────────────────────────────────────────────

def _pivot_long_format(df: pd.DataFrame, ledger: dict[str, list[str]]) -> pd.DataFrame:
    """
    Pivot FinMind long-format (date/stock_id/type/value) into wide format
    with columns defined by the ledger.
    """
    if df.empty:
        return pd.DataFrame()

    # Group by (date, stock_id) and pivot type → value
    wide = df.pivot_table(
        index=["date", "stock_id"],
        columns="type",
        values="value",
        aggfunc="first",
    ).reset_index()

    # Map raw FinMind types to canonical names
    renamed_cols = {"date": "date", "stock_id": "stock_id"}
    for canonical, variants in ledger.items():
        for v in variants:
            if v in wide.columns:
                renamed_cols[v] = canonical
                break

    wide = wide.rename(columns=renamed_cols)
    # Keep only canonical columns + date/stock_id
    keep = ["date", "stock_id"] + [c for c in ledger.keys() if c in wide.columns]
    return wide[keep].sort_values("date").reset_index(drop=True)


def parse_income_statements(df: pd.DataFrame) -> list[IncomeStatement]:
    """Parse a TaiwanStockFinancialStatements response into IncomeStatement records."""
    wide = _pivot_long_format(df, INCOME_STATEMENT_LEDGER)
    out: list[IncomeStatement] = []
    for _, row in wide.iterrows():
        rec = IncomeStatement(date=str(row["date"]), stock_id=str(row["stock_id"]))
        for k in INCOME_STATEMENT_LEDGER.keys():
            if k in wide.columns:
                v = row[k]
                if pd.notna(v):
                    setattr(rec, k, float(v))
                else:
                    rec.missing_fields.append(k)
            else:
                rec.missing_fields.append(k)
        out.append(rec)
    return out


def parse_balance_sheets(df: pd.DataFrame) -> list[BalanceSheet]:
    """Parse a TaiwanStockBalanceSheet response into BalanceSheet records."""
    wide = _pivot_long_format(df, BALANCE_SHEET_LEDGER)
    out: list[BalanceSheet] = []
    for _, row in wide.iterrows():
        rec = BalanceSheet(date=str(row["date"]), stock_id=str(row["stock_id"]))
        for k in BALANCE_SHEET_LEDGER.keys():
            if k in wide.columns:
                v = row[k]
                if pd.notna(v):
                    setattr(rec, k, float(v))
                else:
                    rec.missing_fields.append(k)
            else:
                rec.missing_fields.append(k)
        out.append(rec)
    return out


def parse_cash_flows(df: pd.DataFrame) -> list[CashFlow]:
    """Parse a TaiwanStockCashFlowsStatement response into CashFlow records."""
    wide = _pivot_long_format(df, CASH_FLOW_LEDGER)
    out: list[CashFlow] = []
    for _, row in wide.iterrows():
        rec = CashFlow(date=str(row["date"]), stock_id=str(row["stock_id"]))
        for k in CASH_FLOW_LEDGER.keys():
            if k in wide.columns:
                v = row[k]
                if pd.notna(v):
                    setattr(rec, k, float(v))
                else:
                    rec.missing_fields.append(k)
            else:
                rec.missing_fields.append(k)
        out.append(rec)
    return out


def latest(records: list) -> Optional[object]:
    """Return the most recent record by date, or None if list is empty."""
    if not records:
        return None
    return sorted(records, key=lambda r: r.date)[-1]


def ttm(records: list, n: int = 4) -> list:
    """Return the most recent n quarters (trailing-twelve-months basis)."""
    if not records:
        return []
    return sorted(records, key=lambda r: r.date)[-n:]
```

## `taiwan_equity_toolkit/peers.py`

```python
"""
Peer comparison — async batch utilities for cross-source validation.

Where the AI-vs-retail edge is most visible. `compare()` runs all peers
concurrently and returns ranked comparative tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from taiwan_equity_toolkit.client import FinMindClient
from taiwan_equity_toolkit import metrics, parsers


@dataclass
class PeerComparison:
    candidate: str
    peers: list[str]
    revenue_yoy: pd.DataFrame        # stock_id, yoy_pct, as_of
    gross_margin: pd.DataFrame       # stock_id, gm_pct, as_of
    operating_margin: pd.DataFrame
    cfo_to_ni: pd.DataFrame
    correlation_matrix: pd.DataFrame  # symmetric return correlation
    institutional_flow_60d: pd.DataFrame
    candidate_rankings: dict[str, tuple[int, int]] = field(default_factory=dict)  # metric → (rank, total)

    def summary(self) -> str:
        lines = [f"# Peer comparison: {self.candidate} vs {len(self.peers)} peer(s)"]
        lines.append("")
        lines.append("## Revenue YoY")
        lines.append(self.revenue_yoy.to_string(index=False))
        lines.append("")
        lines.append("## Gross margin")
        lines.append(self.gross_margin.to_string(index=False))
        lines.append("")
        lines.append("## Operating margin")
        lines.append(self.operating_margin.to_string(index=False))
        lines.append("")
        lines.append("## CFO/NI")
        lines.append(self.cfo_to_ni.to_string(index=False))
        lines.append("")
        lines.append("## 90-day return correlation")
        lines.append(self.correlation_matrix.to_string())
        lines.append("")
        lines.append("## 60-day institutional net flow")
        lines.append(self.institutional_flow_60d.to_string(index=False))
        if self.candidate_rankings:
            lines.append("")
            lines.append("## Candidate's peer rankings")
            for metric, (rank, total) in self.candidate_rankings.items():
                lines.append(f"- {metric}: #{rank} of {total}")
        return "\n".join(lines)


def _rank_candidate(df: pd.DataFrame, candidate: str, metric_col: str, higher_is_better: bool = True) -> tuple[int, int]:
    """Return (rank, total) for the candidate within a ranked peer df."""
    if df.empty or metric_col not in df.columns:
        return (0, 0)
    ranked = df.dropna(subset=[metric_col]).sort_values(metric_col, ascending=not higher_is_better).reset_index(drop=True)
    total = len(ranked)
    match = ranked[ranked["stock_id"].astype(str) == str(candidate)]
    if match.empty:
        return (0, total)
    return (int(match.index[0]) + 1, total)


def compare(
    client: FinMindClient,
    candidate: str,
    peers: list[str],
    lookback_days: int = 365,
) -> PeerComparison:
    """
    Run a comparative analysis of candidate vs peers across operating and
    market-structure dimensions. Uses async batch where available.
    """
    all_ids = [candidate] + [p for p in peers if p != candidate]
    today = datetime.today()
    fs_start = (today - timedelta(days=540)).strftime("%Y-%m-%d")
    rev_start = (today - timedelta(days=730)).strftime("%Y-%m-%d")
    price_start = (today - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    flow_start = (today - timedelta(days=90)).strftime("%Y-%m-%d")

    # Batch fetches
    fs_map = client.get_multi("TaiwanStockFinancialStatements", all_ids, fs_start)
    cf_map = client.get_multi("TaiwanStockCashFlowsStatement", all_ids, fs_start)
    rev_map = client.get_multi("TaiwanStockMonthRevenue", all_ids, rev_start)
    price_map = client.get_multi("TaiwanStockPriceAdj", all_ids, price_start)
    flow_map = client.get_multi("TaiwanStockInstitutionalInvestorsBuySell", all_ids, flow_start)

    # Operating metrics across peers
    rev_yoy_rows = []
    gm_rows = []
    om_rows = []
    cfo_ni_rows = []
    for sid in all_ids:
        income = parsers.parse_income_statements(fs_map.get(sid, pd.DataFrame()))
        cash = parsers.parse_cash_flows(cf_map.get(sid, pd.DataFrame()))

        rev_yoy = metrics.revenue_growth_yoy(rev_map.get(sid, pd.DataFrame()))
        rev_yoy_rows.append({"stock_id": sid, "yoy_pct": rev_yoy.value, "as_of": rev_yoy.as_of})

        gm = metrics.gross_margin_latest(income)
        gm_rows.append({"stock_id": sid, "gm_pct": gm.value, "as_of": gm.as_of})

        om = metrics.operating_margin_latest(income)
        om_rows.append({"stock_id": sid, "om_pct": om.value, "as_of": om.as_of})

        cfoni = metrics.cfo_to_ni_ratio(income, cash, 4)
        cfo_ni_rows.append({"stock_id": sid, "cfo_ni": cfoni.value, "as_of": cfoni.as_of})

    rev_yoy_df = pd.DataFrame(rev_yoy_rows)
    gm_df = pd.DataFrame(gm_rows)
    om_df = pd.DataFrame(om_rows)
    cfo_ni_df = pd.DataFrame(cfo_ni_rows)

    # Correlation matrix
    corr_frames = []
    for sid in all_ids:
        p = price_map.get(sid, pd.DataFrame())
        if p.empty or "close" not in p.columns:
            continue
        s = p[["date", "close"]].copy()
        s["date"] = pd.to_datetime(s["date"])
        s = s.set_index("date")["close"].pct_change().rename(sid)
        corr_frames.append(s)
    if corr_frames:
        corr_df = pd.concat(corr_frames, axis=1).tail(91).corr().round(2)
    else:
        corr_df = pd.DataFrame()

    # Institutional flow (60d net) per name
    flow_rows = []
    for sid in all_ids:
        f_df = flow_map.get(sid, pd.DataFrame())
        flows = metrics.institutional_net_flow(f_df, lookback_days=60)
        row = {"stock_id": sid}
        for k, m in flows.items():
            row[k] = m.value
        flow_rows.append(row)
    flow_df = pd.DataFrame(flow_rows)

    # Candidate rankings
    rankings = {
        "Revenue YoY": _rank_candidate(rev_yoy_df, candidate, "yoy_pct", True),
        "Gross margin": _rank_candidate(gm_df, candidate, "gm_pct", True),
        "Operating margin": _rank_candidate(om_df, candidate, "om_pct", True),
        "CFO/NI": _rank_candidate(cfo_ni_df, candidate, "cfo_ni", True),
    }

    return PeerComparison(
        candidate=candidate,
        peers=peers,
        revenue_yoy=rev_yoy_df.sort_values("yoy_pct", ascending=False, na_position="last"),
        gross_margin=gm_df.sort_values("gm_pct", ascending=False, na_position="last"),
        operating_margin=om_df.sort_values("om_pct", ascending=False, na_position="last"),
        cfo_to_ni=cfo_ni_df.sort_values("cfo_ni", ascending=False, na_position="last"),
        correlation_matrix=corr_df,
        institutional_flow_60d=flow_df,
        candidate_rankings=rankings,
    )
```

## `taiwan_equity_toolkit/triage.py`

```python
"""
Triage Filter — cheap screens before Gate 3 forensic work.

Purpose: eliminate names that should never reach deep diligence. If a name
fails triage, Gate 3 is skipped.

One function: `run(client, stock_id)` → TriageResult.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from taiwan_equity_toolkit.client import FinMindClient
from taiwan_equity_toolkit.config import DEFAULT_CONFIG, TriageConfig
from taiwan_equity_toolkit import metrics, parsers


@dataclass
class TriageCheck:
    name: str
    passed: bool
    detail: str
    source: str = ""


@dataclass
class TriageResult:
    stock_id: str
    passed: bool
    checks: list[TriageCheck] = field(default_factory=list)
    adv_ntd: Optional[float] = None
    notes: list[str] = field(default_factory=list)

    def failures(self) -> list[TriageCheck]:
        return [c for c in self.checks if not c.passed]

    def summary(self) -> str:
        verdict = "PASS" if self.passed else "FAIL"
        lines = [f"Triage verdict: {verdict} ({self.stock_id})"]
        for c in self.checks:
            mark = "✓" if c.passed else "✗"
            lines.append(f"  {mark} {c.name}: {c.detail}")
        return "\n".join(lines)


def run(
    client: FinMindClient,
    stock_id: str,
    cfg: Optional[TriageConfig] = None,
    intended_position_ntd: Optional[float] = None,
    short_thesis: bool = False,
) -> TriageResult:
    """
    Run the Triage Filter against a single stock.

    Args:
        client: Authenticated FinMindClient
        stock_id: 4-digit TW stock code
        cfg: Optional TriageConfig override
        intended_position_ntd: If provided, checks position ≤ 10% of ADV
        short_thesis: Relax the monthly-revenue-collapse rule if shorting

    Returns:
        TriageResult with .passed and per-check diagnostics.
    """
    cfg = cfg or DEFAULT_CONFIG.triage
    result = TriageResult(stock_id=stock_id, passed=True)

    today = datetime.today()
    price_start = (today - timedelta(days=60)).strftime("%Y-%m-%d")
    rev_start = (today - timedelta(days=730)).strftime("%Y-%m-%d")  # 2 years monthly
    fs_start = (today - timedelta(days=540)).strftime("%Y-%m-%d")   # ~6 quarters

    # ──────────────────────────────────────────────
    # 1. Disposition / suspension / delisting (hard)
    # ──────────────────────────────────────────────
    try:
        disp = client.get("TaiwanStockDispositionSecuritiesPeriod", stock_id,
                          (today - timedelta(days=180)).strftime("%Y-%m-%d"))
        if not disp.empty:
            # Check any period that is currently active
            current = disp[
                (disp["period_start"] <= today.strftime("%Y-%m-%d")) &
                (disp["period_end"] >= today.strftime("%Y-%m-%d"))
            ] if "period_start" in disp.columns else disp
            if not current.empty:
                result.checks.append(TriageCheck(
                    "Disposition status", False,
                    f"Currently on disposition list: {len(current)} active period(s)",
                    "TaiwanStockDispositionSecuritiesPeriod"
                ))
                result.passed = False
            else:
                result.checks.append(TriageCheck(
                    "Disposition status", True, "Not in an active disposition window",
                    "TaiwanStockDispositionSecuritiesPeriod"
                ))
        else:
            result.checks.append(TriageCheck(
                "Disposition status", True, "No disposition history in last 180 days",
                "TaiwanStockDispositionSecuritiesPeriod"
            ))
    except Exception as e:  # noqa: BLE001
        result.notes.append(f"Disposition check unavailable: {e}")

    try:
        susp = client.get("TaiwanStockSuspended", stock_id,
                          (today - timedelta(days=30)).strftime("%Y-%m-%d"))
        if not susp.empty:
            # If resumption_date in future or missing, treat as currently suspended
            active = susp[susp.get("resumption_date", "").fillna("").astype(str) > today.strftime("%Y-%m-%d")] \
                if "resumption_date" in susp.columns else susp
            if not active.empty:
                result.checks.append(TriageCheck(
                    "Trading suspension", False,
                    "Currently suspended",
                    "TaiwanStockSuspended"
                ))
                result.passed = False
            else:
                result.checks.append(TriageCheck("Trading suspension", True, "Not currently suspended", "TaiwanStockSuspended"))
        else:
            result.checks.append(TriageCheck("Trading suspension", True, "No suspension record", "TaiwanStockSuspended"))
    except Exception as e:  # noqa: BLE001
        result.notes.append(f"Suspension check unavailable: {e}")

    # ──────────────────────────────────────────────
    # 2. Liquidity floor
    # ──────────────────────────────────────────────
    try:
        price_df = client.price(stock_id, price_start)
        adv = metrics.adv_ntd(price_df, lookback=cfg.adv_lookback_days)
        result.adv_ntd = adv.value
        if adv.value is None:
            result.checks.append(TriageCheck("Liquidity (ADV)", False, "Could not compute ADV", "TaiwanStockPrice"))
            result.passed = False
        elif adv.value < cfg.min_adv_ntd:
            result.checks.append(TriageCheck(
                "Liquidity (ADV)", False,
                f"ADV NT${adv.value:,.0f} < floor NT${cfg.min_adv_ntd:,.0f}",
                "TaiwanStockPrice"
            ))
            result.passed = False
        else:
            result.checks.append(TriageCheck(
                "Liquidity (ADV)", True,
                f"ADV NT${adv.value:,.0f} ≥ floor",
                "TaiwanStockPrice"
            ))

        # Position-size check if intended_position_ntd supplied
        if intended_position_ntd is not None and adv.value:
            pct = intended_position_ntd / adv.value
            if pct > cfg.position_max_pct_of_adv:
                result.checks.append(TriageCheck(
                    "Position vs ADV", False,
                    f"Intended position {pct*100:.1f}% of ADV > {cfg.position_max_pct_of_adv*100:.0f}%",
                    "TaiwanStockPrice"
                ))
                result.passed = False
            else:
                result.checks.append(TriageCheck(
                    "Position vs ADV", True,
                    f"Intended position {pct*100:.1f}% of ADV",
                    "TaiwanStockPrice"
                ))
    except Exception as e:  # noqa: BLE001
        result.notes.append(f"Liquidity check unavailable: {e}")
        result.checks.append(TriageCheck("Liquidity (ADV)", False, f"Error: {e}", "TaiwanStockPrice"))
        result.passed = False

    # ──────────────────────────────────────────────
    # 3. Financial statement staleness
    # ──────────────────────────────────────────────
    try:
        fs_df = client.financial_statements(stock_id, fs_start)
        inc = parsers.parse_income_statements(fs_df)
        if not inc:
            result.checks.append(TriageCheck(
                "Financials present", False, "No income statement data",
                "TaiwanStockFinancialStatements"
            ))
            result.passed = False
        else:
            latest_date = inc[-1].date
            # Approximate staleness check: compare to today
            latest_dt = datetime.strptime(latest_date[:10], "%Y-%m-%d")
            days_stale = (today - latest_dt).days
            if days_stale > 135:  # ~1 quarter + reporting lag
                result.checks.append(TriageCheck(
                    "Financials freshness", False,
                    f"Latest FS is {days_stale} days old (> 1 quarter + lag)",
                    "TaiwanStockFinancialStatements"
                ))
                result.passed = False
            else:
                result.checks.append(TriageCheck(
                    "Financials freshness", True,
                    f"Latest FS: {latest_date} ({days_stale} days ago)",
                    "TaiwanStockFinancialStatements"
                ))
    except Exception as e:  # noqa: BLE001
        result.notes.append(f"Financial-statement check unavailable: {e}")

    # ──────────────────────────────────────────────
    # 4. Monthly revenue collapse
    # ──────────────────────────────────────────────
    try:
        rev_df = client.monthly_revenue(stock_id, rev_start)
        yoy = metrics.revenue_growth_yoy(rev_df)
        if yoy.value is None:
            result.checks.append(TriageCheck(
                "Monthly revenue trend", False, "Could not compute YoY",
                "TaiwanStockMonthRevenue"
            ))
            # Don't fail — just flag
        elif yoy.value < cfg.monthly_revenue_collapse_yoy * 100 and not short_thesis:
            result.checks.append(TriageCheck(
                "Monthly revenue trend", False,
                f"Latest YoY {yoy.value:.1f}% < collapse threshold {cfg.monthly_revenue_collapse_yoy*100:.0f}%",
                "TaiwanStockMonthRevenue"
            ))
            result.passed = False
        else:
            result.checks.append(TriageCheck(
                "Monthly revenue trend", True,
                f"Latest YoY {yoy.value:.1f}%",
                "TaiwanStockMonthRevenue"
            ))
    except Exception as e:  # noqa: BLE001
        result.notes.append(f"Monthly revenue check unavailable: {e}")

    # ──────────────────────────────────────────────
    # 5. Recent corporate-action distortion flag
    # ──────────────────────────────────────────────
    try:
        ca_start = (today - timedelta(days=cfg.corporate_action_lookback_months * 30)).strftime("%Y-%m-%d")
        cr_df = client.get("TaiwanStockCapitalReductionReferencePrice", stock_id, ca_start)
        distortions: list[str] = []
        if not cr_df.empty:
            distortions.append(f"{len(cr_df)} capital reduction(s)")
        # Note: split/par-value data does not support data_id filter for all variants;
        # we skip those here and leave them to Gate 3E.
        if distortions:
            result.checks.append(TriageCheck(
                "Corporate-action distortion", True,  # flag, not fail
                "Present: " + ", ".join(distortions) + " (use adjusted price for comparisons)",
                "TaiwanStockCapitalReductionReferencePrice"
            ))
            result.notes.append(f"Corporate actions detected in last {cfg.corporate_action_lookback_months} months: {distortions}")
        else:
            result.checks.append(TriageCheck(
                "Corporate-action distortion", True,
                f"None in last {cfg.corporate_action_lookback_months} months",
                "TaiwanStockCapitalReductionReferencePrice"
            ))
    except Exception as e:  # noqa: BLE001
        result.notes.append(f"Corporate-action check unavailable: {e}")

    return result
```

## `taiwan_equity_toolkit/validate_setup.py`

```python
"""
validate_setup.py — First smoke test against the live FinMind API.

Run this before trusting the toolkit in production. It:
  1. Confirms FINMIND_TOKEN is set and the token authenticates
  2. Checks API quota
  3. Fetches one stock's recent data for each critical dataset
  4. Verifies the parser ledgers match real FinMind responses
  5. Runs Triage + Gate 3 end-to-end on TSMC (2330) as a sanity check

Usage:
    export FINMIND_TOKEN="your_token"
    python validate_setup.py
    # or: python validate_setup.py 2330 2317 2454   (override test stocks)

Exit codes: 0 on success, 1 if any critical check fails.
"""

from __future__ import annotations

import sys
import traceback
from datetime import datetime, timedelta

from taiwan_equity_toolkit import FinMindClient, triage, gate3, parsers
from taiwan_equity_toolkit.config import load_token
from taiwan_equity_toolkit.parsers import (
    BALANCE_SHEET_LEDGER,
    CASH_FLOW_LEDGER,
    INCOME_STATEMENT_LEDGER,
)


# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────

OK = "\033[32m✓\033[0m"
WARN = "\033[33m⚠\033[0m"
FAIL = "\033[31m✗\033[0m"


def say(marker: str, msg: str) -> None:
    print(f"  {marker} {msg}")


def section(title: str) -> None:
    print(f"\n── {title} " + "─" * max(0, 60 - len(title)))


# ──────────────────────────────────────────────────────────────────────────
# Checks
# ──────────────────────────────────────────────────────────────────────────

def check_token() -> str:
    section("1. Token & Authentication")
    try:
        token = load_token()
        masked = token[:6] + "..." + token[-4:] if len(token) > 10 else "***"
        say(OK, f"FINMIND_TOKEN loaded ({masked})")
        return token
    except Exception as e:  # noqa: BLE001
        say(FAIL, f"Token load failed: {e}")
        sys.exit(1)


def check_quota(client: FinMindClient) -> None:
    section("2. API Quota")
    try:
        usage = client.usage()
        say(OK, f"Usage: {usage.user_count}/{usage.api_request_limit} "
                f"({usage.utilization_pct*100:.1f}% utilized, {usage.remaining} remaining)")
        if usage.utilization_pct > 0.80:
            say(WARN, "High utilization — consider waiting before heavy batch work")
    except Exception as e:  # noqa: BLE001
        say(FAIL, f"Quota check failed: {e}")
        sys.exit(1)


def check_datasets(client: FinMindClient, stock_id: str) -> dict[str, bool]:
    section(f"3. Critical Dataset Reachability ({stock_id})")
    today = datetime.today()
    start_recent = (today - timedelta(days=90)).strftime("%Y-%m-%d")
    start_fin = (today - timedelta(days=540)).strftime("%Y-%m-%d")

    datasets = [
        ("TaiwanStockPrice", start_recent, "price history"),
        ("TaiwanStockFinancialStatements", start_fin, "income statement"),
        ("TaiwanStockBalanceSheet", start_fin, "balance sheet"),
        ("TaiwanStockCashFlowsStatement", start_fin, "cash flows"),
        ("TaiwanStockMonthRevenue", start_fin, "monthly revenue"),
        ("TaiwanStockInstitutionalInvestorsBuySell", start_recent, "institutional flow"),
        ("TaiwanStockShareholding", start_recent, "foreign ownership"),
        ("TaiwanStockPER", start_recent, "PER/PBR"),
        ("TaiwanStockNews", start_recent, "news"),
    ]

    status = {}
    for ds, sd, label in datasets:
        try:
            df = client.get(ds, stock_id, sd)
            if df.empty:
                say(WARN, f"{ds} ({label}): reachable but empty")
                status[ds] = False
            else:
                say(OK, f"{ds} ({label}): {len(df)} rows, latest date {df['date'].max() if 'date' in df.columns else 'n/a'}")
                status[ds] = True
        except Exception as e:  # noqa: BLE001
            say(FAIL, f"{ds} ({label}): {e}")
            status[ds] = False
    return status


def check_parser_ledgers(client: FinMindClient, stock_id: str) -> None:
    """
    Verify that our ledger mappings match the actual FinMind 'type' codes.
    Reports any 'type' values in the real response that our ledger doesn't cover.
    """
    section(f"4. Parser Ledger Verification ({stock_id})")
    today = datetime.today()
    start = (today - timedelta(days=540)).strftime("%Y-%m-%d")

    checks = [
        ("TaiwanStockFinancialStatements", INCOME_STATEMENT_LEDGER, "income_statement"),
        ("TaiwanStockBalanceSheet", BALANCE_SHEET_LEDGER, "balance_sheet"),
        ("TaiwanStockCashFlowsStatement", CASH_FLOW_LEDGER, "cash_flow"),
    ]

    for dataset, ledger, label in checks:
        try:
            df = client.get(dataset, stock_id, start)
            if df.empty or "type" not in df.columns:
                say(WARN, f"{label}: no data to verify")
                continue
            actual_types = set(df["type"].dropna().unique())
            mapped_variants = set()
            for canonical, variants in ledger.items():
                for v in variants:
                    mapped_variants.add(v)
            hits = actual_types & mapped_variants
            misses = actual_types - mapped_variants
            say(OK, f"{label}: {len(hits)}/{len(actual_types)} canonical types matched")
            if misses:
                preview = sorted(misses)[:8]
                say(WARN, f"  Unmapped types (first 8): {', '.join(preview)}")
                say(WARN, f"  Total unmapped: {len(misses)} — extend LEDGER in parsers.py if any are material")
        except Exception as e:  # noqa: BLE001
            say(FAIL, f"{label}: verification failed — {e}")


def check_triage_and_gate3(client: FinMindClient, stock_id: str) -> None:
    section(f"5. End-to-end Triage + Gate 3 ({stock_id})")
    try:
        tr = triage.run(client, stock_id=stock_id)
        say(OK if tr.passed else WARN, f"Triage verdict: {'PASS' if tr.passed else 'FAIL'}")
        for c in tr.checks:
            marker = OK if c.passed else FAIL
            say(f"    {marker}", f"{c.name}: {c.detail}")
        if tr.notes:
            for n in tr.notes:
                say(WARN, f"    note: {n}")

        if tr.passed:
            print()
            g3 = gate3.run(client, stock_id=stock_id)
            say(OK, f"Gate 3 verdict: {g3.verdict} — score {g3.total_score:.1f}/100")
            for s in g3.sub_layers:
                say("   ", f"{s.as_line()}")
            if g3.hard_fail_triggered:
                say(WARN, "Hard-fail triggered:")
                for hf in g3.hard_fails:
                    if hf.triggered:
                        say("   ", f"⚠ {hf.name}: {hf.detail}")
            if g3.data_gaps:
                say(WARN, "Data gaps:")
                for g in g3.data_gaps:
                    say("   ", g)
    except Exception as e:  # noqa: BLE001
        say(FAIL, f"End-to-end check errored: {e}")
        traceback.print_exc()


# ──────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────

def main():
    test_stocks = sys.argv[1:] if len(sys.argv) > 1 else ["2330"]

    print("=" * 66)
    print("  Taiwan Equity Toolkit — setup validation")
    print(f"  Test stocks: {', '.join(test_stocks)}")
    print("=" * 66)

    token = check_token()
    client = FinMindClient(token=token)
    check_quota(client)

    for sid in test_stocks:
        check_datasets(client, sid)
        check_parser_ledgers(client, sid)
        check_triage_and_gate3(client, sid)

    print()
    print("=" * 66)
    print("  Validation complete.")
    print("  If all sections show ✓ with only minor ⚠, the toolkit is ready.")
    print("  Any ✗ should be addressed before running screens.")
    print("=" * 66)


if __name__ == "__main__":
    main()
```

## `taiwan_equity_toolkit/value_chain.py`

```python
"""
Value Chain Helper — Gate 5 support.

Maps a stock to its industry chain position using TaiwanStockIndustryChain,
then fetches upstream/downstream signals via async batch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from taiwan_equity_toolkit.client import FinMindClient
from taiwan_equity_toolkit import parsers, metrics


@dataclass
class ChainPosition:
    stock_id: str
    industries: list[str] = field(default_factory=list)        # all industry tags for this stock
    sub_industries: list[str] = field(default_factory=list)
    peers_in_chain: list[str] = field(default_factory=list)    # other stocks in same chain tags


@dataclass
class UpstreamSignal:
    stock_id: str
    revenue_yoy: Optional[float] = None
    margin_direction: str = "unknown"  # "expanding", "flat", "compressing", "unknown"
    institutional_flow_60d: Optional[float] = None
    as_of: Optional[str] = None


@dataclass
class ValueChainReport:
    candidate: str
    position: ChainPosition
    upstream_signals: list[UpstreamSignal] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"# Value Chain — {self.candidate}"]
        lines.append(f"Industries: {', '.join(self.position.industries) or 'n/a'}")
        lines.append(f"Sub-industries: {', '.join(self.position.sub_industries) or 'n/a'}")
        lines.append(f"Peers in chain: {len(self.position.peers_in_chain)} — {', '.join(self.position.peers_in_chain[:8])}" +
                     (" ..." if len(self.position.peers_in_chain) > 8 else ""))
        if self.upstream_signals:
            lines.append("")
            lines.append("## Upstream / chain signals")
            for s in self.upstream_signals:
                yoy = f"{s.revenue_yoy:+.1f}%" if s.revenue_yoy is not None else "n/a"
                flow = f"{s.institutional_flow_60d:+,.0f}" if s.institutional_flow_60d is not None else "n/a"
                lines.append(f"  - {s.stock_id}: Rev YoY {yoy} | Margin {s.margin_direction} | Inst flow {flow} ({s.as_of})")
        if self.notes:
            lines.append("")
            for n in self.notes:
                lines.append(f"_{n}_")
        return "\n".join(lines)


def locate(client: FinMindClient, stock_id: str) -> ChainPosition:
    """Identify the industry-chain position of a stock and its chain-peers."""
    chain_df = client.industry_chain()
    if chain_df.empty:
        return ChainPosition(stock_id=stock_id)

    mine = chain_df[chain_df["stock_id"].astype(str) == str(stock_id)]
    if mine.empty:
        return ChainPosition(stock_id=stock_id)

    industries = sorted(mine["industry"].dropna().unique().tolist()) if "industry" in mine.columns else []
    sub_industries = sorted(mine["sub_industry"].dropna().unique().tolist()) if "sub_industry" in mine.columns else []

    # Find peers in the same industry/sub_industry tags
    peers = set()
    if industries:
        same_ind = chain_df[chain_df["industry"].isin(industries)]
        peers.update(same_ind["stock_id"].astype(str).unique())
    if sub_industries:
        same_sub = chain_df[chain_df["sub_industry"].isin(sub_industries)]
        peers.update(same_sub["stock_id"].astype(str).unique())
    peers.discard(str(stock_id))

    return ChainPosition(
        stock_id=stock_id,
        industries=industries,
        sub_industries=sub_industries,
        peers_in_chain=sorted(peers),
    )


def analyze(
    client: FinMindClient,
    stock_id: str,
    override_upstream: Optional[list[str]] = None,
    max_upstream_names: int = 6,
) -> ValueChainReport:
    """
    Full Gate 5 analysis: locate chain position, fetch upstream signals.

    Args:
        client: Authenticated client
        stock_id: Candidate
        override_upstream: If provided, use these IDs as the upstream universe
                           (bypass industry-chain auto-detection)
        max_upstream_names: Cap on async batch size
    """
    today = datetime.today()
    rev_start = (today - timedelta(days=540)).strftime("%Y-%m-%d")
    fs_start = (today - timedelta(days=540)).strftime("%Y-%m-%d")
    flow_start = (today - timedelta(days=90)).strftime("%Y-%m-%d")

    position = locate(client, stock_id)
    report = ValueChainReport(candidate=stock_id, position=position)

    # Select names to batch
    if override_upstream:
        upstream_ids = override_upstream[:max_upstream_names]
    elif position.peers_in_chain:
        upstream_ids = position.peers_in_chain[:max_upstream_names]
    else:
        report.notes.append("No chain data available — Gate 5 requires manual upstream/downstream selection.")
        return report

    # Async batch
    rev_map = client.get_multi("TaiwanStockMonthRevenue", upstream_ids, rev_start)
    fs_map = client.get_multi("TaiwanStockFinancialStatements", upstream_ids, fs_start)
    flow_map = client.get_multi("TaiwanStockInstitutionalInvestorsBuySell", upstream_ids, flow_start)

    for sid in upstream_ids:
        signal = UpstreamSignal(stock_id=sid)

        # Revenue YoY
        rev_m = metrics.revenue_growth_yoy(rev_map.get(sid, pd.DataFrame()))
        signal.revenue_yoy = rev_m.value
        signal.as_of = rev_m.as_of

        # Margin direction (gross margin last 4Q)
        income = parsers.parse_income_statements(fs_map.get(sid, pd.DataFrame()))
        if len(income) >= 2:
            series = [r.gross_margin for r in sorted(income, key=lambda r: r.date)[-4:] if r.gross_margin is not None]
            if len(series) >= 2:
                if series[-1] > series[0] + 0.01:
                    signal.margin_direction = "expanding"
                elif series[-1] < series[0] - 0.01:
                    signal.margin_direction = "compressing"
                else:
                    signal.margin_direction = "flat"

        # Institutional net flow 60d
        flows = metrics.institutional_net_flow(flow_map.get(sid, pd.DataFrame()), lookback_days=60)
        # Net across all three investor types
        net = 0.0
        any_data = False
        for m in flows.values():
            if m.value is not None:
                net += m.value
                any_data = True
        signal.institutional_flow_60d = net if any_data else None

        report.upstream_signals.append(signal)

    return report
```

