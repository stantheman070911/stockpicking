## read Taiwan_Equity_Agent_System_Prompt.md and adopt the role and rules.

---

## Agent Operational Guide

This repository uses a four-part screening workflow:

```text
Industry / Macro
Company Quality
Setup / Entry
Synthesis
```

Use the workstreams first. Use the public toolkit entry points when a task calls for those specific interfaces.

---

## Canonical Workflow

```python
from taiwan_equity_toolkit.client import FinMindClient
from taiwan_equity_toolkit.models import StrategyMode
from taiwan_equity_toolkit.synthesis import synthesize_candidate
from taiwan_equity_toolkit.workstream_company import run as run_company_workstream
from taiwan_equity_toolkit.workstream_industry import run as run_industry_workstream
from taiwan_equity_toolkit.workstream_setup import run as run_setup_workstream

client = FinMindClient(token="<primary_token>")

industry = run_industry_workstream(client, stock_id="2330")
company = run_company_workstream(client, stock_id="2330")
setup, extras = run_setup_workstream(client, stock_id="2330", existing_book=["2317", "2454"])

assessment = synthesize_candidate(
    stock_id="2330",
    strategy_mode=StrategyMode.TACTICAL_LONG_SHORT,
    industry=industry,
    company=company,
    setup=setup,
    sizing_band=extras["sizing_band"],
)
```

Public toolkit interfaces:

- `triage.run(...)`
- `gate3.run(...)`
- `gate65.run(...)`
- `peers.compare(...)`
- `value_chain.analyze(...)`
- `memo.FullScreenMemo(...)`

---

## Operating Rules

1. Never spoof unavailable data.
2. Never leave unavailable signals inside automated score weights unless an executable proxy exists.
3. When a valuable check cannot be automated, classify the remainder explicitly as:
   - `manual workflow`
   - `optional adapter`
   - `deferred scaffold`
4. Never use broker-branch or paid real-time datasets in the default executable path.
5. Always distinguish:
   - `passed`
   - `failed`
   - `not_assessed`
   - `manual_review_required`

---

## Output Principles

- Lead with the verdict and primary reason.
- Cite every metric with dataset and as-of date when presenting numbers.
- Flag data gaps explicitly.
- Keep manual workflow requirements explicit.
- In tactical mode, a forward setup needs a named dated catalyst or an explicit `manual_review_required` label.
- In quality-compounder mode, a milestone path can fill that role.

---

## Full-Screen Expectations

When running the full screen:

1. Prefer live TAIFEX universe fetch and fall back to `data/taiex_top200_snapshot.json`.
2. Log token usage before and after when available.
3. Use `run_top200_screen.py` as the batch entry point.
4. Preserve `screen_results.json` with the full audit trail.
5. Report top-10 names with:
   - composite score
   - per-workstream states
   - entry verdict
   - thesis stub

---

## Manual Workflow Requirements

The memo and workflow surface must account for:

- variant perception
- invalidation criteria
- conviction input for final sizing
- scenario EV cases
- sell-discipline taxonomy
- pre-mortem
- management forensic memo
- scuttlebutt / channel-check memo
- monitoring cadence
- decision journal
- post-mortem trigger
