# Research D: sector money flow, narrative and classic technical analysis (as of 2026-10-12)
Labels: [A] peer-reviewed; [S] sell-side/fund; [P] practitioner; [N] no evidence found. [n] = Sources.

**Bottom line.** Independent Relative Strength Index (RSI(2)) and Double-7 tests win ~71–77% on indices and ~64% on Nasdaq-100 stocks [16–18,34], matching ours (76%/63%). To lift single stocks, add context filters, not oscillators: 1-month group momentum, breadth/distribution regime, trend template. Exchange-traded fund (ETF) flows lag price.

## 1. Sector rotation and money flow
- **Industry momentum [A].** It drives much of stock momentum [1]. Unlike single stocks, industries keep trending at 1 month: a 1-month/1-month long-short earned 9.6%/yr (t=4.8), vs 3.8% for 6/6 [2]. Holding the top 3 of 10 sectors by 12-month return earned 13.9%/yr over 1928–2009, ~4 percentage points (pp) above buy-and-hold, before costs [P][3].
- **Supplier lag [A].** Customer news reaches suppliers slowly: >1.5%/month alpha [4].
- **52-week high [A].** Nearness to it beats past stock and industry returns as a predictor, with no reversal [5].
- **Volume [A], mixed.** Abnormal 1-day/1-week volume precedes higher next-month returns [6]; but high-volume winners reverse faster [7], and Robinhood buying frenzies precede −4.7% over 20 days [8].
- **Money flow.** The tick-based version predicts returns but depends on its definition [A][9]. Daily on-balance volume and Chaikin money flow: [N].
- **ETF flows lag [A].** Creations follow returns [10]. High-flow ETFs then trail low-flow ones by ~1–4%/month [11]. Specialized/thematic ETFs show ~−3.1%/yr alpha [12].
- **Breadth [P].** All 16 Zweig thrusts since 1957 were higher 12 months later (average +24%); tiny sample [13]. Relative rotation graphs: only contradictory vendor tests [14].
- **Moving-average (MA) rules [A].** The best 1897–1986 Dow rule was weak in 1987–96 after data-snooping correction [15].

## 2. Narrative and attention
- **Attention [A].** Rising Google searches precede higher prices for ~2 weeks, reversed within a year [19]. WallStreetBets research predicted returns before GameStop, but not after [20].
- **Revisions [A].** Earnings surprises and estimate revisions drift [21]. Quarterly changes in consensus recommendations predict robustly [22]. Target-price revisions move prices [23]. Ranking stocks within sectors by their gap to target price earned ~2%/month before costs, 1999–2004 [24].
- **AI [A, working paper].** After ChatGPT, firms with high AI exposure beat low-exposure firms by 40 basis points a day for 2 weeks. This is a single event [25].
- **How booms end [A].** An industry up ≥100% net of the market in 2 years has a 53% chance of a −40% crash (80% after +150%), yet average later returns are not reliably negative; peaks come ~6 months and ~30% later. Warning signs: rising volatility, acceleration, share issuance [26]. Momentum crashes strike in panic rebounds after volatile declines; volatility scaling roughly doubles the Sharpe ratio [27].
- **Free daily data.** Google Trends, Wikipedia views, GDELT news counts, Yahoo revisions/targets, put/call, VIX, Reddit counts; none validated for AI names [N].

## 3. Classic systems (rules; evidence; daily-close use)
- **Minervini.** Close > 50 > 150 > 200-day simple MA (SMA); 200-day rising ≥1 month; ≥30% above the 52-week low and ≤25% below the high; relative strength (RS) ≥70. Volatility contraction: 2–6 shrinking pullbacks, drying volume, breakout on volume. Template [N]; parts supported [5]. Use: leader filter.
- **O'Neil / Investor's Business Daily (IBD).**
  - *Rules:* earnings ≥+25%, new highs, RS ≥80. A follow-through day (FTD) is rally day ≥4 with the index up ≥1.25% on higher volume. A distribution day (DD) is the index down ≥0.2% on higher volume; it expires after 25 sessions or a +5% rise.
  - *Evidence:* hypothetical screen 23.8%/yr, 1998–2007 [P][28]. Live paper test beat the S&P in 2014–17, then lagged [A, low-tier][29]. IBD claims 70–80% FTD success; an independent test found ~a coin flip [P][30]. DD clusters predicted declines only in falling markets; volume was irrelevant [P][31].
  - *Use:* regime filter.
- **Weinstein.** Buy base breakouts above a rising 30-week MA on ≥2× volume, Mansfield RS >0; exit on a weekly close below. Bulkowski's trades: stage-1 buys +13.2% (69% wins), stage-4 −8.3% [P][32]. 10-month SMA, S&P 1901–2012: 10.2% vs 9.3%/yr, max drawdown 42% vs 84% [33]. Use: close > rising 150-day SMA.
- **Wyckoff.** A spring undercuts support, then closes back inside. [N]. Use: close back above the prior 20-day low.
- **Connors.** RSI(2) <10 above the 200-day MA, exit on a close >5-day MA; also Double 7s. Double 7s on SPY 1993–2026: 333 trades, profit factor 2.35, max drawdown 12.5% [16]; 77% wins over 1993–2015 [17]. RSI(2) on the S&P 2016–26 (incl. shorts): 71% wins, profit factor 1.43, far below buy-and-hold [18]. Nasdaq-100 stocks: 64% [34].
- **Larry Williams.** %R, volatility breakout, "Oops" gap reversal. [N]. Use: gap below the prior low, then close above it.
- **Dow Theory.** Industrials and Transports must confirm. [A] Hamilton's 1902–29 calls were ~60% right, with gains mostly from lower volatility; weaker later [35]. Use: regime filter.
- **Elder triple screen, Darvas box.** [N].

