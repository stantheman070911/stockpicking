## read Taiwan_Equity_Agent_System_Prompt.md and adopt the role and rules.

---

## Codebase Conventions

### Language & Runtime
- Python 3.9+. No type-checker enforced, but all public functions use type hints.
- No external framework beyond `FinMind`, `pandas`, `requests`. Keep the dependency surface minimal.

### Key Files Map

| File | Purpose |
|---|---|
| `run_top200_screen.py` | Main entry — full pipeline, do not break its public interface |
| `taiwan_equity_toolkit/config.py` | Single source of truth for all thresholds and weights |
| `taiwan_equity_toolkit/client.py` | All FinMind API calls go through here |
| `taiwan_equity_toolkit/metrics.py` | All ratio calculations — every return must be a `Metric` dataclass |
| `taiwan_equity_toolkit/gate3.py` | The forensic scorecard — most complex module, change carefully |
| `Stock_Selection_Framework.md` | Authoritative spec — consult before changing gate logic |
| `Finmind.md` | API dataset catalog and token credentials |

### Coding Rules

**Metrics must carry provenance.** Every computed ratio must return a `Metric` object with `.value`, `.unit`, `.as_of`, `.source`, `.note`. Never return a bare float from `metrics.py`.

**Hard-fail overrides are non-negotiable.** The 7 hard-fail conditions in `gate3.py` must bypass the numeric score — never make them conditional on the score.

**Sequential gates, fail-closed.** Once a stock fails a gate, it must not advance. Do not add early-exit shortcuts that skip hard-fail checks.

**Config is the only tuning surface.** Thresholds belong in `config.py`. Hard-coded magic numbers in gate logic are a bug.

**Async batch for peer work.** `peers.py` and any multi-stock API calls must use `client.get_multi()` — never loop `client.get()` over a list of stocks.

**Token failover must be preserved.** `run_top200_screen.py` tracks primary and backup token usage. Do not refactor away the failover logic.

### Testing

```bash
python -m pytest tests/
```

Tests use mocked API responses. When adding a new metric or gate check, add a corresponding test in `tests/`. Test naming: `test_<module>.py`.

### Adding a New Gate Check

1. Add the threshold to `config.py` with a clear name.
2. Implement the check in the appropriate module (`triage.py`, `gate3.py`, `gate65.py`).
3. Return a structured result object, not a raw boolean.
4. Update `Stock_Selection_Framework.md` if the spec changes.
5. Add a test covering the pass, fail, and edge-case boundary.

### Data Snapshot

`data/taiex_top200_snapshot.json` is the fallback universe. Update it when the TAIEX composition changes materially (quarterly is sufficient). Include `as_of` date and source URL.

### What Not to Do

- Do not add price targets or forward projections to any output.
- Do not skip the triage filter to "save time" on a single-stock run.
- Do not add broker-branch or real-time datasets that require paid FinMind tiers — the pipeline must run on the free tier.
- Do not cache API responses on disk between runs — stale data causes incorrect gate decisions.
- Do not change `Gate3Weights` without updating `Stock_Selection_Framework.md` and re-running all tests.
