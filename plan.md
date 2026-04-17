# Taiwan Equity Stock-Selection — V2 Full Overhaul Implementation Plan

> **For agentic workers:** Implement this plan phase-by-phase. Each phase lists goal, files, tests, and success criteria. Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Track progress with TodoWrite once implementation begins.

**Goal:** Rebuild the Taiwan equity stock-selection system to reflect every finding in `report.md`, running end-to-end under real FinMind free-tier constraints, with a Version 2 architecture (three parallel workstreams + synthesis memo + sizing/journal/post-mortem infrastructure) that replaces the legacy sequential-gate design.

**Architecture:** Dual-path. **Path A (free-tier default)** runs end-to-end on free-tier FinMind datasets only and emits `passed` / `failed` / `not_assessed` / `manual_review_required` states with no silent failures. **Path B (premium/manual overlay)** preserves architectural hooks (adapters, manual checklists, memo scaffolds) for signals that are valuable but currently unavailable. CB data, broker-branch 分點, 景氣對策信號, tick/snapshot, and expert-network scuttlebutt are explicitly excluded from default scoring and represented as overlays.

**Tech Stack:** Python 3.9+, FinMind REST (free tier), `pandas`, `requests`, `asyncio`, `pytest`. No new external dependencies beyond the current three. YAML for curated data artifacts (supply-chain map, sector bias, governance red-flag patterns).

---

## Part 0 — Context

### Why this overhaul

`report.md` is a 36+ finding professional audit against the current sequential-gate framework. It identifies five largest structural voids:
1. **Variant perception** — framework asks for a thesis but no named counter-party error.
2. **Position sizing** — absent entirely; Druckenmiller/Soros: "70–80% of the equation."
3. **Sell-discipline taxonomy** — collapsed to invalidation criteria only; Freeman-Shor archetypes missing.
4. **Pre-mortem / decision journal / post-mortem** — no feedback loop.
5. **Management forensic** — Gate 2 moat check without proxy/DEF 14A, capital-allocation track record, candor test.

It calls to **replace the seven sequential gates with three concurrent workstreams + a written memo checkpoint**, compress the 17-item quick-disqualify to ~8–10 merged items, demote false-precision thresholds (0.85 correlation hard reject, CFO/NI ≥ 0.8 hard cutoff, 景氣對策信號 as timing), and add mandatory memo fields (variant perception, scenario EV, sizing, catalyst/milestone, invalidation, pre-mortem, exit archetype).

Simultaneously, the current code claims free-tier compatibility but silently calls five Backer/Sponsor-only endpoints: `TaiwanStockIndustryChain`, `TaiwanStockDispositionSecuritiesPeriod`, `TaiwanStockSuspended`, `TaiwanBusinessIndicator`, and all four CB datasets. Under real free-tier tokens these return HTTP 400 and the pipeline emits degraded scores without surfacing the data gap. This is the second reason for the overhaul.

### Decisions already made (user-confirmed, not open questions)

- **CB data**: remove from default scoring, keep as optional premium adapter + manual-review memo section.
- **Broker-branch 分點**: remove from default model entirely.
- **景氣對策信號**: remove from scoring and timing logic.
- **Tick / snapshot**: replace with daily data in default path.
- **Scenario EV / position sizing**: hybrid — Python computes mechanical caps (vol / liquidity / correlation / suggested band); analyst supplies conviction and variant-perception.
- **Scuttlebutt**: manual workflow + checklist + call-log template, not an API feature.
- **Premium-unavailable checks**: surface as `not_assessed` / `manual_review_required`, not hard fails.
- **Scoring**: reweight when a premium component is removed; no dead weights.
- **Module layout**: clean rebuild, delete old gate files.
- **Chain map**: curated `taiwan_supply_chain.yaml` + `TaiwanStockInfo.industry_category` fallback.
- **Backtesting**: deferred scaffold + validation harness (no historical replay).
- **Tokens**: keep hardcoded (user-confirmed).
- **Entry point**: `python run_top200_screen.py` must remain the default command.

---

## Part 1 — Requirements Matrix

Every finding in `report.md` is mapped below. **Implementation modes**: `automate` (code), `manual workflow` (checklist/template/memo field), `optional adapter` (premium hook, default returns `not_assessed`), `deferred scaffold` (spec written, code later). **Fallback behavior**: `hard fail`, `warn-and-continue`, `not_assessed`, `manual_review_required`.

### Matrix A — Process & Architecture

| # | Finding | Report § | Target Artifact | Data Source | Free-Tier? | Mode | Fallback | Tests | Docs |
|---|---|---|---|---|---|---|---|---|---|
| A1 | Replace 7 sequential gates with 3 parallel workstreams + memo checkpoint | §1 F.Line 1; §10 p.333 | `screen.py` (orchestrator), delete gate3/gate65/triage/peers/value_chain | None | Yes | automate | n/a | `test_screen_orchestrator.py`, `test_free_tier_regression.py` | README, CLAUDE.md, AGENTS.md, `docs/v2_architecture.md`, `Stock_Selection_Framework.md` |
| A2 | Industry direction becomes parallel input, not prerequisite gate | §3 Gate1 row p.81 | `workstream_a.py`; remove hardcoded G1 exclusion buckets from `run_top200_screen.py` | TaiwanStockInfo, curated supply-chain YAML, InterestRate, GovernmentBondsYield, CrudeOilPrices, TaiwanExchangeRate | Yes | automate | warn-and-continue | `test_workstream_a.py` | `Stock_Selection_Framework.md`, `AGENTS.md` |
| A3 | Compress 17-item quick-disqualify to 8–10 merged items | §1 F.Line 3; §7.6 | `mass_triage.py` (replaces triage.py), `config.py:TriageConfig` | Free-tier only | Yes | automate | hard fail (per check) | `test_mass_triage.py` | `Stock_Selection_Framework.md` |
| A4 | Automate triage against FinMind feeds | §7.7 p.244 | `mass_triage.py` | TaiwanStockPrice, TaiwanStockMonthRevenue, TaiwanStockFinancialStatements, TaiwanStockCapitalReductionReferencePrice, TaiwanStockDelisting | Yes | automate | hard fail | `test_mass_triage.py` | `taiwan_equity_toolkit/README.md` |
| A5 | Merge Gate 4 (Cross-Source) into Workstream A | §7.1 p.221 | `workstream_a.py` absorbs peer-revenue / institutional-alignment checks; delete `peers.py` | TaiwanStockMonthRevenue, TaiwanStockFinancialStatements, TaiwanStockInstitutionalInvestorsBuySell | Yes | automate | warn-and-continue | `test_workstream_a.py` | `Stock_Selection_Framework.md` |

### Matrix B — Workstream B (Company Quality)

| # | Finding | Report § | Target Artifact | Data Source | Free-Tier? | Mode | Fallback | Tests | Docs |
|---|---|---|---|---|---|---|---|---|---|
| B1 | Two-stage forensic: Stage 1 red-flag screen (10 items, 30–60 min), Stage 2 deep only if 2+ flags trigger | §5.3 p.150; §10 Workstream B | `workstream_b.py` (red_flag_screen + deep_forensic) | TaiwanStockFinancialStatements, BalanceSheet, CashFlow, MonthRevenue, News, Dividend, CapitalReduction | Yes | automate | per-check `not_assessed` if data missing | `test_workstream_b.py::test_two_stage_gating` | `Stock_Selection_Framework.md` |
| B2 | Downgrade CFO/NI ≥ 0.8 from hard reject to flag | §3 p.86; §5.3 | `workstream_b.py::red_flag_screen`, `config.py:WorkstreamBThresholds` | TaiwanStockFinancialStatements + CashFlow (Free) | Yes | automate | flag-only, never hard fail | `test_workstream_b.py::test_cfo_ni_flag_not_hardfail` | `Stock_Selection_Framework.md` |
| B3 | Add management forensic: proxy/DEF 14A, capital-allocation track record, candor test, insider trading, 董監質押比 | §5.7 p.166; §10 Add 7 Missing #2 | `templates/management_forensic_checklist.md`; `workstream_b.py::management_forensic_status` returns `manual_review_required` | SEC EDGAR (US), TWSE MOPS 董監質押 (free but scraped, out-of-scope for V2); free-tier FinMind has no director-share-pledging dataset | Partial — no automatable free-tier source for Taiwan 董監質押 | manual workflow + optional adapter | `manual_review_required` in default path | `test_workstream_b.py::test_management_forensic_default_manual` | `docs/manual_workflows.md`, template file |
| B4 | Add scuttlebutt / channel-check protocol with MNPI firewall | §5.8 p.170; §10 Add 7 Missing #5 | `templates/scuttlebutt_call_log.md`, `workstream_b.py::scuttlebutt_status` returns `manual_review_required` | Tegus/AlphaSense/Third Bridge (premium, out of scope) | No | manual workflow | `manual_review_required` | `test_workstream_b.py::test_scuttlebutt_default_manual` | `docs/manual_workflows.md`, template |
| B5 | Red-flag item: auditor change in past 3 years | §10 Workstream B | `workstream_b.py::red_flag_screen` | TaiwanStockNews (keyword scan) | Yes | automate | `not_assessed` if news fetch fails | `test_workstream_b.py::test_auditor_change_flag` | `Stock_Selection_Framework.md` |
| B6 | Red-flag item: director share pledging > 50% | §10 Workstream B | `workstream_b.py::red_flag_screen` | Not in free-tier FinMind | No | manual workflow + optional adapter | `manual_review_required` | `test_workstream_b.py::test_share_pledging_manual_review` | `docs/manual_workflows.md` |
| B7 | Red-flag item: cross-affiliate guarantees (背書保證) | §10 Workstream B | `workstream_b.py::red_flag_screen` | TaiwanStockNews keyword scan; not in structured FinMind data | Partial | automate (keyword) + manual confirm | `manual_review_required` on hit | `test_workstream_b.py::test_cross_affiliate_flag` | template |
| B8 | Red-flag item: related-party revenue > 30% | §10 Workstream B | `workstream_b.py::red_flag_screen` | Not in free-tier; requires 10-K note parsing | No | manual workflow | `manual_review_required` | `test_workstream_b.py::test_related_party_manual` | template |
| B9 | Red-flag item: debt maturity wall within 18 months | §10 Workstream B | `workstream_b.py::red_flag_screen` | TaiwanStockBalanceSheet (ST borrowings + LT borrowings) + interest coverage | Partial — maturity schedule not in free-tier; proxy via ST/LT split | automate with proxy + manual confirm | flag if proxy triggers, `manual_review_required` for maturity-schedule confirmation | `test_workstream_b.py::test_debt_wall_proxy` | `Stock_Selection_Framework.md` |
| B10 | Red-flag item: historical dilution > 15% over 3 years | §10 Workstream B | `workstream_b.py::red_flag_screen` | TaiwanStockCapitalReductionReferencePrice, TaiwanStockDividend (stock dividends), TaiwanStockParValueChange | Yes | automate | warn-and-continue if data gap | `test_workstream_b.py::test_dilution_flag` | `Stock_Selection_Framework.md` |
| B11 | Red-flag item: governance controversy / legal proceedings | §10 Workstream B | `workstream_b.py::red_flag_screen` | TaiwanStockNews + governance keyword list in `data/taiwan_governance_redflags.yaml` | Yes | automate | `not_assessed` on news failure | `test_workstream_b.py::test_governance_controversy` | data YAML + `docs/manual_workflows.md` |
| B12 | Reverse-DCF as valuation backbone (Mauboussin/Rappaport) | §4.1 p.113; §10 Workstream B | Keep `metrics.py::reverse_dcf_implied_growth`; wire into `workstream_b.py::valuation_panel` | TaiwanStockPER, TaiwanStockFinancialStatements, TaiwanStockCashFlowsStatement, market cap (derived from price × shares_outstanding since `TaiwanStockMarketValue` is premium) | Yes (derived) | automate | warn-and-continue | `test_workstream_b.py::test_reverse_dcf_populates` | `docs/v2_architecture.md` |

