# Short-term bottom / top markers on daily candles — tools & evidence scan (A)

Date: 2026-10-12 · Scope: indicators, open-source scripts (TradingView Pine), quant blogs, papers (arXiv / SSRN / journals), books, libraries, and machine-learning (ML) / foundation models that mark short-term **bottoms (add / buy back)** and **tops (trim / take profit)** on daily OHLCV (open-high-low-close-volume) of US equities. Read-only research: nothing in the repo was changed.

**Reference code (tested):**
- `scratchpad/check/ind.py` contains every shortlisted definition below. All of them are causal and use only bars ≤ t.
- `scratchpad/check/run_check.py` runs range checks plus a **truncation "non-repaint" test**: the value at bar k−1 computed on `data[:k]` must equal the same bar computed on the full history. Every function passes on 1,500 synthetic bars. Adding the same test to the nightly pipeline is a cheap guard against look-ahead.

## Abbreviations (spelled out on first use)

| Full name | Abbr. | 中文 |
|---|---|---|
| Internal Bar Strength | IBS | 收盤位置強度 |
| Relative Strength Index | RSI | 相對強弱指標 |
| ConnorsRSI | CRSI | 康納斯 RSI |
| Average True Range | ATR | 平均真實波幅 |
| Simple / Exponential Moving Average | SMA / EMA | 簡單 / 指數移動平均 |
| Bollinger Bands | BB | 布林通道 |
| Keltner Channel | KC | 肯特納通道 |
| Williams VIX Fix | WVF | 威廉斯合成恐慌指數 |
| CBOE Volatility Index / Nasdaq-100 Volatility Index | VIX / VXN | 波動率指數 |
| Moving Average Convergence Divergence | MACD | 指數平滑異同移動平均 |
| TD Setup Trend (DeMark) | TDST | TD 設定趨勢線 |
| Profit factor (gross profit ÷ gross loss) | PF | 獲利因子 |
| Maximum drawdown | Max DD | 最大回撤 |
| Out-of-sample | OOS | 樣本外 |
| Maximum adverse excursion | MAE | 最大不利偏移 |
| Time-series foundation model | TSFM | 時間序列基礎模型 |
| k-nearest neighbours | kNN | k 最近鄰 |
| Deep reinforcement learning | DRL | 深度強化學習 |
| Market-on-close order | MOC | 收盤市價單 |

**Evidence grades used below:**
- **A**: academic or peer-reviewed, with OOS testing.
- **B**: independent third-party replication.
- **C**: the author's own or vendor material (marketing-grade).
- **D**: no published test found.

---

## 0. Bottom line

1. **Why SPY/QQQ hit 79% and single stocks less.** Baltussen, van Bekkum & Da (Journal of Financial Economics) found that the day-to-day correlation of major index returns turned **negative after ~1999**: indexes now tend to reverse, where they used to keep going. Before 1999, daily AR(1) was significantly positive for 16 of 20 indexes. Afterward it was negative for 16 of 20, and a 5-day reversal strategy had a Sharpe of 0.67 on the S&P 500. The authors attribute this to indexing and ETF arbitrage. It is a property of **index baskets**, not single stocks, so lower hit rates on single names are expected. Single-stock bottom marks should be **gated by market-level confirmation** (B5/B7).
2. **The most promising new bottom inputs carry information RSI(2), BB and TD9 don't have:**
   - **IBS**: where the close sits within the day's range.
   - **N-day closing low with a 200-day filter** ("Double 7s"): independently re-tested through Sep 2026.
   - **Stress context**: VIX/VXN for the ETFs, WVF for single stocks, and breadth computed from your own 100-stock universe.
3. **Tops: the literature agrees with your finding.**
   - On SPY, optimizing IBS in-sample switched the short side off (upper threshold = 1).
   - Overbought RSI(14) periods on SPY showed *below-normal* returns, not *declines*.
   - So use "top" logic as **exits for bottom trades** and **trend exits for the core position**. Judge it by profit kept and drawdown avoided versus holding, not by "% rebought lower".
4. **ML / foundation models: nothing credible yet beats simple rules at turning points on daily bars.**
   - Off-the-shelf TSFMs (Chronos, TimesFM) score about **50–51% directional accuracy** on daily US returns.
   - **Kronos's pretraining data runs to June 2024**, so any Kronos backtest before July 2024 is contaminated by look-ahead.

---

## 1. Ranked shortlist (none of these repaint)

### 1.0 Summary table

