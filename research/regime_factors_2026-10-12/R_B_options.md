# Topic B: Options market effects on US stocks (as of 2026-10-12)

**Labels:** [A] peer-reviewed · [WP] working paper · [S] sell-side/exchange · [P] practitioner · [N] no evidence found · [Own] my own in-sample check of the SPX on free data

**Caveats on [Own]:** Overlapping windows, Newey-West t; ~12 conditions tested, so expect ~1 false positive. Use it to rank ideas, not as proof. Search budget ran out before I found October Goldman/Nomura gamma notes or the Q4 JPM collar strikes.

## 1–2. Mechanism and evidence

| Variable | Measures / mechanism | Evidence (1–20d) |
|---|---|---|
| **Dealer gamma (GEX, zero-gamma flip)** | Dealer hedging per 1% move. Long gamma dampens moves; short gamma amplifies them. | [A] Single stocks: dealer net gamma predicts smaller next-day \|return\|; hedging explains ~10–13% of daily \|returns\| (1990–2012) [1]. [A] Negative index gamma brings intraday momentum (slope 6.6; 0.8, not significant, when positive), which reverses within 3 days [2]. [P] The white paper has no statistics [3]. [Own] GEX<0 (lagged 1d, 2011–26): next-5d realized vol 21.8% vs 10.8% (t≈6.8). Next-20d SPX +2.6% vs +0.8% (t≈2.4). GEX gauges swing size, not direction, which may explain the failed filter test. |
| **Vanna/charm** | IV falls and time decays into OPEX, so dealers buy back hedges. That support ends after expiry. | [P] SpotGamma's "window of weakness" comes with no statistics [4]. [N] Not peer-reviewed. |
| **Monthly OPEX** | Prices pin to large strikes, then are released. | [WP] 28 large caps, 1996–2008: OPEX week +0.45% vs +0.12% other weeks; the following week −0.03% [5]. [P] SPY rose in only 17 of 70 weeks after Mar/Jun/Sep OPEX (1993–2016) [6]. [Own] SPX 1990–2010: OPEX week +0.35%, week after −0.18%. 2011–26: +0.08% and +0.35% (others +0.27%). The effect is gone. |
| **VIXperation** | VIX settlement removes hedge flows. | [A] Abnormal OTM SPX put volume at settlement. This is microstructure, not a return effect [7]. [Own] Post-OPEX weeks with VIX expiry: +0.10% vs +0.49% (not significant). |
| **JPM collar (quarter-end)** | About 35k SPX contracts per leg (~$23bn notional). It can pin the index, then release it at the reset. | [P] Anecdotes only [8]. [N] |
| **0DTE** | About 76% of SPX volume (Sep 2026) [9]. | [WP] 0DTE gamma lowers intraday vol, with no overnight effect [10]. [WP] Annualized vol is ~60bp lower on 0DTE days [11]. [S, conflicted] Market-maker net gamma ≤0.2% of futures liquidity [12]. Effect is intraday; OI-based GEX misses 0DTE flow. |
| **Single-stock call frenzies** | Dealers short calls buy stock as it rises; this unwinds after expiry or an IV crush. | [A] Opening-buy put/call (non-public data) predicts >1% next-week spreads [13]. Calls rich vs puts: +50bp/week, a fading effect [14]. Steep put smirk: −10.9%/yr [15]. [P] Call-heavy OPEXes said to precede reversals, no statistics [4]. NVDA and TSLA are each ~9% of single-stock option volume [16]. |
| **Put/call** | Equity P/C reflects speculation and is read contrarian. Index P/C reflects hedging. | [A] VIX, P/C and TRIN are contrarian at 10–30d [17]. [Own] Equity P/C 10d average, top decile (2007–19): next-20d +0.7pp (t≈1.0). The median drifted from 0.64 (2006–19) to 0.45 (2020–21) to ~0.60 (2022–26), so use rolling percentiles. |
| **SKEW / 25Δ skew** | Price of OTM SPX puts. | [A] Adds no 1-day predictive power [18]. A put-only SKEW carries tail information out to 1 year [19]. [Own] Top decile: next-20d −0.6pp (t≈−1.9), with no deeper drawdowns. |
| **VIX level / VRP** | VRP = VIX² minus realized variance. | [A] VRP explains >15% of quarterly returns but only ~1.2% monthly [20]. [Own] VIX≥30: next-20d +1.8pp (t≈2.1). Interim drawdown −3.8% to −6.7%. |
| **VIX term structure (VIX/VIX3M, VIX9D/VIX)** | >1 = backwardation: acute stress, forced hedging. | [A] Slope predicts VIX-futures/variance-swap returns (no SPX evidence) [21]. [WP] Backwardation precedes positive S&P returns [22]. [P] Weeks with VIX9D>VIX: SPY 4-week median +1.45% vs +1.69%, SD 7.0% vs 4.4% [23]. [Own] VIX/VIX3M>1 (2009–26, 42 episodes): next-20d +2.8% vs +1.0% (t≈2.2); 74% of episodes positive; interim low −3.9% vs −2.5%. |
| **VVIX / MOVE** | Vol of VIX / Treasury implied vol. | [A] High VVIX predicts lower tail-hedge returns over 3–4 weeks [24]. [P] MOVE >150 is an S&P coin flip [25]. [Own] VVIX top decile +0.6pp (t≈0.8); MOVE no edge. |
| **Implied correlation (COR1M/3M), dispersion (DSPX)** | Low = stocks move independently; dispersion sellers are short index vol, fragile if correlation snaps up. | [WP] Implied correlation predicts market returns up to 1 year, in- and out-of-sample [26]. [Own] Bottom decile, next-20d: COR1M −0.8pp (t≈−2.2), COR3M −0.9pp (t≈−2.3). DSPX shows no edge. [P] Record-low COR1M (2.93, 12-Jul-2024) preceded the August shock; one anecdote. |