### Matrix C — Workstream C (Setup / Positioning / Entry)

| # | Finding | Report § | Target Artifact | Data Source | Free-Tier? | Mode | Fallback | Tests | Docs |
|---|---|---|---|---|---|---|---|---|---|
| C1 | TXO open-interest PCR conditional overlay | §3 p.88; §6.4 | `workstream_c.py::txo_pcr_signal` | TaiwanOptionDaily (TXO), TaiwanOptionInstitutionalInvestors | Yes | automate | warn-and-continue | `test_workstream_c.py::test_txo_pcr` | `Stock_Selection_Framework.md` |
| C2 | Foreign institutional flow + SBL as primary ownership signals | §3 p.87; §1.5 | `workstream_c.py::ownership_panel` | TaiwanStockInstitutionalInvestorsBuySell, TaiwanStockShareholding, TaiwanStockSecuritiesLending, TaiwanDailyShortSaleBalances, TaiwanStockMarginPurchaseShortSale | Yes | automate | `not_assessed` per missing field | `test_workstream_c.py::test_ownership_panel` | `Stock_Selection_Framework.md` |
| C3 | Demote 分點 to supplementary context only | §7.3 p.227 | `adapters/premium.py::broker_branch_adapter` returns `not_assessed` by default | TaiwanStockTradingDailyReport (Sponsor) | No | optional adapter | `not_assessed` | `test_premium_adapters.py::test_broker_branch_default_not_assessed` | `docs/premium_adapters.md` |
| C4 | Demote 0.85 correlation hard reject → "document and justify if >0.7" | §5.10 p.178; §7.5 p.233 | `workstream_c.py::correlation_panel`, `portfolio_dashboard.py`; no hard reject | TaiwanStockPriceAdj (candidate + existing book) | Yes | automate | warn-and-continue (documents, never rejects) | `test_workstream_c.py::test_correlation_documents_not_rejects` | `Stock_Selection_Framework.md` |
| C5 | Demote 景氣對策信號: remove from scoring and timing | §5.11 p.182; §7.4 p.230 | Remove from `workstream_a.py` scoring; `adapters/premium.py::business_indicator_adapter` returns `not_assessed` | TaiwanBusinessIndicator (Backer/Sponsor) | No | optional adapter | `not_assessed`; substitute macro backdrop via free-tier global PMI/curve/oil | `test_premium_adapters.py::test_business_indicator_default_not_assessed`, `test_workstream_a.py::test_macro_backdrop_substitute` | `docs/premium_adapters.md` |
| C6 | Keep Gate 6.5 entry separation (valuation / vol / liquidity / crowding) | §4.1 p.113 | `workstream_c.py::entry_panel` | TaiwanStockPER, TaiwanStockPriceAdj, TaiwanStockPrice, TaiwanStockPriceLimit, TaiwanStockMarginPurchaseShortSale | Yes | automate | `not_assessed` per missing | `test_workstream_c.py::test_entry_panel` | `Stock_Selection_Framework.md` |
| C7 | CB dilution / CBAS flow (Taiwan-specific edge) — preserve as overlay | §6.4 p.208; §1.6 | `adapters/premium.py::cb_adapter` default `not_assessed`; memo section `templates/cb_manual_review.md` for public-disclosure tracking | TaiwanStockConvertibleBond* (all 4 Backer/Sponsor) | No | optional adapter + manual workflow | `not_assessed` | `test_premium_adapters.py::test_cb_default_not_assessed` | `docs/premium_adapters.md`, template |
| C8 | TSMC-anchor monthly revenue integration | §6.5 p.211 | `workstream_a.py::tsmc_anchor_signal`; fold monthly revenue of 2330 + supply-chain peers | TaiwanStockMonthRevenue | Yes | automate | warn-and-continue | `test_workstream_a.py::test_tsmc_anchor` | `Stock_Selection_Framework.md` |

### Matrix D — Memo Synthesis & Mandatory Bottom Panel

| # | Finding | Report § | Target Artifact | Data Source | Free-Tier? | Mode | Fallback | Tests | Docs |
|---|---|---|---|---|---|---|---|---|---|
| D1 | Variant Perception mandatory memo field ("market expects X; I believe Y; gap = [type]") | §5.6 p.162; §10 Add 7 Missing #1 | `synthesis.py::MemoV2.variant_perception`, `templates/variant_perception.md`; synthesis rejects memo lacking this field | Analyst input | n/a | manual workflow (enforced by schema) | `manual_review_required` if empty at submission | `test_synthesis.py::test_memo_requires_variant_perception` | template, `docs/v2_architecture.md` |
| D2 | Scenario EV replaces single-point target | §10 Add 7 Missing #4 | `synthesis.py::MemoV2.scenario_ev`, `templates/scenario_ev.md`, computes weighted IRR | Analyst input + computed weighted IRR | n/a | manual workflow + auto-calc of weighted EV | `manual_review_required` if any scenario missing | `test_synthesis.py::test_scenario_ev_weighted` | template |
| D3 | Position sizing memo field tied to conviction + mechanical caps | §5.4 p.154; §10 Add 7 Missing #3 | `sizing.py` (mechanical caps) + `synthesis.py::MemoV2.sizing`, `templates/position_sizing.md` | TaiwanStockPriceAdj (vol), TaiwanStockPrice (ADV), existing-book correlation | Yes (mechanical) | automate (caps) + manual workflow (conviction tier) | `manual_review_required` if conviction blank; caps always computed | `test_sizing.py` (vol cap / liquidity cap / correlation cap / suggested band) | template, `docs/v2_architecture.md` |
| D4 | Mode-conditional catalyst (dated) vs. milestone (observable) | §3 p.92; §7.8 p.245 | `synthesis.py::MemoV2.catalyst_or_milestone`, `templates/catalyst_path.md` with mode toggle | Analyst input | n/a | manual workflow | `manual_review_required` if empty | `test_synthesis.py::test_mode_conditional_catalyst` | template |
| D5 | Written invalidation criteria (existing strength — retain) | §4.2 p.116; §10 | `synthesis.py::MemoV2.invalidation` — already in v1 memo | Analyst input | n/a | manual workflow | `manual_review_required` if empty | `test_synthesis.py::test_invalidation_required` | template |
| D6 | Pre-mortem (Klein) — 20–30 min before entry | §5.9 p.174; §10 Add 7 Missing #6 | `journal.py::PreMortem`, `templates/pre_mortem.md` | Analyst input | n/a | manual workflow | `manual_review_required` if empty | `test_journal.py::test_pre_mortem_required` | template, `docs/manual_workflows.md` |
| D7 | Exit archetype pre-commit (Assassin/Hunter/Connoisseur) + forced −20% review trigger | §5.5 p.158; §10 Add 7 Missing #7 | `sell_discipline.py::ExitArchetype`, `templates/sell_discipline.md` | Analyst input + mechanical −20% trigger | n/a | manual workflow + automated trigger | `manual_review_required` if archetype unchosen | `test_sell_discipline.py::test_archetype_required`, `test_sell_discipline.py::test_drawdown_trigger` | template |

### Matrix E — Infrastructure: Journaling, Monitoring, Post-Mortem, Portfolio Dashboard

| # | Finding | Report § | Target Artifact | Data Source | Free-Tier? | Mode | Fallback | Tests | Docs |
|---|---|---|---|---|---|---|---|---|---|
| E1 | Decision journal — one page per position at entry | §5.9 p.174; §10 | `journal.py::DecisionJournal`, `templates/decision_journal.md` | Analyst input | n/a | manual workflow | n/a | `test_journal.py::test_decision_journal_render` | template |
| E2 | Post-mortem at exit — separate decision quality from outcome | §5.9 p.174; §10 | `journal.py::PostMortem`, `templates/post_mortem.md` | Analyst input | n/a | manual workflow | n/a | `test_journal.py::test_post_mortem_render` | template |
| E3 | Live portfolio dashboard (not a gate) — sector/factor/correlation/beta continuous monitor | §10 Infrastructure | `portfolio_dashboard.py` renders JSON + markdown view | TaiwanStockPriceAdj (book correlation), TaiwanStockInfo.industry_category (sector), book snapshot | Yes | automate | warn-and-continue per missing | `test_portfolio_dashboard.py` | `docs/v2_architecture.md` |
| E4 | Monitoring cadence — weekly (tactical) / quarterly (compounder) | §10 Infrastructure | Documented in memo + journal templates; `synthesis.py::MemoV2.monitoring_cadence` | Analyst mode selection | n/a | manual workflow | n/a | `test_synthesis.py::test_monitoring_cadence_set` | template, `docs/manual_workflows.md` |

