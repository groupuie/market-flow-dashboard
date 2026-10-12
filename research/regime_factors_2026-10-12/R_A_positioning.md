# Topic A: Positioning & flows (as of 2026-10-12)

Caveats: the search budget ran out (NAAIM's October reading not found). Bank positioning figures are model estimates relayed by press, not disclosures.

## 1. Quant / systematic money

**CTA trend followers.** *Estimate:* per futures market, trend signal from 1/3/12-month returns (or price vs 20–200-day MAs); position = signal × (≈10–15% target vol ÷ 20–60-day realized vol); blend horizons; scale to industry AUM. Time-series momentum replicates CTA indices (R² 0.36–0.64, correlation 0.66–0.78; AQR). *Forward-return evidence:* sell-side scenario tables only (GS, BofA, UBS, Nomura). Key property is asymmetry: long CTAs face ~$60–70bn US (~$160–185bn global) of 1-month selling in a down tape (GS, Sept 2026); flat/short CTAs buy in every scenario (March 2026: ~$190bn sold, ~$50bn net short, then GS projected buying "under any scenario"). No peer-reviewed test of CTA positioning → 1–4-week index returns found. Trend's own edge has decayed (post-2009 Sharpe 0.12–0.40 vs 0.70–0.84 before; Kurth-Eisler-Rej-Bouchaud, arXiv 2026). Your QQQ result fits the asymmetry story.

**Vol-control / risk parity.** *Estimate:* equity weight = min(≈1.5, 10% ÷ max(21d, 63d realized vol)); risk parity = equal-risk weights across stocks/bonds/commodities levered to ~10% vol (fragile when stock-bond correlation turns positive). DB mimics 25 vol funds. *Evidence:* [sell-side]; ECB (2020) stylized risk-parity model: March 2020 required selling ~225% of capital; impact unquantified. No forward-return study found.

**Leveraged-ETF rebalancing.** *Estimate:* close-of-day flow ≈ AUM × (L²−L) × daily return (Cheng-Madhavan formula): ×2 for 2x, ×6 for 3x. $10bn of 3x semis ETFs on a −5% day ≈ $3bn sold into the close. *Evidence* [academic, mixed]: ~⅓ of late-day volatility, >50% on ±3% days (Rodier-Haryanto-Shum-Hejazi 2012); "economically insignificant" once offsetting fund flows are counted (Ivanov-Lenkey, JFM 2018); effects fade next day (Barbon et al. WP). Close-to-next-day effect, not a 1–4-week predictor.

## 2. Hedge funds
- **GS/MS prime-book net/gross leverage, sector nets:** private; leaks weekly via Bloomberg, Reuters, Tickmill reposts. [sell-side] narrative only (very low net = rally fuel; high gross + falling net = de-grossing risk). No independent test, no free history.
- **13F crowding:** crowded stocks (HF holdings ÷ ADV) earned 11.3% vs 8.5%/yr (t=6.2) yet crashed together in 2008 (Brown-Howard-Lundblad, RFS 2022): premium plus tail risk. Quarterly, 45-day lag → **no 1–4-week timing value**; a "who is exposed" map only. Live proxy: GVIP (GS Hedge Industry VIP ETF) vs SPY.
- **HF beta to Nasdaq:** rolling 60-day beta of HFRX Equity Hedge or GVIP to QQQ; DB uses L/S-HF beta in its composite. [practitioner]; untested.

## 3. Institutional / real money
- **BofA FMS** (cash ≤4.0% sell, ≥5.0% buy; Bull & Bear >8 sell) [sell-side]: B&B gave 17 sells since 2002, ACWI −2–3% over the next 2–3 months, "right 63%". Tiny n; cash mostly <4% since mid-2025 while equities rose → context, not timing.
- **Fund flows** (EPFR paid; ICI free) [peer-reviewed]: 1-SD monthly shift into equity funds ↔ +1.95% same-month return, ~85% reversed within 4 months (Ben-Rephael-Kandel-Wohl, JFE 2012); daily flows half-reverse within 10 days (Israeli data, JFQA 2011).
- **ETF creations/redemptions** (SMH, SOXX, IGV, XLK) [peer-reviewed]: short high-flow/long low-flow ETFs earned 1–4%/month (Brown-Davies-Ringgenberg, RoF 2021). Best-supported sector-flow signal.
- **Buyback blackouts** [sell-side]: an SSGA study (1994–2018, seen only second-hand) found no significant effect. Weak.
- **Month/quarter-end 60/40 rebalancing** [academic, NBER WP]: 1-SD equity-overweight signal → −16/−17 bp next-day S&P return (t≈3–4), concentrated in the last 4 trading days, strongest at quarter-end, reversed within ~2 weeks (Harvey-Mazzoleni-Melone, 1997–2023).
- **NAAIM** [practitioner]: readings 20–100 mildly contrarian over 12 weeks; <20 = continuation with more drawdown risk; out-of-sample AUC 0.65 for 10% drawdowns (PortfolioOptimizer, 2006–2026; no significance tests).
- **AAII** [peer-reviewed]: contrarian and significant monthly (Fisher-Statman, FAJ 2000) but "little evidence" of short-term predictability (Brown-Cliff). AAII's own study: bearish >46% (+2 SD) → S&P +18% next 12 months (n=40).
- **CFTC TFF (ES/NQ)** [peer-reviewed, weak]: COT sentiment signals for S&P not significant (Chen-Maher 2013); 1-SD position move ≈3.4–4.1% annualized (Dunbar-Jiang 2020), i.e. ~0.3%/month. Leveraged-fund ES shorts are largely basis trades; asset-manager longs are overlays.

## 4. Indicator cards
| Indicator | (a) Measures | (b) Evidence | (c) Free data | (d) Testable rule |
|---|---|---|---|---|
| CTA proxy | trend-model exposure | sell-side; replication academic | Stooq CSV, daily, 1999+ | Take marked bottoms only if proxy ≤0, or after ≥5% drawdown once price reclaims short-term trigger |
| Vol-control proxy | vol-targeted weight | sell-side | same | E=min(1.5, 0.10/max(σ21,σ63)); buy dips if E bottom-quintile (5y) and rising; trim if σ21 +25% in 5 days with E top-decile |
| LETF flow | forced close trades | academic, mixed | issuer AUM; forward-collect | Est. flow >0.5% of ADV → fade at close, exit in 1–3 days |
| Prime book | HF net/gross | sell-side | none | Context: net <10th pct (5y) → allow dips |
| GVIP/SPY | crowding unwind | academic (crowding) | Stooq, daily, 2016+ | 5-day relative return <−2 SD → skip crowded-AI dip-buys until it turns up |
| BofA FMS | manager cash/sentiment | sell-side, n≈17–20 | press only, monthly | Cash ≤3.8% and B&B ≥8 → halve 2x-ETF size |
| ICI flows | fund/ETF flows | academic (monthly) | ici.org, weekly | 4-week US equity inflow top decile → trim; bottom decile → buy dips |
| ETF shares outstanding | sector creations | academic | issuer sites; forward-collect | SMH/SOXX 5-day creation z>+2 → trim; z<−2 at a marked bottom → buy |
| Buyback blackout | corporate bid absent | weak | from earnings dates | Compare hit rates when ≥80% of S&P in blackout vs not |
| 60/40 rebalancing | pension month-end flow | academic | SPY & IEF daily | Drift >+1 SD in last 4 days of quarter → delay buys to day +2; <−1 SD → buy into quarter-end |
| NAAIM | active-manager exposure | practitioner | naaim.org, weekly, 2006+ (history now member/paid; public view delayed) | <40 or 3-week drop >30 → bullish 4–12 weeks; avoid <20; >95 for 2 weeks → trim |
| AAII | retail bull/bear | academic (monthly) | aaii.com Excel (login?), weekly, 1987+ | Bearish ≥50% or spread ≤−20 → dip filter on 4 weeks; bullish ≥55% → trim |
| CFTC TFF | futures by trader type | academic, weak | CFTC Socrata API, weekly, 2006+ | On Friday release: AM net (%OI) <10th pct (52w) and LF short >90th pct → bullish 2–4 weeks |

## 5. Current readings
| Item | Reading | Date | Src |
|---|---|---|---|
| CTA, GS | Global equity long $72bn (54th pct); 1-week US flows flat +$5.7bn, down −$0.5bn; 1-month down tape −$62.6bn US; SPX triggers 7,665/7,444/6,972 | Sep 29 | [1] |
| CTA, GS | Buyers in flat/up tapes; SPX 7,773 above 7,665 | Oct 6 | [2] |
| DB systematic | CTA US 79th pct, later "declined but elevated"; vol control 96th→98th pct→"elevated"; risk-parity equities 82nd pct; systematic overall top decile | Sep 21–Oct 5 | [3][4][5] |
| DB discretionary | −0.27 SD (19th pct) → "below neutral" | Sep 21; Oct 5 | [3][5] |
| HF, GS PB | Fundamental L/S net 53.0% (2nd pct, 5-yr low); US net at 1/3/5-yr lows in Sept; Mag-7 net 22% of US exposure (record); semis 12%. Latest gross: not found (fastest Jan–May rise on record) | Oct 6–11 | [2][6][7][8] |
| BofA FMS (Sept) | Cash 3.9% (Aug 3.5%) → sell signal active; equities net 49% OW (Aug 56%); most crowded: long semis 53%; top tail risk: disorderly bond yields 33%. October survey not yet out | Sep 15 | [9][10] |
| Bull & Bear | 8.1, still "sell" | week to ~Oct 9 | [11] (secondary) |
| Buybacks, GS | 64% of S&P in blackout → 87% → ~93% expected by Oct 2; reopens as Q3 reports land | Sep 22–29 | [1][12] |
| Pension Q3-end, GS | −$33bn US equities (97th pct, 3-yr) | Sep 29 | [1] |
| NAAIM | October: not found (last found 79.70, Jul 29) | — | [13] |
| AAII | Bull 40.3 / Neutral 20.8 / Bear 39.0; spread +1.3 (avg 6.5) | week to Oct 7 | [14] |
| CFTC TFF, futures-only | ES: AM +906.6k, LF −415.1k (−42.6k w/w), dealers −600.8k. NQ: AM +73.8k, LF −19.2k | Oct 6 | [15][16] |

Read-across (inference): systematic money is long and crowded, discretionary/HF net exposure light. By your CTA filter that is the less favorable dip-buy regime, partly offset by light discretionary positioning.

## Most promising to backtest with free daily/weekly data
- **Price-based CTA + vol-control proxies for QQQ, SPY, SMH** with distance-to-trigger (extends your working signal): https://stooq.com/q/d/l/?s=qqq.us&i=d (swap ticker)
- **Month/quarter-end 60/40 rebalancing signal** (best academic support at days horizon): SPY and IEF, same Stooq pattern
- **CFTC TFF ES/NQ percentiles**, keyed to the Friday 15:30 ET release: https://publicreporting.cftc.gov/resource/gpe5-46if.csv ; archive https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm
- **AAII bearish/spread extremes as dip filter:** https://www.aaii.com/sentimentsurvey/sent_results (Excel)
- **GVIP/SPY crowding-unwind gauge:** https://stooq.com/q/d/l/?s=gvip.us&i=d
- **ICI weekly flows, contrarian at 4 weeks:** https://www.ici.org/research/stats

Hygiene: key signals to publication time (COT Friday, AAII Thursday, FMS mid-month); bank percentiles are full-sample normalized and revised (look-ahead); point-in-time stock universe (survivorship); Newey-West or block bootstrap for overlapping windows; hold out 2024–2026.

## Sources
[1] https://www.tickmill.com/blog/institutional-insights-goldman-sachs-sp500-positioning-key-levles-29926
[2] https://www.tickmill.com/blog/institutional-insights-goldman-sachs-us-flows-themes-61026
[3] https://www.tickmill.com/blog/institutional-insights-deutsche-bank-positioning-flows-update-21926
[4] https://www.investing.com/news/stock-market-news/deutsche-bank-sees-equity-positioning-rise-to-overweight-last-week-93CH-4919604
[5] https://www.investing.com/news/stock-market-news/deutsche-bank-says-discretionary-investor-positioning-falls-below-neutral-93CH-4931216
[6] https://www.itiger.com/news/1177929490
[7] https://dailyhodl.com/2026/10/11/hedge-funds-pile-into-magnificent-7-stocks-at-fastest-pace-since-2023-pushing-exposure-to-22/
[8] https://www.hedgeweek.com/hedge-funds-face-margin-calls-amid-ai-stock-sell-off/
[9] https://www.tradingview.com/news/macenews:fec1f37da094b:0-bofa-global-research-fund-manager-survey-fund-managers-cut-back-on-risk-in-september-amid-rising-uncertainty/
[10] https://finance.biggo.com/news/76890938-d6d1-46ac-afa9-3875500a99d5
[11] https://neoreports.substack.com/p/weekly-ai-investment-review-261011
[12] https://www.tickmill.com/blog/institutional-insights-goldman-sachs-sp500-positioning-key-levels-22926
[13] https://ycharts.com/indicators/naaim_number
[14] https://insights.aaii.com/p/aaii-sentiment-survey-pessimism-plummets
[15] https://www.tradingster.com/cot/futures/fin/13874A
[16] https://tradingster.com/cot/futures/fin/209742
Evidence: https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/Demystifying-Managed-Futures.pdf ; https://arxiv.org/html/2607.01550v1 ; https://finance.biggo.com/news/xhFkP50BZk7xib5fewYf ; https://www.ecb.europa.eu/press/financial-stability-publications/fsr/focus/2020/html/ecb.fsrbox202005_02~f6616db9be.en.html ; https://assets.realclear.com/files/2024/04/2408_deutsche.pdf ; https://www.cxoadvisory.com/volatility-effects/front-running-leveraged-etfs-at-the-end-of-the-day ; https://pure.psu.edu/en/publications/do-leveraged-etfs-really-amplify-late-day-returns-and-volatility/ ; https://abarbon.com/papers/liquidity-provision-to-leveraged-etfs-and-equity-options-rebalancing-flows ; https://ideas.repec.org/a/oup/rfinst/v35y2022i7p3231-3271..html ; https://www.etf.com/sections/index-investor-corner/swedroe-crowded-trades-tail-risk ; https://www.investing.com/news/stock-market-news/bofas-hartnett-sees-sell-signal-for-risk-assets-but-no-rush-to-cut-exposure-4706152 ; https://fortune.com/2025/12/19/stocks-bank-of-america-warns-contrarian-sell-signal ; https://ideas.repec.org/a/eee/jfinec/v104y2012i2p363-382.html ; https://ideas.repec.org/a/cup/jfinqa/v46y2011i02p585-603_00.html ; https://revfin.org/?p=2019 ; https://cardanocapital.substack.com/p/buyback-blackouts-93-of-the-s-and ; https://www.nber.org/papers/w33554 ; https://www.edhec.edu/sites/default/files/2026-03/Scientific%20paper.%20ssrn-5122748.pdf ; https://portfoliooptimizer.io/blog/the-naaim-exposure-index-contrarian-or-continuation-indicator/ ; https://naaim.org/programs/naaim-exposure-index/faqs/ ; https://ideas.repec.org/a/taf/ufajxx/v56y2000i2p16-23.html ; https://www.cxoadvisory.com/sentiment-indicators/does-investor-sentiment-give-trading-signals ; https://www.aaii.com/journal/article/feature-investor-sentiment-as-a-contrarian-indicator ; https://ideas.repec.org/a/eee/intfin/v27y2013icp177-201.html ; https://ideas.repec.org/a/eee/ecofin/v51y2020ics1062940818303474.html ; https://publicreporting.cftc.gov/stories/s/TFF-Futures-Only/98ig-3k9y/
