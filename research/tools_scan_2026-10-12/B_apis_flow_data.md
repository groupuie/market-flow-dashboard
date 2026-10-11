# Research B: signal APIs, AI ratings, and institutional/quant positioning data

Checked 2026-10-12 (Taiwan time). Read-only research: nothing in the repo was changed, nothing was signed up for, and no key or email address was sent anywhere.

**How sure each claim is**
- **Verified**: I downloaded the file or called the endpoint myself today, or read the provider's own page.
- **Reported**: taken from a third-party page, or from a search listing I did not open. Marked as such in the text.
- **Not re-verified**: from background knowledge. Check it before relying on it.

**Already tested in this project, not repeated here** (v0.5, 2026-10-11): FINRA daily short-sale volume ratio (f1), Futu main-capital flow (f2), FINRA days-to-cover (f3), insider Form 4 (t6) and volume-contraction consolidation (t30). The system also already has a VIX term-structure layer, a cash-pool layer (ICI money-market funds, FINRA margin, ON RRP), a CTA trend layer (`cta_trend.py`) and a vol-control state layer (RVPOS).

---

## 0. Bottom line

1. **Ready-made "AI / pattern / technical rating" services are a poor fit for backtesting.** Either the history is paid (Danelfin, Kavout, Zacks, TipRanks, Benzinga), or there is no history at all. Finnhub's pattern, support/resistance and aggregate-signal endpoints are premium-only and return only today's snapshot. TradingView, Barchart, Investing.com and StockCharts have no data API, and their terms restrict automated use.
2. **The indicator APIs add nothing new.** Alpha Vantage, Twelve Data, FMP, EODHD and Massive all serve formulas (SMA, RSI, MACD and so on) that the engine already computes locally. The project has already found that these indicators have no standalone directional edge.
3. **The useful free data is on the positioning side.** The following can be downloaded free, with no key and with long daily history:
   - SqueezeMetrics DIX/GEX (daily since 2011, confirmed live today)
   - Cboe put/call ratios (daily since 2006)
   - issuer ETF shares-outstanding files, which give ETF flows (SPY since about 2003)
   - CFTC Traders in Financial Futures for the E-mini S&P 500 and Nasdaq-100 (weekly since 2006)
   - OCC per-stock options volume split by customer, firm and market maker (only the last 2 years, so archiving should start now)
4. **None of these have independent proof that they time short-term tops or bottoms in QQQ or tech stocks.**
   - Peer-reviewed support exists for some of the *mechanisms*: dealer gamma and volatility, put/call as a contrarian signal at 10–30 days, and ETF-flow reversal.
   - All direction claims for DIX/GEX come from the vendor.
   - Treat every item below as a hypothesis to pre-register and test.

---

## 1. Table: technical-signal, pattern, AI-rating APIs and MCP servers

