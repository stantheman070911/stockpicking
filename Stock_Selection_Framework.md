# Stock Selection Framework

## Central Question

Is this the right Taiwan-listed security to express the industry view, at this setup, with this balance-sheet profile, under this positioning backdrop, and with a thesis that can be monitored and invalidated clearly?

## Governing Principles

- Signal hierarchy matters more than checklist volume.
- Industry direction, company quality, and setup quality are distinct judgments.
- Valuable checks that cannot be automated must remain visible as workflows, memo fields, or scaffolds.
- Unavailable data must be surfaced explicitly rather than implied away.
- Every advancement and rejection needs evidence.

## Architecture

```text
Industry / Macro
Company Quality
Setup / Entry
Synthesis
```

The three workstreams run independently. Synthesis combines them into a decision-ready memo and a clear record of what remains manual.

## Industry / Macro

Question: Is the industry direction favorable, and does the surrounding macro and peer context support the trade expression?

Automated checks:

- industry and value-chain mapping through the proxy map and stock information
- peer echo using monthly revenue, financial statements, and institutional flow
- FX backdrop
- rates backdrop

Interpretation rules:

- `TaiwanBusinessIndicator` is context only.
- Missing peer context becomes `manual_review_required`.
- Backdrop checks that are unavailable become `not_assessed`.

## Company Quality

Question: Does the operating profile, balance sheet, sponsorship, and integrity evidence support this as the right vehicle?

Automated checks:

- tradability
- financial freshness
- monthly revenue trajectory
- CFO/NI quality
- balance-sheet stress
- governance and news scan
- capital-action history
- ownership and sponsorship
- monthly versus quarterly consistency

Process rules:

- CFO/NI weakness is a red flag and escalation trigger, not an automatic reject by itself.
- Full forensic expansion is triggered when red flags accumulate or critical findings appear.
- Broker-branch `分點` is excluded from automated scoring.
- Convertible-bond signals belong to the overlay/manual path.

Manual workflow items:

- management forensic
- share-pledging review
- scuttlebutt / channel checks

## Setup / Entry

Question: Is the setup executable, sized appropriately, and sensible relative to the existing book?

Automated checks:

- valuation and expectation gap
- reverse DCF using a market-cap proxy
- volatility
- liquidity and execution
- portfolio overlap dashboard
- crowding and setup pressure
- mechanical sizing band

Process rules:

- Daily data is the executable timing surface.
- Correlation above `0.70` requires explicit justification.
- Scenario EV and final size require analyst judgment in addition to the mechanical outputs.

## Synthesis

Synthesis must record:

- thesis
- variant perception
- invalidation criteria
- catalyst or milestone path
- conviction input for sizing
- scenario EV framing
- sell-discipline taxonomy
- pre-mortem
- management forensic memo
- scuttlebutt memo
- monitoring cadence
- decision journal entry
- post-mortem trigger

## Strategy Modes

- `tactical_long_short`
- `quality_compounder`

Mode rules:

- Tactical mode requires a named dated catalyst or an explicit `manual_review_required` state.
- Quality-compounder mode can use a milestone path in that role.

## Status Model

Every automated output resolves to one of:

- `passed`
- `failed`
- `not_assessed`
- `manual_review_required`

These states must be visible in screen outputs, memos, and JSON artifacts.

## Default Handling of Constrained Signals

| Signal | Treatment |
|---|---|
| Broker-branch `分點` | excluded from automated scoring |
| Convertible-bond data | overlay/manual workflow |
| `TaiwanBusinessIndicator` | context only |
| Tick/snapshot data | daily-data execution proxy |
| Correlation hard reject | justification workflow above `0.70` |

## Data Policy

- Use announcement and as-of dates only.
- Historical validation must reject missing or future as-of dates.
- Unavailable checks become `not_assessed` or `manual_review_required` unless a specific rule requires a different fallback.

## Validation Scope

In scope:

- executable screening path
- fallback-behavior tests
- point-in-time guardrails
- Taiwan transaction-cost assumptions used in validation scaffolding

Documented scaffolds:

- walk-forward validation that depends on higher-grade institutional datasets

## Manual Workflow Artifacts

See:

- `templates/management_forensic.md`
- `templates/channel_check_protocol.md`
- `templates/pre_mortem.md`
- `templates/decision_journal.md`
- `templates/post_mortem.md`
- `taiwan_equity_toolkit/manual_workflows.py`
