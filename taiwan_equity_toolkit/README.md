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
python taiwan_equity_toolkit/full_screen_demo.py 2330 --book 2317,2454 --size-ntd 10000000
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
from taiwan_equity_toolkit import FinMindClient, mass_triage, gate3, workstream_a
from taiwan_equity_toolkit.config import load_token

client = FinMindClient(token=load_token())

# Step 1 — Triage
triage_result = mass_triage.run(client, stock_id='2330')
print(triage_result.summary())

if triage_result.status == "failed":
    # Stop here. Document the failure. Do not proceed to Gate 3.
    pass
else:
    # Step 2 — Gate 3 Forensic Quality
    g3 = gate3.run(client, stock_id='2330')
    print(g3.memo())
    # g3.verdict ∈ {"Pass", "Conditional Watchlist", "Fail", "Fail (Hard-Fail Override)"}
    # g3.total_score is out of 100
    # g3.hard_fail_triggered is a boolean

    # Step 3 — Workstream A (if Gate 3 passed)
    if g3.verdict == "Pass":
        wa = workstream_a.run(client, stock_id='2330')
        print(wa.status, wa.cluster)
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

### `workstream_a.run(client, stock_id)`
Industry / macro context workstream replacing the legacy Gate 4 + Gate 5 split. Returns `WorkstreamAResult` with:

- `.status` — `passed` / `manual_review_required` / `failed`
- `.cluster` — supply-chain cluster or industry fallback
- `.sector_signal` — revenue cluster context
- `.chain_position` — upstream / downstream chain placement
- `.tsmc_anchor` — 2330 revenue indicator
- `.peer_alignment` — revenue, margin, institutional-flow alignment
- `.macro_backdrop` — Fed / UST curve / WTI / TWD context

```python
from taiwan_equity_toolkit import workstream_a

wa = workstream_a.run(client, '2330')
print(wa.status, wa.cluster)
print(wa.peer_alignment.usable_peer_count)
```

Batch the same workstream across a screen universe if needed:

```python
results = workstream_a.run_all(
    client_factory=lambda: FinMindClient(token=load_token()),
    stock_ids=['2330', '2303', '3711'],
)
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
- **Workstream A sector / chain lead-lag timing** — industry-specific expertise required
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
| Workstream A | 5 × (1 + peer_count) | via async batch |
| Gate 6.5 | 3–4 | PER, price adj, price limit, optional futures/options data |

Target: ~30–40 calls per full single-name screen. Workstream A at 3 peer names adds ~20 calls via batch.

---

## Extending the toolkit

Natural next additions:

1. **Value-chain helper** — wrapper around `TaiwanStockIndustryChain` for upstream/downstream batch queries
2. **Reverse-DCF helper** — closed-form implied-growth solver
3. **Convertible-bond dilution calculator** — using `TaiwanStockConvertibleBondDailyOverview`
4. **Branch-broker persistent-buyer detector** — Sponsor-tier `TaiwanStockTradingDailyReport` analysis
5. **Post-trade attribution** — logs which gates were predictive (covered elsewhere)

Add new metrics to `metrics.py`, new checks to `gate3.py` components, new thresholds to `config.py`. Keep the public API (`mass_triage.run`, `gate3.run`, `workstream_a.run`) stable.