| Rank | ID | Name | Role | Data | Repaints? | License | Evidence |
|---|---|---|---|---|---|---|---|
| 1 | B1 | IBS < 0.2 (and multi-day IBS) | bottom | OHLC | No | formula | B/C |
| 2 | B2 | N-day closing low + SMA200 (Double 7s) | bottom + exit | C | No | formula | B |
| 3 | B3 | Williams %R(5) < −90, exit C > H[1] | bottom | HLC | No | formula | C |
| 4 | B4 | ConnorsRSI(3,2,100) (+ Connors stock-pullback variant) | bottom + exit | C (+H/L, volume for variant) | No | formula | C |
| 5 | B5 | VIX/VXN stress filter (SPY/QQQ) | bottom filter | **+ ^VIX/^VXN close (free)** | No | formula | C |
| 6 | B6 | Williams VIX Fix spike (single stocks) | bottom filter | HLC | No | formula; Pine open-source | D/C |
| 7 | B7 | Own-universe breadth capitulation | bottom filter | C of ~100 names (point-in-time) | No | formula | D |
| 8 | B8 | One oscillator slot: WaveTrend / Fisher / Laguerre RSI | bottom/top | HLC | No | formula; Pine MPL/none | D |
| 1 | T1 | Mean-reversion exits (C > SMA5, C > H[1], RSI2 > 70, IBS > 0.8, 7-day closing high) | take-profit | OHLC | No | formula | B/C |
| 2 | T2 | Chandelier Exit (22, 3) / (22, 2) / (22, 1) | trailing exit | HLC | No | formula | B |
| 3 | T3 | SuperTrend (10, 3) or UT Bot ATR trail (a=1, ATR 10) | trend exit (core) | HLC | No on close (intrabar flips repaint live) | formula; Pine MPL | C |
| 4 | T4 | Over-extension trim: C > EMA20 + 2.5·ATR10 or RSI14 ≥ 80, confirmed | trim | HLC | No | formula | D |
| 5 | T5 | TD Sequential Countdown 13 + TDST | exhaustion top/bottom | HLC | No | formula (DeMark trademarks) | D |
| 6 | T6 | Elder Impulse (EMA13 slope & MACD-hist slope) | trim / no-add filter | C | No | formula | D |

### 1.1 Conventions (these change thresholds if you get them wrong)

- **Wilder smoothing (RMA)** is used by RSI and ATR. In pandas it is `x.ewm(alpha=1/n, adjust=False).mean()`.
  - TradingView seeds RMA with an SMA of the first n values, while pandas seeds with the first value.
  - The difference fades within a few hundred bars, so discard the first ~250 bars.
- **EMA** is `x.ewm(span=n, adjust=False).mean()`.
- **Standard deviation:** TradingView's `ta.stdev` (and therefore its BB) uses the **population SD** (`ddof=0`). Use the same for BB and WVF, or the band levels will shift.
- **Timing:** every signal is computed after bar *t* closes.
  - **Raw** variant: act at the close of *t* (realistic only with a near-close estimate or MOC) or at the open of *t+1*.
  - **Confirmed** variant (your house rule): act at the close of *t+1* if C[t+1] > H[t] for bottoms, or C[t+1] < L[t] for tops. These are `confirm_bottom` and `confirm_top` in `ind.py`.
  - **Test both.** Several published edges, IBS especially, are 1-day effects that the confirmation day can use up. Pandey & Joshi report that open-to-open execution of IBS "performed poorly".
- **Prices:** use split- and dividend-adjusted O/H/L/C with **one common adjustment factor**. IBS and %R break if H/L are adjusted differently from C.
- **Leveraged ETFs:** compute signals on the **underlying** (QQQ, SPY, NVDA…) and apply them to the 2× product.

### 1A. Bottom signals (add / buy back)

#### B1. IBS (rank 1)

**Rule**
- IBS = (C − L) / (H − L), set to 0.5 when H = L.
- **Bottom** when IBS < 0.20. Grid: 0.10 / 0.15 / 0.20 / 0.25.
- Optional filters: C < C[1] (a down day); C > SMA(C, 200).
- **Exit** (pick one): IBS > 0.80, or C > H[t−1], or the first up close. Hard time cap of 5 days.

**Multi-day form:** IBS_n = (C − LL_n)/(HH_n − LL_n) = 1 + %R(n)/100. So B3 (Williams %R) is the same family.

**Code:** `ibs()`, `williams_r()`. **Data:** OHLC only. **Repaints:** no.

**Evidence (B/C)**
- Pagonidis (2013), "The IBS effect: mean reversion in equity ETFs", is the original rule (long < 0.2, short > 0.8). It is cited by Pandey & Joshi.
- Pandey & Joshi (2023, arXiv 2306.12434) tested 15 country ETFs over 2009–2019:
  - Best single-ETF threshold strategy: Sharpe 2.17. Min-max long/short basket: Sharpe 2.91.
  - Example next-day probability of a gain after IBS < 0.2: 60.6% (EWJ).
  - Performance **fell** for holds longer than 1 day and for 2-day IBS.
  - Limitations: no formal OOS split and no commissions.
- R-bloggers / QuantShare (2013) on SPY: parameters were fitted on data up to 2000, and the strategy "performed well" OOS after 2000 on the long side only. No numbers were given in the text.
- AlgoTradeKit's TradingView script (2025) uses IBS < 0.2 with C > EMA252 and exits on IBS > 0.9. It reports no statistics.

**Why it might add something:** a close pinned at the day's low is information that close-only oscillators (RSI(2), BB) don't contain.

**To test:** raw vs confirmed entry; SPY/QQQ vs single stocks. Expect the strongest results on the index ETFs.

#### B2. N-day closing low with a trend filter, "Double 7s" (rank 2)

**Rule**
- **Bottom:** C > SMA(C, 200) **and** C ≤ min(C, 7). The 7-bar window includes today.
- **Exit:** C ≥ max(C, 7).
- Grid: N = 5…10.

**Code:** `double7()`.

**Evidence (B)**
- Connors & Alvarez, *Short Term Trading Strategies That Work* (2009), chapter 10:

  | Ticker | Period | Trades | Win rate | Avg trade |
  |---|---|---|---|---|
  | SPY | 1993–2008 | 153 | 80.4% | +0.85% |
  | QQQ | from 1999 | 68 | 79.4% | — |