## 3. Free data

| Series | URL | Start | Notes |
|---|---|---|---|
| VIX, VIX3M, VIX9D, VIX6M, VIX1D, VVIX, SKEW, COR1M, COR3M, DSPX, VXN, VXSMH, SPX | `https://cdn.cboe.com/api/global/us_indices/daily_prices/<SYMBOL>_History.csv` | VIX/SKEW 1990; VVIX 2006; COR 2006; VIX3M 2009; VIX9D 2011; DSPX 2014; VIX1D 2022; VXSMH 2025-09 | Daily to 10-09; 307-redirects to cdn-api.cboe.com |
| Put/call 2006-11→2019-10-04 | `https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/equitypc.csv` (also totalpc, indexpc) | 2006 | Frozen |
| Put/call 2019-10-07→ | `https://cdn.cboe.com/data/us/options/market_statistics/daily/YYYY-MM-DD_daily_options` | 2019 | Still published, one JSON per day (ratios, call/put volume, OI); Cboe exchange only |
| GEX/DIX | `https://squeezemetrics.com/monitor/static/DIX.csv` | 2011-05 | Daily, includes SPX |
| MOVE | `https://query1.finance.yahoo.com/v8/finance/chart/%5EMOVE?period1=1041379200&period2=1791800000&interval=1d` | 2003 | Unofficial; metadata mislabeled, values match MOVE |
| Single-stock IV/GEX | No free source | – | Paid only: ORATS, OptionMetrics, Cboe DataShop |

**Bias warnings:** Act at the next open. Lag SqueezeMetrics one day. Dollar GEX and P/C drift, so use rolling 1-year percentiles. Early COR/DSPX/VIX1D history may be back-calculated. Only 42 inversion episodes make t≈2 marginal.

## 4. Testable rules (daily close, enter next open)

- **R1:** Bottom signal + VIX/VIX3M ≥1.0 (or ≥0.95, rising) → bigger 10–20d rebound? Compare median return, hit rate and MAE (worst drawdown during the trade).
- **R2:** Same test with VIX ≥30 or VVIX in its 1-year top decile.
- **R3:** GEX(t−1) <0 or in its 1-year bottom decile: don't veto the buy; double stop width or halve 2x-ETF size. Judge by return per unit of risk.
- **R4:** Trim signal plus COR1M/COR3M in the 1-year bottom decile: trim harder and add no leverage. Check 20d return and max drawdown.
- **R5:** Trim signal plus SKEW in its 1-year top decile confirms the trim (weak).
- **R6:** Bottom signal plus equity P/C 10d average in its 1-year top decile confirms the bottom (weak).
- **R7:** Use OPEX, post-OPEX, VIX-expiry and quarter-end weeks as control flags only; keep one only if it works out-of-sample.
- **R8:** Single names: test the call-minus-put IV spread [14] and smirk [15]. This needs paid data.

## 5. Current readings (2026-10-09 close; Cboe CSV/JSON above)

