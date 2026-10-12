# R-C: Macro and cross-asset background values (as of 2026-10-12)

**Labels:** [A] peer-reviewed · [S] sell-side, fund or official · [P] practitioner · [N] none found · [Q] our quick in-sample check (Yahoo daily 2008–26; overlapping windows, 20–45 episodes; descriptive, not significance-tested). **[Q] baseline, next 20 sessions (fwd20):** NDX +1.4% mean, 66% up, 10th pct −5.4%; SOX +1.9%, 62%, −7.7%.

## 1. Variable by variable

| Variable | (a) Mechanism | (b) Evidence | (c) Free data | (d) Rule to test |
|---|---|---|---|---|
| Oil | Cost and inflation shock | [A] Driesprong+ 2008: oil rises predict lower next-month returns. [A] Kilian-Park 2009: the effect depends on supply vs demand shock. [Q] Brent ≥+20% in 20d → NDX fwd20 +3.7% (mostly rebounds) | Yahoo CL=F, BZ=F; FRED DCOILWTICO, DCOILBRENTEU (1986/87–) | Brent Δ20d ≥+20% and Dated Brent − futures > $5 → test a 5–10d entry delay |
| Gold | Safe haven, real rates | [A] Baur-Lucey 2010: a haven during crashes, not a predictor. [A] Huang-Kilic 2019: +1 SD log(gold/platinum) → +6.4% next-year return; 1-month R² 1.2%; mostly positive out of sample | Yahoo GC=F, PL=F | Gold/platinum z > +1 → loosen trim |
| Natural gas, silver | Regional cost; high-beta metal | [N] | Yahoo NG=F, SI=F; FRED DHHNGSP | Skip |
| Copper/gold | Growth vs fear | [P] Gundlach (10y guide). [Q] no effect | Yahoo HG=F, GC=F | Low priority |
| UST yields, real yields, term premium (TP), 2s10s | Discount-rate shock to long-duration tech | [A] Welch-Goyal 2008; Goyal-Welch-Zafirov 2024: term spread etc. fail out of sample. [A] Ang-Bekaert 2007: the short rate predicts negatively. [A] Bernanke-Kuttner 2005: a 25bp surprise cut ≈ +1%; high-tech moves 1.5×. [S] Goldman 2025: stocks struggle when the 10y rises >2 SD in a month (~60bp); 100bp real yield ≈ 7% of P/E. [S] Morgan Stanley 2026: 4.5% level. [Q] 10y ≥+40bp in 20d → NDX fwd20 −0.4%, SOX up 48% of the time, 10th pct −10.7%; no 60d effect | Treasury par (1990–) and real (2003–) CSVs; FRED DGS2, DGS10, DFII10, T10Y2Y, THREEFYTP10 | Δ20d DFII10 or THREEFYTP10 > +2 SD → no leveraged dip-buys |
| JGB/Bund/Gilt, yen carry | Global term premium; forced deleveraging | [A] Brunnermeier-Nagel-Pedersen 2008: carry trades crash when risk appetite and funding fall. [S] BIS Bulletin 90: ~¥40tn ($250bn) of carry before the Aug-2024 unwind. [Q] USDJPY ≤−3% in 10d → fwd20 ≈ baseline (moves with the selloff, not ahead). Gilt: [N] | MOF CSV (1974–); Bundesbank API; Yahoo JPY=X; CFTC | JGB Δ20d > +2 SD and USDJPY Δ10d ≤ −3% → pause adds 5d |
| Inflation | Policy path, real yields | [A] Savor-Wilson 2013: average returns are higher on CPI, jobs and FOMC days. [A] Campbell-Pflueger-Viceira 2020: high inflation turns the stock-bond correlation positive. [A] Lucca-Moench 2015: pre-FOMC drift (+49bp), gone after 2015 (Kurov+ 2021). Breakevens: [N] | FRED CPIAUCSL, PCEPILFE, T10YIE, T5YIFR | 2y up ≥10bp on CPI day → 3d pause |
| Consumer | Demand, breadth of earnings | [A] Fisher-Statman 2003: high confidence → lower next-month Nasdaq and small-cap returns. [A] Lemmon-Portniaguina 2006: same, small stocks. [A] Hong-Torous-Valkanov 2007: retail stocks lead the market ~1–2 months. Retail sales, delinquencies: [N] | Census; UMich (1978–); FRED RSAFS, DRCCLACBS; Yahoo XLY, XLP, XRT | XLY/XLP 60d < −5% → tighter trim |
| Credit | Funding and default risk | [A] Gilchrist-Zakrajšek 2012: the excess bond premium (EBP) predicts economic activity. [A] Fama-French 1989: wide spreads → higher long-run returns, but this fails out of sample. [Q] HYG/IEF bottom-decile Δ20d → NDX fwd20 +2.4%, 10th pct −9.1% | FRED BAMLH0A0HYM2 (~3y only); Yahoo HYG, IEF; Fed EBP CSV (1973–) | Halve dip size when HYG/IEF is at a 60d low |
| DXY | Dollar funding, foreign-earnings translation | [N]. [Q] top-decile Δ20d → NDX fwd60 +2.5% vs +4.4% | Yahoo DX-Y.NYB | Already in composite |
| Financial conditions indices | Built from market prices, so they move with markets | [A] Adrian-Boyarchenko-Giannone 2019: NFCI predicts GDP downside, not returns. The GS FCI is proprietary | FRED NFCI (weekly 1971–) | Low priority |
| Fed liquidity | Reserves → risk appetite | [P] "net liquidity" charts; trending-series fits are often spurious. [N] peer-reviewed | FRED WALCL, WTREGEN, RRPONTSYD | Weekly changes only |

