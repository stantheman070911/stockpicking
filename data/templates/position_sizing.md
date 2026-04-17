# Position Sizing Template

## Purpose
Document how conviction translates into a position band after applying mechanical caps from volatility, liquidity, and correlation.

## Required Fields
- <<REQUIRED>> Stock / setup:
- <<REQUIRED>> Conviction tier:
- <<REQUIRED>> Mechanical caps available from sizing.py:
- <<REQUIRED>> Chosen position band:
- <<REQUIRED>> Why the chosen size is below or at the cap:
- <<REQUIRED>> What would justify sizing up:
- <<REQUIRED>> What would force sizing down:

## Guidance
- Separate what the system permits from what the analyst chooses.
- Use ranges or bands when the entry is staged.
- If the position is intentionally smaller than the cap, state the unresolved risk.

## Example
```md
Stock / setup: 2317 on AI server ramp.
Conviction tier: Medium-high.
Mechanical caps available from sizing.py: Vol cap 6%, liquidity cap 4%, correlation cap 3.5%.
Chosen position band: 2.5% to 3.0%.
Why the chosen size is below or at the cap: Customer concentration risk is still unresolved.
What would justify sizing up: Two consecutive months of AI server revenue acceleration plus stable margin mix.
What would force sizing down: Correlation to the existing AI basket rises further or channel inventory deteriorates.
```
