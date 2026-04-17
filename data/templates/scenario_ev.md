# Scenario EV Template

## Purpose
Replace a single-point target with a weighted base / bull / bear framing that can be audited after the fact.

## Required Fields
- <<REQUIRED>> Stock / setup:
- <<REQUIRED>> Base case probability:
- <<REQUIRED>> Base case IRR / payoff:
- <<REQUIRED>> Bull case probability:
- <<REQUIRED>> Bull case IRR / payoff:
- <<REQUIRED>> Bear case probability:
- <<REQUIRED>> Bear case IRR / payoff:
- <<REQUIRED>> Weighted EV / IRR:
- <<REQUIRED>> Key driver assumptions:

## Guidance
- Probabilities should sum to 100%.
- Keep the drivers tied to named operating metrics, not vague sentiment.
- If the scenario math comes from code later, paste the computed output and document the analyst overrides.

## Example
```md
Stock / setup: 2454 around handset recovery and edge-AI mix.
Base case probability: 50%
Base case IRR / payoff: 14% IRR on normalizing gross margin.
Bull case probability: 25%
Bull case IRR / payoff: 28% IRR if flagship share gains persist.
Bear case probability: 25%
Bear case IRR / payoff: -12% IRR if inventory digestion extends.
Weighted EV / IRR: 11%
Key driver assumptions: Smartphone TAM, AI edge attach rate, and margin mix from premium chipsets.
```