### Matrix F — Premium Overlay & Deferred Scaffolds

| # | Finding | Report § | Target Artifact | Data Source | Free-Tier? | Mode | Fallback | Tests | Docs |
|---|---|---|---|---|---|---|---|---|---|
| F1 | CB adapter (possible future public-disclosure integration) | §6.4 | `adapters/premium.py::cb_adapter` | TWSE public disclosures (out of scope) or FinMind Backer | No | optional adapter | `not_assessed` | `test_premium_adapters.py` | `docs/premium_adapters.md` |
| F2 | Broker-branch 分點 adapter | §1.5 | `adapters/premium.py::broker_branch_adapter` | TaiwanStockTradingDailyReport (Sponsor) | No | optional adapter | `not_assessed` | `test_premium_adapters.py` | `docs/premium_adapters.md` |
| F3 | National team / government bank adapter | Framework §3C p.205 | `adapters/premium.py::government_bank_adapter` | TaiwanstockGovernmentBankBuySell (Sponsor) | No | optional adapter | `not_assessed` | `test_premium_adapters.py` | `docs/premium_adapters.md` |
| F4 | 景氣對策信號 adapter | §5.11 | `adapters/premium.py::business_indicator_adapter` | TaiwanBusinessIndicator (Backer/Sponsor) | No | optional adapter | `not_assessed` | `test_premium_adapters.py` | `docs/premium_adapters.md` |
| F5 | Tick / minute-K adapter | Framework §6.5C | `adapters/premium.py::tick_adapter` | TaiwanStockPriceTick / TaiwanStockKBar (Sponsor) | No | optional adapter | `not_assessed` (daily-data substitute in default) | `test_premium_adapters.py` | `docs/premium_adapters.md` |
| F6 | Large-trader open interest adapter | Framework §3D | `adapters/premium.py::large_trader_oi_adapter` | TaiwanFutures/OptionOpenInterestLargeTraders (Backer/Sponsor) | No | optional adapter | `not_assessed` | `test_premium_adapters.py` | `docs/premium_adapters.md` |
| F7 | TaiwanStockIndustryChain adapter (premium source of truth) | §10 Workstream A | `adapters/premium.py::industry_chain_adapter` | TaiwanStockIndustryChain (Backer/Sponsor); default fallback to curated YAML | No | optional adapter | curated YAML fallback (never `not_assessed` — we always have chain data) | `test_premium_adapters.py::test_industry_chain_falls_back_to_yaml` | `docs/premium_adapters.md` |
| F8 | Full backtesting with point-in-time fundamentals | §9 p.278 | `docs/backtesting_deferred_scaffold.md` + `tests/test_point_in_time_guard.py` (look-ahead bias guard only) | TEJ / Compustat / CRSP (out of scope) | No | deferred scaffold | n/a (no backtest runs) | look-ahead guard test present | `docs/backtesting_deferred_scaffold.md` |

### Matrix Summary

| Mode | Count |
|---|---|
| automate | 18 findings |
| manual workflow | 13 findings |
| optional adapter | 8 findings |
| deferred scaffold | 1 finding |
| **Total distinct findings covered** | **40** (includes 10 KEEP items + 8 IMPROVE + 10 ADD NEW critical/high + 2 REMOVE + 2 COMPRESS + 4 DOWNGRADE + 4 supporting infrastructure) |

Every finding enumerated in the Explore agent's report has a row above. If the engineer finds a finding with no row, stop and revise the matrix before coding.

---

## Part 2 — V2 Target Architecture

### Module layout (final state)

```
stockpicking/
├── run_top200_screen.py                    # REWRITTEN: thin CLI shim that invokes V2 orchestrator
├── README.md                                # REWRITTEN
├── CLAUDE.md                                # UPDATED
├── AGENTS.md                                # UPDATED
├── Stock_Selection_Framework.md             # REWRITTEN as V2 spec
├── Taiwan_Equity_Agent_System_Prompt.md     # UPDATED (no sequential gates; three workstreams)
├── Finmind.md                               # UPDATED with free-tier emphasis
├── report.md                                # UNTOUCHED (research input)
│
├── data/
│   ├── taiex_top200_snapshot.json           # KEPT
│   ├── taiwan_supply_chain.yaml             # NEW: curated chain map
│   ├── taiwan_governance_redflags.yaml      # NEW: keyword patterns (Rebar/Procomp style)
│   └── templates/                            # NEW (or docs/templates — one of the two)
│       ├── variant_perception.md
│       ├── scenario_ev.md
│       ├── position_sizing.md
│       ├── catalyst_path.md
│       ├── invalidation.md
│       ├── pre_mortem.md
│       ├── decision_journal.md
│       ├── post_mortem.md
│       ├── sell_discipline.md
│       ├── management_forensic_checklist.md
│       ├── scuttlebutt_call_log.md
│       ├── red_flag_screen.md
│       └── cb_manual_review.md
│
├── docs/
│   ├── v2_architecture.md                   # NEW: workstream topology, memo panel, sizing
│   ├── free_tier_policy.md                  # NEW: what runs under free tier; caveats
│   ├── premium_adapters.md                  # NEW: how Path B adapters plug in
│   ├── manual_workflows.md                  # NEW: scuttlebutt, management forensic, memo fields
│   ├── migration_from_v1.md                 # NEW: what changed, how to read old output
│   └── backtesting_deferred_scaffold.md     # NEW: PIT policy, what's deferred, why
│
├── taiwan_equity_toolkit/
│   ├── __init__.py                          # EXPORTS updated — clean API surface
│   ├── README.md                            # REWRITTEN: module reference for V2
│   │
│   ├── config.py                            # EXPANDED: FreeTierPolicy, V2 weights, SizingCaps, SellDiscipline, MacroContext
│   ├── states.py                            # NEW: Status enum + helpers (passed/failed/not_assessed/manual_review_required)
│   ├── client.py                            # UPDATED: premium-dataset detection, no silent 400 failures, emits NotAssessed
│   ├── parsers.py                           # KEPT as-is (it works)
│   ├── metrics.py                           # KEPT + extended (all Metric discipline retained)
│   │
│   ├── universe.py                          # NEW: fetch_live_universe + snapshot + sector-bias optional tilt
│   ├── mass_triage.py                       # NEW: replaces triage.py — 8 merged automatable checks
│   │
│   ├── workstream_a.py                      # NEW: industry/macro — sector tailwind, supply-chain lead/lag, TSMC anchor, peer-rev+institutional merged from ex-Gate 4
│   ├── workstream_b.py                      # NEW: company quality — two-stage (red-flag screen → deep forensic), reverse-DCF, management forensic status, scuttlebutt status
│   ├── workstream_c.py                      # NEW: setup/positioning/entry — ownership panel, TXO PCR, entry panel (val/vol/liq/crowding), correlation documentation
│   │
│   ├── synthesis.py                         # NEW: MemoV2 with mandatory bottom panel (variant perception, scenario EV, sizing, catalyst/milestone, invalidation, pre-mortem, exit archetype)
│   ├── sizing.py                            # NEW: mechanical caps (vol, liquidity, correlation, suggested band); analyst supplies conviction
│   ├── sell_discipline.py                   # NEW: Freeman-Shor archetypes + −20% review trigger
│   ├── journal.py                           # NEW: PreMortem, DecisionJournal, PostMortem templates + renderers
│   ├── portfolio_dashboard.py               # NEW: live sector/factor/correlation/beta exposure view
│   │
│   ├── adapters/
│   │   ├── __init__.py
│   │   └── premium.py                       # NEW: CB, broker-branch, govt-bank, business-indicator, tick, large-trader-OI, industry-chain adapters — default not_assessed (industry-chain falls back to YAML)
│   │
│   ├── screen.py                            # NEW: orchestrator — universe → mass_triage → (WS A ∥ WS B ∥ WS C concurrent) → synthesis memo per survivor
│   ├── full_screen_demo.py                  # REWRITTEN: single-stock V2 demo
│   └── validate_setup.py                    # UPDATED: checks free-tier endpoints, flags any premium usage
│
└── tests/
    ├── __init__.py
    ├── conftest.py                          # NEW: shared mock-FinMind fixtures, pinned snapshot date
    ├── test_run_top200_screen.py            # UPDATED: entry-point compatibility
    ├── test_states.py                       # NEW
    ├── test_client_premium_detection.py     # NEW
    ├── test_universe.py                     # NEW
    ├── test_mass_triage.py                  # REPLACES test_triage.py
    ├── test_workstream_a.py                 # NEW
    ├── test_workstream_b.py                 # REPLACES test_gate3.py
    ├── test_workstream_c.py                 # NEW
    ├── test_synthesis.py                    # NEW
    ├── test_sizing.py                       # NEW
    ├── test_sell_discipline.py              # NEW
    ├── test_journal.py                      # NEW
    ├── test_portfolio_dashboard.py          # NEW
    ├── test_premium_adapters.py             # NEW
    ├── test_free_tier_regression.py         # NEW: end-to-end smoke test with mocked free-tier responses
    ├── test_point_in_time_guard.py          # NEW: no future-dated reads
    ├── test_metrics.py                      # KEPT + expanded
    ├── test_value_chain.py                  # DELETE (logic merged into workstream_a)
    ├── test_gate3.py                        # DELETE
    └── test_validate_setup.py               # UPDATED
```

### Data flow (Path A — free-tier default)