## 2. What timed AI and semis in 2023–26
- **How fast yields rose** was the most repeatable headwind: SOX −17.5% (31 Jul–30 Oct 2023; 10y +92bp) and −16.6% (7 Mar–19 Apr 2024; +52bp), consistent with Goldman's finding that speed matters [S].
- **Vol and carry shocks** were sharpest but buyable: 10 Jul–7 Aug 2024 SOX −25%, USDJPY −10%, VIX close 38.6, 10y falling [S, BIS].
- **22 Jan–8 Apr 2025:** SOX −35% (DeepSeek, tariffs). Yields rose as stocks fell (10y +27bp 4–8 Apr, +51bp by 11 Apr), the most dangerous mix.
- **2026 Iran war** (Hormuz shut from 28 Feb): Brent +59%, SOX −15.6% to 30 Mar, then +105% to 22 Jun. 22 Jun–29 Jul: SOX −28.6% as Brent rose 16.5% after the ceasefire lapsed and the Fed turned hawkish (AI-specific causes not checked).
- **Sep–Oct 2026:** the 10y passed 5% and the Fed hiked, yet SOX rose 12.5% (15 Sep–9 Oct); year to date SOX +71%, 10y +105bp. Yield-level thresholds failed; earnings dominated.
- **Takeaway:** watch the speed of real-yield and term-premium moves, plus vol and carry stress. Oil spikes were buyable unless credit confirmed.

## 3. Current readings (close on or before Fri 9 Oct unless noted)