## 4. Practitioner frameworks
- **MarketSmith / TraderLion.** O'Neil/Minervini rules (buy ≤5% above pivot, 7–8% stop). [N].
- **Qullamaggie.**
  - *Setup:* a stock up 30–100% in 1–3 months, then a tight 2–8-week range on the 10/20-day MAs.
  - *Trade:* buy the opening-range high with a stop at the day's low. Sell 1/3–1/2 after 3–5 days; trail the rest to a close below the 10/20-day MA.
  - *Episodic pivot:* a ≥10% news gap on heavy volume.
  - *Evidence:* self-reported 25–30% wins, unaudited [36]. Systematized (2008–25): 19%/yr, −21% drawdown, 2,382 trades, survivorship unaddressed [P][37].
  - *Fit:* a big-winner edge, not a 70%-win method.
- **Brian Shannon.** Price above a rising anchored volume-weighted average price (VWAP) from earnings, a gap or a pivot means buyers are in control. [N].
- **Others.** SMB Capital: intraday [N]. TrendSpider: a tool. Tom Lee: no rules; S&P targets within ±3% in 3 of 11 years [38].

## 5. Current state (to 2026-10-09)
- **Indices.** S&P 500 record close 7,818.93 on 10/6; 7,811.54 on 10/9, +14.1% year-to-date (YTD). Nasdaq 27,366, +17.7% [39].
- **Breadth is narrow.**
  - S&P 500: 35% above the 50-day MA, 48% above the 200-day [40]. All US stocks: 26%/39% [41].
  - Goldman (9/28): since 1990, breadth this weak near index highs appeared almost only in 1998–2000 [S][42].
  - Zweig indicator neutral [43]. RSP −0.2% vs SPY +4.2% over 3 months (my Yahoo calculation).
- **IBD status.** Not found (paywalled). My IBD-rule count on Yahoo volume: S&P 500 7 DDs in 25 sessions (9/8, 9/14–16, 9/28, 10/7, 10/8), "under pressure" territory; Nasdaq 2.
- **AI groups, 1-month/3-month (my calculation).**
  - IGV +11.3/+21.5%.
  - SMH +7.7/+3.0% and SOXX +8.2/+1.1%, 10% and 15% below their 6/22 peaks.
  - Memory is split: MU +5.3/+9.8%; DRAM ETF −29% from its peak; WDC −28.5% over 3 months.
  - Over 3 months: optical leads (LITE +43.6%, ANET +19.6%); DELL +37.4%.
  - Power is mixed: VRT −20.6% and below its 200-day; CEG +15.9%; XLU −8.8%.
  - MSFT +37.1%; ORCL −26.5% YTD.
- **Flows.** September: tech-sector ETFs −$1.7B, thematic +$4.9B [44]; semiconductor ETF outflows [45] while SMH rose 9.4% [46].
- **Narrative.** On 10/8 a chip index fell 3.4% on reports of OpenAI's revenue run-rate at ~$50B vs ~$70B estimated earlier [47]. TSMC's ~50% sales growth and Samsung's ninefold profit "failed to excite," amid "circular spending" worries [48]. Micron beat ($54.2B vs $51.5B; guidance $61.5B); stock flat [49].
- **Macro.** Fed hike to 3.75–4.00% on 9/16 [50]; 10-year yield ~5.3%, highest since 2002 [48].
- **Bubble flag.** SOXX/SMH +145% in 2 years (+106pp vs SPY) cross the [26] threshold; volatility not yet accelerating.

## Most promising to backtest (free daily data)
1. **Group momentum.** Each Friday rank ~12 AI groups (SMH, IGV, memory, optical, power, servers, hyperscalers, QQQ) by 21-day return; take bottom/pullback longs only in the top 4; compare 5/10/20-day win rates with the bottom 4.
2. **Breadth regime.** Long only if ≥40% of the universe is above its 50-day MA or that share rose over 5 days; flag "narrow" when the index is ≤2% from its 52-week high and <50% are above the 200-day MA.
3. **DD/FTD regime.**
   - DD: a close ≤−0.2% on higher volume, dropped after 25 sessions or after a close ≥5% above it. Pressure means ≥5 DDs.
   - FTD: rally day ≥4 with no close below the rally low, up ≥1.25% on higher volume.
   - Compare bottom-mark wins at ≥5 vs ≤2 DDs, and 20-day returns after FTDs.
