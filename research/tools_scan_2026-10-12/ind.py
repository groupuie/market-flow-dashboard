"""Reference implementations used in research_tools_A.md (daily OHLCV, causal / non-repainting).
All functions only use data up to and including bar t."""
import numpy as np
import pandas as pd


# ---------- shared helpers (TradingView conventions) ----------
def rma(x, n):                      # Wilder smoothing = ta.rma (used by ta.rsi, ta.atr)
    return x.ewm(alpha=1.0 / n, adjust=False).mean()


def ema(x, n):                      # ta.ema
    return x.ewm(span=n, adjust=False).mean()


def sd_pop(x, n):                   # ta.stdev default (biased=True) = population SD
    return x.rolling(n).std(ddof=0)


def rsi(x, n):
    d = x.diff()
    up, dn = rma(d.clip(lower=0), n), rma((-d).clip(lower=0), n)
    out = 100 - 100 / (1 + up / dn)
    return out.where(dn != 0, 100.0).where(d.notna().cumsum() > 0)


def true_range(h, l, c):
    pc = c.shift(1)
    return pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)


def atr(h, l, c, n):
    return rma(true_range(h, l, c), n)


def confirm_bottom(sig, h, c):      # existing house rule: signal at t, act at t+1 if C[t+1] > H[t]
    return sig.shift(1, fill_value=False) & (c > h.shift(1))


def confirm_top(sig, l, c):         # signal at t, act at t+1 if C[t+1] < L[t]
    return sig.shift(1, fill_value=False) & (c < l.shift(1))


# ---------- B1 IBS / multi-day IBS (= Williams %R family) ----------
def ibs(h, l, c):
    rng = h - l
    return ((c - l) / rng).where(rng > 0, 0.5)


def williams_r(h, l, c, n):
    hh, ll = h.rolling(n).max(), l.rolling(n).min()
    return -100 * (hh - c) / (hh - ll)


# ---------- B2 N-day closing low (Double 7s) ----------
def double7(c, n=7, trend=200):
    entry = (c > c.rolling(trend).mean()) & (c <= c.rolling(n).min())
    exit_ = c >= c.rolling(n).max()
    return entry, exit_


# ---------- B4 ConnorsRSI ----------
def updown_streak(c):
    v = c.to_numpy()
    s = np.zeros(len(v))
    for i in range(1, len(v)):
        if v[i] > v[i - 1]:
            s[i] = s[i - 1] + 1 if s[i - 1] > 0 else 1
        elif v[i] < v[i - 1]:
            s[i] = s[i - 1] - 1 if s[i - 1] < 0 else -1
        else:
            s[i] = 0
    return pd.Series(s, index=c.index)


def percent_rank(x, n=100):         # % of the previous n values strictly below today's value
    return x.rolling(n + 1).apply(lambda w: (w[:-1] < w[-1]).mean() * 100, raw=True)


def connors_rsi(c, n_rsi=3, n_streak=2, n_rank=100):
    return (rsi(c, n_rsi) + rsi(updown_streak(c), n_streak) + percent_rank(c.pct_change(), n_rank)) / 3


# ---------- B5 Williams VIX Fix (CM_Williams_Vix_Fix defaults) ----------
def vix_fix(h, l, c, pd_=22, bbl=20, mult=2.0, lb=50, ph=0.85):
    hc = c.rolling(pd_).max()
    wvf = (hc - l) / hc * 100
    upper = wvf.rolling(bbl).mean() + mult * sd_pop(wvf, bbl)
    range_high = wvf.rolling(lb).max() * ph
    spike = (wvf >= upper) | (wvf >= range_high)
    trigger = spike.shift(1, fill_value=False) & ~spike      # first bar after the spike ends
    return wvf, spike, trigger


# ---------- B6 VIX / VXN stress (needs ^VIX or ^VXN daily close) ----------
def vix_stress(vix):
    bb = vix > vix.rolling(20).mean() + 2 * sd_pop(vix, 20)
    stretch = (vix >= 1.05 * vix.rolling(10).mean()).astype(int).rolling(3).sum() == 3
    return bb, stretch, vix > 20


# ---------- B7 universe breadth capitulation (panel of closes: dates x tickers) ----------
def breadth_oversold(closes):
    r2 = closes.apply(lambda s: rsi(s, 2))
    lower = closes.rolling(20).mean() - 2 * closes.rolling(20).std(ddof=0)
    os_ = (r2 < 10) | (closes < lower)
    return os_.sum(axis=1) / closes.notna().sum(axis=1)


# ---------- B8 oscillator slot ----------
def wavetrend(h, l, c, n1=10, n2=21):
    ap = (h + l + c) / 3
    esa = ema(ap, n1)
    d = ema((ap - esa).abs(), n1)
    ci = (ap - esa) / (0.015 * d)
    wt1 = ema(ci, n2)
    wt2 = wt1.rolling(4).mean()
    return wt1, wt2


