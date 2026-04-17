# Sell Discipline Template

## Purpose
Pre-commit the exit archetype and review rules so losing and winning positions are managed intentionally.

## Required Fields
- <<REQUIRED>> Stock / setup:
- <<REQUIRED>> Exit archetype {Assassin / Hunter / Connoisseur}:
- <<REQUIRED>> Forced review trigger:
- <<REQUIRED>> Add-on rule:
- <<REQUIRED>> Trim / take-profit rule:
- <<REQUIRED>> Dead-money time stop:

## Guidance
- The archetype should describe how the position is meant to be managed, not how it felt in prior trades.
- Include the mandatory drawdown review level when one exists.
- Add-on rules should require new evidence, not price action alone.

## Example
```md
Stock / setup: 2884 rate-sensitive rerating.
Exit archetype {Assassin / Hunter / Connoisseur}: Connoisseur
Forced review trigger: Review immediately at -20% from cost or if the thesis invalidation trigger hits earlier.
Add-on rule: Add only after the next earnings print confirms fee-income recovery and capital strength.
Trim / take-profit rule: Trim only if the setup reaches scenario-EV fair value with no fresh catalyst path.
Dead-money time stop: Re-underwrite after two quarters if the catalyst path has not progressed.
```