| Service | What it returns | Free tier | Paid tier (price) | History: can past signals be downloaded for a backtest? | Terms / limits | Independent evidence of accuracy | Key? |
|---|---|---|---|---|---|---|---|
| **Finnhub** ([API spec](https://finnhub.io/static/swagger.json)) | Pattern recognition (double/triple top and bottom, head-and-shoulders, triangle, wedge, channel, flag, candlesticks, with entry, stop and target), support/resistance levels, an "aggregate indicators" buy/neutral/sell vote plus ADX trend flag, 50+ indicators, candles | Free key covers: quote, analyst recommendation trends, insider transactions and insider sentiment, earnings (last 4 quarters), company news (1 year) | **Verified:** Finnhub's own spec marks `/scan/pattern`, `/scan/support-resistance`, `/scan/technical-indicator`, `/indicator` and even `/stock/candle` as **"Premium Access Required"**. Price not captured (the pricing page did not render). | **No.** The scan endpoints accept only `symbol` and `resolution` (no date range), so they return today's state only. History exists only if you archive it nightly from now on. | — | None found. The algorithm is undisclosed. | Yes |
| **Alpha Vantage** ([docs](https://www.alphavantage.co/documentation/), [premium](https://www.alphavantage.co/premium/)) | 50+ indicators (SMA, EMA, RSI, BBANDS, STOCH, ADX, OBV…) computed on its own prices. MACD and VWAP are premium. Daily OHLCV with "25+ years". | **25 requests/day.** On free keys the daily `outputsize=full` and `TIME_SERIES_DAILY_ADJUSTED` are premium, so long price history is effectively paid. | $49.99/mo (75 req/min) up to $249.99/mo (1,200 req/min) | Indicator series are historical, but they are standard formulas you can compute locally. There is no proprietary signal. | Real-time data is "for personal use" | Not applicable (standard indicators) | Yes. Official MCP server ([mcp.alphavantage.co](https://mcp.alphavantage.co/)) |
| **Massive** (formerly Polygon.io) ([pricing](https://massive.com/pricing), [options](https://massive.com/options)) | OHLCV aggregates, SMA/EMA/MACD/RSI endpoints, options (chains, trades, daily open interest), plus Benzinga analyst ratings and news through partner data | Stocks Basic $0: 5 calls/min, 2 years, end-of-day. Options Basic $0: 2 years, end-of-day, no open interest or greeks. | Stocks: Starter $29 (5 yr), Developer $79 (10 yr), Advanced $199 (20+ yr, real-time). Options: Starter $29 (2 yr, daily OI), Developer $79 (4 yr, trades), Advanced $199 (5+ yr, trades and quotes). | Yes for price and options history (depth depends on tier). Indicators are plain formulas. | Terms not reviewed | Not applicable (data vendor) | Yes. MCP: [massive-com/mcp_massive](https://github.com/massive-com/mcp_massive) (MIT; `MASSIVE_API_KEY`; hosted at mcp.massive.com) |
| **Financial Modeling Prep (FMP)** ([pricing](https://site.financialmodelingprep.com/developer/docs/pricing)) | Indicators (SMA, EMA, WMA, DEMA, TEMA, RSI, ADX, Williams %R, standard deviation) | Basic $0: 250 calls/day, 5 years of end-of-day data. Indicators first appear in the Premium tier. | Starter $19/mo, Premium $49/mo (30+ yr), Ultimate $99/mo (annual billing) | Plain formulas | "Displaying or redistributing data sourced from FMP requires a specific Data Display and Licensing Agreement" | Not applicable | Yes. Community MCP servers exist (not verified) |
| **Twelve Data** ([pricing](https://twelvedata.com/pricing), [MCP](https://twelvedata.com/docs/llms/ai/mcp-server.md)) | 100+ indicators on every tier | Basic: 8 credits/min, 800/day, indicators included | Grow $79, Pro $229, Ultra $999 per month. The same page's comparison table says "from $29 / $99 / $329"; the discrepancy is unexplained. | Plain formulas. History depth not stated. | Data for "personal, internal, and non-commercial purposes". Basic is "internal non-display usage", so display on a public site is **not** covered. | Not applicable | Yes. Official MCP server |
| **EODHD** ([pricing](https://eodhd.com/pricing)) | Technical Indicator API | Free: 20 calls/day, 1 year of end-of-day data, **no** indicators | Indicators only in $29.99/mo (EOD+Intraday Extended) or $99.99/mo (All-in-one). End-of-day history 30+ years. | Plain formulas | Not reviewed | Not applicable | Yes. MCP server "included" on all plans |
| **Tiingo** ([pricing](https://www.tiingo.com/about/pricing)) | Clean end-of-day prices only, no signals | $0: 50 requests/hour, 1,000/day, 500 symbols/month, 30+ years | Power $30/mo; Business (commercial) $50/mo | Good price source for backtests | "Internal use only… you may not display or share the data" | Not applicable | Yes |
| **Benzinga** ([option-activity docs](https://docs.benzinga.com/api-reference/calendar-api/get-optionactivity.md)) | Analyst ratings. Unusual options activity: sentiment, sweep/block/large/unusual type, cost basis, size, open interest, volume. | None found | Quoted by sales, not public. Some Benzinga data also comes through Massive. | A `date_from`/`date_to` query exists; history depth is not stated | Not reviewed | No independent test of this feed found | Yes (`token`) |
| **Danelfin** | AI Score 1–10, with technical, fundamental and sentiment sub-scores | — | **Reported** by a competitor's summary ([Pineify](https://pineify.app/danelfin/danelfin-pricing)): API Basic $52/mo (2,500 calls/mo), Expert $149/mo, Max $449/mo. Danelfin's own site refused automated access (HTTP 403), so this is unconfirmed. | **Reported:** historical AI Scores since 2017 through the API (JSON), so backtestable on a paid tier | Not reviewed | Vendor backtests only. See the robo-analyst study below for the closest independent evidence. | Yes |
| **Kavout** ([API tutorial](https://www.kavout.com/api-tutorial)) | K Score plus momentum, growth, quality and value scores | — | "Available exclusively to subscribers"; price not shown | A `trade_date` parameter returns past dates; a "CSV download button" exports the full history; 10,000 rows per request | Not reviewed | Vendor only | Yes |
| **Tickeron / TrendSpider / Trade Ideas** | AI pattern "robots" / auto-trendlines with an in-app backtester / Holly AI day-trade ideas | — | Subscriptions | **No public API for exporting historical signals found** (search-level check only) | — | Vendor claims only | — |
| **Zacks** | Zacks Rank 1–5, built on earnings-estimate revisions | Current rank on the website | **Reported:** history through Zacks Professional Services and WRDS (institutional, paid) ([Zacks historical](https://www.zackspro.com/historical.asp), [WRDS](https://wrds-www.wharton.upenn.edu/pages/about/data-vendors/zacks/)) | Paid only | — | The underlying factor (estimate revisions) has academic support, and the project's own learnings agree. Zacks' own Rank return figures are vendor claims. | — |
| **TipRanks** | Smart Score; analyst, insider and blogger aggregates | — | **Reported:** enterprise feeds, including through Nasdaq; price on request | Paid only | — | Vendor only | — |
| **Barchart** ([OnDemand](https://www.barchart.com/solutions/services/ondemand)) | "Barchart Opinion": 13 indicators turned into a % buy/sell | Website only | OnDemand APIs, quote-based (not verified) | No free history | — | None found | — |
| **StockCharts SCTR, Investing.com technical summary** | Relative-strength rank; indicator vote | Website only | — | No API and no history | Site terms restrict automated collection (not re-verified) | None | — |
| **TradingView Technical Ratings** ([method](https://www.tradingview.com/support/solutions/43000614331-technical-ratings/), [terms](https://www.tradingview.com/policies/)) | A vote across 15 moving averages (SMA/EMA 10–200, Hull 9, VWMA 20, Ichimoku) and 11 oscillators (RSI, Stochastic, CCI, ADX, AO, Momentum, MACD, Stoch RSI, Williams %R, Bull Bear Power, Ultimate Oscillator). Each scores −1, 0 or +1. Overall = mean of the two group means. Strong Buy > 0.5, Buy 0.1 to 0.5, Neutral −0.1 to 0.1, Sell −0.5 to −0.1, Strong Sell < −0.5. | Website | — | **No official data API.** Unofficial libraries (`tradingview_ta`, `tradingview-screener`) give only today's value. **The legitimate route to history is to recompute the rating from our own OHLCV using the published formula above.** | Terms: data "licensed for exclusive display-only use". They prohibit "any machine-driven processes that do not involve the direct, human-readable display of such data" and third-party tools that enable this. Scraping for a nightly engine therefore breaks the terms. | None independent. Its parts (RSI, MACD, MAs) were each weak in this project's tests. | No (if recomputed locally) |
| **Finance MCP servers** | Wrappers around the APIs above: Alpha Vantage (official), Massive (official, MIT), Twelve Data (official), EODHD (official), [Financial Datasets](https://github.com/financial-datasets/mcp-server) (prices, statements, news; MIT), yfinance MCPs such as [narumiruna/yfinance-mcp](https://enterprisedna.co/directories/mcp/narumiruna-yfinance-mcp) (unofficial Yahoo), [atilaahmettaner/tradingview-mcp](https://github.com/atilaahmettaner/tradingview-mcp) (MIT, about 5k stars, uses unofficial TradingView libraries, current snapshot only). Finnhub, FMP and Alpaca MCPs were not verified. | — | — | **An MCP server adds no new data and no new history.** It runs inside a Claude session, not in a GitHub Actions job. For nightly jobs, call the REST API directly. | Same as the underlying API. The TradingView and Yahoo wrappers carry terms risk. | — | Mostly yes |

**Closest independent evidence on "AI/robo ratings"**
- Coleman, Merkley & Pacelli studied 7 robo-analyst firms: 134,781 reports on 1,002 stocks, 2003–2018 ([CXO summary](https://www.cxoadvisory.com/investing-expertise/robo-vs-traditional-analyst-stock-recommendations); published in *The Accounting Review* as "Human Versus Machine…", [listing](https://academicnewsletter.sufe.edu.cn/info/415020); journal details not re-verified).
- Buy-recommendation portfolios earned a **gross** annualized 3-factor alpha of **6.9%** (5-factor 6.4%), against 1.2% (1.7%) for human analysts.
- Sell recommendations earned about **0** for both groups.
- Limits: these numbers come from the 2020 working-paper version, they are before trading costs, and the portfolios were rebalanced daily.
- This is weak support for the general idea of machine ratings. It is not evidence that Danelfin, Kavout or Tickeron work, and it says nothing about timing tops.

---

## 2. Table: daily or weekly proxies for institutional and quant positioning

| Source | What it measures | Frequency and publication lag | History start | Free? | How to download (verified today?) | Published evidence for timing bottoms/tops | Notes |
|---|---|---|---|---|---|---|---|
| **SqueezeMetrics DIX and GEX** | DIX: dark-pool short-volume share across S&P 500 stocks. GEX: estimated dealer gamma exposure on S&P 500 options (in dollars). | Daily, after the close | **2011-05-02** | Free, no key | **Verified:** `https://squeezemetrics.com/monitor/static/DIX.csv`, columns `date,price,dix,gex`, 3,884 rows up to **2026-10-09** | **Vendor:** white papers claim high DIX is bullish and low GEX means higher volatility. **Peer-reviewed support for the gamma mechanism** (not for the DIX direction): Baltussen, Da, Lammers & Martens (*J. Financial Economics* 2021) found intraday momentum "much more pronounced" on negative-gamma days and not significant on positive-gamma days, with a "reverts over the next few days" pattern and hypothetical Sharpe ratios of 0.87–1.73 for the intraday strategy ([summary](https://alphaarchitect.com/hot-topic-does-gamma-hedging-actually-affect-stock-prices/)). Ni, Pearson, Poteshman & White (*Review of Financial Studies* 2021, 34(4)) is on option market-maker hedging and stock volatility ([IDEAS](https://ideas.repec.org/a/oup/rfinst/v34y2021i4p1952-1986..html); finding not re-verified). **DIX: no independent test found.** This project's f1 test at the single-stock level points the *opposite* way from DIX's story, in line with Wang, Yan & Zheng (JFE 2020). | Black-box method, S&P 500 only, could be discontinued, display terms unknown. Best use: a **volatility-state** filter for SPY/QQQ, not a direction call. |
| **CTA trend-follower positioning** (Commodity Trading Advisor) | Estimated net exposure of trend funds to equity-index futures | Daily (estimated) | As far back as futures prices go | No free bank series (Goldman Sachs, Nomura and UBS are client-only), but the method is reproducible | **Method:** Kestner (2020), "Replicating CTA Positioning: An Improved Method", as summarized by [Macrosynergy](https://macrosynergy.com/?p=42643): 16 liquid futures; signal = average weekly return over the lookback, divided by realized volatility, times the square root of the number of weeks; capped at 1.0; 90-day volatility; best single lookback about 32 weeks; ensemble of 16, 32 and 52 weeks. It reported **R² > 75%** against the SG Trend Index. Calibration targets: the SG Trend Index (access terms not checked), or daily returns of the trend ETFs DBMF (since 2019) and KMLM (since 2020) from free price data (inception dates not re-verified). | **No evidence found that the estimated positioning predicts index returns.** The Macrosynergy piece uses it to estimate flows and trigger levels and does not test prediction. | Useful as a calibration check for the existing `cta_trend.py`: does it reach R² ≥ 0.7 against DBMF or SG Trend? |
| **Vol-control and risk-parity funds** | Equity exposure ≈ min(cap, target vol ÷ realized vol), rebalanced with a lag | Daily (estimated) | Any period with price data | Reproducible, no public data | No positioning data exists. The mechanism is described by industry, e.g. [Milliman](https://milliman.com/-/media/milliman/importedfiles/ektron/vol_control_funds.ashx) (not re-read). | No peer-reviewed short-term **timing** evidence found. Harvey et al. (2018, *Journal of Portfolio Management*) cover volatility targeting's effect on Sharpe ratio and tails, not flow timing ([Quantpedia summary](https://quantpedia.com/the-impact-of-volatility-targeting-on-equities-bonds-commodities-and-currencies); not re-read). | Already covered by RVPOS. Project learning: forced selling happens at the index level only. |
| **Dealer gamma per stock** | Gamma and delta per contract, from which net GEX per stock can be computed | Snapshot (15-min delayed) | **None. Today only.** | Free, no key | **Verified:** `https://cdn.cboe.com/api/global/delayed_quotes/options/NVDA.json` (redirects to cdn-api.cboe.com) returned 4,234 NVDA contracts with `delta, gamma, iv, open_interest, volume`. | Same mechanism evidence as GEX | History must be **archived nightly from now on**. Paid history: Massive Options Developer $79/mo (4 years). Cboe terms not checked. |
| **Cboe put/call ratios** | Total, equity, index, SPX and VIX put/call volume and ratios | Daily, after the close | **2006-11-01** (total, equity, index); SPX from 2010-07-06 | Free, no key | **Verified.** (a) Old CSVs `https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/{totalpc,equitypc,indexpc,spxpc}.csv` run to **2019-10-04**. (b) Daily JSON `https://cdn.cboe.com/data/us/options/market_statistics/daily/YYYY-MM-DD_daily_options` works from **2019-10-07** to today (tested 2019-10-07, 2020-03-16, 2022-06-16, 2026-10-09). Together they give a continuous series from 2006. | **Peer-reviewed:** Simon & Wiggins (*J. Futures Markets* 2001; Jan 1989 to Jun 1999) found the volatility index, put/call ratio and TRIN work as **contrarian** signals, statistically and economically significant for S&P futures returns over **10, 20 and 30 trading days**, with better out-of-sample trading results ([IDEAS](https://ideas.repec.org/a/wly/jfutmk/v21y2001i5p447-462.html)). Pan & Poteshman (RFS 2006) found strong next-week predictability, but only with non-public "open-buy" data. | Old sample, so it needs a fresh out-of-sample test. Cboe-only volume, whose market share drifts over time, so use rolling z-scores. The file header says the data is "compiled for the convenience of site visitors and is furnished without responsibility…" |
| **OCC options volume per stock** | Daily options volume per underlying, split by **customer (C), firm (F) and market maker (M)** and by put/call, per exchange | Daily, next day | **Only the last 2 years** (the server says "Report date cannot be prior to 2 years") | Free, no key | **Verified:** `https://marketdata.theocc.com/volume-query?reportDate=YYYYMMDD&format=csv&volumeQueryType=O&symbolType=U&symbol=NVDA&reportType=D&accountType=ALL&productKind=ALL&porc=BOTH` | Johnson & So (JFE 2012): a high option-to-stock volume ratio predicts weaker returns. Pan & Poteshman (2006): see above. Customer-only put/call per stock is untested here. | About 500 trading days available now, so statistical power is low. **Start archiving nightly** so the history grows. Paid unusual-activity history: Benzinga, Massive Options. |
| **Dark-pool volume (FINRA ATS weekly)** | Weekly shares and trades per symbol for ATS (dark pools) and non-ATS OTC, also by firm | Weekly. Published about 3 weeks after week start (week of 2026-09-14 was updated 2026-10-05). | API: 2022-01 onward; earlier weeks in a separate historic dataset | Free, no key | **Verified:** POST `https://api.finra.org/data/group/otcMarket/name/weeklySummary` with EQUAL filters on `issueSymbolIdentifier`, `weekStartDate` and `tierIdentifier` (returned data for 2022-01-03 through 2026-09-14). Weeks before 2022 are in `weeklySummaryHistoric`, queryable only by week, tier or month. | No peer-reviewed short-term timing evidence found. The related daily short-volume test (f1) was weak at 2 weeks. | Low priority. Use `lastUpdateDate` as the "known on" date. |
| **ETF daily flows** | Creations and redemptions = Δshares outstanding × NAV | Daily (about a 1-day reporting lag) | SPY: about **2003** (≈5,900 daily rows) | Free from issuers, no key | **Verified:** SSGA `https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/navhist-us-en-spy.xlsx` has columns Date, NAV, Shares Outstanding, Total Net Assets, up to **2026-10-08**. The same pattern probably works for XLK and other SPDRs (not verified). iShares and Invesco (QQQ) files were not verified. ETF.com and ETFdb offer no free bulk history. | **Peer-reviewed:** Brown, Davies & Ringgenberg (*Review of Finance* 2021, 25(4):937–972; [IDEAS](https://ideas.repec.org/a/oup/revfin/v25y2021i4p937-972..html)), about 1,200 ETFs, 2007–2015. Going long the most-redeemed quintile and short the most-created earned a **gross annualized 4-factor alpha of 5–13%**. The >1% abnormal return of high-inflow ETFs "completely reverses by t+6" ([CXO summary of the 2016 draft](https://cxoadvisory.com/equity-premium/predictable-etf-driven-price-distortions)). | Evidence is across ETFs, before costs, at weekly-to-monthly horizons. A time-series use on SPY/QQQ is untested. SSGA file: "may not be reproduced… or disclosed to third parties without SSGA's express written consent", so use internally and publish derived marks only. |
| **13F holdings** | Quarterly long holdings of large managers | Quarterly; up to 45 days after quarter end | 2013 (structured data sets) | Free (SEC EDGAR) | SEC "Form 13F data sets" (URL not re-checked) | Too slow for daily timing | Not recommended for marks |
| **Insider Form 4** | Insider buys and sells | Within 2 business days of the trade | 2006 (SEC structured sets) | Free (SEC EDGAR) | SEC insider transaction data sets (URL not re-checked). Finnhub's free tier also has `/stock/insider-transactions` and `/stock/insider-sentiment`. | Already tested here (t6): no stable edge | — |
| **CFTC Traders in Financial Futures (TFF)** | Long and short positions of dealers, asset managers and leveraged funds (hedge funds and CTAs) in **E-mini S&P 500 (code 13874A)** and **Nasdaq Mini (209742)** | Weekly: Tuesday positions, released Friday | **2006-06-13** | Free, no key (an app token is optional) | **Verified:** `https://publicreporting.cftc.gov/resource/gpe5-46if.json?$where=cftc_contract_market_code='13874A'`, latest **2026-10-06** | No strong evidence found. The literature on Commitments of Traders as a timing signal is mixed (not re-verified). | Weekly, so use it as background regime, or as a check on the CTA replication (leveraged-fund net vs the modelled CTA exposure). US government data, so no licensing issue. |
| **NAAIM Exposure Index** | Average equity exposure of active managers (−200 to +200) | Weekly | July 2006 | Free on naaim.org | Page fetched, but the download link loads dynamically and was **not confirmed** | **Reported:** [Portfolio Optimizer blog](https://portfoliooptimizer.io/blog/the-naaim-aaii-equities-allocation-spread-another-smart-money-relative-sentiment-indicator/), July 2006 to June 2026: a NAAIM-vs-AAII spread strategy had Sharpe 1.03 vs 0.78 for SPY, with no significance test. The author warns about "heavy data torturing". | Weak evidence. Low priority. |
| **AAII Sentiment Survey** | Individual investors' bull/bear percentages | Weekly (Thursday) | July 1987 | **Full history is members-only** (Sentiment Investing $198/yr) ([AAII](https://www.aaii.com/o/sentimentsurvey)) | `sentiment.xls` returned HTTP 403 | Fisher & Statman (*Financial Analysts Journal* 2000, [DOI 10.2469/faj.v56.n2.2340](https://rpc.cfainstitute.org/research/financial-analysts-journal/2000/investor-sentiment-and-stock-returns)) found a negative (contrarian) link to future returns, significant for individual investors and strategists. Brown & Cliff (*J. Empirical Finance* 2004) found little *near-term* predictive power (not re-verified). | Paid, and the evidence is mixed |
| **CNN Fear & Greed** | Composite of 7 market indicators | Daily | A few years via an unofficial endpoint | No official API | **Verified blocked:** the unofficial JSON endpoint returned HTTP 418, "You're a bot" | No independent study found | Do not scrape. If wanted, rebuild its parts from free data (SPX vs 125-day MA, put/call, VIX vs 50-day MA, junk-bond spread, stocks vs bonds over 20 days). |

---

## 3. Top 5 worth testing now

Restricted to sources that are free and that allow downloading daily (or long weekly) history. Each test is written in the project's own format: pre-register first, enter at the t+1 open, use block bootstrap, and report win rate and average per trade together.

1. **SqueezeMetrics GEX, with DIX second** (daily since 2011, about 15 years, verified live).
   - **Why:** this is the only free, long, daily series for dealer options hedging.
   - **Test 1:** when GEX is in its bottom quintile (or below 0), are SPY/QQQ absolute 5–10-day moves and the chance of a ≥5% drawdown higher? This is a volatility-state check.
   - **Test 2:** do the existing bottom marks (△2 double-bottom, IVTS>1) work better when GEX is negative and turning up?
   - **Test 3:** does DIX in its top decile lead to better 20-day SPY returns? This repeats the vendor's claim out of sample.
   - **Known:** gamma affects intraday momentum and volatility (peer-reviewed). **Untested:** any multi-day direction effect.
2. **Cboe put/call ratios** (daily since 2006: CSV plus daily JSON, verified).
   - **Why:** a classic contrarian fear gauge with peer-reviewed support at 10–30 days, though from 1989–1999.
   - **Test:** equity put/call 5-day or 10-day average as a z-score against the past year. Do extreme highs confirm SPY/QQQ bottoms over the next 10–20 days, beyond what the VIX layer already gives?
3. **ETF creations and redemptions from issuer files** (SPY since about 2003, verified; XLK and other SPDRs probably the same format).
   - **Test:** SPY (and XLK) 5-day flow as a percentage of assets, as a z-score. Do big outflows come before rebounds and big inflows before weak 10–20-day returns, as the reversal finding suggests?
   - **Known:** reversal across ETFs (peer-reviewed, before costs). **Untested:** the same effect in time series for a single ETF.
4. **CFTC Traders in Financial Futures for E-mini S&P 500 and Nasdaq Mini** (weekly since 2006, verified, no key).
   - **Use 1:** a weekly regime layer, e.g. leveraged-fund net short beyond its 3-year range, tested for 4–8-week QQQ returns.
   - **Use 2:** an independent check on the CTA model. Does modelled CTA exposure move with leveraged-fund net positions?
   - Note: this is weekly, not daily. Align it to the Friday release.
5. **OCC per-stock options volume by account type, plus a nightly Cboe chain snapshot.**
   - The OCC history is only 2 years, so **start archiving now**.
   - **Test:** customer-only put/call and option-to-stock volume per stock for the ~100 tech names (the Johnson & So direction), at 1–2-week horizons.
   - The nightly Cboe snapshot builds per-stock gamma history for NVDA and the other large names going forward.
   - Low statistical power today. Re-test once 3 or more years have been collected.

**Cheap extra:** recompute the TradingView Technical Rating locally from our own OHLCV (formula above). It costs an afternoon and answers "do TradingView ratings work?". The expected value is low, because its parts were each weak in this project's tests.

**Not worth time now:**
- Finnhub pattern and support/resistance endpoints: premium, snapshot only.
- Paid indicator APIs: the same formulas as the local engine.
- TradingView or Investing.com scraping: against their terms.
- CNN Fear & Greed: blocked.
- AAII: paid.
- 13F: too slow.
- Form 4: already tested.
- FINRA dark-pool weekly: weak link to timing.

---

## 4. API keys and display rights

**No key needed** (all verified today):
- SqueezeMetrics CSV
- Cboe CSV, daily JSON and delayed option chains
- OCC volume query
- FINRA Query API public datasets
- CFTC Socrata API (an app token is optional)
- SSGA NAV-history files
- SEC EDGAR

**SEC note:** EDGAR's fair-access policy asks for a User-Agent naming the requester and a contact address. If the owner adds EDGAR jobs, he should keep that User-Agent string in a GitHub Secret too, so his contact address is not committed to the public repo.

**Key required, and the owner must create it himself:**
- Alpha Vantage, Massive, Finnhub, Twelve Data, FMP, EODHD and Tiingo
- Danelfin, Kavout, Benzinga, Financial Datasets, Barchart and TipRanks
- Rules for any of these keys:
  - Store it only as a **GitHub Actions Secret** (e.g. `MASSIVE_API_KEY`) and read it from the environment in the nightly Python job.
  - Never put it in code, HTML or JS, Markdown, gists or URLs.
  - The dashboard is a **public static GitHub Pages site**, so the browser must never call a keyed API. A key in JS is visible to everyone.
  - The nightly job fetches the data and publishes only derived marks.

**Rights to show data on a public site:** several free tiers forbid public display.
- Tiingo: "internal use only".
- Twelve Data Basic: "internal non-display".
- FMP: display needs a license agreement.
- TradingView: display-only on its own site, and machine processing is banned.
- SSGA files: "may not be… disclosed to third parties".
- SqueezeMetrics and Cboe: terms not checked.
- Safe default: keep raw vendor series inside the private pipeline and publish only our own derived signals (marks, states, z-score bands), not the raw data.

**"Known on" dates for backtests:**
- CFTC: Tuesday positions released Friday afternoon (Eastern time), so usable from Monday.
- FINRA ATS: use `lastUpdateDate`, about 3 weeks after week start.
- OCC and Cboe daily statistics: next trading day.
- DIX/GEX: release time unknown, so use the t+1 open.
- ETF shares outstanding: often reflect the previous day's creations, so test with a 1-day lag.

---

## Sources

**Tools and APIs**
- [Finnhub API spec (swagger.json)](https://finnhub.io/static/swagger.json)
- [Alpha Vantage documentation](https://www.alphavantage.co/documentation/)
- [Alpha Vantage premium](https://www.alphavantage.co/premium/)
- [Alpha Vantage MCP](https://mcp.alphavantage.co/)
- [Massive pricing](https://massive.com/pricing)
- [Massive options](https://massive.com/options)
- [massive-com/mcp_massive](https://github.com/massive-com/mcp_massive)
- [FMP pricing](https://site.financialmodelingprep.com/developer/docs/pricing)
- [Twelve Data pricing](https://twelvedata.com/pricing)
- [Twelve Data MCP server](https://twelvedata.com/docs/llms/ai/mcp-server.md)
- [EODHD pricing](https://eodhd.com/pricing)
- [Tiingo pricing](https://www.tiingo.com/about/pricing)
- [Benzinga option activity API](https://docs.benzinga.com/api-reference/calendar-api/get-optionactivity.md)
- [Pineify: Danelfin pricing (competitor summary)](https://pineify.app/danelfin/danelfin-pricing)
- [Kavout API tutorial](https://www.kavout.com/api-tutorial)
- [Zacks historical data](https://www.zackspro.com/historical.asp)
- [WRDS: Zacks](https://wrds-www.wharton.upenn.edu/pages/about/data-vendors/zacks/)
- [Barchart OnDemand](https://www.barchart.com/solutions/services/ondemand)
- [TradingView Technical Ratings](https://www.tradingview.com/support/solutions/43000614331-technical-ratings/)
- [TradingView Terms of Use](https://www.tradingview.com/policies/)
- [atilaahmettaner/tradingview-mcp](https://github.com/atilaahmettaner/tradingview-mcp)
- [financial-datasets/mcp-server](https://github.com/financial-datasets/mcp-server)
- [narumiruna yfinance MCP listing](https://enterprisedna.co/directories/mcp/narumiruna-yfinance-mcp)

**Data sources**
- [SqueezeMetrics DIX/GEX CSV](https://squeezemetrics.com/monitor/static/DIX.csv)
- [Cboe total put/call CSV](https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/totalpc.csv)
- [Cboe daily market statistics JSON (example date)](https://cdn.cboe.com/data/us/options/market_statistics/daily/2026-10-09_daily_options)
- [Cboe delayed option chain (NVDA)](https://cdn.cboe.com/api/global/delayed_quotes/options/NVDA.json)
- [OCC volume query (example)](https://marketdata.theocc.com/volume-query?reportDate=20251013&format=csv&volumeQueryType=O&symbolType=U&symbol=NVDA&reportType=D&accountType=ALL&productKind=ALL&porc=BOTH)
- [FINRA API: OTC weekly summary](https://api.finra.org/data/group/otcMarket/name/weeklySummary)
- [CFTC Traders in Financial Futures API](https://publicreporting.cftc.gov/resource/gpe5-46if.json)
- [SSGA SPY NAV history](https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/navhist-us-en-spy.xlsx)
- [AAII Sentiment Survey](https://www.aaii.com/o/sentimentsurvey)
- [NAAIM Exposure Index](https://naaim.org/programs/naaim-exposure-index/)

**Evidence**
- [CXO: robo vs traditional analysts (Coleman, Merkley, Pacelli)](https://www.cxoadvisory.com/investing-expertise/robo-vs-traditional-analyst-stock-recommendations)
- [Human Versus Machine (journal listing)](https://academicnewsletter.sufe.edu.cn/info/415020)
- [Alpha Architect: does gamma hedging affect prices (Baltussen et al.)](https://alphaarchitect.com/hot-topic-does-gamma-hedging-actually-affect-stock-prices/)
- [Ni, Pearson, Poteshman, White, RFS 2021 (IDEAS)](https://ideas.repec.org/a/oup/rfinst/v34y2021i4p1952-1986..html)
- [Simon & Wiggins 2001 (IDEAS)](https://ideas.repec.org/a/wly/jfutmk/v21y2001i5p447-462.html)
- [Brown, Davies, Ringgenberg, Review of Finance 2021 (IDEAS)](https://ideas.repec.org/a/oup/revfin/v25y2021i4p937-972..html)
- [CXO: predictable ETF-driven price distortions](https://cxoadvisory.com/equity-premium/predictable-etf-driven-price-distortions)
- [Macrosynergy: Estimating the positioning of trend followers](https://macrosynergy.com/?p=42643)
- [Milliman: vol control funds](https://milliman.com/-/media/milliman/importedfiles/ektron/vol_control_funds.ashx)
- [Quantpedia: impact of volatility targeting](https://quantpedia.com/the-impact-of-volatility-targeting-on-equities-bonds-commodities-and-currencies)
- [Portfolio Optimizer: NAAIM–AAII spread](https://portfoliooptimizer.io/blog/the-naaim-aaii-equities-allocation-spread-another-smart-money-relative-sentiment-indicator/)
- [Fisher & Statman 2000, FAJ](https://rpc.cfainstitute.org/research/financial-analysts-journal/2000/investor-sentiment-and-stock-returns)