| Item | Value | Src |
|---|---|---|
| WTI / Brent front-month | $91.85 / $104.72; EIA spot 6 Oct $96.24 / $125.44 (steep backwardation) | Y, F |
| Hormuz | 4 transits on 4 Oct vs 85/day pre-war; 9 ships hit 1–6 Oct | SL |
| Henry Hub | $3.22 | Y |
| Gold / silver / copper | $4,216 / $60.67 / $6.64 per lb | Y |
| UST 2y / 10y / 30y | 4.80 / 5.24 / 5.60%. 10y highest since 2007; Δ20d +17 / +28bp | T |
| 2s10s | +44bp | F |
| 10y TIPS real yield | 2.91%, highest since 2008 | T |
| 10y breakeven / 5y5y | 2.33 / 2.32% | F |
| 10y term premium (Kim-Wright) | 1.08% (2 Oct), highest since 2010 | F |
| JGB 10y / 30y | 3.09 / 4.14% (8 Oct) | MOF |
| Bund 10y | ≈3.53% | BBk |
| USD/JPY / DXY | 158.06 / 102.21 (DXY Δ20d +3.1%) | Y |
| CPI Aug (released 11 Sep) | 3.4% y/y, +0.4% m/m; core 2.4%, +0.3% | TE, CIC |
| Next CPI | Sep CPI: Wed 14 Oct, 8:30 ET | BLS |
| PCE Aug (released 30 Sep) | 3.4%; core 3.0%; real spending +0.6% m/m; real income 0.0% | BEA |
| Retail sales Aug (released 16 Sep) | +1.2% m/m; next release 15 Oct | CEN |
| UMich prelim Oct (9 Oct) | 46.3 (Sep 48.1); 1y inflation expectations 4.7% | UM |
| Card delinquency Q2 | 2.85% (Q3-2025: 2.99%) | F |
| HY / IG OAS; EBP | 3.15 / 0.82% (8 Oct); EBP −0.39 (Sep) | F, EBP |
| VIX / VIX3M | 14.84 / 17.77 (ratio 0.84, calm) | Y |
| NFCI | −0.494 (week to 2 Oct): loose | F |
| Fed assets / ON RRP / TGA | $6.748tn / $0.3bn / $880bn | F |
| Fed funds | 3.75–4.00% after a 25bp hike on 16 Sep (12–0). SEP median: 4.1% at end-2026, core PCE 3.4% | FED |
| Next FOMC | 27–28 Oct | FED |
| BOJ | 1.25% after a hike on 18 Sep (7–2); next meeting 29–30 Oct | BOJ |
| Event risk | 14 Oct CPI · 15 Oct PPI, retail sales · 23 Oct UMich final · 28 Oct FOMC · 29 Oct Q3 GDP, Sep PCE, ECB · 30 Oct BOJ, ECI · 3 Nov midterms · Hormuz attacks | BLS, BEA, ECB, BOJ |

**[Q] signals on now:** only DXY Δ20d (top decile); 10y Δ20d +27bp is just under its +31bp line. Gold/platinum (2.51) is in its 2008–26 top quintile, bullish per Huang-Kilic, but that covers only 4 regimes. SOX is 14% below its 22 Jun peak.

## Most promising to backtest with free daily data
1. **VIX term structure / variance risk premium as dip-buy enabler:** VIX/VIX3M ≥ 1, or VIX² − 21d realized SPX variance in top quintile → larger dip-buys. [A] Bollerslev-Tauchen-Zhou: explained >15% of quarterly return variation (1990–2005). [Q] SOX fwd60 +11.3% vs +6.0%, deeper tails. Yahoo ^VIX, ^VIX3M, ^GSPC.
2. **Speed of real-yield / term-premium rises:** Δ20d DFII10 or THREEFYTP10 > +2 SD → no leveraged dip-buys (isolates the harmful part of your 5y input). FRED DFII10, THREEFYTP10.
3. **Credit confirmation:** HYG/IEF at a 60d low → halve dip size. Yahoo HYG, IEF.
4. **Oil supply-shock flag** (rule in the table). Yahoo BZ=F; FRED DCOILBRENTEU.
5. **Consumer lead:** XLY/XLP 60d < −5% → tighter trim. Yahoo XLY, XLP.
6. **Event overlay:** FOMC-cycle even weeks ([A] Cieslak+ 2019); 3d pause when the 2y jumps ≥10bp on CPI day. Test post-2015 separately. Fed calendar; Treasury CSV.

**Skeptic's note:** most macro predictors fail out of sample (Welch-Goyal). Use walk-forward thresholds; require the effect in both 2008–16 and 2017–26.

**Caveats:** BLS site/API were blocked, so CPI is from two secondary sources (consistent with FRED index data). The web-search budget ran out late. DOIs marked * are from memory.

