## read Taiwan_Equity_Agent_System_Prompt.md and adopt the role and rules.

---

## Agent Operational Guide

This file documents how AI agents should operate within this codebase. The canonical identity, reasoning rules, and stock-selection methodology are defined in `Taiwan_Equity_Agent_System_Prompt.md` — read that first.

---

## Canonical Workflow

When asked to run a screen or analyze stocks, execute the full pipeline in order. Do not skip gates.

```
Gate 1 (industry judgment)
  → Gate 2 (company qualitative judgment)
    → Triage Filter (toolkit: mass_triage.run)
      → Gate 3 Forensic (toolkit: gate3.run)
        → Gate 4 Peer Validation (toolkit: peers.compare)
          → Gate 5 Value Chain (toolkit: value_chain.analyze)
            → Gate 6 Portfolio Fit (judgment)
              → Gate 6.5 Entry Architecture (toolkit: gate65.run)
                → Gate 7 Thesis & Catalyst (judgment)
```

Gates 1, 2, 6, and 7 require human-in-the-loop judgment. Gates 3, 4, 5, and 6.5 are fully automated via the toolkit.

---

## Toolkit Function Reference

### Client initialization
```python
from taiwan_equity_toolkit.client import FinMindClient
client = FinMindClient(token="<primary_token>")
```
Tokens are in `Finmind.md`. Use primary first; roll over to backup when quota exhausted (`client.usage()` returns remaining capacity).

### Triage
```python
from taiwan_equity_toolkit.mass_triage import run as mass_triage_run
from taiwan_equity_toolkit.config import TriageConfig
result = mass_triage_run(client, stock_id="2330", cfg=TriageConfig(), intended_position_ntd=5_000_000)
if result.failures():
    # stock is rejected — log result.summary() and stop
```

### Gate 3
```python
from taiwan_equity_toolkit.gate3 import run as gate3_run
result = gate3_run(client, stock_id="2330")
# result.score: int (0–100)
# result.hard_fail: bool
# result.memo(): formatted markdown
```

### Gate 4 Peer Comparison
```python
from taiwan_equity_toolkit.peers import compare
result = compare(client, candidate="2330", peers=["2303", "6770"])
# result.candidate_rankings: dict[metric → (rank, total)]
# result.summary(): formatted markdown
```

### Gate 5 Value Chain
```python
from taiwan_equity_toolkit.value_chain import analyze
result = analyze(client, stock_id="2330")
# result.position, result.upstream_signals, result.downstream_signals
```

### Gate 6.5 Entry Architecture
```python
from taiwan_equity_toolkit.gate65 import run as gate65_run
result = gate65_run(client, stock_id="2330", existing_book=["2317", "2454"], intended_position_ntd=5_000_000)
# result.verdict: "Enter Now" | "Stagger / Scale In" | "Wait for Setup" | "Reject for Book Fit"
```

### Memo Assembly
```python
from taiwan_equity_toolkit.memo import FullScreenMemo
memo = FullScreenMemo(stock_id, triage_result, gate3_result, peer_result, vc_result, gate65_result)
print(memo.render())
```

---

## Output Principles

**Lead with verdict.** First line of any response on a stock is a one-sentence verdict: Pass / Conditional / Reject with the single most important reason.

**Structure by gate.** Use gate numbers as section headers. Show what data was used, what the metric value was, and what the threshold is.

**Cite every metric.** Use `Metric.cite()` format: `"CFO/NI = 0.87x (FinancialStatements + CashFlowsStatement, 2024-09-30)"`. Never state a number without a source and date.

**Flag data gaps explicitly.** If a dataset returned no rows or stale data, say so. Do not silently skip the check.

**No price targets without named catalyst.** Any forward projection requires a specific, dated, named catalyst. Vague macro optimism is not a catalyst.

**No trade moralization.** State analysis and risk flags. Do not editorialize on whether a trade is "good" or "safe."

---

## Hard Rules (Non-Negotiable)

1. Never advance a stock past a gate it failed.
2. Never skip the 7 hard-fail overrides in Gate 3 — a high numeric score does not override them.
3. Never report a metric without its source dataset and as-of date.
4. Never use broker-branch or real-time datasets that require paid FinMind tiers.
5. Never place hypothetical trades or suggest position sizing beyond what Gate 6.5 computes.
6. Never analyze stocks outside the Taiwan 500 TAIEX universe without explicit user instruction.

---

## Taiwan Market Context (Always Apply)

- **USD/TWD direction** affects exporters (foundries, OSAT, IC design) differently than domestic plays.
- **Institutional flow (three-investor types)** — foreign + trust buying together is a stronger signal than either alone.
- **Dividend ex-div season** (Q2) causes mechanical price drops; do not mistake ex-div corrections for fundamental deterioration.
- **Cross-strait risk** is a permanent tail risk — note elevated cross-strait tension in any Gate 7 thesis.
- **Semiconductor supply-chain positioning** — upstream (wafer, chemical) vs. midstream (foundry, OSAT) vs. downstream (system, brand) matters for cycle timing.
- **Monthly revenue** is the highest-frequency Taiwan fundamental signal — always check for inflection before quarterly financials confirm.

---

## When Running the Full Screen

1. Confirm the universe source: prefer live TAIFEX fetch, fall back to `data/taiex_top200_snapshot.json`.
2. Log token usage before and after — switch to backup if primary is below 100 requests remaining.
3. Log funnel counts at each gate: started → triage pass → Gate 3 pass → final ranked list.
4. Write `screen_results.json` with full audit trail. Do not discard rejects — they are needed for audit.
5. Report the top-10 with gate scores, entry verdict, and the single-sentence investment thesis for each.
