# Taiwan Equity Stock-Picking System

An AI-driven, deterministic screening framework for Taiwan Stock Exchange (TWSE) and TPEx securities. Screens the TAIEX Top-200 universe through a 7-gate + triage methodology backed by the FinMind API to produce a ranked, auditable watchlist.

---

## What It Does

Takes 200 of the largest Taiwan-listed stocks and runs them through a sequential gate pipeline:

1. **Gate 1** — Industry directional filter (macro-aligned sector buckets)
2. **Gate 2** — Company qualitative check (moat, cleanest representation)
3. **Triage Filter** — Cheap mechanical screens: liquidity, suspension, staleness, solvency collapse
4. **Gate 3** — Forensic quality scorecard (100-pt, 5 sub-layers, 7 hard-fail overrides)
5. **Gate 4** — Peer validation via async batch comparison
6. **Gate 5** — Value-chain / supply-chain positioning
7. **Gate 6** — Portfolio fit (judgment)
8. **Gate 6.5** — Entry architecture: valuation percentile, realized vol, book correlation
9. **Gate 7** — Thesis & named catalyst (judgment)

Output: `screen_results.json` with a top-10 ranked list, full audit trail of all rejects by gate, and every metric cited with dataset name and as-of date.

---

## Project Structure

```
stockpicking/
├── run_top200_screen.py              # Main entry point — full TAIEX Top-200 pipeline
├── Taiwan_Equity_Agent_System_Prompt.md  # AI agent identity, rules, canonical workflow
├── Stock_Selection_Framework.md      # Authoritative gate methodology specification
├── Finmind.md                        # FinMind API datasets, tokens, rate limits
├── data/
│   └── taiex_top200_snapshot.json    # Fallback universe (200 stock IDs, Apr 2026)
├── taiwan_equity_toolkit/
│   ├── config.py                     # All thresholds and tunable parameters
│   ├── client.py                     # FinMind REST wrapper (auth, retry, async batch)
│   ├── parsers.py                    # FinMind long-format → typed dataclass records
│   ├── metrics.py                    # Derived financial ratios with source citations
│   ├── triage.py                     # Triage Filter (9 cheap checks)
│   ├── gate3.py                      # Gate 3 forensic scorecard
│   ├── gate65.py                     # Gate 6.5 entry architecture
│   ├── peers.py                      # Gate 4 peer comparison (async batch)
│   ├── value_chain.py                # Gate 5 supply-chain positioning
│   ├── memo.py                       # Structured memo formatter
│   ├── full_screen_demo.py           # Single-stock demo pipeline
│   └── validate_setup.py             # API connectivity validator
└── tests/
    ├── test_run_top200_screen.py
    ├── test_gate3.py
    ├── test_metrics.py
    ├── test_triage.py
    ├── test_value_chain.py
    └── test_validate_setup.py
```

---

## Setup

### Requirements

```bash
pip install -U FinMind pandas requests
```

No other dependencies. Python 3.9+.

### FinMind Tokens

Two tokens are pre-configured in `Finmind.md` and used by the pipeline with automatic failover:

- **Primary:** registered to `stantheman911@gmail.com`
- **Backup:** registered to `lamylu0811@gmail.com`

Rate limits: 600 req/hour (authenticated), 300 req/hour (free tier).

---

## Usage

### Validate API connectivity first

```bash
python taiwan_equity_toolkit/validate_setup.py
# with specific stocks:
python taiwan_equity_toolkit/validate_setup.py 2330 2317 2454
```

### Single-stock demo

```bash
python taiwan_equity_toolkit/full_screen_demo.py 2330
python taiwan_equity_toolkit/full_screen_demo.py 2330 --peers 2303,6770 --book 2317,2454 --size-ntd 10000000
```

### Full Top-200 screen

```bash
python run_top200_screen.py
```

Outputs `screen_results.json` with:
- `top_10`: ranked selections with composite scores
- `all_ranked`: complete ordered list of passers
- `rejects`: full audit trail keyed by gate (Gate 1, Triage, Gate 3, Gate 4, Gate 5, Gate 6.5)
- `token_usage`: API request counts per token

