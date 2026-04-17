# Stock Selection Framework — Pre-Trade

> **Central question this framework answers:**
> *Is this the right security to express the industry view, at this price, with this balance-sheet risk, under this positioning backdrop, and with this catalyst path?*
>
> **Core principles:**
> - We trade *industries*, not companies. Confirm the direction first, then select the cleanest representation.
> - Signal hierarchy over data volume. More data without decision rights is noise.
> - Forensic diligence on finalists only. Cheap screens kill weak names early.
> - Quality of the business and quality of the entry are separate judgments. A high-quality security can still be a poor trade today.
> - Every advancement is a decision with citations. Every rejection is a decision with reasons.

---

## Framework Architecture

```
Gate 1 — Industry Direction
        ↓
Gate 2 — Company Qualitative
        ↓
Triage Filter — Cut to deep-work shortlist
        ↓
Gate 3 — Forensic Quality (scorecard + hard-fail overrides)
        ↓
Gate 4 — Cross-Source Industry Validation
        ↓
Gate 5 — Value Chain Positioning
        ↓
Gate 6 — Portfolio Fit (Strategic)
        ↓
Gate 6.5 — Entry Architecture (tactical: price, timing, execution)
        ↓
Gate 7 — Thesis & Dated Catalyst
        ↓
Actionable Watchlist ✓
```

Gates are sequential. A name that fails any gate stops advancing. Failure is documented with the specific evidence and gate number.

---

## Gate 1 — Industry-Level Screening

**Question:** Is the industry moving in the direction of our intended trade, and is institutional money backing that direction?

- [ ] Industry currently **expanding or contracting** — direction aligned with long or short posture?
- [ ] Macro leading indicators support direction
  - Taiwan: `TaiwanBusinessIndicator` (景氣對策信號 — monitoring color, leading composite)
  - Global: ISM, PMI, US treasury curve shape (`GovernmentBondsYield`), CNN Fear & Greed (`CnnFearGreedIndex`)
  - Currency: `TaiwanExchangeRate` (USD/TWD especially for export sectors)
- [ ] Industry-chain anchor identified via `TaiwanStockIndustryChain`
- [ ] Corresponding sector ETF or industry proxy shows institutional accumulation or distribution
  - Check via `TaiwanStockInstitutionalInvestorsBuySell` aggregated across industry constituents
- [ ] Industry cycle phase identified — Expansion / Plateau / Contraction
- [ ] Taiwan-specific cross-references where relevant
  - Semiconductor: TSMC monthly revenue (`TaiwanStockMonthRevenue`), foundry utilization commentary, upstream equipment orders
  - Export sectors: Taiwan export orders data, USD/TWD trend
  - Financials: domestic interest rate regime (`InterestRate` for relevant central banks)

---

## Gate 2 — Company Qualitative

**Question:** Do I actually understand this business, and is it the cleanest representation of the industry view?

- [ ] Business model explainable in **one paragraph** — what they sell, how, to whom
- [ ] Customer "must-buy" logic articulated — substitutes identified or ruled out
- [ ] Moat identified and tested for durability (tech, scale, brand, switching cost, regulatory)
- [ ] Industry-specific KPIs understood
  - Foundry: utilization rate, ASP per wafer, node mix, capex intensity
  - OSAT: utilization, ASP per pin, mix of advanced packaging
  - IC design: inventory days, design win pipeline, royalty mix
  - Hardware ODM: GPU server share, AI revenue mix, book-to-bill
  - Financials: NIM, NPL ratio, CAR, fee income mix
  - Shipping: freight rate index, fleet utilization, contract vs. spot mix
- [ ] Industry position: #1, #2, or #3 by market cap, share, or technical leadership
  - Market cap ranking: `TaiwanStockMarketValue` filtered by industry
  - Index weight: `TaiwanStockMarketValueWeight`
- [ ] If not a leader, specific edge justified (niche dominance, cycle-specific beneficiary, M&A optionality)

---

## Triage Filter — Shortlist Cutoff

**Purpose:** Eliminate names that do not deserve deep forensic work. Gate 3 is expensive; this filter makes it affordable.

A name must clear **all** of the following to advance to Gate 3. Any single failure = park or reject.