- StrategyQuant re-tested it independently on SPY, Jan 1993–Sep 2026, with zero costs: 333 trades, PF 2.35, Sharpe 0.85, Max DD ≈ 12.5%, ≈ 28% time in market.
- The book's data ended in 2008, so 2009–2026 is effectively OOS. **The edge persisted on SPY.**

**Note:** the 200-day filter deliberately skips bear-market bottoms such as 2022. That is good for 2× ETFs because it limits averaging down, but it misses V-bottoms below the 200-day. Test with and without the filter.

#### B3. Williams %R(5) < −90 (rank 3)

**Rule**
- %R(5) = −100 · (HH5 − C) / (HH5 − LL5).
- **Bottom** when %R(5) < −90.
- **Exit** when C > H[t−1].
- Grid: lookback 2 / 5 / 10; threshold −90 / −95.

**Evidence (C):** Quantified Strategies tested QQQ since inception and reported 72% wins, average +0.9% per trade, about 15 trades per year, 21% time in market, and a largest loss of −18%. This is the author's own test, with no OOS split and unclear costs.

**Value:** the entry is a sibling of IBS(5) and RSI(2). The useful new part is the fast exit "close above yesterday's high" (see T1). Keep the entry only if it overlaps little with your existing marks.

#### B4. ConnorsRSI (rank 4)

**Rule**
- CRSI(3, 2, 100) = [RSI(C, 3) + RSI(streak, 2) + PercentRank(1-day % change, 100)] / 3.
- **Streak:** count of consecutive up closes (+1, +2…) or down closes (−1, −2…); 0 when the close is unchanged. RSI(·, 2) is applied to the streak series as if it were a price.
- **PercentRank:** the percentage of the previous 100 one-day changes that are below today's change.
- **Bottom:** CRSI < 10 for ETFs, < 5 for volatile stocks.
- **Exit:** CRSI > 70. Grid: 50 / 60 / 70 / 80.

**Code:** `connors_rsi()`, `updown_streak()`, `percent_rank()`.

**Connors stock "pullback" variant** (relevant for flow stars):
- Filters: price > $5; 21-day average volume ≥ 250k; ADX(10) > 30.
- Setup day: today's low is at least W% below yesterday's close (W = 2–8%); the close is in the bottom X% of the day's range (X = 10/25, i.e. IBS ≤ 0.10/0.25); CRSI < 5–15.
- Next day: buy with a **limit order Z% below the setup close** (Z = 4–10%).
- Exit: CRSI > 50–80.

**Evidence (C)**
- StockCharts ChartSchool gives the definition and the 10/90 levels, with no statistics.
- The Connors Research guidebook (2012) tested US stocks over 2001–2012. Example row: 472 trades, 78.8% wins, average +14.97%, 7.0 days held (W8 / X10 / Y5 / Z10, exit CRSI > 80).
- Caveats: no slippage or commissions, the authors' own test, and heavy parameter mining (all of the top-20 variants are reported).

**Value:** the streak and percent-rank parts add "how long and how extreme" information. The limit-entry variant is structurally different from your confirmation rule: it buys *deeper* into the fall instead of waiting for strength.

#### B5. VIX/VXN stress filter for SPY/QQQ (rank 5)

Needs ^VIX and ^VXN daily closes (free).

**Rule:** apply as an AND-filter on existing SPY bottoms (use VXN for QQQ). Test each option separately:
- (a) VIX > 20 on the signal day.
- (b) VIX > BB_upper(VIX, 20, 2).
- (c) Connors "VIX stretch": VIX ≥ 1.05 · SMA(VIX, 10) for 3 consecutive days.

**Code:** `vix_stress()`.

**Evidence (C)**
- backtest.substack tested SPY with RSI(7) < 30, C > SMA150, and exit when C > H[t−3]:

  | Variant | Win rate | PF | Trades |
  |---|---|---|---|
  | Base strategy | 81.2% | 3.47 | not stated |
  | Plus VIX > 20 | 86.0% | 5.64 | 57 |

  Period not stated, no stop. Small sample.
- The VIX-stretch idea comes from Connors & Alvarez (2009).

**Value:** a separate "fear" input that mainly raises precision while cutting the number of trades.

#### B6. Williams VIX Fix spike, for single stocks (rank 6)

**Rule** (CM_Williams_Vix_Fix defaults)
- WVF = (max(C, 22) − L) / max(C, 22) · 100.
- upper = SMA(WVF, 20) + 2.0 · SD_pop(WVF, 20).
- rangeHigh = max(WVF, 50) · 0.85.
- spike = WVF ≥ upper **or** WVF ≥ rangeHigh.
- **Trigger:** the first bar after a spike ends (spike[t−1] true and spike[t] false). Alternative: a spike within the last 3 bars **and** your RSI(2)/BB bottom.

**Code:** `vix_fix()`.

**License:** the formula is Larry Williams' public concept (Active Trader, 2007). ChrisMoody's Pine code is open-source on TradingView. The copy I examined states no explicit license, and TradingView's House Rules apply.

**Evidence (D/C):** no rigorous test found. Marketcalls (2015, Nifty futures) found WVF on its own "did not work well". Combined with an India VIX percentile it was their best version, but the results are only in images. Treat WVF as a **severity filter**, not a standalone signal.

**Value:** it works for any ticker (MU, SMCI…) where no implied-volatility index exists.