```
run_top200_screen.py
    └─ taiwan_equity_toolkit.screen.run_screen()
        │
        ├─ universe.build_universe()              [live TAIFEX → snapshot fallback]
        │
        ├─ universe.apply_sector_tilt()           [optional analyst bias from config; does NOT hard-exclude]
        │
        ├─ mass_triage.run_all()                  [parallel, 8 checks, free-tier only]
        │      each stock → TriageResult { status: passed|failed, checks[] }
        │
        ├─ for each triage passer: RUN CONCURRENTLY
        │      ├─ workstream_a.run(stock_id)     → WorkstreamAResult
        │      ├─ workstream_b.run(stock_id)     → WorkstreamBResult (two-stage)
        │      └─ workstream_c.run(stock_id)     → WorkstreamCResult
        │
        ├─ synthesis.build_memo(a, b, c)         → MemoV2
        │      bottom panel fields are stubbed as manual_review_required until analyst fills
        │
        ├─ sizing.compute_caps(stock_id, book)   → SizingCaps (mechanical)
        │
        ├─ portfolio_dashboard.snapshot(book)    → DashboardView (independent of screen run)
        │
        └─ emit: screen_results.json + per-name MemoV2 markdown stubs
```

### State vocabulary (applied everywhere)

```python
class Status(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_ASSESSED = "not_assessed"                    # data unavailable (premium or fetch error)
    MANUAL_REVIEW_REQUIRED = "manual_review_required" # analyst input expected
```

Every `WorkstreamResult`, `TriageCheck`, `MemoV2` field, and `AdapterResult` carries a `status: Status`. Output JSON never uses implicit/empty or boolean states for gate-like decisions.

### Backward compatibility

- `python run_top200_screen.py` remains the default command; output file remains `screen_results.json`.
- Top-level JSON keys **added**: `workstream_a`, `workstream_b`, `workstream_c`, `synthesis_memos`, `portfolio_dashboard`, `premium_adapters_status`.
- Top-level JSON keys **removed**: `gate1_rejects`, `gate3_details`, `gate4_failures`, `gate5_failures`, `triage_failures` (replaced by `mass_triage_failures` with the new check names).
- Migration notes in `docs/migration_from_v1.md` map every removed key to its V2 equivalent.

---

## Part 3 — Phased Implementation Plan

Each phase below specifies: **goal**, **tasks** (checkbox steps), **files touched**, **dependencies** (which earlier phases must be complete), **risks**, **deliverables**, and **success criteria**. Commit at the end of each task group. Run the full test suite after each phase.

### Phase 0 — Foundation (cutover preparation, no deletion yet)

**Goal:** Lock the state vocabulary and expanded config so all downstream modules share a single target type system. No deletion of old modules yet — only additions.

**Dependencies:** None.

**Tasks:**
- [ ] **0.1** Create `taiwan_equity_toolkit/states.py` with `Status` enum, `StatusedResult` base dataclass, and helper `combine_statuses(...)` (worst-case merge).
- [ ] **0.2** Extend `taiwan_equity_toolkit/config.py`: add `FreeTierPolicy`, `WorkstreamBThresholds` (red-flag screen cutoffs), `WorkstreamBScoreWeights` (replaces `Gate3Weights` — to be deleted in Phase 5), `WorkstreamCConfig`, `SizingCaps` (vol cap %, liquidity cap % of ADV, correlation cap, suggested band bounds), `SellDisciplineArchetypes` (Assassin/Hunter/Connoisseur defaults), `MacroContextConfig`, `PREMIUM_DATASETS` frozen set. **Do not yet remove** `Gate3Weights` / `Gate3Thresholds` / `Gate65Config` / `TriageConfig` — they stay until their consumers are deleted in later phases.
- [ ] **0.3** Update `taiwan_equity_toolkit/client.py`: add `is_premium(dataset_name: str) -> bool` using `PREMIUM_DATASETS`; change `get()` to raise `PremiumDatasetRequired` (new exception, subclass of `FinMindError`) **before** the HTTP call if the dataset is premium and the active token is free-tier. Consumers catch and emit `Status.NOT_ASSESSED`. (Silent HTTP 400 failures stop here.)
- [ ] **0.4** Write `tests/test_states.py` covering enum values, `combine_statuses` precedence (failed > manual_review_required > not_assessed > passed).
- [ ] **0.5** Write `tests/test_client_premium_detection.py` covering: premium dataset raises `PremiumDatasetRequired`; free-tier dataset passes through; `is_premium` correctly identifies all 10+ known premium datasets.
- [ ] **0.6** Run `python -m pytest tests/test_states.py tests/test_client_premium_detection.py -v`. Expected: all new tests pass; existing tests still pass.
- [ ] **0.7** Commit: `feat: add Status vocabulary and premium-dataset detection (Phase 0)`.

**Files:** `taiwan_equity_toolkit/states.py` (NEW), `taiwan_equity_toolkit/config.py` (EDIT), `taiwan_equity_toolkit/client.py` (EDIT), `tests/test_states.py` (NEW), `tests/test_client_premium_detection.py` (NEW).

**Risks:** Existing `gate3.py` / `triage.py` / etc. still use old config types. Config additions must be **additive only** this phase to avoid cascade breakage. Mitigation: do not touch existing `Gate3Weights` etc. until their consumers die.

**Deliverables:** Status vocab live; premium detection surfaces data gaps.

**Success criteria:**
- All new tests pass.
- All pre-existing tests still pass (verifies additive-only discipline).
- `FinMindClient.get("TaiwanStockIndustryChain", "2330")` now raises `PremiumDatasetRequired` instead of HTTP 400.

---

### Phase 1 — Curated Data Artifacts

**Goal:** Ship the curated supply-chain map and governance red-flag keyword list that Path A depends on in place of premium FinMind sources.

**Dependencies:** Phase 0.

**Tasks:**
- [ ] **1.1** Create `data/taiwan_supply_chain.yaml`. Content: hierarchical chain map derived from existing `INDUSTRY_ANCHORS` in `config.py` plus the semiconductor supply-chain anchors already referenced in `Taiwan_Equity_Agent_System_Prompt.md` line 190 (foundry 2330/2303/6770 → IDM → OSAT 2308/3711/6239/2449 → IC design 2454/3034/3443 → equipment → ODM/OEM 2317/2382/3231/2324; plus financials 2881/2882/2884/2886 and discretionary sectors). Shape: `{cluster: {sub_cluster: [stock_id]}}` with bidirectional `upstream`/`downstream` arrows per cluster. Ship with `as_of` date field. Exact content below in Deliverable.
- [ ] **1.2** Create `data/taiwan_governance_redflags.yaml` — keyword patterns for the News scan in Workstream B. Include Rebar-style / Procomp-style precedent keywords: 質押 (pledging), 背書保證 (cross-affiliate guarantee), 關係人交易 (related-party), 更換會計師 (auditor change), 重編 (restatement), 繼續經營 (going concern), 解散 (dissolution), 停止交易 (trading halt), 聲請重整 (reorganization), 掏空 (embezzlement), 內線交易 (insider trading), 財報不實 (financial-statement fraud). Include English fallbacks.
- [ ] **1.3** Create `data/templates/` directory with empty (but structured) markdown templates for each memo field. Files: `variant_perception.md`, `scenario_ev.md`, `position_sizing.md`, `catalyst_path.md`, `invalidation.md`, `pre_mortem.md`, `decision_journal.md`, `post_mortem.md`, `sell_discipline.md`, `management_forensic_checklist.md`, `scuttlebutt_call_log.md`, `red_flag_screen.md`, `cb_manual_review.md`. Each template must include: purpose header, required fields (marked `<<REQUIRED>>`), guidance, example. `variant_perception.md` must explicitly require: market expectation, analyst thesis, error type {behavioral / analytical / informational / technical}, evidence gap.
- [ ] **1.4** Write `tests/test_curated_data.py`: YAML files parse; every `INDUSTRY_ANCHORS` stock appears somewhere in `taiwan_supply_chain.yaml`; every template has `<<REQUIRED>>` markers parseable; governance keyword YAML has ≥ 12 patterns.
- [ ] **1.5** Run tests; commit: `feat: add curated supply-chain, governance keywords, memo templates (Phase 1)`.

**Files:** `data/taiwan_supply_chain.yaml` (NEW), `data/taiwan_governance_redflags.yaml` (NEW), `data/templates/*.md` (NEW), `tests/test_curated_data.py` (NEW).

**Risks:** The curated supply-chain map is an editorial artifact — misclassification is possible. Mitigation: document `as_of` + source; make it replaceable via premium `TaiwanStockIndustryChain` adapter in Phase 10.

**Deliverables:** `data/` gains 3 YAML/directory artifacts; templates installed.

**Success criteria:**
- YAML parses without error.
- Every stock in `INDUSTRY_ANCHORS` is reachable via the new chain map.
- Tests pass.

---

### Phase 2 — Universe & Mass Triage (replaces `triage.py`)

**Goal:** Build the compressed 8-check mass triage on free-tier data only, behind the new universe builder. Then delete `triage.py`. Gate 1's hardcoded exclusion buckets move out of `run_top200_screen.py` into an optional sector tilt (not a hard gate).

**Dependencies:** Phase 0 (states), Phase 1 (YAML is nice-to-have but not required here).