| Item | Value |
|---|---|
| VIX / VIX3M | 14.84 / 17.77. Ratio 0.835, steep contango (20th pct since 2009). |
| VIX9D / VIX1D | 11.26 / 9.05; VIX9D/VIX 0.76 (2nd pct): very calm front end |
| VVIX | 84.88 (32nd pct) |
| SKEW | 154.34, the 98th pct since 1990 (141.8 on Oct-7) |
| COR1M / COR3M | 6.93 / 11.33, around the 1st/2nd pct since 2006 |
| DSPX | 36.02 (95th pct): calm index, dispersed stocks |
| VXN / VXSMH | 20.55 / 36.38 (VXSMH: 22nd pct of its 1-year history) |
| MOVE | 98.47 (peak 113.6 on Oct-5; 94th pct of trailing year) |
| Put/call | Total 0.82. Equity 0.56 (10d average 0.56, the 2019–26 median). Index 1.13. SPX 1.24. |
| GEX / DIX | +$12.8bn (98.8th pct of raw history; last negative 2026-06-26) / 0.473. SPX 7,811.5, near its 7,818.9 record (Oct-6). |
| Dealer commentary | SpotGamma 12-Sep: flip 7,600; dealer short gamma $8–10bn → ~$4bn after September OPEX [27]. IBTimes/CNBC, 10–11 Sep: VIX 3-month call skew at the 91st pct; Nomura's McElligott warns of a "negative risk trinity" (midterms, rates, Middle East) [28]. October notes: not found. |
| Calendar | OPEX Fri 16-Oct. VIX expiry Wed 21-Oct. Midterms 3-Nov. VIX expiry 18-Nov; OPEX 20-Nov. VIX expiry 16-Dec; quarterly OPEX 18-Dec. JPM collar reset 31-Dec (strikes not found) [29]. |
| AI names | NVDA $233.95 (2-Oct). Option deltas imply ~50% odds of a $6T market cap (~$249) by end-October [30]. Semiconductor IV has fallen since late June [27]. AMD/AVGO/MU/TSM/PLTR option activity: not found. |

**Regime:** long gamma, low index vol, record-low correlation, high SKEW. In my check this mix preceded below-average 20d drift (weak evidence); not a crash signal.

## Most promising to backtest with free daily data

1. VIX/VIX3M ≥1 as a bottom amplifier: https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv + https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX3M_History.csv
2. GEX regime to set position size and stops: https://squeezemetrics.com/monitor/static/DIX.csv
3. Low implied correlation as a signal to trim and reduce leverage: https://cdn.cboe.com/api/global/us_indices/daily_prices/COR1M_History.csv + https://cdn.cboe.com/api/global/us_indices/daily_prices/COR3M_History.csv
4. High SKEW to confirm a trim: https://cdn.cboe.com/api/global/us_indices/daily_prices/SKEW_History.csv
5. Equity P/C as a contrarian confirmation: https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/equitypc.csv + https://cdn.cboe.com/data/us/options/market_statistics/daily/2026-10-09_daily_options (one file per date)
6. VVIX spike as a capitulation signal (weak on its own; pair with #1): https://cdn.cboe.com/api/global/us_indices/daily_prices/VVIX_History.csv

## Sources

1. https://ideas.repec.org/a/oup/rfinst/v34y2021i4p1952-1986..html
2. https://www3.nd.edu/~zda/intramom.pdf
3. https://slopeofhope.com/wp-content/uploads/2020/11/GEX-white_paper.pdf
4. https://spotgamma.com/july-opex-opens-the-window-of-weakness/
5. https://cxoadvisory.com/calendar-effects/option-expiration-week-stock-return-drill-down
6. https://sentimentrader.com/blog/the-headwind-from-option-expiration/
7. https://quantpedia.com/is-vix-index-manipulated/
8. https://insights.hypercall.xyz/jpm-collar-q1-2026
9. https://spotgamma.com/?p=21409
10. https://harbourfrontquant.substack.com/p/impact-of-zero-dte-options-on-the
11. https://quantpedia.com/do-sp500-0dtes-options-increase-market-volatility/
12. https://www.cboe.com/insights/posts/volatility-insights-evaluating-the-market-impact-of-spx-0-dte-options
13. https://www.nber.org/papers/w10925
14. https://ideas.repec.org/a/cup/jfinqa/v45y2010i02p335-367_00.html
15. https://ideas.repec.org/a/cup/jfinqa/v45y2010i03p641-662_00.html
16. https://www.cboe.com/insights/posts/state-of-the-options-industry-options-market-continued-to-break-records-in-q-2-2026
17. https://ideas.repec.org/a/wly/jfutmk/v21y2001i5p447-462.html
18. https://ideas.repec.org/a/eee/ecmode/v64y2017icp449-464.html
19. https://ideas.repec.org/a/eee/finsta/v53y2021ics1572308920301194.html
20. https://www.federalreserve.gov/pubs/feds/2007/200711/index.html
21. https://www.cxoadvisory.com/volatility-effects/vix-term-structure-slope-and-variance-asset-future-returns/
22. https://macrosynergy.com/?p=41000
23. https://flashalpha.com/articles/vix-term-structure-inversions-since-2018-data-study
24. https://www.federalreserve.gov/econres/feds/volatility-of-volatility-and-tail-risk-premiums.htm
25. https://sentimentrader.com/blog/the-surprising-reach-of-bond-volatility
26. https://cepr.org/publications/dp12760
27. https://spotgamma.com/september-opex-negative-gamma-7600/
28. https://www.ibtimes.com/wall-street-getting-nervous-about-whats-next-investors-hedge-against-negative-risk-trinity-3807361
29. https://www.macroption.com/options-expiration-calendar/ ; https://www.macroption.com/vix-expiration-calendar/
30. https://www.ibtimes.com/nvidia-closing-6-trillion-valuation-options-traders-see-october-key-window-3808223