## Sources
- Y: https://query1.finance.yahoo.com/v8/finance/chart/{symbol}
- T: https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2026/all?type=daily_treasury_yield_curve (real: type=daily_treasury_real_yield_curve)
- F: https://fred.stlouisfed.org/graph/fredgraph.csv?id={SERIES}
- MOF: https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv
- BBk: https://api.statistiken.bundesbank.de/rest/data/BBSIS/D.I.ZST.ZI.EUR.S1311.B.A604.R10XX.R.A.A._Z._Z.A
- SL: https://straits.live/briefs/2026-10-09
- TE: https://tradingeconomics.com/united-states/inflation-cpi/news/583187
- CIC: https://cpiinflationcalculator.com/the-consumer-price-index-rises-0-4-in-august-2026-seasonally-adjusted-and-holds-at-3-4-annually/
- BLS: https://www.bls.gov/schedule/2026/10_sched_list.htm
- BEA: https://www.bea.gov/news/2026/personal-income-and-outlays-august-2026 ; https://www.bea.gov/news/schedule
- CEN: https://www.census.gov/retail/marts/www/marts_current.pdf
- UM: https://www.sca.isr.umich.edu/
- EBP: https://www.federalreserve.gov/econres/notes/feds-notes/ebp_csv.csv
- FED: https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm ; https://www.federalreserve.gov/monetarypolicy/fomcprojtabl20260916.htm ; https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
- BOJ: https://www.boj.or.jp/en/mopo/mpmdeci/mpr_2026/k260918a.pdf ; https://www.boj.or.jp/en/mopo/mpmsche_minu/index.htm
- ECB: https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html
- War and July FOMC: https://www.omanobserver.om/article/1188189/world/region/trump-accuses-iran-of-total-violation-of-ceasefire ; https://www.atfx.com/en-au/analysis/financial-events/september-fomc-meeting-2026-is-a-rate-hike-on-the-table
- Goldman: https://www.goldmansachs.com/insights/articles/how-higher-rates-affect-us-stocks · Morgan Stanley: https://investinglive.com/stock-market-update/morgan-stanley-says-us-stock-correction-largely-done-rates-the-final-hurdle-before-higher-20260406/ · BIS: https://www.bis.org/publ/bisbull90.htm
- Driesprong+: https://ideas.repec.org/a/eee/jfinec/v89y2008i2p307-327.html · Kilian-Park: https://doi.org/10.1111/j.1468-2354.2009.00568.x* · Huang-Kilic: https://conference.nber.org/conf_papers/f80928.pdf · Baur-Lucey: https://doi.org/10.1111/j.1540-6288.2010.00244.x*
- Welch-Goyal: https://doi.org/10.1093/rfs/hhm014* · Goyal-Welch-Zafirov: https://www.sfi.ch/en/publications/a-comprehensive-2022-look-at-the-empirical-performance-of-equity-premium-prediction · Ang-Bekaert: https://doi.org/10.1093/rfs/hhl021* · Bernanke-Kuttner: https://www.nber.org/papers/w10402
- Brunnermeier+: https://www.nber.org/papers/w14473 · Savor-Wilson: https://doi.org/10.1017/S0022109013000141* · Campbell+: https://doi.org/10.1086/707766* · Lucca-Moench: https://doi.org/10.1111/jofi.12196* · Kurov+: https://ideas.repec.org/a/eee/finlet/v40y2021ics1544612320315956.html · Cieslak+: https://doi.org/10.1111/jofi.12818*
- Fisher-Statman: https://www.cxoadvisory.com/sentiment-indicators/does-consumer-confidence-predict-stock-market-returns/ · Lemmon-Portniaguina: https://doi.org/10.1093/rfs/hhj038* · Hong+: https://ideas.repec.org/a/eee/jfinec/v83y2007i2p367-396.html · Gilchrist-Zakrajšek: https://doi.org/10.1257/aer.102.4.1692* · Fama-French: https://doi.org/10.1016/0304-405X(89)90095-0* · Adrian+: https://doi.org/10.1257/aer.20161923* · Bollerslev+: https://www.federalreserve.gov/econres/feds/expected-stock-returns-and-variance-risk-premia.htm