def fisher(h, l, n=10):
    hl2 = (h + l) / 2
    mx, mn = hl2.rolling(n).max(), hl2.rolling(n).min()
    raw = ((hl2 - mn) / (mx - mn).replace(0, np.nan) - 0.5).to_numpy()
    v = np.zeros(len(raw))
    f = np.full(len(raw), np.nan)
    fprev = 0.0
    for i in range(len(raw)):
        if np.isnan(raw[i]):
            continue
        vi = 0.66 * raw[i] + 0.67 * (v[i - 1] if i else 0.0)
        vi = 0.999 if vi > 0.99 else (-0.999 if vi < -0.99 else vi)
        v[i] = vi
        fprev = 0.5 * np.log((1 + vi) / (1 - vi)) + 0.5 * fprev
        f[i] = fprev
    fish = pd.Series(f, index=h.index)
    return fish, fish.shift(1)


def laguerre_rsi(c, g=0.5):
    x = c.to_numpy()
    out = np.full(len(x), np.nan)
    l0 = l1 = l2 = l3 = x[0]
    for i in range(len(x)):
        p0, p1, p2, p3 = l0, l1, l2, l3
        l0 = (1 - g) * x[i] + g * p0
        l1 = -g * l0 + p0 + g * p1
        l2 = -g * l1 + p1 + g * p2
        l3 = -g * l2 + p2 + g * p3
        cu = max(l0 - l1, 0) + max(l1 - l2, 0) + max(l2 - l3, 0)
        cd = max(l1 - l0, 0) + max(l2 - l1, 0) + max(l3 - l2, 0)
        out[i] = cu / (cu + cd) if (cu + cd) > 0 else np.nan
    return pd.Series(out, index=c.index)


# ---------- T2 Chandelier ----------
def chandelier_long(h, l, c, n=22, k=3.0):
    return h.rolling(n).max() - k * atr(h, l, c, n)


# ---------- T3 SuperTrend / UT Bot ----------
def supertrend(h, l, c, n=10, k=3.0):
    a = atr(h, l, c, n).to_numpy()
    hl2 = ((h + l) / 2).to_numpy()
    cl = c.to_numpy()
    ub, lb = hl2 + k * a, hl2 - k * a
    fub, flb = ub.copy(), lb.copy()
    d = np.ones(len(cl))                     # +1 up-trend, -1 down-trend
    for i in range(1, len(cl)):
        if np.isnan(a[i - 1]):
            continue
        flb[i] = lb[i] if (lb[i] > flb[i - 1] or cl[i - 1] < flb[i - 1]) else flb[i - 1]
        fub[i] = ub[i] if (ub[i] < fub[i - 1] or cl[i - 1] > fub[i - 1]) else fub[i - 1]
        if d[i - 1] == -1:
            d[i] = 1 if cl[i] > fub[i] else -1
        else:
            d[i] = -1 if cl[i] < flb[i] else 1
    line = np.where(d == 1, flb, fub)
    return pd.Series(d, index=c.index), pd.Series(line, index=c.index)


def ut_bot(h, l, c, a=1.0, n=10):
    nloss = (a * atr(h, l, c, n)).to_numpy()
    x = c.to_numpy()
    ts = np.full(len(x), np.nan)
    for i in range(1, len(x)):
        if np.isnan(nloss[i]):
            continue
        p = ts[i - 1] if not np.isnan(ts[i - 1]) else x[i - 1]
        if x[i] > p and x[i - 1] > p:
            ts[i] = max(p, x[i] - nloss[i])
        elif x[i] < p and x[i - 1] < p:
            ts[i] = min(p, x[i] + nloss[i])
        elif x[i] > p:
            ts[i] = x[i] - nloss[i]
        else:
            ts[i] = x[i] + nloss[i]
    ts = pd.Series(ts, index=c.index)
    buy = (c > ts) & (c.shift(1) <= ts.shift(1))
    sell = (c < ts) & (c.shift(1) >= ts.shift(1))
    return ts, buy, sell


# ---------- T5 TD Sequential countdown 13 (simplified) ----------
def td_countdown13(h, l, c, side="sell"):
    C, H, L = c.to_numpy(), h.to_numpy(), l.to_numpy()
    n = len(C)
    out = np.zeros(n, bool)
    sell = side == "sell"
    run = opp = 0
    active = False
    cnt = 0
    c8 = np.nan
    tdst = np.nan
    for i in range(4, n):
        up = C[i] > C[i - 4]
        dn = C[i] < C[i - 4]
        run = run + 1 if (up if sell else dn) else 0
        opp = opp + 1 if (dn if sell else up) else 0
        if run == 9:                                   # setup completes -> (re)start countdown
            active, cnt, c8 = True, 0, np.nan
            tdst = L[i - 8:i + 1].min() if sell else H[i - 8:i + 1].max()
        if active and opp == 9:                        # opposite setup cancels
            active = False
        if active and (H[i] < tdst if sell else L[i] > tdst):   # price leaves setup range -> cancel
            active = False
        if active and ((C[i] >= H[i - 2]) if sell else (C[i] <= L[i - 2])):
            if cnt < 12:
                cnt += 1
                if cnt == 8:
                    c8 = C[i]
            elif (H[i] >= c8) if sell else (L[i] <= c8):   # bar-13 qualifier, else deferred
                out[i] = True
                active = False
    return pd.Series(out, index=c.index)


# ---------- T6 Elder Impulse ----------
def elder_impulse(c):
    e13 = ema(c, 13)
    macd = ema(c, 12) - ema(c, 26)
    hist = macd - ema(macd, 9)
    green = (e13 > e13.shift(1)) & (hist > hist.shift(1))
    red = (e13 < e13.shift(1)) & (hist < hist.shift(1))
    return green, red
