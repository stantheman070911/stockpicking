# A Professional Framework Weighed Down by Its Own Rigor


## Evaluating Sir's Discretionary Stock Selection Framework Against Institutional Practice


---

## Table of Contents | 目錄

1. [Executive Verdict | 執行摘要](#1-executive-verdict--執行摘要)
2. [Framework Outline | 框架輪廓](#2-framework-outline--框架輪廓)
3. [Side-by-Side Comparison | 並排比較](#3-side-by-side-comparison--並排比較)
4. [Strengths | 優勢分析](#4-strengths--優勢分析)
5. [Weaknesses & Blind Spots | 弱點與盲點](#5-weaknesses--blind-spots--弱點與盲點)
6. [Distinctive Elements | 差異化特色](#6-distinctive-elements--差異化特色)
7. [What Should Be Simplified | 應簡化之處](#7-what-should-be-simplified--應簡化之處)
8. [Style Fit | 風格適配度](#8-style-fit--風格適配度)
9. [Backtesting & Validation Design | 回測與驗證設計](#9-backtesting--validation-design--回測與驗證設計)
10. [Version 2 Redesign Blueprint | 第二版重設計藍圖](#10-version-2-redesign-blueprint--第二版重設計藍圖)
11. [Priority Improvement Roadmap | 優先改進路線圖](#11-priority-improvement-roadmap--優先改進路線圖)
12. [Reference Sources | 參考來源](#12-reference-sources--參考來源)

---

## 1. Executive Verdict | 執行摘要

### English

**This framework is closer to institutional-quality analyst architecture than to any actual working investor's live process — and that is both its strongest feature and its largest vulnerability.**

Measured against documented practice at Capital Group, Dodge & Cox, Baillie Gifford, Fundsmith, Akre Focus Fund, Pershing Square, Citadel Surveyor, Point72 Academy, Street of Walls training materials, Morgan Stanley Asia Semiconductors (Charlie Chan), and CLSA Taiwan (Sebastian Hou), the framework is materially more rigorous than a typical sophisticated retail process and more structured than what most pod-shop analysts actually execute under earnings-season pressure. In ambition, it is roughly equivalent to the **Point72 Academy + Street of Walls Investment Thesis curriculum + Schilit's forensic playbook + Marathon's capital-cycle framing + a Taiwan-specific microstructure overlay** — stacked in a single document.

The core weaknesses are **structural, not factual**. Three fault lines run through the entire architecture:

**Fault Line 1 — Sequential gates in a parallel-workflow business.** The strict sequential "hard stop at each gate" structure contradicts every documented professional workflow. Byrne Hobart (ex-Point72), Citadel's published risk framework (PCRG), Pershing Square's N-2 filing, Baillie Gifford's Portfolio Construction Group, and Dodge & Cox's investment committee all describe **iterative parallel streams converging at a committee or PM checkpoint** — not linear passes. The framework mistakes the *output* of a well-run process (clean justification across dimensions) for the *process itself*.

**Fault Line 2 — Hedge-fund catalyst doctrine imposed on all styles.** The framework imports conventions from pod-shop long/short practice — dated catalysts required, 0.85 correlation reject, mandatory derivatives/CB positioning gates — that are **style-specific** and would actively damage a quality-compounder, long-term growth, or deep-value mandate.

**Fault Line 3 — Checklist density that violates empirical checklist research.** The framework contains roughly 60–80 explicit criteria plus a 17-item quick-disqualify list. Atul Gawande's checklist research and Boeing's Boorman principle establish **5–9 items per decision point** as the validated cognitive range; the WHO Safe Surgery Checklist has 19 items total across three pauses. Checklists exceeding this range "degrade compliance and become ritualistic" under time pressure. Pabrai's ~80-item list is a deliberate outlier used only at the *end* of diligence, not as a gate-by-gate screen.

**One-sentence verdict:** The framework is the product of an analyst who has read widely and respected the rigor of the best practitioners. Version 2 is what those practitioners *actually do* — simultaneously leaner in architecture and richer in behavioural discipline, with the five missing elements (variant perception, position sizing, pre-mortem, sell taxonomy, management forensic) added and the structural over-engineering compressed.

The investor who benefits most from the current framework is a **single-analyst or small-team Taiwan-focused long/short discretionary investor running a concentrated book of 12–14 names with 2–6 week diligence cycles** — essentially an independent analogue to a Citadel Surveyor sector pod adapted to Taiwan microstructure. That is a narrow fit, but a real and valuable one.


## 2. Framework Outline | 框架輪廓

### English

The framework is a **sequential pre-trade architecture** with the following declared gate structure:

| Gate | Core Question | Declared Effort Weight |
|------|--------------|----------------------|
| Gate 1 | Industry direction — does macro/sector provide structural tailwinds? | ~10% |
| Gate 2 | Business model in one paragraph + moat + KPIs | ~10% |
| Gate 2.5 | Quick-disqualify triage (17-item; liquidity, solvency, disposition status) | ~5% |
| Gate 3 | Forensic depth: 3A Operating quality / 3B Balance sheet / 3C Ownership & positioning / 3D Derivatives & CB / 3E Data integrity | ~35–40% |
| Gate 4 | Cross-source industry validation (peer revenue, ETF flow, institutional alignment) | ~10% |
| Gate 5 | Value-chain positioning — lead/lag dynamics (upstream → TSMC → OSAT → IC design → EMS → end customer) | ~10% |
| Gate 6 | Strategic portfolio fit — beta, correlation (hard reject at >0.85), theme overlap, position count (sweet spot: 12–14 names) | ~5% |
| Gate 6.5 | Tactical entry architecture — valuation context, volatility, liquidity, crowding, event proximity | ~5% |
| Gate 7 | Written thesis, dated catalyst (required; reject if none), explicit invalidation criteria | ~5% |

**Declared style:** Concentrated, discretionary, long-biased or long/short, Taiwan-focused, industry-first, sequential gate-driven.

**Declared sweet spot:** 12–14 names per book; 2–6 week diligence cycles per new name.

**Critical observation:** The framework's declared effort allocation (35–40% on Gate 3 forensics) reflects short-fund and distressed-credit practice, not long-only or generalist long/short. This mismatch between the declared user profile and the implied effort budget is one of the framework's central structural tensions.



## 3. Side-by-Side Comparison | 並排比較

### English

*Primary reference: Document 4. Supporting citations from Documents 1–3 where they add non-redundant institutional detail.*

| Framework Component | What This Framework Does | What Documented Professionals Do | Match / Divergence | Practical Implication | Recommendation |
|---|---|---|---|---|---|
| **Gate 1 — Industry direction first** | Mandatory top-down industry call before security selection | Style-dependent. Marathon (*Capital Returns*, Chancellor) and sell-side sector coverage are industry-first. Fundsmith, Nomad, Akre, Baillie Gifford LTGG, Buffett, Pulak Prasad are explicitly **company-first** — they derive sector context after identifying a business | Partial match; presents as universal what is a stylistic choice | Biases framework toward cyclicals and supply-chain names; forecloses the entire quality-compounder process family that has generated the best documented long-term returns | **Modify:** make industry direction a parallel input, not a prerequisite gate |
| **Sequential hard-stop gate flow** | Gates 1→7 executed in order; each is pass/fail | Hobart (pod analyst, ex-Point72), Street of Walls, Citadel PCRG, Pershing Square N-2 filing, Baillie Gifford Portfolio Construction Group, Dodge & Cox investment committee: all describe **iterative parallel work** — Micro (company) + Macro (industry) + Setup (positioning) integrated at pitch/IC checkpoint time | Diverges sharply from all documented practice | In real conditions, analyst either skips gates or cargo-cults them; rigidity slows response to new information | **Modify:** replace with three concurrent workstreams converging at a single memo checkpoint |
| **Gate 2 — Business model in one paragraph + moat + KPIs** | Qualitative screening | Universal across quality-compounder and L/S shops; Baillie Gifford's Ten Questions, Akre's three-legged stool (compounding machine / skilled reinvestor / long runway), Dorsey moat taxonomy all execute this | Strong match | Genuinely high-ROI gate | **Keep unchanged** |
| **Triage filter (liquidity, solvency, disposition list)** | Hard screens before expensive work | Universal at every shop; efficient and cheap | Strong match | Sensible early kill | **Keep; automate against FinMind / TEJ feeds** |
| **Gate 3 — 35–40% of effort on forensics** | Mandatory deep forensic on every name | Short-only funds (Kynikos/Chanos, Muddy Waters/Block, Greenlight-on-shorts), EM, distressed credit: yes. Generalist long-only: **red-flag screen only** (~Schilit 7 shenanigans), with deep forensic only when flags trigger (~10–20% total effort). Pod L/S (Hobart): realistically 10–15% of effort per name | Heavy divergence from long-only; consistent with short/EM/distressed | ~40–80 hours per name makes the pipeline infeasible for >6–10 names/year at a normal pace | **Modify:** two-stage — mandatory red-flag screen (~10 items, 30–60 min); full forensic only when flags trigger |
| **CFO/NI ≥ 0.8 as hard reject trigger** | Hard gate | Schilit documents CFO/NI gap as a **yellow flag**, not a hard threshold. Fundsmith/Akre use cash conversion as preference, not cutoff. Short sellers (Block, Chanos, Einhorn) weight it more heavily, but still contextually | Correct direction, wrong rigidity | Will false-reject seasonally working-capital-heavy businesses, fast-growers reinvesting free cash, and cyclicals mid-cycle | **Modify:** treat as a flag triggering deeper review, not automatic rejection |
| **Gate 3C — Ownership & positioning (institutional flow, foreign ownership, margin/short, SBL, broker branch, top-10 concentration)** | Mandatory panel | Pod L/S: short interest + borrow cost + skew are institutional-grade (Rapach, Ringgenberg & Zhou, *JFE* 2016; Boehmer 2022). 13F mostly a crowding check. Broker-branch (分點) is Taiwan-retail culture; limited foreign-institutional use; academic support thin; regime-sensitive, increasingly noisy post-2023 as foreign flow and ETF mechanics dominate | Mixed — some genuine edge, some noise | SBL utilisation and institutional flow signals are real; 分點 risks over-fitting to retail behaviour | **Modify:** keep SBL/borrow cost, foreign institutional flow, short interest; **demote 分點 to supplementary context** |
| **Gate 3D — Derivatives & CB signals** | Mandatory | Yang et al. 2025 (*Pacific-Basin Finance Journal*) confirms TXO PCR outperforms VIX-TW for option writing. Foreign OI and futures basis have documented explanatory power (Chuang et al. 2017). CB signals matter when CBs are outstanding; CBAS flow is niche | Partial match; strongest for Taiwan | Valuable in Taiwan; largely inapplicable outside East Asia | **Keep for Taiwan; make conditional** — activate only when CB outstanding or options open interest meets minimum depth |
| **Gate 4 — Cross-source industry validation** | Peer revenue, ETF flow, peer institutional alignment | Morgan Stanley Charlie Chan, Bernstein Stacy Rasgon, CLSA Sebastian Hou all anchor on TSMC/supply-chain read-across after the 10th-of-month monthly revenue | Strong match for Asia tech | **Substantially redundant** with Gate 1 + Gate 5 | **Merge** into Gate 1 or Gate 5; eliminate as a standalone gate |
| **Gate 5 — Value-chain positioning** | Identify accumulation lead/lag in supply chain | Asia semi analysts at MS, Bernstein, CLSA literally organise research this way: upstream wafer → TSMC → OSAT → IC design → EMS → end customer | Strong match | Highly valued; mostly relevant for tech/cyclicals | **Keep; scope-limit to supply-chain-heavy industries** |
| **Gate 6 — Portfolio fit with 0.85 correlation hard reject** | Sector/correlation/beta review; reject if correlation >0.85 | Pods enforce beta-neutral, factor-neutral, sector balance **continuously via risk system** (Citadel PCRG per Risk.net). Dalio's "15 uncorrelated bets" is a *principle*, not a threshold. Druckenmiller **intentionally stacks correlated exposure** when conviction is high. No documented fund uses 0.85 specifically | Conceptually right; mechanically invented | Hard threshold has no evidentiary basis; will reject legitimate concentration bets; adds false precision | **Modify:** replace hard reject with "document correlation and justify explicitly if >0.7"; make portfolio fit a live dashboard, not a one-time gate |
| **Gate 6.5 — Tactical entry architecture** | Explicitly separates valuation, volatility, liquidity, crowding, catalyst proximity as orthogonal dimensions | Druckenmiller: "I never use valuation to time — valuation tells me how far the market can go *once a catalyst enters*." Street of Walls explicitly teaches **Setup** as a first-class pillar, "the most overlooked part of a stock pitch." Steinhardt: variant perception + catalyst convergence | Strong match; one of the framework's strongest features | Separating "good business" from "good entry" is rare and genuinely valuable | **Keep; refine with reverse-DCF (Mauboussin/Rappaport) as the valuation backbone** |
| **Dated catalyst required; reject if none** | Mandatory | Point72 Academy, Street of Walls pod doctrine: yes. Fundsmith, Akre, Nomad, Baillie Gifford, Buffett, Klarman deep value, Druckenmiller macro-tactical: **no**. Einhorn held Allied Capital 6 years without a dated catalyst; Ackman held Herbalife for years | Specific to one style; miscalibrated for others | Damages quality-compounder and long-duration theses; forces manufactured short-term catalysts | **Modify:** in event-driven/tactical mode, require dated catalyst; in quality-compounder/long-duration mode, require a "thesis-validation milestone" (a specific observable, even if undated) |
| **Written thesis + invalidation criteria** | Mandatory | Universally recommended (Annie Duke kill-criteria, Klein pre-mortem, Mauboussin BAIT taxonomy); **inconsistently implemented even at top shops** | Exceeds typical implementation | Genuinely rare and valuable; most shops talk about this and don't enforce it on paper | **Keep; this is a distinctive strength** |
| **Quick-disqualify 17-item checklist** | Pre-filter | Pabrai uses ~80-item checklist only at the **end** of diligence (a deliberate outlier). Gawande's research validates 5–9 items per decision point; Boorman (Boeing chief checklist designer) stated >9 items "degrade compliance and become ritualistic" | Violates empirical checklist research | Becomes analytical theater under time pressure | **Compress to 8–10 items; merge overlapping categories** |
| **Taiwan data (monthly revenue, SBL, TXO PCR, institutional flow, supply chain)** | Core inputs | Matches MS Charlie Chan and CLSA Sebastian Hou actual workflows; Hung et al. on revenue momentum; Yang et al. 2025 on TXO PCR; Chang 2025 on warrant IV skew. Monthly revenue is **the** Taiwan event | Strong match; framework strength highest here | Genuine, academically-supported edge | **Keep; note it does not port outside Taiwan/Korea** |
| **景氣對策信號 as timing input** | Listed as macro leading indicator | Wu & Tang (2012): only M1B of the nine components has significant explanatory power. Taiwan 0050-ETF backtests using 景氣燈號 **underperform simple DCA** as a timing signal | Diverges from its own evidence base | Injects noise if used as a timing gate; negative-alpha signal for market timing | **Demote to contextual regime-backdrop; do not use as timing gate** |
| **Broker-branch (分點) accumulation** | Listed as primary in Gate 3C | Dominant in Taiwanese retail/prop culture; limited foreign institutional use; academic validation thin; increasingly noisy post-2023 as foreign flow and ETF mechanics dominate | Retail-flavoured; regime-sensitive | Low-alpha in current market structure | **Demote to supplementary** |
| **Position sizing logic** | Absent | Druckenmiller and Soros: "Sizing is 70–80% of the equation." Freeman-Shor (*Art of Execution*, analysis of 1,866 investments across 45 top managers): hit rates were only ~49%; the differentiator was **sizing up winners and cutting losers**. Kelly, fractional Kelly, vol-scaled risk contribution, and conviction-tier sizing are all standard tools | Absent — structural void | Framework decides "buy or not" but not "how much"; this is one of the largest missing elements | **Add: mandatory position sizing framework tied to conviction and edge** |
| **Sell discipline** | Collapsed into thesis invalidation criteria only | Freeman-Shor's empirical taxonomy (Assassins / Hunters / Rabbits / Raiders / Connoisseurs): top managers follow explicit rules such as "review at −20% drawdown" and "let winners run past target." As written, framework could produce a "Rabbit" — holding losers because invalidation technically hasn't triggered | Necessary but insufficient | Missing forced review triggers, add-on rules, time-stops for dead money | **Add: sell-discipline taxonomy per Freeman-Shor; pre-commit rules at entry** |
| **Variant perception** | Absent | Steinhardt's defining concept. Mauboussin/Rappaport *Expectations Investing*. Marks' second-level thinking. Every buy-side pitch interview rubric. All require explicit articulation of *what the market believes vs. what you believe*, ideally via reverse-DCF | Absent — structural void | Even a clean pass through all seven gates doesn't establish edge if you cannot name the counterparty error | **Add: mandatory memo field — "The market expects X; I believe Y; the gap is driven by [behavioral / analytical / informational / technical] error"** |
| **Management quality assessment** | Gate 2 mentions "moat" but no systematic process | Akre's three-legged stool. Buffett's rationality/candor/resistance triad. Marcellus's Coffee Can framework. DEF 14A / proxy analysis for incentive-comp structure. Capital-allocation track record (M&A hit rate, buyback timing, ROIC trajectory). Candor test across 5–10 years of letters. Insider trading pattern (Form 4 for US; 內部人持股轉讓 for Taiwan) | Absent — structural void | For Taiwan: especially glaring given family-pyramid governance structure and share-pledging red flag | **Add: management forensic as mandatory module; in Taiwan, include director share-pledging ratio** |
| **Scuttlebutt / channel checks** | Absent | Fisher-style customer/supplier interviews endorsed by Buffett, Weschler, Combs. Used extensively at pod shops via Tegus/AlphaSense, GLG, Guidepoint, Third Bridge. Post-Rajaratnam compliance architecture requires explicit guardrails (recorded, logged, pre-approved expert list), but omitting entirely is unusual | Absent | Structural time-lag vs. professionals with real-time human intelligence | **Add: channel-check protocol with compliance guardrails** |
| **Pre-mortem / decision journal / post-mortem** | Absent | Klein's pre-mortem (20–30 minutes; empirically raises risk identification by ~30%). Annie Duke decision journal. Dalio's Issue Log. Brett Steenbarger performance journaling. All are validated behavioural-hygiene tools | Absent | No feedback loop to improve the framework itself over time | **Add: pre-mortem before entry; decision journal per position; post-mortem at exit (Duke's "resulting" discipline)** |



## 4. Strengths | 優勢分析

### English

**4.1 The Valuation/Entry Separation (Gate 6.5) is Unusually Well-Engineered**

Most documented processes fold entry timing into a general "valuation" step; this framework explicitly carves out valuation-vs-history, volatility/correlation, liquidity/execution, and crowding/catalyst-proximity as orthogonal dimensions. That mirrors Druckenmiller's stated practice ("I never use valuation to time — valuation tells me how far the market can go once a catalyst enters") and Street of Walls' Micro/Macro/**Setup** triad, where Setup is called "the most overlooked part of a stock pitch." Few investor letters or published processes make this split as cleanly.

**4.2 Written Thesis + Dated Invalidation Requirement**

This is rarer than it should be and maps directly to best-in-class practice. Annie Duke's kill-criteria work, Klein's pre-mortem research, and Mauboussin's BAIT taxonomy all argue that an investor who cannot write the invalidation ex ante is running on "resulting" rather than process. Most real shops *talk* about kill criteria and don't enforce them in writing. Requiring it on paper is a genuine process upgrade that distinguishes this framework from typical implementation.

**4.3 Taiwan Microstructure Awareness is Professional-Grade**

The framework correctly treats TSMC monthly revenue, foreign institutional flow, securities lending utilisation, and TXO open-interest PCR as first-class inputs — all of which have either peer-reviewed academic support (Hung et al. on revenue momentum; Yang et al. 2025 on TXO PCR; Chuang et al. 2017 on foreign futures OI; Chang 2025 on warrant IV skew) or dominate the actual workflow of Morgan Stanley Charlie Chan and CLSA Sebastian Hou. The industry-chain anchor (upstream wafer → TSMC → OSAT → IC design → EMS → end customer) is literally how Asia semi sell-side organises thinking.

**4.4 Forensic Battery Stronger than Typical Long-Only Practice**

Schilit's cash-flow quality tests, dilution-history tracking, refinancing-wall analysis, auditor-change monitoring, and related-party-transaction scans are the documented toolkit of Chanos at Kynikos, Block at Muddy Waters, and Einhorn at Greenlight on shorts. The Taiwan-specific red-flag panel — director share pledging (董監質押比), cross-affiliate guarantees (背書保證), related-party transactions — which the Rebar Group and Procomp fraud cases produced as hard lessons, is **correctly imported**. Most generic US frameworks would miss these entirely.

**4.5 Triage Filter is Efficient and Cheap**

Killing weak names on liquidity, disposition-stock status, and obvious solvency before expensive work matches how pod shops and concentrated funds actually triage their universe. The cost savings compound across a diligence pipeline.

**4.6 Concentration Discipline Matches Pershing/Akre/Nomad Territory**

The 12–14 name sweet spot is consistent with documented concentrated-fund practice: Pershing Square (8–12 names), Nomad Investment Partnership (<15 names), Akre Focus (~19 names). The deep per-name work is feasible at this concentration level in a way it is not for broader coverage mandates.



## 5. Weaknesses & Blind Spots | 弱點與盲點

### English

**5.1 The Gate Sequence Contradicts Every Documented Professional Workflow**

Professionals work **iteratively with parallel streams**; the framework's strict sequential "hard stop at each gate" is pedagogical in design and will, in real conditions, either be skipped when something urgent happens or cargo-culted when it is not. Hobart on pod analyst life, the Citadel PCRG description, Baillie Gifford's Portfolio Construction Group, and Dodge & Cox's committee model all describe iteration plus checkpoint review — not linear passes. **The framework mistakes the output of a well-run process for the process itself.**

**5.2 Industry-First Is a Style Choice Presented as Universal**

Marathon's capital-cycle approach (*Capital Returns*, Chancellor) and sell-side sector coverage are industry-first. Fundsmith, Nomad, Akre, Baillie Gifford, Buffett, Klarman, and Pulak Prasad are explicitly company-first. The framework's insistence on confirming direction before selection **forecloses the entire quality-compounder family of processes** — the family with the best documented long-term returns.

**5.3 The 35–40% Forensic Budget is Short-Fund Dress Code Applied Generally**

At a concentrated long-only, forensic work is a red-flag triage, with deep forensics only when flags trigger — typically 10–20% of total effort. A pod analyst covering 30–80 names (Hobart's documented day: 5am news scan through continuous catalyst surveillance) cannot spend a third of time on forensics and still monitor incremental data flow. For the framework's nominal 12–14 name book this is *manageable*; scaled to more names or to anything other than Taiwan small/mid-cap it becomes infeasible.

**5.4 Position Sizing Logic is Absent — and That Is the Largest Single Gap**

Druckenmiller and Soros have both stated that sizing is "70–80% of the equation." Freeman-Shor's *Art of Execution* analysed 1,866 investments across 45 top managers and found hit rates were only ~49% — the differentiator was sizing up winners and cutting losers. Kelly Criterion, fractional Kelly, vol-scaled risk contribution, and conviction-tier sizing are all standard professional tools. None appear in this framework. A framework that decides "buy or not" without deciding "how much" is structurally incomplete.

**5.5 Sell Discipline Collapsed to Invalidation Criteria Only**

Thesis invalidation criteria are necessary but not sufficient. Freeman-Shor's empirical taxonomy identifies five manager archetypes — Assassins (cut fast), Hunters (average down methodically), Rabbits (freeze on losses), Raiders (take profits too early), Connoisseurs (let winners run). Top performers follow explicit pre-committed rules: "review at −20% drawdown," "let winners run past target," "time-stop for dead-money positions." The framework as written could produce a "Rabbit" — a manager who holds losers because the formal invalidation condition has not technically been met.

**5.6 Variant Perception is Not Required — the Single Most Consequential Omission**

Steinhardt made variant perception the defining feature of his process. Mauboussin and Rappaport's *Expectations Investing* builds the entire analytical architecture around mapping market expectations via reverse-DCF. Marks' second-level thinking requires explicit articulation of what *everyone else* believes and why your view differs. Every buy-side pitch interview rubric at the top firms requires naming the counterparty error: "who is on the other side of my trade, and why are they wrong?" The framework asks for a thesis but not for a named counter-party error. Without this, even a clean pass through all seven gates does not establish edge — it establishes research, which is not the same thing.

**5.7 Management Quality is Structurally Underweighted**

Gate 2 identifies a moat but does not require a DEF 14A / proxy analysis, an incentive-comp forensic read, a capital-allocation track record scorecard (M&A hit rate, buyback timing, ROIC trajectory), a candor test (language consistency across 5–10 years of annual letters), or an insider trading pattern check (Form 4 for US; 內部人持股轉讓 for Taiwan). Akre's three-legged stool, Buffett's rationality/candor/resistance triad, and Marcellus's Coffee Can framework all make management quality a central, systematically-evaluated criterion. For a Taiwan framework this is especially glaring given family-pyramid governance structures and the share-pledging red flag.

**5.8 Scuttlebutt / Channel Checks / Expert Networks are Absent**

Fisher-style customer and supplier interviews are endorsed by Buffett, Weschler, Combs, and used extensively at pod shops via Tegus, AlphaSense, GLG, Guidepoint, and Third Bridge. Post-Rajaratnam / SAC Capital compliance architecture requires explicit guardrails — recorded, logged, pre-approved expert lists — but omitting channel checks entirely is unusual for any framework claiming professional grade. The framework relies almost exclusively on reported quantitative data, creating a structural time lag against professionals with real-time human intelligence.

**5.9 No Pre-Mortem, Decision Journal, Post-Mortem, or Monitoring Cadence**

Klein's pre-mortem (20–30 minutes; empirically raises risk identification by ~30%), Duke's decision journal, Dalio's Issue Log, and Steenbarger's performance journaling are the validated behavioural-hygiene toolkit. A framework that enters positions through seven gates and exits on invalidation has **no feedback loop to improve itself**. Over time, the framework will be as good as its last reading — not as good as its accumulated experience.

**5.10 The 0.85 Correlation Reject Has No Evidentiary Basis**

No documented fund uses 0.85 as a specific correlation threshold. Dalio's principle is uncorrelated bets without a specific cutoff. Pods enforce factor-residual risk via Barra/Axioma, not a single pairwise number. Druckenmiller intentionally stacks correlated exposure when conviction is high. The hard threshold will produce false rejects — for example, rejecting a second AI beneficiary in an AI-dominated cycle — while providing no protection against the factor risk it purports to address.

**5.11 景氣對策信號 Contradicts Its Own Evidence Base**

Taiwan 0050-ETF backtests using 景氣燈號 as a timing signal underperform simple dollar-cost averaging. Wu and Tang (2012) find only M1B of the nine component indicators has significant explanatory power for market returns. As a timing input it is a negative-alpha signal.

**5.12 Checklist Density Violates Gawande's Checklist Research**

The WHO Safe Surgery Checklist has 19 items across three pauses. Boeing cockpit checklists average 5–9 items per phase. Boorman (Boeing's lead checklist designer) told Gawande that checklists exceeding ~9 items per decision point "degrade compliance and become ritualistic." This framework contains roughly 60–80 explicit criteria plus a 17-item quick-disqualify list. Under time pressure — which is the condition that matters — it will become analytical theatre.



## 6. Distinctive Elements | 差異化特色

### English

Several elements are genuinely differentiated versus standard practice and deserve explicit protection in any redesign:

**6.1 Explicit Strategic/Tactical Split (Gate 6 vs. Gate 6.5)**
More structured than all but a handful of published frameworks. Maps to practices scattered across Druckenmiller (entry timing on technicals), Steinhardt (catalyst-forces-convergence), and Street of Walls (Setup as first-class) but consolidates them in one document in a way no single source does.

**6.2 Written Invalidation Requirement**
Exceeds typical implementation even at top shops. Most discretionary investors talk about kill criteria; few write them before entering. Annie Duke and Gary Klein would approve. This is the framework's clearest process differentiator from retail practice.

**6.3 Taiwan-Specific Microstructure Gate**
The combination of disposition-stock awareness, price-limit regime sensitivity, CB dilution tracking, foreign SBL dynamics, and monthly revenue integration is more sophisticated than generic US frameworks ported to Asia. Taiwanese retail investors use 分點 and 融資融券 as primary inputs; foreign institutions under-weight these; integrating both with a clear academic and practitioner evidence base is a real structural edge.

**6.4 Convertible Bond Signal Integration**
Most equity frameworks ignore CBs entirely. For Taiwan small/mid-cap tech where CB issuance is a common dilution pattern and the CBAS market functions as an early-warning system for credit stress, this integration is legitimate and under-utilised by foreign practitioners.

**6.5 TSMC-as-Anchor Monthly Revenue Integration**
Matches how Morgan Stanley Asia Semi (Charlie Chan) and CLSA (Sebastian Hou) actually organise their research flow. Few retail-facing or generalist frameworks formalise this lead indicator relationship explicitly.

**6.6 Taiwan Governance Red Flags (Correctly Imported)**
The Rebar Group and Procomp cases established that director share pledging (董監質押比), cross-affiliate guarantees (背書保證), and related-party transactions with subsidiaries are the specific failure modes in Taiwanese corporate governance. Most frameworks importing from US practice would miss these entirely. Their explicit inclusion is a genuine contribution.


## 7. What Should Be Simplified | 應簡化之處

### English

**7.1 Collapse Gate 4 into Gates 1 and 5**
Cross-source industry validation, peer revenue trends, ETF flow confirmation, and value-chain positioning overlap substantially. Run them as a single "industry read" pass with an explicit divergence flag. Eliminating Gate 4 as a standalone gate removes one sequential bottleneck without losing any analytical content.

**7.2 Compress Gate 3 from Universal Deep-Forensic to Two-Stage Filter**
Stage 1: Schilit-style red-flag screen (~10 items, 30–60 minutes). Stage 2: full forensic battery only when Stage 1 flags trigger. This matches actual long-only and pod-analyst practice and keeps the framework scalable beyond 6–10 names per year.

**7.3 Demote 分點 Accumulation from Primary to Supplementary**
Regime-sensitive, retail-flavoured, academic support thin, increasingly noisy post-2023 as foreign flow and ETF mechanics dominate. Retain as contextual colour, not as a signal in the scoring panel.

**7.4 Demote 景氣對策信號 to Contextual Regime-Backdrop**
The evidence does not support timing use. Relegate to background macro context.

**7.5 Downgrade the 0.85 Correlation Hard Reject**
Replace with a documentation requirement: analyst must state the correlation to the existing book and explicitly justify if the overlap is high. This forces the same thinking without generating false rejects.

**7.6 Compress Quick-Disqualify from 17 Items to ~8**
Merge overlapping categories:
- Governance flags + auditor change + director selling → single "governance red flag"
- Correlation + sector overlap → "deliberate overweight, explicitly justified"
- Revenue collapse + cash burn rate → "survival risk"
- Liquidity + ADV + free float → "tradability"

**7.7 Automate the Triage Filter**
Liquidity, disposition-list status, revenue collapse, corporate-action distortion are all programmable against FinMind / TEJ data feeds. No analyst judgment time should be consumed here.

**7.8 Make the Dated-Catalyst Requirement Mode-Conditional**
In event-driven/tactical mode: require a dated catalyst.
In quality-compounder/long-duration mode: require a "thesis-validation milestone" — a specific observable, even if undated (e.g., "three consecutive quarters of gross margin recovery above 45%").



## 8. Style Fit | 風格適配度

### English

| Investor Style | Fit | Key Issues |
|---|---|---|
| **Long/Short Equity (Tiger Cubs, single-manager L/S)** | Strong | Closest native fit. Add sizing logic and Freeman-Shor sell taxonomy |
| **Taiwan / Asia Specialist** | Strong | Microstructure awareness is unusually good; data dependencies match; monthly revenue is the right anchor |
| **Concentrated PM (<15 names)** | Strong | 12–14 name sweet spot matches Pershing/Akre/Nomad territory; deep per-name work is feasible |
| **Deep Value (Klarman, Greenblatt special situations)** | Moderate-to-Strong | Catalyst gate fits event-driven value; forensic depth fits distressed; industry-first is less natural; sizing absent |
| **Cyclical / Macro-Sensitive** | Strong | Industry-first and capital-cycle logic align with Marathon's framework; value-chain lead/lag is directly applicable |
| **Long-Only Fundamental (Capital Group, T. Rowe, Dodge & Cox)** | Moderate | Forensic budget too high; positioning data mostly wasted; industry-first bias fights quality-compounder logic; sizing absent |
| **Event-Driven / Merger Arb** | Moderate | Catalyst + invalidation criteria are native; forensic depth fits; Taiwan microstructure less relevant; legal/transactional timeline module missing |
| **Quality Compounder (Fundsmith, Nomad, Akre, Polen)** | Weak | Industry-first bias, mandatory dated-catalyst requirement, and 0.85 correlation cap are all miscalibrated for this style. Buffett, Smith, and Sleep do not operate this way |
| **Broad-Universe Screener (50+ names)** | Weak | Forensic budget and gate depth make >20 names/year infeasible for a single analyst; framework is not designed for breadth |
| **Multi-Manager Pod Shop (Citadel, Millennium, Point72)** | Moderate | Tactical entry and catalyst requirements align with pod mandates; but sequential forensic structure is incompatible with pod velocity; sizing absent |
| **Systematic / Quantitative** | Very Weak | Too qualitative, manual, and document-heavy for systematic deployment; explicitly designed for concentrated, discretionary PMs |



## 9. Backtesting & Validation Design | 回測與驗證設計

### English

The framework is not well-suited for a single black-box total backtest. The correct approach is layer-by-layer validation: test whether each gate has predictive power or risk-filtering effect independently before testing whether the combined portfolio holds up net of costs. The framework's edge may not come from any single factor, but from *ordering* — first eliminating the wrong industries and wrong vehicles, then using quality, events, and trading feasibility to improve the hit rate.

**Gate Structure for Testability**

| Layer | Content | Treatment |
|---|---|---|
| **Hard Constraints** | Suspended, delisting pipeline, clearly insolvent, data missing, disposition-listed | Automated; exclude from universe; no analyst time |
| **Soft Scores** | Industry direction, operating quality, balance sheet quality, valuation, growth, entry | Rankable; test monotonicity individually before compositing |
| **Monitoring Flags** | Governance anomalies, derivatives divergence, catalyst proximity, broker pattern changes, director pledging changes | Contextual monitoring; not direct score inputs |

**Critical Data Integrity Requirements**

All financial, monthly revenue, material announcement, estimate, and industry KPI data must use **announcement dates / as-of dates** — never back-filled with post-revision values. This is the single most important defence against look-ahead bias and the most commonly violated discipline in private backtests.

Taiwan-specific note: TWSE's own P/E and P/B ratios explicitly state they use only "the most recently formatted quarterly report published on MOPS at the time of calculation." Any backtest that uses post-restatement financials will overstate strategy viability.

**Multiple-Testing Discipline**

White's Reality Check, Bailey et al. on backtest overfitting, and Novy-Marx on multi-signal strategy overfitting all establish that a framework with 60–80 criteria tested against historical data without rigorous out-of-sample and walk-forward validation will produce spurious results. The correct protocol is:

1. Define the universe with point-in-time data
2. Decompose gates into hard constraints, soft scores, and flags
3. Test each gate's marginal contribution independently
4. Composite only gates with individually validated predictive power
5. Apply liquidity, cost, and tax constraints
6. Out-of-sample validation with a held-out period
7. 5-year train / 1-year walk-forward rolling test
8. Output: performance attribution, factor regression, capacity stress

**Taiwan-Specific Cost Floor**

Per ROC Ministry of Finance and TWSE regulations: stock sellers bear **0.3% securities transaction tax**; day-trading qualifying transactions bear **0.15%** through December 31, 2027. Any Taiwan backtest omitting this will systematically overstate net returns. At 2–4 round-trips per year on a 12–14 name book, the aggregate cost drag is material.



## 10. Version 2 Redesign Blueprint | 第二版重設計藍圖

### English

**Governing Principle:** Version 2 is simultaneously **leaner in architecture** and **richer in behavioural discipline**. The current framework is over-engineered where professionals use intuition, parallelism, and iteration — and under-engineered where professionals use explicit protocols: variant perception, position sizing, pre-mortem, sell taxonomy, management forensic, and channel checks.

---

### Keep Unchanged | 保留不變

| Element | Rationale |
|---|---|
| Business-model-in-one-paragraph test | Universal, high-ROI, fast |
| Moat identification (Gate 2) | Baillie Gifford Ten Questions; Akre three-legged stool; genuinely valuable |
| Triage filter — automate it | Sensible, cheap, programmable |
| Taiwan microstructure: SBL, foreign institutional flow, TXO PCR, monthly revenue, industry-chain anchor | Academically supported; matches MS/CLSA workflow; genuine edge |
| Strategic / tactical entry split (Gate 6 vs. 6.5) | Framework's clearest structural strength |
| Written thesis + invalidation criteria | Distinctive and genuinely rare |
| Taiwan governance red flags: share pledging, cross-guarantees, related-party transactions | Correctly imported from Rebar/Procomp cases |

---

### Reorder — Replace Sequential Gates with Three Parallel Workstreams | 重排

Replace the seven sequential gates with **three concurrent workstreams** converging at a single written-memo checkpoint. This is the Street of Walls + Dodge & Cox + Hobart pod-analyst structure — how documented professionals actually work.

```
WORKSTREAM A — Industry / Macro
  ├─ Sector tailwind / capital-cycle phase (Marathon framing)
  ├─ Value-chain positioning: upstream → TSMC → OSAT → IC Design → EMS
  ├─ Peer revenue / ETF flow cross-check (formerly Gate 4 — now merged here)
  └─ 景氣對策信號: backdrop only, not timing gate

WORKSTREAM B — Company Quality
  ├─ Business model + moat + KPIs (one paragraph)
  ├─ Management quality forensic (NEW):
  │     • Incentive comp structure (proxy / DEF 14A)
  │     • Capital allocation track record: M&A hit rate, buyback timing, ROIC trajectory
  │     • Candor test: 5–10 years of annual letter language
  │     • Taiwan: director share-pledging ratio (董監質押比)
  ├─ Red-flag screen (~10 items; 30–60 minutes):
  │     • CFO/NI divergence > threshold? → flag (not auto-reject)
  │     • Director share pledging > 50%? → flag
  │     • Cross-affiliate guarantees? → flag
  │     • Auditor changed in past 3 years? → flag
  │     • Related-party revenue > 30% of total? → flag
  │     • Debt maturity wall within 18 months? → flag
  │     • Historical dilution > 15% over 3 years? → flag
  │     • Governance controversy or legal proceedings? → flag
  │     [Full forensic battery only if 2+ flags trigger]
  ├─ Scuttlebutt / channel check protocol (NEW):
  │     • 2–5 calls via Tegus / AlphaSense / Third Bridge
  │     • Customer / supplier / former employee sampling
  │     • MNPI firewall: recorded, logged, pre-approved expert list
  └─ Valuation: reverse-DCF to map market expectations (Mauboussin / Rappaport)

WORKSTREAM C — Setup / Positioning / Entry
  ├─ Taiwan microstructure (conditional overlay):
  │     • Foreign institutional flow + SBL utilisation
  │     • TXO open-interest PCR (Yang et al. 2025)
  │     • CB pricing / conversion premium (only if CB outstanding)
  │     • 分點 data: supplementary context only
  ├─ Tactical entry: volatility, liquidity, crowding, catalyst proximity
  └─ Portfolio fit: sector/factor/correlation → document; justify if correlation > 0.7

         ↓ CONVERGE AT WRITTEN MEMO CHECKPOINT ↓

MEMO BOTTOM PANEL (new mandatory fields):
  ├─ Variant Perception (REQUIRED):
  │     "The market expects [X]. I believe [Y].
  │      The gap is driven by [behavioral / analytical / informational / technical] error."
  ├─ Scenario EV (bull × prob + base × prob + bear × prob = expected IRR)
  ├─ Position Sizing:
  │     • Target $ risk contribution per name
  │     • Fractional Kelly ceiling
  │     • Conviction tier: starter / core / high-conviction
  ├─ Catalyst path OR thesis-validation milestone (mode-dependent)
  ├─ Written invalidation criteria (existing strength — keep)
  └─ Pre-Mortem (Klein protocol, 20–30 minutes):
        "Assume it is 18 months from now and this position has lost 40%.
         What went wrong? Which assumption was most fragile?"
```

---

### Add Seven Missing Elements | 新增七個缺失元素

**1. Variant Perception / Reverse-DCF**
Mandatory memo field per Mauboussin–Rappaport *Expectations Investing* and Steinhardt's process: "The market expects X; I believe Y; the gap is driven by [behavioral / analytical / informational / technical] error." Without naming the counterparty error, there is no demonstrable edge.

**2. Management-Quality Forensic**
Proxy / DEF 14A analysis: incentive comp structure, capital-allocation track record (M&A hit rate, buyback timing, ROIC trajectory), candor test across 5–10 years of letters, insider trading pattern. For Taiwan: director share-pledging ratio as a mandatory red-flag check.

**3. Position Sizing Logic**
Tied to conviction and edge. Suggested framework:
- Target $ risk contribution per name (e.g., 1–2% of portfolio AUM at risk per position)
- Fractional Kelly ceiling (typically 0.25× full Kelly to limit ruin risk)
- Conviction tiers: Starter (0.5–1%), Core (2–4%), High-Conviction (5–8%)
- Rule: "Size up when right" (Druckenmiller) — pre-define the add-on trigger

**4. Scenario EV with Explicit Probabilities**
Bull / base / bear scenarios with payoffs and assigned probabilities → expected IRR. Replaces single-point price targets. Per Mauboussin: forces explicit acknowledgement of the range of outcomes rather than anchoring on the base case.

**5. Scuttlebutt / Channel-Check Protocol with Compliance Guardrails**
Target 2–5 expert calls per new name via Tegus / AlphaSense / Third Bridge. Fisher-style customer, supplier, and former-employee sampling. Explicit MNPI firewall: calls recorded, logged, sourced from a pre-approved expert list.

**6. Pre-Mortem + Decision Journal + Post-Mortem**
- **Pre-mortem** (Klein): before entry, spend 20–30 minutes imagining the position has failed and writing the failure narrative. Empirically raises risk identification by ~30%.
- **Decision journal**: one-page entry per position at entry (thesis, probabilities, emotional state, expected review date).
- **Post-mortem** at exit: separate decision quality from outcome (Duke's "resulting" discipline) — was the process right regardless of the outcome?

**7. Sell-Discipline Taxonomy (Freeman-Shor)**
Pre-commit one of three exit archetypes at entry:
- **Assassin mode** (event-driven / tactical): cut at predefined loss threshold, no exceptions.
- **Hunter mode** (value / deep-value): average down methodically per pre-defined rules; maximum add size defined at entry.
- **Connoisseur mode** (quality compounder): let winners run past initial target; review at predefined intervals; time-stop for dead-money positions.

In all modes: **forced review at −20% drawdown**, regardless of whether formal invalidation criteria have triggered.

---

### Delete or Downgrade | 刪除或降級

| Element | Action | Replacement |
|---|---|---|
| Sequential gate architecture as mandatory | **Delete** | Three parallel workstreams with memo checkpoint |
| Gate 4 as standalone | **Delete** | Merge into Workstream A |
| 0.85 correlation hard reject | **Delete** | "Document and explicitly justify if >0.7" |
| 景氣對策信號 as timing gate | **Downgrade** | Contextual regime backdrop only |
| 分點 as primary signal | **Downgrade** | Supplementary contextual colour |
| Full forensic battery as universal mandatory | **Downgrade** | Red-flag screen gates entry to full forensic |
| 17-item quick-disqualify checklist | **Compress** | 8-item checklist (merged categories) |
| CFO/NI ≥ 0.8 as auto-reject | **Downgrade** | Flag triggering review, not rejection |
| Dated catalyst as universal requirement | **Downgrade** | Mode-conditional (event-driven vs. compounder) |

---

### The Version 2 Document Format | 第二版文件格式

**A two-page living document per name:**

```
PAGE 1 — Three-Column Parallel Research
┌─────────────────┬──────────────────┬──────────────────────┐
│  INDUSTRY/MACRO │  COMPANY QUALITY │  SETUP/ENTRY         │
│                 │                  │                      │
│  • Sector phase │  • BM + moat +   │  • Taiwan micro      │
│  • Value chain  │    KPIs          │    structure         │
│  • Peer echo    │  • Mgmt forensic │  • Tactical entry    │
│  • Macro regime │  • Red-flag      │  • Portfolio fit     │
│                 │    screen        │  • Correlation (doc) │
│                 │  • Channel       │                      │
│                 │    checks        │                      │
└─────────────────┴──────────────────┴──────────────────────┘

PAGE 2 — Synthesis Bottom Panel
┌──────────────────────────────────────────────────────────┐
│  VARIANT PERCEPTION (required)                           │
│  "Market expects X. I believe Y. Gap driven by [type]."  │
├──────────────────────────────────────────────────────────┤
│  SCENARIO EV   Bull: __% × __% + Base: __% × __% + Bear │
├──────────────────────────────────────────────────────────┤
│  POSITION SIZING   Tier: __ / $ risk: __ / Kelly: __     │
├──────────────────────────────────────────────────────────┤
│  CATALYST PATH or THESIS MILESTONE (mode-dependent)      │
├──────────────────────────────────────────────────────────┤
│  INVALIDATION CRITERIA (explicit, pre-committed)         │
├──────────────────────────────────────────────────────────┤
│  PRE-MORTEM: "If −40% in 18 months, what failed?"        │
├──────────────────────────────────────────────────────────┤
│  EXIT ARCHETYPE: Assassin / Hunter / Connoisseur         │
│  Forced review trigger: −20% drawdown in all modes       │
└──────────────────────────────────────────────────────────┘
```

**Accompanying infrastructure:**
- **Live portfolio dashboard** (not a gate): sector/factor/correlation/beta exposure tracked continuously
- **Decision journal**: one-page entry per position, reviewed at each monitoring cadence
- **Monitoring cadence**: weekly for tactical/L/S mode; quarterly for quality-compounder mode
- **Post-mortem log**: completed at every exit; filed for process improvement


## 11. Priority Improvement Roadmap | 優先改進路線圖

### English

| Priority | Action | Source | Expected Benefit | Trade-off |
|---|---|---|---|---|
| **Critical** | Replace sequential gate architecture with three parallel workstreams + memo checkpoint | Doc 4 (primary) | Eliminates the core structural mismatch with how documented professionals actually work | Requires rewriting the operational SOP |
| **Critical** | Add mandatory variant-perception / reverse-DCF memo field | Doc 4 (Steinhardt, Mauboussin/Rappaport) | Establishes that edge exists before deploying capital; prevents high-quality research from masquerading as an investment thesis | Requires explicit market-expectations modelling |
| **Critical** | Add position sizing framework (fractional Kelly + conviction tiers) | Doc 4 (Druckenmiller/Soros, Freeman-Shor) | Converts research edge into portfolio edge; addresses the 70–80% of the equation currently absent | Reduces discretionary flexibility |
| **Critical** | Add Freeman-Shor sell-discipline taxonomy; pre-commit archetype at entry | Doc 4 (Freeman-Shor *Art of Execution*) | Prevents Rabbit behaviour (holding losers on technical invalidation grounds); forces pre-commitment | Requires explicit rules that feel constraining in the moment |
| **High** | Add Klein pre-mortem before every entry | Doc 4 (Klein; Duke) | Empirically raises risk identification by ~30%; forces engagement with fragile assumptions | 20–30 minutes per new position |
| **High** | Add management quality forensic as explicit mandatory module | Doc 4 (Akre, Buffett, Marcellus) | Fills the largest qualitative gap; especially important for Taiwan given family-pyramid governance | Requires proxy/DEF 14A review per new name |
| **High** | Compress Gate 3 to two-stage filter (red-flag screen → full forensic conditional) | Doc 4 (Schilit, Hobart) | Makes the framework scalable beyond 6–10 names/year | Red-flag screen items need clear definitions |
| **High** | Compress 17-item quick-disqualify to ~8 items | Doc 4 (Gawande, Boorman) | Restores cognitive usability under time pressure | Requires explicit merging of overlapping items |
| **High** | Remove 0.85 correlation hard reject; replace with "document and justify" | Doc 4 | Eliminates false rejects; preserves the risk-awareness intent | None — strictly superior change |
| **High** | Collapse Gate 4 into Workstream A (Parallel Industry/Macro) | Doc 4 | Removes redundant gate; reduces friction | None |
| **Medium** | Add scuttlebutt / channel-check protocol with compliance guardrails | Doc 4 (Fisher, Tegus/AlphaSense model) | Fills structural time-lag vs. real-time intelligence professionals | Requires expert network access and compliance setup |
| **Medium** | Add scenario EV with explicit probabilities (bull/base/bear × payoff) | Doc 4 (Mauboussin) | Forces engagement with outcome range; replaces anchored single-point targets | Requires probability assignment discipline |
| **Medium** | Add decision journal and post-mortem log | Doc 4 (Duke, Dalio) | Creates feedback loop for framework improvement over time | Maintenance overhead |
| **Medium** | Demote 分點 to supplementary; demote 景氣對策信號 to backdrop | Doc 4 (academic evidence review) | Removes negative-alpha inputs from scoring panel | None |
| **Medium** | Establish point-in-time data policy for any backtest | Docs 1–3 (CRSP, LSEG, TEJ) | Prevents look-ahead bias from overstating strategy viability | More expensive data required |
| **Lower** | Mode-conditional catalyst requirement (event-driven vs. compounder) | Doc 4 | Unlocks quality-compounder style compatibility without damaging tactical L/S discipline | Requires explicit strategy-mode declaration at fund level |
| **Lower** | Live portfolio dashboard replacing Gate 6 | Doc 4 (Citadel PCRG model) | Converts one-time gate check into continuous risk monitoring | Dashboard infrastructure required |



## 12. Reference Sources | 參考來源

### English

**Documented Practitioner Processes (Primary Reference)**
- Baillie Gifford — Ten Questions framework; Portfolio Construction Group methodology; public commentary on long-duration compounding discipline
- Dodge & Cox — Investment committee model; iterative parallel research structure
- Capital Group — Analyst research portfolio; modular investment division structure
- Pershing Square — N-2 filing (investment process documentation); 8–12 name concentration model
- Citadel Surveyor / PCRG — Published risk framework description (Risk.net)
- Point72 Academy — Published investment thesis curriculum; pod analyst training documentation
- Street of Walls — Investment thesis training material: Micro / Macro / **Setup** triad
- Fundsmith / Terry Smith — "Do nothing" as explicit philosophy; quality-compounder process documentation
- Nomad Investment Partnership — Quarterly letters (Sleep and Zakaria); <15 name concentration
- Akre Focus Fund — Three-legged stool framework (compounding machine / skilled reinvestor / long runway)
- Byrne Hobart — Pod analyst workflow documentation (ex-Point72)
- Marathon Asset Management — Capital-cycle framework (*Capital Returns*, Chancellor)

**Named Practitioners (Documented Statements)**
- Stanley Druckenmiller — Entry timing philosophy; sizing doctrine ("70–80% of the equation"); correlated concentration when conviction is high
- George Soros — Sizing doctrine
- Michael Steinhardt — Variant perception as defining investment concept
- James Chanos (Kynikos Associates) — Short-selling forensic toolkit
- Carson Block (Muddy Waters) — Short-selling forensic toolkit
- David Einhorn (Greenlight Capital) — Forensic accounting in short selling; Allied Capital case
- Bill Ackman (Pershing Square) — Long-duration thesis holding
- Seth Klarman (Baupost) — Deep value without timing requirements
- Pulak Prasad (Nalanda Capital) — Company-first avoidance screen
- Phil Fisher — Scuttlebutt / channel-check methodology

**Behavioural Research and Checklist Science**
- Atul Gawande — *The Checklist Manifesto*; WHO Safe Surgery Checklist (19 items, 3 pauses)
- Daniel Boorman (Boeing) — Checklist design principle: >9 items per decision point degrades compliance
- Gary Klein — Pre-mortem methodology; ~30% risk identification improvement
- Annie Duke — *Thinking in Bets*; kill-criteria and "resulting" discipline; decision journal
- Michael Mauboussin — BAIT taxonomy; *Expectations Investing* (with Rappaport); scenario EV
- Alfred Rappaport — *Expectations Investing*; reverse-DCF framework
- Brett Steenbarger — Performance journaling in professional trading contexts
- Ray Dalio — Issue Log; "15 uncorrelated bets" principle

**Practitioner Analytics**
- Richard Freeman-Shor — *The Art of Execution*: analysis of 1,866 investments across 45 top managers; Assassin / Hunter / Rabbit / Raider / Connoisseur taxonomy

**Forensic Accounting**
- Howard Schilit — *Financial Shenanigans*: 7 shenanigan categories; CFO/NI gap as yellow flag

**Academic Research (Taiwan / Asia Markets)**
- Hung, M., et al. — Monthly revenue momentum in Taiwan
- Yang, C., et al. (2025, *Pacific-Basin Finance Journal*) — TXO put/call ratio outperforms VIX-TW for option writing signals
- Chuang, W., et al. (2017) — Foreign institutional futures OI explanatory power in Taiwan
- Chang (2025) — Warrant implied volatility skew as a signal in Taiwan
- Rapach, D., Ringgenberg, M., & Zhou, G. (2016, *Journal of Financial Economics*) — Short interest as a predictor of stock returns
- Boehmer, E. (2022) — Institutional short-selling signals
- Wu, H., & Tang, C. (2012) — 景氣對策信號 component analysis; M1B significance; 景氣燈號 underperforms DCA

**Academic Research (Factors and Performance Evaluation)**
- Fama, E., & French, K. — Five-factor model; Kenneth French Data Library
- Jegadeesh, N., & Titman, S. (1993) — Momentum strategy foundational research
- White, H. (2000) — Reality Check for data snooping
- Bailey, D., et al. — Backtest overfitting research
- Novy-Marx, R. — Multi-signal strategy overfitting
- AQR Capital Management — Quality-Minus-Junk factor; low-risk/beta factor research

**Official Regulatory and Market Structure**
- SEC EDGAR — 10-K, 10-Q, 8-K, DEF 14A (proxy), beneficial ownership, Form 4 insider filings
- TWSE MOPS — Financial statements, monthly revenue, material disclosures, director shareholding changes, derivatives information
- TAIFEX — Three institutional categories' aggregate positions in futures and options
- ROC Ministry of Finance / TWSE — Securities transaction tax (0.3% standard; 0.15% day-trade through December 31, 2027)
- TWSE ESG Platform — Domestic ESG disclosure and sustainability reporting

**Data Infrastructure**
- Bloomberg / LSEG (London Stock Exchange Group) — Point-in-time fundamentals, I/B/E/S consensus estimates, SmartEstimate, industry KPIs
- S&P Global / Compustat — Time-stamped fundamental data
- CRSP — Survivor-bias-free historical data; inactive securities
- TEJ (Taiwan Economic Journal) — Point-in-time Taiwanese market data
- FinMind — Taiwan open-data financial API (automation of triage filter)
- Tegus / AlphaSense / Third Bridge / GLG — Expert network platforms for channel checks and scuttlebutt