**Tasks:**
- [ ] **2.1** Create `taiwan_equity_toolkit/universe.py`. Move `fetch_live_universe()`, `load_snapshot_universe()`, `_parse_taifex_top200_from_table()`, `_validate_universe()`, `_normalize_stock_ids()` from `run_top200_screen.py`. Add `apply_sector_tilt(universe, tilt_config) -> tuple[list, dict]` that applies the OLD Gate 1 exclusion buckets + favor IDs **only if explicitly enabled in config** — default is no tilt (pure passthrough). Returns `(tilted_universe, tilt_notes)` where `tilt_notes` is annotative, not a rejection.
- [ ] **2.2** Create `taiwan_equity_toolkit/mass_triage.py`. Compress the 17 quick-disqualify items into the 8 merged buckets from report §7.6:
    1. **Tradability** = liquidity (ADV ≥ NT$50M) + free float + position-vs-ADV cap. Free-tier: `TaiwanStockPrice`.
    2. **Active trading** = not delisted + not on disposition. Uses `TaiwanStockDelisting` (free). `TaiwanStockDispositionSecuritiesPeriod` is premium → falls back to `Status.NOT_ASSESSED` with warning note, **does not hard-fail**.
    3. **Survival risk** = monthly revenue YoY > −30% (unless short thesis) + no persistent cash burn proxy. Free-tier.
    4. **Data freshness** = latest financial statement ≤ 135 days old. Free-tier.
    5. **Corporate-action cleanliness** = no unexplained capital reduction / par-value change / split in past 24 months. Free-tier.
    6. **Basic governance** = News scan for 掏空 / 解散 / 停止交易 / 聲請重整 keywords (from Phase 1 YAML). Free-tier.
    7. **Business parse** = `TaiwanStockInfo` returns category (sanity check that name is tradable equity, not warrant/ETF-leveraged). Free-tier.
    8. **Single-name exposure prep** = intended position ≤ 10% of ADV (retained from v1).
    
    Emit `MassTriageResult(stock_id, status, checks[], adv_ntd, notes[])`. A stock is `failed` only if at least one automatable check hard-fails. Premium-dependent checks that can't run emit `not_assessed` at the check level but do **not** cause the stock to fail overall.
- [ ] **2.3** Write `tests/test_universe.py` and `tests/test_mass_triage.py` covering each of the 8 checks + the premium-fallback behavior (disposition check → `not_assessed`, stock still passes).
- [ ] **2.4** Run `pytest tests/test_universe.py tests/test_mass_triage.py -v`.
- [ ] **2.5** Commit: `feat: universe and mass_triage (Phase 2.a)`.
- [ ] **2.6** Update `run_top200_screen.py` to import universe/mass_triage instead of the old `build_universe()` + `run_mass_triage()` locals. Keep old code paths around temporarily (wired to new modules) to avoid breaking the orchestrator.
- [ ] **2.7** Run existing test suite. Expect: `test_run_top200_screen.py` still passes with new mass_triage wiring. Fix any breakage.
- [ ] **2.8** DELETE `taiwan_equity_toolkit/triage.py` and `tests/test_triage.py`. Grep the repo for any lingering imports; the only expected importer is the now-updated `run_top200_screen.py`.
- [ ] **2.9** Run full test suite. Commit: `refactor: delete legacy triage module (Phase 2.b)`.

**Files:** `taiwan_equity_toolkit/universe.py` (NEW), `taiwan_equity_toolkit/mass_triage.py` (NEW), `run_top200_screen.py` (EDIT), `tests/test_universe.py` (NEW), `tests/test_mass_triage.py` (NEW), `taiwan_equity_toolkit/triage.py` (DELETE), `tests/test_triage.py` (DELETE).

**Risks:** `run_top200_screen.py` imports `triage` at module scope — deleting without updating would break the whole file. Mitigation: the task sequence re-wires imports **before** deletion (2.6 → 2.8).

**Deliverables:** 8-check mass triage running on free-tier only; Gate 1 hardcoded bias moved to optional tilt.

**Success criteria:**
- `python run_top200_screen.py` still executes end-to-end (using new mass_triage).
- `screen_results.json` still produced (schema may change in later phases).
- No HTTP 400 errors logged from the triage stage.

---

### Phase 3 — Workstream A: Industry / Macro (absorbs ex-Gate 4 and Gate 5)

**Goal:** Build the industry-macro workstream — sector tailwind, supply-chain lead/lag (from YAML, falling back to TaiwanStockInfo.industry_category), TSMC-anchor monthly revenue, peer institutional alignment, macro backdrop (global PMI via US curve + crude oil + TWD). 景氣對策信號 **not** used. Delete `value_chain.py` and `peers.py`.

**Dependencies:** Phase 0, Phase 1 (needs YAML), Phase 2 (mass_triage must be gone).

**Tasks:**
- [ ] **3.1** Create `taiwan_equity_toolkit/workstream_a.py` with public `run(client, stock_id, context=None) -> WorkstreamAResult`. Internal panels:
    - `sector_tailwind_panel()` — reads `TaiwanStockMonthRevenue` for stock + peers from YAML chain map; computes 3m/12m revenue YoY for the chain cluster.
    - `value_chain_position_panel()` — looks up stock in `taiwan_supply_chain.yaml`, returns `upstream_peers` + `downstream_peers` + `cluster`. If not found, falls back to `TaiwanStockInfo.industry_category` clustering (free).
    - `tsmc_anchor_signal()` — fetches 2330 monthly revenue YoY, reports as a separate indicator for semiconductor-adjacent names.
    - `peer_alignment_panel()` — async batch across up to 6 chain peers: revenue YoY, gross margin, institutional net flow 60d. This absorbs ex-Gate 4 cross-source validation and ex-Gate 5 upstream signals into one panel.
    - `macro_backdrop_panel()` — fetches `InterestRate(FED)`, `GovernmentBondsYield(UST 10Y / 2Y spread)`, `CrudeOilPrices(WTI)`, `TaiwanExchangeRate(USD)`. 景氣對策信號 **not fetched**. Attempted via premium adapter in Phase 10.
- [ ] **3.2** `WorkstreamAResult` dataclass: `{stock_id, status, cluster, sector_signal, chain_position, tsmc_anchor, peer_alignment, macro_backdrop, notes[]}`. `status` is computed from the panels — `passed` if sector signal is neutral-or-positive AND chain position resolves AND no macro red flag; `failed` is rare here (this workstream is informational, not a hard gate). Most failures collapse to `manual_review_required` where an analyst overlay decides.
- [ ] **3.3** Write `tests/test_workstream_a.py` — each panel, YAML lookup + fallback, macro backdrop composition, premium-dataset fallback (no 景氣對策信號 call, no industry-chain call).
- [ ] **3.4** Wire `workstream_a.run()` into `run_top200_screen.py` in place of the current `run_gate4_batch` / `run_gate5_batch` calls. Keep output intermediate for now.
- [ ] **3.5** Run test suite + `python run_top200_screen.py` against the real free-tier token. Verify no premium-dataset errors.
- [ ] **3.6** DELETE `taiwan_equity_toolkit/peers.py`, `taiwan_equity_toolkit/value_chain.py`, `tests/test_value_chain.py`. Grep for any lingering imports outside the already-updated `run_top200_screen.py`; `full_screen_demo.py` may still import them — update it to use workstream_a.
- [ ] **3.7** Commit: `feat: workstream A + delete peers/value_chain (Phase 3)`.

**Files:** `taiwan_equity_toolkit/workstream_a.py` (NEW), `tests/test_workstream_a.py` (NEW), `run_top200_screen.py` (EDIT), `taiwan_equity_toolkit/full_screen_demo.py` (EDIT), `taiwan_equity_toolkit/peers.py` (DELETE), `taiwan_equity_toolkit/value_chain.py` (DELETE), `tests/test_value_chain.py` (DELETE).

**Risks:** The YAML chain map is editorial — names outside the semi cluster will not resolve. Mitigation: fallback to `TaiwanStockInfo.industry_category` guarantees every stock gets *some* clustering.

**Deliverables:** Workstream A fully functional on free-tier.

**Success criteria:**
- `python -m pytest tests/test_workstream_a.py -v` passes.
- A run of `python run_top200_screen.py` produces workstream_a output for every mass_triage passer.
- No premium-dataset calls originate from workstream_a (verify by grepping module for premium dataset names).

---

### Phase 4 — Workstream C: Setup / Positioning / Entry (replaces Gate 6.5)

**Goal:** Build the setup/positioning/entry workstream. Valuation & reverse-DCF sanity, volatility, liquidity, crowding, correlation documentation (no hard reject). TXO PCR conditional overlay. 分點 default `not_assessed`. Delete `gate65.py`.

**Dependencies:** Phase 0.

**Tasks:**
- [ ] **4.1** Create `taiwan_equity_toolkit/workstream_c.py`. Panels:
    - `ownership_panel()` — foreign flow (60d), institutional net flow by type, SBL utilization, margin/short structure, foreign ownership ratio vs. statutory limit.
    - `txo_pcr_panel()` — fetches `TaiwanOptionDaily` + `TaiwanOptionInstitutionalInvestors` for the matching options ID (if listed); returns `not_assessed` if no listed options.
    - `valuation_panel()` — `TaiwanStockPER` 5y percentile + reverse-DCF implied growth (calls `metrics.reverse_dcf_implied_growth`).
    - `volatility_panel()` — 30d + 90d realized vol, meme-threshold check.
    - `liquidity_panel()` — ADV check, price-limit regime.
    - `crowding_panel()` — margin balance trajectory 60d, short interest, disposition status (premium → `not_assessed`).
    - `correlation_panel(existing_book)` — reports correlation to each existing holding. **Does not reject.** Flags `manual_review_required` if > 0.7.
- [ ] **4.2** `WorkstreamCResult`: `{stock_id, status, panels{}, entry_recommendation, notes[]}`. `entry_recommendation ∈ {enter_now, stagger_scale_in, wait_for_setup, needs_review}`. Replace hard correlation reject with "needs_review".
- [ ] **4.3** Write `tests/test_workstream_c.py`: each panel, correlation documentation vs. rejection, TXO PCR fallback, disposition → `not_assessed`.
- [ ] **4.4** Wire into `run_top200_screen.py`. Keep intermediate.
- [ ] **4.5** DELETE `taiwan_equity_toolkit/gate65.py`; update `full_screen_demo.py`; run suite; commit.

**Files:** `taiwan_equity_toolkit/workstream_c.py` (NEW), `tests/test_workstream_c.py` (NEW), `run_top200_screen.py` (EDIT), `taiwan_equity_toolkit/full_screen_demo.py` (EDIT), `taiwan_equity_toolkit/gate65.py` (DELETE).

**Risks:** Existing `TaiwanStockPriceLimit` is free-tier with `data_id`; confirmed in Finmind.md. No new premium exposure.