#### B7. Own-universe breadth capitulation (rank 7)

**Rule**
- Each day, compute the share of universe names with RSI(2) < 10 **or** C < BB_lower(20, 2).
- **Washed-out flag** when the share ≥ 0.6. Grid: 0.4 / 0.6 / 0.8.

**Uses**
- (i) An AND-filter for QQQ/SPY bottoms.
- (ii) A gate for single-stock bottoms: buy a stock's bottom only when the market is also washed out. Conversely, flag drops that happen on low breadth as stock-specific.

**Code:** `breadth_oversold(closes_panel)`.

**Evidence (D):** the idea resembles Quantifiable Edges' Capitulative Breadth Indicator (CBI). The CBI formula isn't published; its author is excited by readings of 10+, and the old blog post shows numbers only in images. This exact rule is untested.

**Must use point-in-time membership**, otherwise survivorship bias inflates the results.

#### B8. One oscillator slot: WaveTrend, or Fisher, or Laguerre RSI (rank 8, low prior)

**WaveTrend** (LazyBear; defaults n1 = 10, n2 = 21; levels ±53 / ±60)
- ap = (H + L + C) / 3.
- esa = EMA(ap, 10); d = EMA(|ap − esa|, 10).
- ci = (ap − esa) / (0.015 · d).
- wt1 = EMA(ci, 21); wt2 = SMA(wt1, 4).
- **Bottom:** wt1 crosses above wt2 while wt1 < −53 (or −60).
- **Top:** wt1 crosses below wt2 while wt1 > 53.