### Cleanliness Screens
- [ ] Not on disposition securities list (`TaiwanStockDispositionSecuritiesPeriod`)
- [ ] Not currently suspended (`TaiwanStockSuspended`)
- [ ] Not on day-trading suspension list without clear transient reason (`TaiwanStockDayTradingSuspension`)
- [ ] Not in active delisting pipeline (`TaiwanStockDelisting`)
- [ ] Not within corporate-action distortion window (recent capital reduction, par-value change, split) unless distortion is understood and thesis accounts for it
  - `TaiwanStockCapitalReductionReferencePrice`, `TaiwanStockSplitPrice`, `TaiwanStockParValueChange`

### Liquidity Floor
- [ ] Average daily dollar volume (20-day) ≥ minimum threshold for intended position size
  - Rule of thumb: intended position ≤ 10% of ADV
  - Source: `TaiwanStockPrice` → `Trading_money` mean over 20 trading days

### Financial Sanity
- [ ] Most recent quarter exists and is not more than one quarter stale
  - `TaiwanStockFinancialStatements` latest `date` within one quarter
- [ ] Monthly revenue (`TaiwanStockMonthRevenue`) not in collapse (> 30% YoY decline) unless shorting
- [ ] Not obviously insolvent at a glance (positive shareholders' equity, positive operating cash flow most recent four quarters — overrides considered on case-by-case basis)

### Price-History Cleanliness
- [ ] Adjusted price series (`TaiwanStockPriceAdj`) not heavily distorted by repeat corporate actions
- [ ] If multiple corporate actions in past 24 months, note the adjustments made before any technical or performance comparison

### Peer Context
- [ ] Not a deep outlier vs. 2–3 closest peers on recent 90-day return without a specific, verifiable reason

**Output of triage:** Shortlist with a one-line reason per name. Rejections logged with the specific screen that failed.

---

## Gate 3 — Forensic Quality

**Weight:** 35–40% of total screening effort. Deep work only on triage-passers.

**Question:** Does every available layer of company, balance-sheet, ownership, derivatives, and data-integrity evidence support the conclusion that this is the correct vehicle for the industry thesis?

Five sub-layers, evaluated sequentially. Scorecard at the end.

### 3A. Operating Quality

- [ ] Revenue trajectory — monthly (`TaiwanStockMonthRevenue`) and quarterly (`TaiwanStockFinancialStatements`)
  - Month-over-month and year-over-year growth
  - Trailing-12-month (TTM) revenue trend
  - Acceleration vs. deceleration in most recent three months
- [ ] Margin profile — gross, operating, net (derived from `TaiwanStockFinancialStatements`)
  - Direction (expanding, flat, compressing)
  - Stability (standard deviation across recent 8 quarters)
  - Peer-relative position
- [ ] Earnings quality — EPS trend and composition
  - Recurring vs. non-recurring items
  - One-time gains (FX, asset disposal, investment income) stripped out
- [ ] Cash conversion — net income vs. cash flow from operations (`TaiwanStockCashFlowsStatement`)
  - Persistent gap between accounting profit and operating cash flow = red flag
  - Target: CFO / Net Income ≥ 0.8 on trailing basis, absent specific working-capital explanation
- [ ] Return metrics — ROE, ROA, ROIC
  - Level and direction
  - Stability through cycle
  - DuPont decomposition where meaningful (margin × turnover × leverage)
- [ ] Peer-relative operating performance — comparative analysis using async batch query on industry peers

### 3B. Balance Sheet & Cash Survival

The non-negotiable block. A right industry call on a broken balance sheet is still a losing trade.

- [ ] Leverage
  - Net debt / EBITDA
  - Debt / equity, debt / assets
  - Short-term debt as % of total debt
  - Source: `TaiwanStockBalanceSheet`
- [ ] Liquidity
  - Current ratio, quick ratio
  - Cash + equivalents vs. short-term debt (coverage ratio ≥ 1.0 is baseline)
- [ ] Interest coverage
  - EBIT / interest expense
  - Trend direction over 8 quarters
- [ ] Working capital dynamics
  - Cash conversion cycle (DSO + DIO − DPO)
  - Trend — lengthening cycle in a growing business often signals channel stuffing or collection weakness
- [ ] Free cash flow integrity (`TaiwanStockCashFlowsStatement`)
  - FCF = CFO − Capex
  - FCF margin (FCF / Revenue)
  - FCF trend over 8 quarters
  - Dividend coverage: FCF ≥ cash dividends paid (`TaiwanStockDividend`)
- [ ] Debt maturity and refinancing pressure
  - Any debt maturing in next 12 months? Size relative to cash + FCF generation?
  - Refinancing window friendly or hostile given current rate regime?
- [ ] Capital structure history — dilution and repair
  - Historical capital reductions (`TaiwanStockCapitalReductionReferencePrice`)
  - Par-value changes (`TaiwanStockParValueChange`)
  - Splits (`TaiwanStockSplitPrice`)
  - Repeated dilution without operational repair = disqualifying pattern

### 3C. Ownership, Crowding & Market Structure

Who owns this, who's accumulating, who's distributing, and is the sponsorship healthy or crowded?

- [ ] Three institutional investors net flow — foreign, trust, dealer (`TaiwanStockInstitutionalInvestorsBuySell`)
  - Trend over 5, 20, 60 trading days
  - Divergence between the three types — is sponsorship broad or single-source?
- [ ] Foreign ownership ratio (`TaiwanStockShareholding`)
  - Current level vs. 52-week range
  - Proximity to statutory upper limit (`ForeignInvestmentUpperLimitRatio`)
- [ ] Margin financing and short sale structure (`TaiwanStockMarginPurchaseShortSale`)
  - Margin balance trend (rising into rally = retail-heavy, caution)
  - Short balance trend
  - Short / margin ratio
- [ ] Securities lending and SBL (`TaiwanStockSecuritiesLending`, `TaiwanDailyShortSaleBalances`)
  - SBL balance vs. average daily volume
  - Short covering vs. new short creation
- [ ] Short-sale suspension status (`TaiwanStockMarginShortSaleSuspension`) — if suspended, note implications
- [ ] Shareholding concentration (`TaiwanStockHoldingSharesPer`)
  - Distribution across holder tiers
  - Movement between tiers over recent months
- [ ] Broker / branch accumulation patterns (Sponsor tier: `TaiwanStockTradingDailyReport`, `TaiwanStockTradingDailyReportSecIdAgg`)
  - Persistent buyer brokers
  - Government-bank flow (`TaiwanstockGovernmentBankBuySell`) — "national team" signal
- [ ] Crowding judgment
  - Is sponsorship broadening (healthy) or narrowing into a single type (fragile)?
  - Is this a consensus position among foreign institutions with no remaining marginal buyer?

### 3D. Derivatives & Capital Structure Confirmation

Does the derivatives market and convertible bond market confirm or challenge the equity thesis?

- [ ] Single-stock futures / options participation where listed
  - `TaiwanFuturesDaily`, `TaiwanOptionDaily` for corresponding futures/options IDs
  - Open interest trend
  - Institutional net position (`TaiwanFuturesInstitutionalInvestors`, `TaiwanOptionInstitutionalInvestors`)
- [ ] Dealer behavior around key dates (earnings, monthly revenue release)
  - Dealer net positioning ahead of event
- [ ] Convertible bond signals (if applicable)
  - `TaiwanStockConvertibleBondInfo` — is there an outstanding CB?
  - `TaiwanStockConvertibleBondDaily` — CB price vs. conversion price
  - `TaiwanStockConvertibleBondInstitutionalInvestors` — institutional flow in the CB
  - `TaiwanStockConvertibleBondDailyOverview` — put date, call date, redemption pressure
  - CB trading tight to conversion price + institutional accumulation = positive tell
  - CB trading below par with weak equity = distress signal
- [ ] Overall capital-structure read
  - Does the derivatives / CB market agree with the equity thesis direction?
  - If not, why? Is there information in the other instruments you're missing?

### 3E. Data Integrity & Event Audit

Before trusting the forensic output, confirm the data isn't lying to you.

- [ ] Corporate-action distortions documented and adjusted for
  - Capital reductions, splits, par-value changes in past 24 months
  - Adjusted price used for technicals; reported figures used for fundamentals
- [ ] Recent news flow (`TaiwanStockNews`) checked for consistency with reported data
  - Are the numbers telling the same story as management commentary?
  - Any auditor change, director resignation, related-party transaction disclosure?
- [ ] Monthly revenue vs. quarterly financial statement consistency check
- [ ] Dividend policy history (`TaiwanStockDividend`, `TaiwanStockDividendResult`) — any pattern of aggressive payouts funded by debt?
- [ ] No undisclosed pledged shares or director selling pattern flagged in news

### Gate 3 Scorecard — 100 Points

| Sub-Layer | Weight | Scoring Guide |
|---|---|---|
| **3A. Operating Quality** | 25 | Growth direction + margin trajectory + CFO/NI ≥ 0.8 + ROIC stability + peer rank |
| **3B. Balance Sheet & Cash Survival** | 35 | Leverage + liquidity + interest coverage + FCF integrity + maturity schedule + dilution history |
| **3C. Ownership & Market Structure** | 20 | Institutional flow direction + ownership breadth + margin/short structure + concentration trend |
| **3D. Derivatives & Capital Structure** | 10 | Derivatives confirm direction + CB consistency with equity |
| **3E. Data Integrity & Event Audit** | 10 | No corporate-action distortion unaddressed + news consistent + no flagged governance concerns |
| **Total** | **100** | |

### Gate 3 Verdict

| Score | Verdict | Action |
|---|---|---|
| ≥ 80 | **Pass — Forensic Quality Confirmed** | Advance to Gate 4 |
| 65 – 79 | **Conditional — Watchlist** | Park with specific conditions for revisit; do not advance to entry |
| < 65 | **Fail — Wrong Security** | Reject. Industry thesis may still be correct via a different name |

### Hard-Fail Overrides

Regardless of numeric score, any of the following triggers **automatic rejection** at Gate 3:

1. Near-term refinancing wall (< 12 months) with weak interest coverage (< 2x) and insufficient cash
2. Severe and persistent divergence between net income and CFO (CFO/NI < 0.5 for 4+ consecutive quarters)
3. Repeated dilution or capital reduction without evidence of operational repair
4. Governance red flags — auditor change without explanation, large-scale director selling, related-party revenue concentration
5. Corporate-action-driven price illusion that cannot be cleanly adjusted for
6. Unresolved conflict between business-quality data and ownership/derivatives data (e.g., operating metrics strong but foreign selling persistent and heavy with no explanation)
7. Data gaps so large that a confident forensic read is impossible — declare "insufficient data" and reject

### Gate 3 Output Format

Produce a structured note with:
- **Verdict:** Pass / Conditional / Fail + score
- **Three-bullet thesis** (why this name is the right vehicle for the industry view)
- **Three-bullet risk list** (the specific data-backed concerns)
- **Data integrity note** (corporate-action adjustments, data staleness flags)
- **Handoff to Gate 4** or reason for rejection

---

## Gate 4 — Cross-Source Industry Validation

**Question:** Does the peer group, sector ETF, and industry-chain data confirm the direction this single name is pointing?

- [ ] 2–3 closest peers identified via `TaiwanStockIndustryChain` and market-cap ranking
- [ ] Peer price action (`TaiwanStockPriceAdj`) shows high overlap with candidate — or deviation is explainable
  - Correlation of 90-day returns across peers
  - Divergences investigated and documented
- [ ] Peer fundamental direction (monthly revenue, latest quarter) confirms the candidate's trajectory
  - Async batch query across peer `TaiwanStockMonthRevenue`
  - Async batch query across peer `TaiwanStockFinancialStatements`
- [ ] Corresponding sector ETF or index (if applicable) flow consistent with name-level flow
- [ ] Peer institutional flows (`TaiwanStockInstitutionalInvestorsBuySell` across peers) show same direction — are institutions treating this as an industry trade or a name-specific one?

---

## Gate 5 — Value Chain Positioning

**Question:** Where does this name sit in the value chain, and what do upstream/downstream signals say about timing?

- [ ] Value-chain position mapped via `TaiwanStockIndustryChain`
  - Upstream (leading) vs. downstream (lagging) identified
  - Specific role in the chain (raw materials, components, assembly, brand, distribution)
- [ ] Upstream signals reviewed
  - Upstream peers' monthly revenue and financial statements (async batch)
  - Upstream news flow (`TaiwanStockNews` across upstream names)
  - Commodity inputs where relevant (`CrudeOilPrices`, `GoldPrice`)
- [ ] Lead/lag timing researched — there is no shortcut
  - Historical lag between upstream and downstream in this specific chain
  - Current position within that lag window
- [ ] Downstream validation (for upstream names) or upstream confirmation (for downstream names)
- [ ] Cross-source data corroborates transmission direction

---

## Gate 6 — Portfolio Fit (Strategic)

**Question:** Does this name, at a structural level, belong in the existing book?

- [ ] **Beta alignment** with portfolio posture
  - Defensive posture → prefer low-beta names
  - Aggressive posture → high-beta acceptable
- [ ] **Sector / industry overlap** with existing positions
  - Avoid concentration beyond deliberate thesis weighting
- [ ] **Position count** — room in the book? (Sweet spot 12–14; cap ~30)
- [ ] **Geographic and FX exposure** — does this add or duplicate existing TWD, USD, CNY exposure?
- [ ] **Thematic overlap** — is this a new theme or another expression of a theme already over-represented?

*Gate 6 is strategic: does it fit the book? Gate 6.5 is tactical: is now the time?*

---

## Gate 6.5 — Entry Architecture

**Question:** Is the price, timing, and execution path appropriate *today*?

A name can pass Gates 1–6 and still fail here. This is the difference between a good security and a good trade.

### 6.5A. Valuation & Expectation Gap
- [ ] Multiples in context — PE, PB, PS, EV/EBITDA vs. own 3-year and 5-year history
  - Source: `TaiwanStockPER` + derived from `TaiwanStockFinancialStatements` and `TaiwanStockMarketValue`
- [ ] Multiples vs. peer group (async batch across peers)
- [ ] Reverse-DCF sanity check — what growth rate is the current price implying?
  - Is the implied growth plausible given operating reality?
- [ ] CEO guidance direction vs. consensus — is there a setup for beat or miss?
- [ ] Valuation location verdict: **Attractive / Fair / Stretched / Expensive**

### 6.5B. Volatility & Correlation
- [ ] Realized volatility — 30-day and 90-day, annualized (from `TaiwanStockPriceAdj`)
- [ ] Beta to TAIEX (rolling 90-day using `TaiwanVariousIndicators5Seconds` or daily index)
- [ ] **Correlation to existing book** — 90-day return correlation against each existing position
  - A "new" position 0.9 correlated to three existing holdings is not a new position
- [ ] Incremental portfolio risk contribution estimated

### 6.5C. Liquidity & Execution
- [ ] ADV (20-day dollar volume) vs. intended position size — exit-able without market impact?
- [ ] Price-limit regime check (`TaiwanStockPriceLimit`) — any special limit-up/down rules (ETF leverage, emerging stock)?
- [ ] Tick-size and spread reasonable for intended hold horizon

### 6.5D. Crowding & Catalyst Proximity
- [ ] Current positioning vs. positioning when Gate 3 was run — has the trade become crowded in the interim?
- [ ] Distance to next dated catalyst (days / weeks)
- [ ] Pre-event positioning implication — too close to earnings = elevated swing risk
- [ ] Disposition period check (`TaiwanStockDispositionSecuritiesPeriod`) — any restriction during intended hold?

### Gate 6.5 Verdict

| Outcome | Meaning |
|---|---|
| **Enter Now** | Price, timing, correlation, liquidity all green |
| **Stagger / Scale In** | Entry acceptable but size should be built in tranches due to volatility or crowding |
| **Wait for Setup** | Security passes quality, but current price/timing/correlation is suboptimal — park with trigger conditions |
| **Reject for Book Fit** | Correlation or crowding makes this a bad marginal addition regardless of standalone quality |

---

## Gate 7 — Thesis & Dated Catalyst

**Question:** Can I write down, in one page, why this trade works, when it works, and what would prove me wrong?

The written thesis must answer all of the following:

- [ ] **Direction** — long or short and the core argument
- [ ] **Key assumptions** — what has to remain true for the trade to work
- [ ] **Supporting data** — which macro, industry, KPI, and ownership signals back it
- [ ] **Dated catalyst map**
  - What specific event is expected to move the price?
  - When is it expected? (Earnings date, guidance window, product launch, macro print, regulatory decision)
  - Without a dated catalyst, conviction decays under time pressure — reject
- [ ] **Invalidation criteria** — what specific data point or price action proves the thesis wrong?
  - Example: "Monthly revenue growth drops below 10% YoY for two consecutive months" or "Stock closes 15% below entry"
- [ ] **Expected swing-risk range** — if the trade goes against, what is the reasonable max-loss estimate?
- [ ] **Conviction level** — stated explicitly: high / medium / low and why

---

## Quick-Disqualify Checklist

Apply at any gate. Any one of these triggers stop.

| Condition | Gate | Reason |
|---|---|---|
| Can't explain business model in one paragraph | 2 | Universe incomplete |
| Industry contracting, buying only because "cheap" | 1 | Single name can't fight ETF basket outflows |
| On disposition / suspension / delisting list | Triage | Tradability impaired |
| Intended position > 10% of ADV | Triage | Exit will move the market |
| Monthly revenue collapsing without a short thesis | Triage | Structural operational problem |
| Debt wall + weak coverage + insufficient cash | 3B | Balance-sheet risk overrides sector thesis |
| CFO persistently lagging net income | 3A/3B | Earnings quality suspect |
| Repeated dilution without operational repair | 3B | Value-destroying capital history |
| Governance red flags (auditor change, director selling pattern) | 3E | Information asymmetry against outsiders |
| Derivatives / CB market contradicts equity thesis without explanation | 3D | Unresolved cross-instrument conflict |
| Same sector / theme as existing positions, no deliberate overweight | 6 | Over-exposure, diluted diversification |
| Correlation > 0.85 with existing position | 6.5 | Not a new position in risk terms |
| Valuation in extreme historical percentile with no fresh catalyst | 6.5 | Late to the trade |
| Too close to earnings with no edge on the print | 6.5 | Event risk without event thesis |
| No dated catalyst | 7 | Open-ended view bleeds conviction over time |
| No written invalidation criteria | 7 | Can't know when to get out |
| Meme-level daily volatility (±20%) | 6.5 | Unmanageable swing-punch risk |

---

## Full Workflow

```
Industry direction confirmed
        ↓
Business model and industry role clear
        ↓
Triage Filter clears name for deep work
        ↓
Forensic Quality scored ≥ 80 AND no hard-fail override
        ↓
Peers, sector ETF, industry-chain confirm direction
        ↓
Value-chain lead/lag timing understood
        ↓
Fits existing book at structural level
        ↓
Entry price / correlation / liquidity / crowding all green
        ↓
Thesis written with dated catalyst + invalidation criteria
        ↓
Actionable Watchlist ✓
```

---

## Data Hierarchy — Primary FinMind Datasets by Gate

| Gate | Primary datasets |
|---|---|
| **1. Industry** | `TaiwanBusinessIndicator`, `TaiwanStockIndustryChain`, `TaiwanExchangeRate`, `GovernmentBondsYield`, `InterestRate`, `TaiwanStockInstitutionalInvestorsBuySell` (aggregated) |
| **2. Qualitative** | `TaiwanStockInfo`, `TaiwanStockMarketValue`, `TaiwanStockMarketValueWeight` |
| **Triage** | `TaiwanStockDispositionSecuritiesPeriod`, `TaiwanStockSuspended`, `TaiwanStockDelisting`, `TaiwanStockPrice`, `TaiwanStockMonthRevenue`, `TaiwanStockCapitalReductionReferencePrice` |
| **3A** | `TaiwanStockMonthRevenue`, `TaiwanStockFinancialStatements`, `TaiwanStockCashFlowsStatement` |
| **3B** | `TaiwanStockBalanceSheet`, `TaiwanStockCashFlowsStatement`, `TaiwanStockDividend` |
| **3C** | `TaiwanStockInstitutionalInvestorsBuySell`, `TaiwanStockShareholding`, `TaiwanStockMarginPurchaseShortSale`, `TaiwanStockSecuritiesLending`, `TaiwanDailyShortSaleBalances`, `TaiwanStockHoldingSharesPer`, `TaiwanStockTradingDailyReport`, `TaiwanstockGovernmentBankBuySell` |
| **3D** | `TaiwanFuturesDaily`, `TaiwanOptionDaily`, `TaiwanFuturesInstitutionalInvestors`, `TaiwanOptionInstitutionalInvestors`, `TaiwanStockConvertibleBondInfo`, `TaiwanStockConvertibleBondDaily`, `TaiwanStockConvertibleBondInstitutionalInvestors`, `TaiwanStockConvertibleBondDailyOverview` |
| **3E** | `TaiwanStockNews`, `TaiwanStockCapitalReductionReferencePrice`, `TaiwanStockSplitPrice`, `TaiwanStockParValueChange` |
| **4. Cross-source** | Peer batch via `TaiwanStockPriceAdj`, `TaiwanStockMonthRevenue`, `TaiwanStockFinancialStatements`, `TaiwanStockInstitutionalInvestorsBuySell` (async batch) |
| **5. Value Chain** | `TaiwanStockIndustryChain`, upstream/downstream async batch of revenue and financials |
| **6. Portfolio Fit** | Existing book data + `TaiwanStockMarketValueWeight` |
| **6.5. Entry** | `TaiwanStockPER`, `TaiwanStockPriceAdj`, `TaiwanStockPrice`, `TaiwanStockPriceLimit`, `TaiwanVariousIndicators5Seconds` |
| **7. Thesis** | All of the above, synthesized |

Use async batch query wherever the dataset supports it (most `data_id`-based datasets do). Comparative peer analysis is where AI's data-processing advantage most clearly translates to edge.