**Deliverables:** Workstream C running on free-tier.

**Success criteria:**
- Tests pass.
- Correlation > 0.85 no longer hard-rejects — it surfaces `needs_review`.

---

### Phase 5 — Workstream B: Company Quality (replaces Gate 3)

**Goal:** Build the two-stage forensic — 10-item red-flag screen → deep forensic only if 2+ flags fire. CFO/NI becomes a flag, not hard reject. CB check removed from scoring. Management forensic + scuttlebutt surface `manual_review_required`. Delete `gate3.py`.

**Dependencies:** Phase 0, Phase 1 (needs governance YAML).

**Tasks:**
- [ ] **5.1** Create `taiwan_equity_toolkit/workstream_b.py::red_flag_screen(client, stock_id)`:
    1. CFO/NI < 0.8 for recent quarter → flag (not reject).
    2. Director share pledging > 50% → **manual_review_required** (no free-tier data).
    3. Cross-affiliate guarantees (背書保證) → News keyword scan → flag if matched; confirm manually.
    4. Auditor change in past 3 years → News keyword scan (更換會計師).
    5. Related-party revenue > 30% → **manual_review_required** (no free-tier data).
    6. Debt wall proxy: ST/LT ratio + interest coverage < 2x → flag.
    7. Historical dilution > 15% over 3 years → `TaiwanStockCapitalReductionReferencePrice` + stock dividends + par-value changes.
    8. Governance controversy → News scan against `data/taiwan_governance_redflags.yaml`.
    9. Auditor change also checked here as a composite.
    10. ROE trajectory collapsing over 3 years (operating quality early warning) → financial-statement derived.
    
    Emit `RedFlagScreenResult(flags[], trigger_count)`. If `trigger_count < 2` → skip deep forensic.
- [ ] **5.2** `workstream_b.py::deep_forensic(client, stock_id)` — only called when `trigger_count >= 2`. Full balance-sheet survival + operating quality + data-integrity audit. Scoring weights reweighted (see 5.3).
- [ ] **5.3** Update `config.py::WorkstreamBScoreWeights`: remove derivatives/CB sub-layer entirely (those are now workstream C + manual). Redistribute Gate 3's 10-pt derivatives weight: +5 to balance-sheet-survival (now 40), +5 to data-integrity (now 15). Operating quality stays 25, ownership stays 20 (though ownership is largely in WS C — here we keep only the capital-structure subset). Total = 100. Document rationale in comments referencing `report.md §7` and the removal of CB scoring.
- [ ] **5.4** `workstream_b.py::valuation_panel` — reverse-DCF via `metrics.reverse_dcf_implied_growth` using price × shares_outstanding as market-cap proxy (since `TaiwanStockMarketValue` is premium). Document the substitution in output notes.
- [ ] **5.5** `workstream_b.py::management_forensic_status` — returns `Status.MANUAL_REVIEW_REQUIRED` with a pointer to `data/templates/management_forensic_checklist.md`. Optional premium adapter in Phase 10.
- [ ] **5.6** `workstream_b.py::scuttlebutt_status` — returns `Status.MANUAL_REVIEW_REQUIRED` with pointer to `data/templates/scuttlebutt_call_log.md`.
- [ ] **5.7** `WorkstreamBResult`: `{stock_id, status, red_flag_screen, deep_forensic (nullable), valuation, management_forensic_status, scuttlebutt_status, hard_fails[], notes[]}`. Only the 7 original hard-fails that are still valid on free-tier fire here (CFO/NI persistent, refinancing wall, extreme leverage, excessive data gaps, repeated dilution, governance red flags from news, unresolved cross-data conflict).
- [ ] **5.8** Write `tests/test_workstream_b.py`: each red-flag item, two-stage gating, CFO/NI flag-not-reject, share-pledging → manual, CB not in scoring, reverse-DCF populates, management-forensic default manual, scuttlebutt default manual.
- [ ] **5.9** Wire into `run_top200_screen.py`; DELETE `taiwan_equity_toolkit/gate3.py` and `tests/test_gate3.py`. Commit.

**Files:** `taiwan_equity_toolkit/workstream_b.py` (NEW), `taiwan_equity_toolkit/config.py` (EDIT — remove Gate3Weights/Thresholds, add WorkstreamBScoreWeights), `tests/test_workstream_b.py` (NEW), `run_top200_screen.py` (EDIT), `taiwan_equity_toolkit/full_screen_demo.py` (EDIT), `taiwan_equity_toolkit/gate3.py` (DELETE), `tests/test_gate3.py` (DELETE).

**Risks:** Weight redistribution changes numeric scores — any external consumer reading `gate3_score` will break. Mitigation: new field name (`workstream_b_score`), migration notes in `docs/migration_from_v1.md`.

**Deliverables:** Workstream B fully functional. CB removed from scoring. Management forensic + scuttlebutt explicit as manual.

**Success criteria:**
- Tests pass.
- A dormant Nvidia-like semiconductor name that previously hit CFO/NI hard-fail now flags, not rejects (regression-tested with a fixture).

---

### Phase 6 — Synthesis Memo & Mandatory Bottom Panel

**Goal:** Replace `memo.py`'s gate-oriented structure with V2 two-page memo (Page 1 = three-column workstreams; Page 2 = seven mandatory bottom-panel fields). Enforce `manual_review_required` until analyst populates.

**Dependencies:** Phases 3, 4, 5 (all three workstreams).

**Tasks:**
- [ ] **6.1** Create `taiwan_equity_toolkit/synthesis.py` with `MemoV2` dataclass:
    ```python
    @dataclass
    class MemoV2:
        stock_id: str
        generated_at: str
        # Page 1: three-column parallel research
        workstream_a: WorkstreamAResult
        workstream_b: WorkstreamBResult
        workstream_c: WorkstreamCResult
        # Page 2: synthesis bottom panel (all mandatory)
        variant_perception: MemoField                # required
        scenario_ev: ScenarioEV                      # required (computes weighted IRR)
        position_sizing: SizingRecommendation        # hybrid: caps computed, conviction analyst
        catalyst_or_milestone: CatalystPath          # mode-conditional
        invalidation_criteria: MemoField             # required
        pre_mortem: MemoField                        # required
        exit_archetype: ExitArchetypeSelection       # required
        monitoring_cadence: str                      # "weekly" | "quarterly"
        overall_status: Status
    ```
- [ ] **6.2** Each `MemoField` has `{content: str, status: Status, template_path: str}`. If `content` is empty → `status = manual_review_required`. Render method outputs markdown that clearly marks any `manual_review_required` field with a callout.
- [ ] **6.3** `synthesis.build_memo_skeleton(stock_id, a, b, c)` — produces a MemoV2 where all Page-2 fields default to `manual_review_required` pointing at their template. This is what the pipeline emits; analyst fills in to flip to `passed`.
- [ ] **6.4** `synthesis.render(memo: MemoV2) -> str` — markdown rendering with the two-page structure. Page 1 renders A/B/C as a 3-column table or stacked sections (markdown limitation). Page 2 renders each mandatory field with header, status badge, content, template path if not yet filled.
- [ ] **6.5** `synthesis.validate(memo: MemoV2) -> list[str]` — returns list of missing mandatory fields; empty = memo complete.
- [ ] **6.6** DELETE `taiwan_equity_toolkit/memo.py` (replaced by synthesis.py). Update `full_screen_demo.py`, `run_top200_screen.py`, and any other importer.
- [ ] **6.7** Write `tests/test_synthesis.py`: skeleton emits manual_review_required for all 7 fields; validate() returns 7 missing; filling all → validate returns empty; render() marks missing fields; mode-conditional catalyst (event-driven vs compounder) branch.
- [ ] **6.8** Run full suite; commit.

**Files:** `taiwan_equity_toolkit/synthesis.py` (NEW), `tests/test_synthesis.py` (NEW), `taiwan_equity_toolkit/memo.py` (DELETE), `run_top200_screen.py` (EDIT), `taiwan_equity_toolkit/full_screen_demo.py` (EDIT).

**Risks:** v1 memo consumers break. Mitigation: migration doc, and `run_top200_screen.py` now emits V2 memos by default.

**Deliverables:** V2 memo live. Seven mandatory bottom-panel fields enforced.

**Success criteria:**
- Generated memos for every candidate show all 7 bottom-panel fields with `manual_review_required` status until filled.
- Tests pass.

---

### Phase 7 — Sizing, Sell Discipline, Journaling

**Goal:** Implement mechanical sizing caps (Druckenmiller/Freeman-Shor), Freeman-Shor archetype selection, and the journal templates (pre-mortem, decision journal, post-mortem).

**Dependencies:** Phase 0 (config), Phase 6 (memo integration).

**Tasks:**
- [ ] **7.1** Create `taiwan_equity_toolkit/sizing.py`:
    - `compute_sizing_caps(stock_id, existing_book, cfg: SizingCaps, client) -> SizingCaps` returning: `{vol_cap_pct, liquidity_cap_pct_of_adv, correlation_cap, suggested_band: (low, high), notes[]}`.
    - Vol cap from 90d realized vol: higher vol → smaller max position.
    - Liquidity cap: intended ≤ 10% of ADV (baseline) × risk tier multiplier.
    - Correlation cap: reduce size by portfolio covariance contribution above 0.7.
    - Suggested band: (low = 0.5%, high = 4% of AUM) modulated by above caps. Analyst picks final within band.
- [ ] **7.2** `sizing.render(caps) -> str` markdown table embedded in memo Page 2.
- [ ] **7.3** Create `taiwan_equity_toolkit/sell_discipline.py`:
    - `ExitArchetype = Literal["assassin", "hunter", "connoisseur"]`
    - `select_default_archetype(strategy_mode) -> ExitArchetype` — event-driven → assassin, value → hunter, quality-compounder → connoisseur.
    - `ExitRules` dataclass: archetype + forced −20% review trigger + archetype-specific rules (e.g., Hunter: max average-down size = 1.5× initial; Connoisseur: let winners run past target, time-stop for dead money at 12mo).
    - `render(rules) -> str`.