### Run tests

```bash
python -m pytest tests/
```

---

## Key Configuration (`taiwan_equity_toolkit/config.py`)

| Parameter | Default | Purpose |
|---|---|---|
| `min_adv_ntd` | NT$50M | Triage liquidity floor |
| `cfo_to_ni_healthy` | 0.8x | Gate 3 operating quality threshold |
| `interest_coverage_min` | 2.0x | Gate 3 debt servicing minimum |
| `net_debt_to_ebitda_warning` | 3.0x | Gate 3 leverage caution level |
| `net_debt_to_ebitda_hardfail` | 5.0x | Gate 3 hard-fail override |
| `pass_threshold` | 80 | Gate 3 pass score |
| `conditional_threshold` | 65 | Gate 3 conditional score |
| `correlation_hardfail` | 0.85 | Gate 6.5 portfolio overlap reject |
| `TRIAGE_WORKERS` | 8 | Parallel workers for triage |
| `GATE3_WORKERS` | 4 | Parallel workers for Gate 3 |
| `INTENDED_POSITION_NTD` | NT$5M | Position size for liquidity checks |

---

## Gate 3 Scorecard (100 points)

| Sub-layer | Weight | What It Measures |
|---|---|---|
| 3A Operating Quality | 25 pts | Revenue growth, margin direction, CFO/NI, ROE |
| 3B Balance Sheet | 35 pts | Leverage, liquidity, interest coverage, FCF integrity |
| 3C Ownership | 20 pts | Institutional flow, foreign ownership trend, margin/short structure |
| 3D Derivatives | 10 pts | CB presence, futures/options confirms thesis |
| 3E Data Integrity | 10 pts | Monthly/quarterly consistency, governance red flags |

**Verdicts:** Pass ≥ 80 · Conditional 65–79 · Fail < 65

**Hard-fail overrides (any one = immediate reject regardless of score):**
1. Refinancing wall + weak interest coverage
2. Persistent CFO/NI divergence (4+ quarters < 0.5x)
3. Governance red flags (auditor change, dilution, related-party transactions)
4. Ownership/derivatives conflict with fundamentals
5. Extreme leverage (net debt/EBITDA > 5x)
6. Repeat dilution without repair
7. Excessive data gaps (> 50% missing critical fields)

---

## Architecture Notes

- **Fail-closed, sequential gates:** Failing any gate stops processing that stock.
- **Cheap before expensive:** Triage (fast API checks) runs before Gate 3 (heavy financial analysis).
- **Async batch:** Peer comparisons (`peers.py`) use concurrent fetches — critical for throughput.
- **Citation discipline:** Every `Metric` object carries `.source`, `.as_of`, `.unit`. `Metric.cite()` is the standard output.
- **Token failover:** Pipeline tracks usage and rolls over from primary to backup token automatically.
- **Snapshot fallback:** Live TAIFEX universe fetch with JSON snapshot fallback for resilience.
- **No price targets:** Framework stops at actionable watchlist. No forward projections without named, dated catalyst.

---

## Data Sources

All data sourced from [FinMind](https://finmindtrade.com/) free-tier API (75+ Taiwan datasets):

- **Price & volume:** `TaiwanStockPrice`, `TaiwanStockPEInstitutional`
- **Financials:** `TaiwanStockFinancialStatements`, `TaiwanStockBalanceSheet`, `TaiwanStockCashFlowsStatement`
- **Monthly revenue:** `TaiwanStockMonthRevenue`
- **Institutional flow:** `TaiwanStockInstitutionalInvestorsBuySell`
- **Margin/short:** `TaiwanStockMarginPurchaseShortSale`
- **Derivatives:** `TaiwanFuturesDaily`, `TaiwanOptionDaily`
- **Macro:** `TaiwanBusinessIndicator`, `TaiwanDollarFuturesDaily`

See `Finmind.md` for the full dataset catalog and tier requirements.
