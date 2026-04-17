# Taiwan Equity Toolkit

Reusable Python infrastructure for Taiwan equity screening, ranking, and memo support.

## Core Modules

- `models.py`: shared result contracts and status enums
- `data_policy.py`: dataset availability, fallback rules, score normalization, point-in-time policy
- `workstream_industry.py`: Industry / Macro
- `workstream_company.py`: Company Quality
- `workstream_setup.py`: Setup / Entry
- `synthesis.py`: synthesis checkpoint and memo requirements
- `manual_workflows.py`: explicit workflow templates for non-programmable findings

## Quick Start

```python
from taiwan_equity_toolkit.client import FinMindClient
from taiwan_equity_toolkit.config import load_token
from taiwan_equity_toolkit.models import StrategyMode
from taiwan_equity_toolkit.synthesis import synthesize_candidate
from taiwan_equity_toolkit.workstream_company import run as run_company_workstream
from taiwan_equity_toolkit.workstream_industry import run as run_industry_workstream
from taiwan_equity_toolkit.workstream_setup import run as run_setup_workstream

client = FinMindClient(token=load_token())

industry = run_industry_workstream(client, stock_id="2330")
company = run_company_workstream(client, stock_id="2330")
setup, extras = run_setup_workstream(client, stock_id="2330", existing_book=["2317"])

assessment = synthesize_candidate(
    stock_id="2330",
    strategy_mode=StrategyMode.TACTICAL_LONG_SHORT,
    industry=industry,
    company=company,
    setup=setup,
    sizing_band=extras["sizing_band"],
)
```

## Public Interfaces

The toolkit exposes these public entry points:

- `triage.run(...)`
- `gate3.run(...)`
- `gate65.run(...)`
- `peers.compare(...)`
- `value_chain.analyze(...)`
- `memo.FullScreenMemo(...)`

The workstream modules are the primary implementation surface, and the public entry points above are part of the supported API.

## Status Contract

Every automated check and workstream resolves to one of:

- `passed`
- `failed`
- `not_assessed`
- `manual_review_required`

Checks marked `not_assessed` or `manual_review_required` contribute zero live score weight unless an executable proxy is present.

## Data-Availability Rules

The toolkit keeps unavailable checks explicit.

Typical treatments:

- broker-branch `分點`: excluded from automated scoring
- convertible-bond review: overlay/manual path
- `TaiwanBusinessIndicator`: context only
- tick/snapshot timing: daily-data proxy

## Manual Workflow Support

The toolkit includes explicit workflow support for:

- management forensic
- channel-check protocol
- pre-mortem
- decision journal
- post-mortem

See:

- `manual_workflows.py`
- `templates/management_forensic.md`
- `templates/channel_check_protocol.md`
- `templates/pre_mortem.md`
- `templates/decision_journal.md`
- `templates/post_mortem.md`

## Validation and Tests

Validator:

```bash
python taiwan_equity_toolkit/validate_setup.py
```

Tests:

```bash
python3 -m unittest discover -s tests
```