- [ ] **7.4** Create `taiwan_equity_toolkit/journal.py`:
    - `PreMortem` dataclass: `{assumed_loss_pct, horizon_months, failure_narrative, most_fragile_assumption, risk_mitigations, completed_at}`.
    - `DecisionJournal`: `{stock_id, thesis, bull_prob, base_prob, bear_prob, emotional_state, conviction_tier, expected_review_date, entry_date}`.
    - `PostMortem`: `{stock_id, entry_date, exit_date, outcome_pct, decision_quality {"right"|"wrong"|"mixed"}, outcome_vs_thesis, lessons, framework_improvements}`.
    - Each has `render()` method using its template from `data/templates/`.
- [ ] **7.5** Wire `sizing`, `sell_discipline`, `journal` into `synthesis.MemoV2` Page-2 fields (sizing, exit archetype, pre-mortem).
- [ ] **7.6** Write `tests/test_sizing.py`, `tests/test_sell_discipline.py`, `tests/test_journal.py`.
- [ ] **7.7** Run suite; commit.

**Files:** `taiwan_equity_toolkit/sizing.py` (NEW), `taiwan_equity_toolkit/sell_discipline.py` (NEW), `taiwan_equity_toolkit/journal.py` (NEW), `tests/test_sizing.py` (NEW), `tests/test_sell_discipline.py` (NEW), `tests/test_journal.py` (NEW), `taiwan_equity_toolkit/synthesis.py` (EDIT).

**Risks:** Kelly-like sizing over-promises precision. Mitigation: the user explicitly called out hybrid — caps are mechanical, conviction is analyst. Code enforces this boundary.

**Deliverables:** Mechanical sizing caps + archetype + journal templates live.

**Success criteria:**
- Sizing tests cover all four cap types.
- Sell discipline rejects an entry memo where no archetype is selected.
- Journal renders three template kinds.

---

### Phase 8 — Portfolio Dashboard

**Goal:** Implement the live portfolio exposure dashboard. Not a gate — continuous monitor.

**Dependencies:** Phases 3, 4 (workstreams A & C feed sector/correlation inputs).

**Tasks:**
- [ ] **8.1** Create `taiwan_equity_toolkit/portfolio_dashboard.py`:
    - Input: a list of current book positions `{stock_id, weight, entry_date}`.
    - Output: `DashboardView` with sector allocation, rolling 60d correlation matrix, beta-to-TAIEX, factor heuristics (growth/value/quality/momentum proxies), flagged concentrations.
    - Data: `TaiwanStockPriceAdj` (correlations/beta), `TaiwanStockInfo.industry_category` (sectors), optional curated chain-cluster grouping.
    - Render: markdown table + JSON export.
- [ ] **8.2** Expose via `screen.py` as `emit_dashboard(book) -> DashboardView`. Called independently of a screen run (the book state is user-provided).
- [ ] **8.3** Write `tests/test_portfolio_dashboard.py`.
- [ ] **8.4** Commit.

**Files:** `taiwan_equity_toolkit/portfolio_dashboard.py` (NEW), `tests/test_portfolio_dashboard.py` (NEW).

**Risks:** Book state has no source of truth in the repo today. Mitigation: accept JSON input (`data/current_book.json.example`) and document.

**Deliverables:** Portfolio dashboard module live.

**Success criteria:** Tests pass; dashboard rendering on a toy book of 3 names works.

---

### Phase 9 — Orchestrator + Entry-Point Wiring

**Goal:** Consolidate the pipeline into `taiwan_equity_toolkit/screen.py`; make `run_top200_screen.py` a thin CLI shim; revamp `full_screen_demo.py` for single-name V2 runs.

**Dependencies:** Phases 2–7 (all core modules).

**Tasks:**
- [ ] **9.1** Create `taiwan_equity_toolkit/screen.py`:
    - `run_screen(universe=None, config=DEFAULT_CONFIG, output_path=None) -> ScreenRun`.
    - Internal: universe.build → mass_triage.run_all → for each passer: asyncio.gather(workstream_a, workstream_b, workstream_c) → synthesis.build_memo_skeleton → sizing.compute_sizing_caps → append to ScreenRun.results.
    - Concurrency via `ThreadPoolExecutor` (per-stock) or `asyncio` (per-workstream inside a stock).
    - Token failover logic moves out of `run_top200_screen.py` and into `screen.py`; `get_active_token()` stays public.
    - Output JSON schema: `{run_date, universe_source, universe_as_of, token_usage, funnel_counts, mass_triage_failures[], workstream_a_results{}, workstream_b_results{}, workstream_c_results{}, synthesis_memos{stock_id: markdown}, sizing_caps{}, portfolio_dashboard (optional), premium_adapters_status{dataset: not_assessed}, manual_review_queue[]}`.
- [ ] **9.2** Rewrite `run_top200_screen.py` to be a thin CLI wrapper — argument parsing, token init, `screen.run_screen()`, write output. Preserve the filename and command interface.
- [ ] **9.3** Rewrite `taiwan_equity_toolkit/full_screen_demo.py` for V2 single-name run. Same CLI pattern.
- [ ] **9.4** Update `taiwan_equity_toolkit/__init__.py` exports to the V2 surface: `screen`, `universe`, `mass_triage`, `workstream_a`, `workstream_b`, `workstream_c`, `synthesis`, `sizing`, `sell_discipline`, `journal`, `portfolio_dashboard`, `adapters`, `metrics`, `parsers`, `client`, `config`, `states`.
- [ ] **9.5** Update `tests/test_run_top200_screen.py` to cover the V2 orchestrator surface.
- [ ] **9.6** Write `tests/test_free_tier_regression.py` — end-to-end with mocked FinMind responses for 3–5 representative stocks; verifies no premium dataset is called, output schema is correct, all 4 states appear in output.
- [ ] **9.7** Run full suite; `python run_top200_screen.py` against free-tier token; inspect `screen_results.json`; commit.

**Files:** `taiwan_equity_toolkit/screen.py` (NEW), `run_top200_screen.py` (REWRITE), `taiwan_equity_toolkit/full_screen_demo.py` (REWRITE), `taiwan_equity_toolkit/__init__.py` (EDIT), `tests/test_run_top200_screen.py` (EDIT), `tests/test_free_tier_regression.py` (NEW).

**Risks:** CLI / JSON schema change affects any downstream consumer. Mitigation: migration notes + acceptance tests replicate the old top-level keys where they still make sense.

**Deliverables:** One-command pipeline, V2 from the inside.

**Success criteria:**
- `python run_top200_screen.py` runs end-to-end on free-tier tokens.
- `screen_results.json` contains memo skeletons for every candidate with the 7 mandatory-bottom-panel fields marked `manual_review_required`.
- No HTTP 400 errors. No silent fallbacks.

---

### Phase 10 — Premium Adapters (Optional Overlay Path B)

**Goal:** Implement the premium adapter scaffold. Each adapter default returns `not_assessed`; if the environment exports a Backer/Sponsor token, the adapter activates. Industry-chain adapter is the one exception — it falls back to the curated YAML rather than `not_assessed`.

**Dependencies:** Phases 3, 4, 5 (workstream modules that consume adapters).

**Tasks:**
- [ ] **10.1** Create `taiwan_equity_toolkit/adapters/__init__.py` and `taiwan_equity_toolkit/adapters/premium.py` exporting adapters F1–F7 from the matrix. Each adapter has signature `(client, stock_id, *, allow_premium=False) -> AdapterResult` where `AdapterResult = {status, data, note}`. Default `allow_premium=False` → every adapter returns `{status: not_assessed, data: None, note: "premium tier required"}`.
- [ ] **10.2** Adapter for `TaiwanStockIndustryChain` is special: on `allow_premium=False` it returns the curated YAML result (status=passed); on `allow_premium=True` it queries the premium dataset and cross-validates.
- [ ] **10.3** Add `config.py::FreeTierPolicy.allow_premium_adapters: bool = False`.
- [ ] **10.4** Wire adapters into Workstream A/B/C so they surface `not_assessed` by default but activate transparently if `allow_premium=True`.
- [ ] **10.5** Write `tests/test_premium_adapters.py` — default behavior, YAML fallback, transparent activation.
- [ ] **10.6** Document in `docs/premium_adapters.md`. Commit.

**Files:** `taiwan_equity_toolkit/adapters/__init__.py` (NEW), `taiwan_equity_toolkit/adapters/premium.py` (NEW), `taiwan_equity_toolkit/config.py` (EDIT), `workstream_a.py/b.py/c.py` (EDIT), `tests/test_premium_adapters.py` (NEW), `docs/premium_adapters.md` (NEW).

**Risks:** Misuse: activating adapters without a Backer token will 400. Mitigation: adapter checks token tier via `client.usage()` before activating.

**Deliverables:** Path B scaffold complete; default path unaffected.

**Success criteria:**
- With default config, `premium_adapters_status` in output shows every adapter `not_assessed`.
- Toggling `allow_premium_adapters=True` with a free-tier token does NOT silently fail — it logs a clear "premium tier required" message.

---

### Phase 11 — Documentation Overhaul

**Goal:** Rewrite `README.md`, `CLAUDE.md`, `AGENTS.md`, `taiwan_equity_toolkit/README.md`, `Stock_Selection_Framework.md`, and `Taiwan_Equity_Agent_System_Prompt.md`. Add new docs under `docs/`.

**Dependencies:** Phases 1–10 (all code shipped).

