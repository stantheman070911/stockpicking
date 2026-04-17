## read Taiwan_Equity_Agent_System_Prompt.md and adopt the role and rules.

---

## Codebase Conventions

### Runtime

- Python 3.9+
- Keep dependencies minimal
- Default test command:

```bash
python3 -m unittest discover -s tests
```

### Architectural Rules

- The screening model is organized as `Industry / Macro`, `Company Quality`, `Setup / Entry`, and `Synthesis`.
- Unavailable checks must stay explicit in status handling.
- Public toolkit interfaces are part of the supported API:
  - `triage.run`
  - `gate3.run`
  - `gate65.run`
  - `value_chain.analyze`
- Keep thresholds in `config.py` when they are meant to be tunable.

### Key Files

| File | Purpose |
|---|---|
| `run_top200_screen.py` | batch entry point |
| `taiwan_equity_toolkit/models.py` | status/result contracts |
| `taiwan_equity_toolkit/data_policy.py` | availability rules, scoring, PIT policy |
| `taiwan_equity_toolkit/workstream_industry.py` | Industry / Macro |
| `taiwan_equity_toolkit/workstream_company.py` | Company Quality |
| `taiwan_equity_toolkit/workstream_setup.py` | Setup / Entry |
| `taiwan_equity_toolkit/synthesis.py` | synthesis checkpoint |
| `taiwan_equity_toolkit/manual_workflows.py` | manual workflow templates |

### Coding Rules

- Every automated check must return a structured result with explicit status.
- `not_assessed` and `manual_review_required` checks contribute zero live score weight.
- Do not reintroduce dead weights for removed signals.
- Do not reintroduce fail-closed dependencies on unavailable datasets.
- Keep documentation aligned with implementation.

### Validation

- The point-in-time policy lives in `data_policy.py`.
- Taiwan transaction-cost assumptions live there as well.
- Higher-grade walk-forward validation that depends on external institutional datasets belongs in documented scaffolds, not in implied runtime behavior.

### Docs Sync

Keep these documents aligned with the code:

- `README.md`
- `taiwan_equity_toolkit/README.md`
- `AGENTS.md`
- `CLAUDE.md`
- `Stock_Selection_Framework.md`
- `Taiwan_Equity_Agent_System_Prompt.md`