4. **Volume-confirmed bottom.** Volume ≥1.5× the 50-day average and a close in the top half of the range. Skip attention spikes (search or Reddit counts ≥3× their 60-day median).
5. **Crash throttle.** If a group's 504-day return beats SPY's by ≥100pp and its 63-day volatility is ≥1.25× its 252-day, trade 1x instead of 2x and act on top marks first.
6. **Trend filter.** Take stock bottoms only if close > 50 > 150 > 200-day SMA, the 200-day is above its level 21 sessions ago, and the close is ≥75% of the 52-week high. Use point-in-time Nasdaq-100 members.

**Bias controls.** Point-in-time members (survivorship), 2024–26 holdout, walk-forward tests, costs and 2x decay; thrust/FTD samples are small.

## Sources
1 https://ideas.repec.org/a/bla/jfinan/v54y1999i4p1249-1290.html; 2 https://rodneywhitecenter.wharton.upenn.edu/wp-content/uploads/2018/03/Juhani.pdf; 3 https://quantpedia.com/strategies/sector-momentum-rotational-system; 4 https://academicnewsletter.sufe.edu.cn/info/360813; 5 https://academicnewsletter.sufe.edu.cn/info/361244; 6 https://sites.duke.edu/sgervais/?p=64; 7 https://academicnewsletter.sufe.edu.cn/info/361612; 8 https://profiles.wustl.edu/en/publications/attention-induced-trading-and-returns-evidence-from-robinhood-use/; 9 https://rpc.cfainstitute.org/research/financial-analysts-journal/2001/can-money-flows-predict-stock-returns; 10 https://rpc.cfainstitute.org/research/cfa-digest/2014/11/are-flows-costly-to-etf-investors-digest-summary; 11 https://revfin.org/?p=2019; 12 https://alphaarchitect.com/competition-for-attention-in-the-etf-space/; 13 https://www.nasdaq.com/articles/stock-market-indicator-has-been-100-accurate-1957-it-signals-big-move-2025; 14 https://riverbendinvestmentmanagement.substack.com/p/using-relative-rotation-graphs-for; 15 https://www.fmg.ac.uk/sites/default/files/2020-11/dp303.pdf; 16 https://strategyquant.com/blog/larry-connors-double-7-strategy-tested-on-spy-and-8-other-markets/; 17 https://www.thechartist.com.au/?p=5968; 18 https://backtrex.com/en/backtests/connors-rsi-2-sp-500; 19 https://academicnewsletter.sufe.edu.cn/info/360414; 20 https://academicnewsletter.sufe.edu.cn/info/351572; 21 https://www.nber.org/papers/w5375; 22 https://opact.sdu.edu.tr/vufind/SummonRecord/FETCH-LOGICAL-a5967-edcb61ed493d55f767fd3723877bd0dcba926898eb40bb6949376c32c17edced3; 23 https://academicnewsletter.sufe.edu.cn/info/361259; 24 https://www.cxoadvisory.com/investing-expertise/finding-a-use-for-analyst-price-targets; 25 https://cepr.org/voxeu/columns/generative-ai-and-firm-valuation; 26 https://alphaarchitect.com/are-stock-market-bubbles-identifiable/; 27 https://www.nber.org/papers/w20439; 28 https://www.aaii.com/journal/article/investing-in-proven-growth-using-can-slim-revised; 29 https://mail.articlegateway.com/index.php/JAF/article/download/5134/4892; 30 https://www.luxalgo.com/library/concept/follow-through-day/; 31 https://ThePatternSite.com/DistributionDay.html; 32 https://www.thepatternsite.com/Stages.html; 33 https://trevcan.duckdns.org/files/trevor/papers/emintham-Papers/Faber-%20A%20Quantitative%20Approach%20to%20Tactical%20Asset%20Allocation.pdf; 34 https://backtest.substack.com/p/the-2-period-rsi-a-simple-system; 35 https://www.cxoadvisory.com/technical-trading/classic-research-dow-theory-long-dead/; 36 https://completetradersedge.com/?p=233509; 37 https://stonkscapital.substack.com/p/modeling-kullamagi-part-2-momentum; 38 https://anachart.com/strategist/tom-lee/; 39 https://www.lanacion.com.ar/usa/how-major-us-stock-indexes-fared-friday-1092026-nid09102026/; 40 https://chartrow.com/sp500/market-breadth; 41 https://www.thetrading.tools/market-breadth; 42 https://cryptobriefing.com/goldman-sachs-sp500-breadth-dotcom-low/; 43 https://www.thetrading.tools/zweig-breadth-thrust; 44 https://www.ftportfolios.com/Commentary/Insights/2026/10/8/asset-flows-monitor-october-2026-edition; 45 https://insight.factset.com/u.s.-etf-monthly-summary-september-2026-results; 46 https://247wallst.com/investing/2026/10/01/every-sp-sector-fell-in-september-except-one/; 47 https://theedgemalaysia.com/node/821129; 48 https://www.lpl.com/research/blog/weekly-market-performance-october-9-2026.html; 49 https://www.asktraders.com/?p=255274; 50 https://www.centralbanking.com/central-banks/monetary-policy/7976918/federal-reserve-delivers-first-rate-hike-since-2023
