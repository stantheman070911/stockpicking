# Taiwan Equity Stock-Picking System

AI-assisted Taiwan equity screening, memo preparation, and batch ranking built on deterministic toolkit outputs and explicit analyst workflow.

## Architecture

The screening process is organized as four parts:

1. `Industry / Macro`
2. `Company Quality`
3. `Setup / Entry`
4. `Synthesis`

The three workstreams run independently and feed a single synthesis checkpoint that records thesis, risks, position-sizing context, and manual requirements.

## Execution Paths

### Default executable path

- Runs end to end from `python run_top200_screen.py`
- Uses the datasets and functions available in the configured FinMind environment
- Does not fabricate unavailable checks
- Emits explicit states for every automated assessment:
  - `passed`
  - `failed`
  - `not_assessed`
  - `manual_review_required`

### Overlay and manual path

- Holds checks that are valuable but not available in the default executable path
- Uses one of:
  - `manual workflow`
  - `optional adapter`
  - `deferred scaffold`
- Keeps missing automation visible instead of silently dropping the finding

## Methodology Highlights

- Broker-branch `分點` is excluded from automated scoring.
- Convertible-bond review lives in the overlay/manual path.
- `景氣對策信號` is context, not executable timing logic.
- Setup logic uses daily data rather than tick or snapshot feeds.
- Position sizing is hybrid: Python computes mechanical caps and a sizing band, and the analyst supplies conviction.
- Correlation above `0.70` requires explicit justification rather than an automatic reject.
- Every final memo must make room for:
  - variant perception
  - invalidation
  - scenario EV framing
  - sell discipline
  - pre-mortem
  - management forensic
  - monitoring cadence
  - decision journal
  - post-mortem trigger

## Commands

Run the batch screen:

```bash
python run_top200_screen.py
```

Validate the environment:

```bash
python taiwan_equity_toolkit/validate_setup.py
```

Run a single-name demo:

```bash
python taiwan_equity_toolkit/full_screen_demo.py 2330
```

Run tests:

```bash
python3 -m unittest discover -s tests
```

## Output Contract

The main artifact is `screen_results.json`.

It contains:

- `schema_version`
- `top10`
- `all_ranked`
- `funnel`
- `removed_or_downgraded_signals`
- `metadata`

Each ranked name includes:

- composite score
- per-workstream status
- entry verdict
- thesis stub
- primary reason
- manual requirement count

## Data-Availability Handling

Unavailable or out-of-scope checks do not stay inside live score weights unless a defensible executable proxy exists.

The system responds to missing data with one of:

- `not_assessed`
- `manual_review_required`
- `warn-and-continue`

## Public Interfaces

Supported toolkit entry points:

- `triage.run(...)`
- `gate3.run(...)`
- `gate65.run(...)`
- `peers.compare(...)`
- `value_chain.analyze(...)`
- `memo.FullScreenMemo(...)`

Primary implementation modules:

- `taiwan_equity_toolkit/workstream_industry.py`
- `taiwan_equity_toolkit/workstream_company.py`
- `taiwan_equity_toolkit/workstream_setup.py`
- `taiwan_equity_toolkit/synthesis.py`

## Repo Map

- `Stock_Selection_Framework.md`: screening methodology
- `Taiwan_Equity_Agent_System_Prompt.md`: agent operating model
- `Finmind.md`: dataset reference and tokens
- `run_top200_screen.py`: batch screen entry point
- `taiwan_equity_toolkit/`: reusable toolkit
- `templates/`: manual workflow templates