**Tasks:**
- [ ] **11.1** Rewrite `README.md`: V2 overview, one-command run, dual-path explanation, free-tier scope, manual workflow list, where to find templates.
- [ ] **11.2** Update `CLAUDE.md`: new coding conventions (Status vocab, adapter pattern, template paths), new "What Not to Do" entries (no premium dataset in default path; no silent 400 swallowing; no bare-float metrics).
- [ ] **11.3** Rewrite `AGENTS.md`: V2 agent workflow — three concurrent workstreams, memo checkpoint, mandatory bottom-panel fields, scuttlebutt protocol, pre-mortem requirement.
- [ ] **11.4** Rewrite `Stock_Selection_Framework.md` as the V2 spec: no sequential gates; three workstreams; memo panel; sell discipline; point-in-time policy.
- [ ] **11.5** Update `Taiwan_Equity_Agent_System_Prompt.md`: remove sequential-gate references; add workstream concurrency; add mandatory memo panel; add pre-mortem / sizing / sell-archetype obligations.
- [ ] **11.6** Update `Finmind.md`: emphasize free-tier reality, tier-detection behavior, adapter boundary.
- [ ] **11.7** Rewrite `taiwan_equity_toolkit/README.md`: module reference per V2 surface.
- [ ] **11.8** Write `docs/v2_architecture.md`, `docs/free_tier_policy.md`, `docs/premium_adapters.md`, `docs/manual_workflows.md`, `docs/migration_from_v1.md`, `docs/backtesting_deferred_scaffold.md`.
- [ ] **11.9** Commit docs overhaul.

**Files:** All doc files.

**Risks:** Docs and code drift over time. Mitigation: each doc explicitly notes the commit/date it reflects; CI lint (future enhancement, not in scope) would catch drift.

**Deliverables:** Complete, self-consistent documentation set.

**Success criteria:**
- A new reader can follow `README.md` → `run_top200_screen.py` → inspect output → understand what's automated and what's manual, without ever reading code.

---

### Phase 12 — Backtesting Scaffold & Point-in-Time Guard

**Goal:** Write the deferred-scaffold doc and implement the point-in-time guard + validation harness.

**Dependencies:** Phase 9 (orchestrator) + Phase 11 (doc section).

**Tasks:**
- [ ] **12.1** Write `docs/backtesting_deferred_scaffold.md`: PIT policy, look-ahead-bias guardrails (every FinMind call must use `end_date ≤ run_date`), Taiwan transaction-cost assumptions (commission + tax + slippage estimate), explicit list of what's deferred (historical replay requires TEJ/Compustat) and why.
- [ ] **12.2** Implement `tests/test_point_in_time_guard.py`: instruments FinMindClient (mock) to fail any call whose `end_date > run_date`; runs a pinned-date pipeline; verifies no violation.
- [ ] **12.3** Implement `tests/test_free_tier_regression.py` (already in Phase 9; extend here with a snapshot-diff assertion on output JSON schema).
- [ ] **12.4** Commit.

**Files:** `docs/backtesting_deferred_scaffold.md` (NEW), `tests/test_point_in_time_guard.py` (NEW), `tests/test_free_tier_regression.py` (EDIT).

**Risks:** PIT guard may be over-strict and reject legitimate current-date runs. Mitigation: guard is test-only; production code doesn't enforce it.

**Deliverables:** Scaffold doc + PIT test.

**Success criteria:**
- `pytest tests/test_point_in_time_guard.py` passes with mocked PIT pipeline.

---

### Phase 13 — End-to-End Verification & Final Acceptance

**Goal:** Run the full pipeline against the live free-tier token, inspect a sample of memos, validate documentation, and confirm the acceptance criteria below.

**Dependencies:** Phases 0–12.

**Tasks:**
- [ ] **13.1** Ensure full test suite is green: `python -m pytest tests/ -v`. Expected: all pass, >80% coverage on new modules.
- [ ] **13.2** Run `python run_top200_screen.py`. Observe logs for any HTTP 400 (should be zero). Inspect `screen_results.json`: funnel counts reasonable, memo skeletons present, all 4 status states observed somewhere in the output.
- [ ] **13.3** Spot-check 3 memos (TSMC 2330, a financials name, a mid-cap tech): verify 7 mandatory bottom-panel fields all show `manual_review_required` and point at correct template path. Verify no reference to 景氣對策信號 or broker-branch in the memo body.
- [ ] **13.4** Verify all docs build/render: open each `.md` file, verify no stale references to gate3/gate65/peers/value_chain.
- [ ] **13.5** Produce a final summary in `docs/overhaul_summary.md` mapping each row of the Requirements Matrix (Part 1) to its implementing commit hash(es). This is the report-back artifact for the user.
- [ ] **13.6** Commit: `docs: overhaul summary mapping findings to implementations`.

**Files:** `docs/overhaul_summary.md` (NEW).

**Risks:** Live FinMind calls consume quota. Mitigation: run once; use mocked replay for subsequent test iterations.

**Deliverables:** Production-ready V2.

**Success criteria:** See Acceptance Criteria in Part 5.

---

## Part 4 — Risks & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Curated supply-chain YAML goes stale as Taiwan market evolves | Med | Document `as_of` in YAML; premium-chain adapter (Phase 10) can cross-validate and flag drift when Backer token available |
| Deleting gate3.py/gate65.py/triage.py/peers.py/value_chain.py breaks external scripts the user hasn't told me about | High | Phase sequencing: delete only after importer is updated; grep for lingering imports before each delete; keep `run_top200_screen.py` filename/CLI unchanged |
| Removing CB scoring changes final rankings vs. v1 | Med | Expected — this is intentional per the user's explicit instruction. Migration doc explains |
| 10-item red-flag screen produces false negatives vs. v1's heavier screen | Med | Two-stage design (Stage 2 deep forensic when 2+ flags fire) catches most of what v1 caught; Phase 5 tests include a fixture stock that triggered hard-fail in v1 to verify it still triggers Stage 2 |
| Analyst friction: 7 mandatory memo fields may feel heavy | Low | Templates ship with examples; `manual_review_required` states make missing fields highly visible; no field is optional per report.md |
| Free-tier rate limit (600 req/hr) hits during a full Top-200 run | Med | Existing token-failover logic preserved; async batch for peer work preserved; staleness threshold means refresh cadence is daily not per-minute |
| Premium adapter misactivation without Backer token → 400 errors | Low | Adapter checks token tier via `client.usage()` before calling; fails loud with clear message |
| Point-in-time guard doesn't catch restated fundamentals from free-tier | High (for backtesting) | Accepted limit — documented in `docs/backtesting_deferred_scaffold.md`; backtesting is explicitly deferred |

---

## Part 5 — Acceptance Criteria (Final)

The overhaul is complete if and only if all of the following are true:

1. **Single default command.** `python run_top200_screen.py` runs end-to-end on free-tier tokens (no changes to env) and produces `screen_results.json`.
2. **No silent premium calls.** `grep` across default-path modules (`universe.py`, `mass_triage.py`, `workstream_a.py`, `workstream_b.py`, `workstream_c.py`, `synthesis.py`, `sizing.py`, `sell_discipline.py`, `journal.py`, `portfolio_dashboard.py`, `screen.py`) for premium dataset names (`TaiwanStockIndustryChain`, `TaiwanStockDispositionSecuritiesPeriod`, `TaiwanStockSuspended`, `TaiwanBusinessIndicator`, `TaiwanStockConvertibleBond*`, `TaiwanStockTradingDailyReport*`, `TaiwanstockGovernmentBankBuySell`, `TaiwanStockMarketValue*`, `TaiwanStockKBar`, `TaiwanStockPriceTick`, `TaiwanStockHoldingSharesPer`, `TaiwanStock10Year`, `TaiwanStockWeekPrice`, `TaiwanStockMonthPrice`, `TaiwanStockEvery5SecondsIndex`, `CnnFearGreedIndex`) yields zero matches outside `adapters/premium.py` and its tests.
3. **V2 architecture in code**, not patchwork: `gate3.py`, `gate65.py`, `peers.py`, `value_chain.py`, `triage.py`, `memo.py` are all DELETED; new modules `workstream_a/b/c.py`, `synthesis.py`, `sizing.py`, `sell_discipline.py`, `journal.py`, `portfolio_dashboard.py`, `mass_triage.py`, `screen.py`, `universe.py` exist.
4. **Four status states** (`passed`, `failed`, `not_assessed`, `manual_review_required`) all appear somewhere in a fresh `screen_results.json` from a live free-tier run.
5. **Seven mandatory memo fields** — for every stock passing mass_triage, the generated memo skeleton shows variant_perception, scenario_ev, position_sizing, catalyst_or_milestone, invalidation_criteria, pre_mortem, exit_archetype — each either populated or `manual_review_required` with a pointer to its template.
6. **Mechanical sizing caps** are computed for every passer (vol, liquidity, correlation, suggested band). Conviction tier remains analyst-only.
7. **Sell archetype** (Assassin/Hunter/Connoisseur + forced −20% review) is required in every memo and documented in `sell_discipline.py`.
8. **Tests pass**: `python -m pytest tests/ -v` → 100% of tests green. New test modules (states, universe, mass_triage, workstream_a, workstream_b, workstream_c, synthesis, sizing, sell_discipline, journal, portfolio_dashboard, premium_adapters, free_tier_regression, point_in_time_guard, curated_data, client_premium_detection) all exist.
9. **Docs updated**: `README.md`, `CLAUDE.md`, `AGENTS.md`, `taiwan_equity_toolkit/README.md`, `Stock_Selection_Framework.md`, `Taiwan_Equity_Agent_System_Prompt.md`, `Finmind.md` all reflect V2. `docs/v2_architecture.md`, `docs/free_tier_policy.md`, `docs/premium_adapters.md`, `docs/manual_workflows.md`, `docs/migration_from_v1.md`, `docs/backtesting_deferred_scaffold.md`, `docs/overhaul_summary.md` exist.
10. **Findings map**: `docs/overhaul_summary.md` lists every row from the Requirements Matrix (Part 1) with its implementing commit hash(es); no row is left unmapped.

---

## Part 6 — Reporting Protocol During Execution

Once implementation begins, after **each phase** the agent reports:

- **Phase N complete**
- **What changed** — bulleted list of behavioral changes
- **Files changed** — absolute paths grouped by NEW / EDIT / DELETE
- **Tests run** — command + pass/fail counts
- **What remains** — next phase(s)
- **Blockers / tradeoffs** — anything unexpected

This matches the user's "high-visibility execution" requirement. Use TodoWrite to maintain per-task state within each phase.