**Fisher Transform** (Ehlers, *Technical Analysis of Stocks & Commodities*, Nov 2002; length 10; TradingView's built-in uses 9)
- Price = hl2 = (H + L) / 2.
- v = 0.66 · [(hl2 − min(hl2, 10)) / (max(hl2, 10) − min(hl2, 10)) − 0.5] + 0.67 · v[−1].
- If |v| > 0.99, set v = ±0.999.
- F = 0.5 · ln((1 + v) / (1 − v)) + 0.5 · F[−1]; trigger = F[−1].
- **Bottom:** F crosses above the trigger while F < −1.5. The −1.5 threshold is to be tested.

**Laguerre RSI** (Ehlers, *Cybernetic Analysis for Stocks and Futures*, 2004; γ = 0.5)
- L0 = (1 − γ)·C + γ·L0[−1]
- L1 = −γ·L0 + L0[−1] + γ·L1[−1]
- L2 = −γ·L1 + L1[−1] + γ·L2[−1]
- L3 = −γ·L2 + L2[−1] + γ·L3[−1]
- CU = Σ of positive (Lk − Lk+1); CD = Σ of positive (Lk+1 − Lk); LRSI = CU / (CU + CD).
- **Bottom:** crosses up through 0.2. **Top:** crosses down through 0.8.

**Code:** `wavetrend()`, `fisher()`, `laguerre_rsi()`.

**Evidence (D):** no independent tests found. All three re-scale the same recent price range that RSI(2) and BB already use. **Keep one only if** its overlap with your existing marks is low and it raises precision.

#### Position-management add-on (not a signal): Connors TPS scale-in

Source: Connors, *High Probability ETF Trading* (2009), as given in a Wealth-Lab forum thread.

- Condition: the ETF is above its SMA200.
- RSI(2) < 25 on two days in a row → buy 10% of the position.
- Each later close below the previous entry → add 20%, then 30%, then 40%.
- Exit when RSI(2) > 70.

This is the author's own rule, with no stop. With 2× ETFs it is **averaging down**: use it only with a hard cap and the 200-day filter.

### 1B. Top, take-profit and trend-exit signals

#### T1. Mean-reversion exits for bottom trades (rank 1)

**Rules:** the first rule that fires closes the "swing" tranche.
- (a) C > SMA(C, 5) (the Connors RSI(2) exit).
- (b) C > H[t−1] (the Quantified Strategies %R exit).
- (c) RSI(2) > 70 (TPS / R3).
- (d) IBS > 0.8–0.9.
- (e) C ≥ max(C, 7) (Double 7s).
- (f) CRSI > 70.
- Plus a time stop of 5–10 days.

**Evidence (B/C):** these exits are part of every Connors and Quantified Strategies result quoted above. The Algomatic article "13 essential exits for mean reversion" lists them without numbers.

**Why rank 1:** your top marks show no edge, but exiting a bottom trade on the **first sign of strength** is how the published 70–80% win rates are produced. Score each exit by round-trip win rate and average return against your current "sell at the next top mark".

#### T2. Chandelier Exit (rank 2)

**Rule** (Chuck LeBeau)
- Long stop = max(H, 22) − 3.0 · ATR(22), using Wilder ATR.
- Exit when C < stop.
- Tighter versions for swing tranches: (22, 2) and (22, 1).

**Code:** `chandelier_long()`.

**Evidence (B):** Arthur Hill (StockCharts, 2016) tested an RSI(5) mean-reversion system on SPY, QQQ and IJR over 2000–2016 with Chandelier exits. In the cross-back-above-30 tests, tightening from (22, 2) to (22, 1) raised the annual return (CAR) and the win rate for all three ETFs; IJR reached 83% wins over 80 trades. Most figures are in images.

#### T3. SuperTrend (10, 3), or an ATR trailing stop ("UT Bot") (rank 3)

Role: the exit for the **core** leveraged position.

**SuperTrend** (Olivier Seban)
- Bands = hl2 ± 3 · ATR(10), Wilder ATR.
- The lower band may only rise during an uptrend, and the upper band may only fall during a downtrend.
- A flip to downtrend (C < final lower band) → exit or trim the core.

**UT Bot** (QuantNomad)
- nLoss = a · ATR(10), with a = 1 (grid 1–3).
- The trailing stop follows a 4-case recursion (see `ut_bot()`).
- Sell when C crosses below the stop.

**Code:** `supertrend()`, `ut_bot()`.

**Evidence (C/B)**
- Quantified Strategies tested the weekly S&P 500 from 1960: 41 trades, 68% wins, Max DD 25%, 63% time in market. This is the author's own test, on weekly data.
- An independent HackerNoon port (2026) tested FX and gold over 2020–2026 with costs and concluded SuperTrend is "a good trend filter and a poor standalone robot".
- No good daily-equity test was found.

**Caution:** on TradingView, intrabar flips repaint in real time. Use closing values only.

#### T4. Over-extension trim (rank 4)

**Rule**
- ext = C > EMA(C, 20) + 2.5 · ATR(10) (Keltner 20 / 2.5), **or** RSI(14) ≥ 80.
- Trim a fraction (e.g. 1/3) when ext[t−1] is true **and** C[t] < L[t−1] (your confirmation style).
- Mirror for bottoms: C < EMA20 − 2.5 · ATR10.

**Evidence (D)**
- **Known:** overbought periods show below-normal returns, not declines. CXO Advisory's SPY RSI(14) test (1993–2008) had 34 round trips with 27 winners, but standalone RSI trading lagged buy-and-hold.
- **To test:** whether trimming 1/3 improves the risk-adjusted return of a 2× position compared with holding.

#### T5. TD Sequential Countdown 13 + TDST (rank 5)

**Rule** (sell side)
- **Setup:** 9 consecutive closes with C > C[t−4].
- **Countdown:** starts on setup bar 9. Count bars with C ≥ H[t−2]; they need not be consecutive.
- **Bar 13 qualifier:** bar 13 needs H ≥ the close of countdown bar 8; otherwise it is deferred.
- **Cancellation:** cancel if a buy setup completes first, or if a bar's H is below the lowest L of the setup (price has left the setup range).
- **TDST support:** the lowest L of setup bars 1–9. A close below it means the trend has failed.
- **Buy side mirrors** this: C ≤ L[t−2], and the bar-13 low ≤ the close of countdown bar 8.

**Code:** `td_countdown13(side="sell"|"buy")`. This is a **simplified** version with no recycle or TD Combo options; verify it against Perl, *DeMark Indicators* (2008).

**Evidence (D):** Oxford Strat tested countdown entries on 42 futures markets (1980–2013), but the results are only in images.

**Value:** you already have Setup 9. Countdown 13 is rare (≈0.3–0.5% of bars on synthetic data) and may mark exhaustion tops in flow stars.

#### T6. Elder Impulse (rank 6)

**Rule**
- **Green:** EMA13 rising **and** the MACD histogram (12, 26, 9) rising.
- **Red:** both falling. **Blue:** mixed.
- Trim on the first red bar after ≥ 3 green bars.
- Also use it as a filter: **no adds on red bars**.

**Code:** `elder_impulse()`.

**Evidence (D):** Elder, *Come Into My Trading Room* (2002). A StockCharts article (2012) shows examples but no statistics.

### 1C. Suggested test protocol

1. **One harness with the same exits.** For each new bottom signal, run the raw and confirmed variants with the T1 exits.
   - Report: win %, mean and median return, MAE, days held, and trades per year.
   - Split the results by group: SPY/QQQ, Mag7, top-100 tech, and flow stars.
2. **Random-entry baseline for bottoms.** Use the same tickers, exit rule and holding-time distribution, as you already did for tops. In a bull market, random "buy, then exit on the first up day" can already exceed 60%.
3. **Overlap check.** Measure the overlap (Jaccard, ±2 days) with your existing RSI2 / BB / TD9 marks.
   - Keep signals that add new events, or that raise precision in a confluence score (the number of signals firing within 2 days).
4. **OOS discipline.**
   - Choose parameters on 2000–2017, check them on 2018–2022, and look at 2023–2026 only once.
   - Log every variant you try: about 15 candidates times their grids means some will reach 70% by luck.
   - Prefer parameter plateaus over single best points.
5. **Survivorship and selection bias.** Today's top-100 tech list and the flow-star list were picked with hindsight. Bottoms "work" partly because these names survived and rallied. Use point-in-time membership (e.g. historical QQQ holdings), and include names that collapsed.
6. **Leveraged ETFs.** Generate signals on the underlying and add a time stop: 2× products lose value to volatility while you wait.
7. **Earnings.** Tag signals within ±1 day of an earnings report (needs earnings dates). The drift after a big surprise can overpower mean reversion.
8. **Costs.** Assume at least 2–5 basis points per side for ETFs and 5–10 for single stocks.

---

## 2. Rejected or deprioritized candidates (one line each)

### Repaint or look-ahead (look great on charts, unusable live)

- **ZigZag (any version):** the last leg keeps being revised until it is confirmed, and the swing points are only known after future bars.
- **Pivot or fractal marks** (`ta.pivothigh/low(left, right)`, Williams fractals, swing labels): they are confirmed R bars late but drawn back on the pivot bar. Usable only when shifted by R bars, at which point they are just a lagging breakout.
- **Nadaraya-Watson Envelope (LuxAlgo):** the default "repainting smoothing" refits the whole window, and LuxAlgo says it repaints. The endpoint (non-repainting) mode behaves like ordinary bands, so it is redundant with BB.
- **Divergence detectors and Market Cipher clones (VuManChu Cipher B):** divergences are fractal or pivot confirmed, lag by at least 2 bars, and are often drawn with a negative offset. The indicator bundles WaveTrend, money flow, RSI and Stochastic. No published evidence; the original Market Cipher is closed-source and paid.
- **Centered or back-shifted series:** a centered DPO and the Ichimoku Chikou span use future bars on history. Check pandas-ta's `centered` / `lookahead` flags.
- **Heikin-Ashi reversals:** HA candles are synthetic, lagged prices. Pine strategies on HA charts fill at HA prices unless `fill_orders_on_standard_ohlc` is set. No evidence found.
- **Any Pine `request.security(..., lookahead=barmerge.lookahead_on)` without a `[1]` offset:** the Pine docs say it "will return data from the future on historical bars".

### No evidence, or redundant with what you already have

- **Machine Learning: Lorentzian Classification (jdehorty):**
  - The author says it does not repaint once a bar closes.
  - Its in-script "Trade Stats" use mid-bar entries by default, which is optimistic; the author calls them "not a substitute for proper backtesting".
  - It is a kNN model over RSI, WaveTrend, CCI and ADX of the same price, so it is highly correlated with oscillators you already run.
  - As I recall the open-source code, labels are built from short (about 4-bar) price changes; I did not re-verify this. When porting, a misaligned label and feature bar leaks the future.
  - No independent OOS evidence. The Python port `advanced-ta` was last released in Feb 2024 and states no license.
- **Squeeze Momentum (LazyBear):** BB(20, 2) inside KC(20, 1.5), momentum = linreg(C − mean(mean(HH20, LL20), SMA20), 20). It is a volatility-compression breakout tool, not a reversal marker. No evidence.
- **QQE / QQE MOD (Mihkel00):** a double-smoothed RSI trend filter (RSI 6, SF 5, QQE 3 / 1.61, BB 50 / 0.35). It lags, and there is no evidence.
- **HalfTrend (everget), Range Filter (DonovanWall), UT Bot used alone:** ATR trend-followers that nearly duplicate SuperTrend / Chandelier. No evidence. Keep one ATR trail, in T3.
- **Stochastic RSI (14, 14, 3, 3):** pins at 0 or 100 constantly on daily stocks and is redundant with RSI(2).
- **Laguerre RSI and Fisher Transform:** only as the optional B8 slot.
- **Volume-climax / capitulation-volume rules** (e.g. volume > 2 × SMA50(volume) on a down day that closes off its lows): no published test found. If tried, use one only as a filter on B1 or B6.

### Needs data you don't have, or too rare

- **Zweig Breadth Thrust:** needs NYSE advances and declines; 8 signals in 40 years (StockCharts, 2019). It confirms a thrust *after* the low rather than marking the low.
- **Quantifiable Edges CBI:** the formula is unpublished and it needs S&P 1500 data.
- **Lowry 90% down/up days:** needs NYSE up/down volume.

### ML and foundation models

- **Kronos** (MIT license)
  - Released models: mini 4.1M parameters (context 2048), small 24.7M and base 102.3M (context 512). The large 499M model is not open.
  - The authors report +93% RankIC over the best TSFM for price forecasting, plus a China A-share simulation (CSI300 / 800, 0.15% cost).
  - **Pretraining data runs to June 2024, so backtests before July 2024 are contaminated.**
  - No independent replication and no turning-point evaluation. The README says the pipeline is "not a production-ready quantitative trading system".
  - Compute: running small or base on a Mac CPU / Apple GPU for about 100 daily series looks feasible (my estimate). Sampling-based forecasts multiply the cost, and fine-tuning wants a GPU.
  - Verdict: **research-only.** If tried, use July 2024+ forecasts as one feature and compare them with the B-signals on the same days.
- **Chronos / Chronos-Bolt / Chronos-2 and TimesFM** (Apache-2.0)
  - Re(Visiting) TSFMs in Finance (2025), US daily excess returns, OOS 2001–2023:
    - Zero-shot R²: Chronos-large −1.37%, TimesFM-500M −2.80%. Directional accuracy ≈ 50–51%.
    - Fine-tuning gave limited gains. Finance-specific pretraining helped but still trailed CatBoost.
  - A 2026 study (5 US stocks, 20-day horizon) beat a random walk significantly in only 2 cases (p ≈ 0.042, uncorrected) and concluded the models are "not reliable sources of alpha".
  - Chronos-2 multivariate on the Mag7 (2026): lower MAPE than univariate, but no directional or trading test.
  - TimesFM financial fine-tune (2024): claims better mock-trading Sharpe; the authors' own test.
  - A substack test of monthly TimesFM forecasts on the top-50 US stocks: Sharpe 0.96 vs 0.46 for SPY, but drawdowns of 45%+. Useful only as a filter.
  - Verdict: **reject for daily turning points.**
- **Microsoft Qlib** (MIT): a framework for cross-sectional factor models (Alpha158 / Alpha360 features with LightGBM etc.), with China A-share data by default. It could host a walk-forward "bottom classifier", but nothing in it is built for turning points, and setup is heavy. **Deprioritize.**
- **FinRL** (MIT, DRL): its own team's follow-up paper (Gort et al. 2022) is about *detecting backtest overfitting* in DRL agents (crypto, 2-month test). DRL is data-hungry and fragile for about 100 daily series. **Reject.**

### Libraries (tools, not signals)

- **TA-Lib** (BSD-style; C library plus Python wrapper): fast and stable. Has RSI, STOCHRSI, WILLR, CCI, ADX, MACD, BBANDS and ATR, but no SuperTrend, IBS or CRSI. Good for cross-checking your RSI and BB values.
- **pandas-ta** (MIT): version 0.4.71b0 is a beta (Sep 2025) with a low maintenance score. It has squeeze, qqe, supertrend, stochrsi, td_seq, fisher and willr. Check its look-ahead flags (`dpo` centered, `ichimoku`) first.
- **vectorbt** (Apache-2.0 + Commons Clause, which bars selling products that are mostly vectorbt): fast parameter grids; fine for personal use.
- **backtesting.py** (AGPL-3.0): simple. AGPL only matters if you distribute or serve it.
- **freqtrade** (GPL-3.0) and **Jesse** (MIT): crypto-bot frameworks whose strategy repos are mostly intraday crypto. Little transfers to daily US equities.
- **backtrader** (GPL-3.0): contains reference code for Laguerre RSI and the Laguerre Filter.
- **Recommendation:** keep the indicator math in plain pandas/numpy (`ind.py`). Each rule is 30 lines or fewer, and you control the conventions in 1.1.

---

## 3. Sources

Opened and read in this session unless marked "(search result, not opened)".

**Indicators and rules**
- [ConnorsRSI — StockCharts ChartSchool](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/connorsrsi)
- [ConnorsRSI Pullbacks Guidebook — Connors Research (PDF mirror)](https://c.mql5.com/forextsd/forum/119/connorsrsi-pullbacks-guidebook.pdf)
- [Short Term Trading Strategies That Work, ch. 10 "Double 7's" — Connors & Alvarez (PDF mirror)](https://c.mql5.com/forextsd/forum/56/sttstw_chap10.pdf)
- [Larry Connors' Double 7 Strategy: Tested on SPY — StrategyQuant](https://strategyquant.com/blog/larry-connors-double-7-strategy-tested-on-spy-and-8-other-markets/)
- [Profitable Williams %R Strategy For Mean Reversion — Quantified Strategies](https://quantifiedstrategies.substack.com/p/profitable-williams-r-strategy-for)
- [Connors TPS Strategy — Wealth-Lab forum](https://wl6.wealth-lab.com/Forum/Posts/Connors-TPS-Strategy-40197)
- [Using Internal Bar Strength as a Key Indicator for Trading Country ETFs — Pandey & Joshi, arXiv 2306.12434](https://arxiv.org/html/2306.12434v1)
- [IBS reversion edge with QuantShare — R-bloggers (2013)](https://www.r-bloggers.com/2013/01/ibs-reversion-edge-with-quantshare/)
- [IBS Trading Strategy for SPY and NDQ — AlgoTradeKit (TradingView)](https://in.tradingview.com/script/C6uAEwxB-IBS-Internal-Bar-Strength-Trading-Strategy-for-SPY-and-NDQ)
- [Mean reversion effect in ETF price series — QuantConnect forum](https://www.quantconnect.com/forum/discussion/5675/mean-reversion-effect-in-etf-price-series/) (search result, not opened)
- [CM Williams Vix Fix: Pine Script to AmiBroker AFL — Marketcalls](https://www.marketcalls.in/amibroker/cm-williams-vix-fix-pinescript-to-amibroker-afl-conversion.html)
- [Equity Returns after Extreme VIX and William VIX FIX Readings — Marketcalls](https://www.marketcalls.in/amibroker/equity-returns-after-extreme-vix-and-william-vix-fix-readings.html)
- [When SPY pulls back and VIX spikes — backtest.substack](https://backtest.substack.com/p/when-spy-pulls-back-and-vix-spikes)
- [backtrader Laguerre RSI source (Ehlers, Cybernetic Analysis)](https://backtrader.readthedocs.io/en/latest/_modules/backtrader/indicators/lrsi.html)
- [Wave Trend Oscillator (LazyBear port) — ProRealCode](https://www.prorealcode.com/prorealtime-indicators/wave-trend-oscillator/)
- [Fisher Transform concept — LuxAlgo](https://www.luxalgo.com/library/concept/fisher-transform.md) (search result, not opened; the formula is from Ehlers 2002)
- [UT Bot Alerts port — Indie Script portal](https://indie-script.github.io/indicators/UT%20Bot%20Alerts/)
- [QQE MOD port — Indie Script portal](https://indie-script.github.io/indicators/QQE%20MOD%20Indicator%20(Mihkel00%20Concept,%20Port)/)
- [pandas-ta squeeze source — tradingstrategy.ai docs](https://tradingstrategy.ai/docs/_modules/pandas_ta/momentum/squeeze.html) (search result, not opened)
- [Chandelier Exit — StockCharts ChartSchool](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/chandelier-exit)
- [SystemTrader: Mean-Reversion System with the Chandelier Exit (SPY, QQQ, IJR) — Arthur Hill, StockCharts](https://articles.stockcharts.com/article/articles-arthurhill-2016-12-systemtrader---testing-a-mean-reverion-system-with-the-chandelier-exit-spy-qqq-ijr---rsi5/)
- [The SuperTrend Indicator Backtested — Quantified Strategies](https://quantifiedstrategies.substack.com/p/the-supertrend-indicator-backtested)
- [The Truth About TradingView's SuperTrend Strategy — HackerNoon (2026)](https://hackernoon.com/the-truth-about-tradingviews-supertrend-strategy-after-67-years-of-backtesting)
- [13 Essential Exits for Mean-Reversion Strategies — Algomatic Trading](https://algomatictrading.substack.com/p/13-essential-exits-for-mean-reversion)
- [Simple Test of RSI as an Abnormal Returns Indicator — CXO Advisory](https://cxoadvisory.com/technical-trading/simple-test-of-rsi-as-an-abnormal-returns-indicator)
- [TD Sequential (test on 42 futures) — Oxford Capital Strategies](https://oxfordstrat.com/indicators/td-sequential-3/)
- [Digging Deeper into Elder's Impulse System — StockCharts](https://articles.stockcharts.com/article/articles-chartwatchers-2012-01-digging-deeper-into-elders-impulse-system/)

**Market structure and breadth**
- [Indexing and Stock Market Serial Dependence Around the World — Baltussen, van Bekkum & Da, JFE (accepted manuscript), doi:10.1016/j.jfineco.2018.07.016](https://personal.eur.nl/vanbekkum/2018%20JFE%20BaltussenVanBekkumDa.pdf)
- [Effect of Tracking Products on Short-term Equity Index Trending/Reversal — CXO Advisory](https://www.cxoadvisory.com/technical-trading/effect-of-tracking-products-on-short-term-equity-index-trendingreversal/)
- [A CBI of 9 and S&P 500 at a 20-Day Low — Quantifiable Edges via Investing.com](https://investing.com/analysis/a-cbi-of-9--spx-at-a-20day-low-200300649)
- [40 Years of the Zweig Breadth Thrust — StockCharts](https://articles.stockcharts.com/article/articles-arthurhill-2019-01-perspective---40-years-of-the-zweig-breadth-thrust---weight-of-the-evidence/)

**Repainting and rejected scripts**
- [Repainting — TradingView Pine Script docs](https://www.tradingview.com/pine-script-docs/concepts/repainting/)
- [Nadaraya-Watson Envelope — LuxAlgo](https://www.luxalgo.com/library/indicator/nadaraya-watson-envelope/)
- [Machine Learning: Lorentzian Classification — jdehorty (TradingView)](https://www.tradingview.com/script/WhBzgfDu-Machine-Learning-Lorentzian-Classification/)
- [advanced-ta (Python port of Lorentzian Classification) — PyPI](https://pypi.org/project/advanced-ta/)
- [VuManChu Cipher B + Divergences — TradingView](https://tradingview.com/script/Msm4SjwI-VuManChu-Cipher-B-Divergences)

**ML and foundation models**
- [Kronos: A Foundation Model for the Language of Financial Markets — arXiv 2508.02739](https://arxiv.org/html/2508.02739v1) · [PDF](https://arxiv.org/pdf/2508.02739)
- [Kronos repository (MIT) — GitHub](https://github.com/shiyu-coder/Kronos)
- [Re(Visiting) Time Series Foundation Models in Finance — arXiv 2511.18578](https://arxiv.org/html/2511.18578v1)
- [Pretrained Time-Series Foundation Models for Financial Return Forecasting — arXiv 2606.27100](https://arxiv.org/pdf/2606.27100)
- [Multivariate Financial Forecasting using the Chronos TSFMs — arXiv 2605.21504](https://arxiv.org/pdf/2605.21504)
- [Financial Fine-tuning a Large Time Series Model (TimesFM) — arXiv 2412.09880](https://arxiv.org/html/2412.09880v1)
- [Does this large language model made by Google beat the market? TimesFM for trading — What Works in Trading](https://whatworksintrading.substack.com/p/does-this-large-language-model-made)
- [Deep RL for Cryptocurrency Trading: Practical Approach to Address Backtest Overfitting — Gort et al., arXiv 2209.05559](https://arxiv.org/abs/2209.05559v1)
- [Chronos forecasting — GitHub](https://github.com/amazon-science/chronos-forecasting) · [TimesFM — GitHub](https://github.com/google-research/timesfm) · [Qlib — GitHub](https://github.com/microsoft/qlib) · [FinRL — GitHub](https://github.com/AI4Finance-Foundation/FinRL) (canonical repos, not opened this session)

**Libraries**
- [pandas_ta package status — depscope](https://depscope.dev/pkg/pypi/pandas_ta) · [pandas-ta — GitHub](https://github.com/twopirllc/pandas-ta)
- [vectorbt 0.25.0 — PyPI (Apache 2.0 with Commons Clause)](https://pypi.org/project/vectorbt/0.25.0)
- [backtesting.py — GitHub (AGPL-3.0)](https://github.com/kernc/backtesting.py)
- [TA-Lib Python wrapper — GitHub](https://github.com/TA-Lib/ta-lib-python) · [freqtrade — GitHub](https://github.com/freqtrade/freqtrade) · [Jesse — GitHub](https://github.com/jesse-ai/jesse) (canonical repos, not opened this session)
