# Market / cross-asset / flow-proxy features (daily, aligned to US trading calendar; no lookahead)
import os, numpy as np, pandas as pd
from lib import DT, load, series

def rk(x, n, mp=None):
    return x.rolling(n, min_periods=mp or max(20, n // 3)).rank(pct=True)

def zs(x, n, mp=None):
    m = x.rolling(n, min_periods=mp or n // 2).mean(); s = x.rolling(n, min_periods=mp or n // 2).std()
    return (x - m) / s

def cta_pos(c, lbs=(21, 63, 126, 252), volwin=90, tgt=0.15, cap=2.0):
    """Kestner-style trend-follower position estimate: avg of clipped trend t-stats × vol scaling."""
    lr = np.log(c).diff()
    sd = lr.rolling(volwin, min_periods=60).std()
    sig = []
    for L in lbs:
        t = np.log(c / c.shift(L)) / (sd * np.sqrt(L))
        sig.append(t.clip(-1, 1))
    raw = sum(sig) / len(sig)
    scale = (tgt / (sd * np.sqrt(252))).clip(upper=cap)
    return raw, raw * scale

def volctl(c, tgt=0.10, cap=1.5):
    lr = np.log(c).diff()
    rv21 = lr.rolling(21, min_periods=15).std() * np.sqrt(252)
    rv63 = lr.rolling(63, min_periods=40).std() * np.sqrt(252)
    e = ((tgt / rv21).clip(upper=cap) + (tgt / rv63).clip(upper=cap)) / 2
    return e, rv21, rv63

def market_features(cal, eq_panel=None):
    M = {}
    spx = series("^GSPC", cal); spy = series("SPY", cal); ndx = series("^NDX", cal); sox = series("^SOX", cal)
    qqq = series("QQQ", cal); smh = series("SMH", cal)
    # --- CTA trend positioning estimates ---
    for nm, px in (("spx", spx), ("ndx", ndx), ("sox", sox)):
        raw, vs = cta_pos(px)
        M[f"cta_{nm}"] = vs; M[f"ctaraw_{nm}"] = raw
        M[f"cta_{nm}_chg5"] = vs - vs.shift(5); M[f"cta_{nm}_chg10"] = vs - vs.shift(10)
        M[f"cta_{nm}_pct"] = rk(vs, 756)
        M[f"flip21_{nm}"] = px / px.shift(20) - 1     # % above the price that flips the 1m signal
        M[f"flip63_{nm}"] = px / px.shift(62) - 1
    for nm, s in (("tlt", "TLT"), ("oil", "CL=F"), ("gold", "GC=F"), ("dxy", "DX-Y.NYB")):
        raw, vs = cta_pos(series(s, cal))
        M[f"cta_{nm}"] = vs; M[f"cta_{nm}_chg5"] = vs - vs.shift(5)
    # --- vol-control / risk-parity proxies ---
    e, rv21, rv63 = volctl(spx)
    M["volctl"] = e; M["volctl_chg5"] = e - e.shift(5); M["volctl_chg10"] = e - e.shift(10); M["volctl_pct"] = rk(e, 756)
    M["rv21"], M["rv63"] = rv21, rv63
    lr_spx = np.log(spx).diff(); lr_tlt = np.log(series("TLT", cal)).diff()
    M["sb_corr63"] = lr_spx.rolling(63, min_periods=40).corr(lr_tlt)
    # --- VIX complex ---
    vix = series("^VIX", cal); vix3m = series("^VIX3M", cal); vix9d = series("^VIX9D", cal); vvix = series("^VVIX", cal)
    M["vix"] = vix; M["vix_pct"] = rk(vix, 252); M["vix_ratio"] = vix / vix3m; M["vix9_ratio"] = vix9d / vix
    M["vix_chg5"] = np.log(vix / vix.shift(5)); M["vix_chg1"] = np.log(vix / vix.shift(1))
    M["vix_ma_ratio"] = vix / vix.rolling(20).mean()
    M["vrp"] = vix - rv21 * 100
    M["vvix"] = vvix; M["vvix_pct"] = rk(vvix, 252)
    M["skew"] = series("^SKEW", cal); M["skew_pct"] = rk(M["skew"], 252)
    M["vix_ratio_max5"] = M["vix_ratio"].rolling(5).max()
    M["vix_ratio_max10"] = M["vix_ratio"].rolling(10).max()
    # --- dealer gamma / dark pool (SqueezeMetrics), lag 1 day for safety ---
    dx = pd.read_csv(os.path.join(DT, "dix.csv"), parse_dates=["date"]).set_index("date")
    dx = dx.reindex(cal.union(dx.index)).sort_index().ffill(limit=3).reindex(cal).shift(1)
    M["dix"] = dx["dix"]; M["dix5"] = dx["dix"].rolling(5).mean(); M["dix_pct"] = rk(M["dix5"], 252)
    M["gex"] = dx["gex"]; M["gex_pct"] = rk(dx["gex"], 252); M["gex_neg"] = (dx["gex"] < 0).astype(float).where(dx["gex"].notna())
    # --- credit ---
    hyg = series("HYG", cal); ief = series("IEF", cal); lqd = series("LQD", cal)
    hr = np.log(hyg / ief)
    M["hy_chg5"] = hr - hr.shift(5); M["hy_chg20"] = hr - hr.shift(20); M["hy_dd60"] = hr - hr.rolling(60).max()
    M["hy_z20"] = (hr - hr.shift(20)) / (hr.diff().rolling(250, min_periods=120).std() * np.sqrt(20))
    lr_ = np.log(lqd / ief); M["ig_chg20"] = lr_ - lr_.shift(20)
    # --- rates ---
    tnx = series("^TNX", cal); irx = series("^IRX", cal); fvx = series("^FVX", cal); tyx = series("^TYX", cal); move = series("^MOVE", cal)
    M["tnx"] = tnx; M["tnx_chg5"] = (tnx - tnx.shift(5)) * 100; M["tnx_chg20"] = (tnx - tnx.shift(20)) * 100; M["tnx_chg60"] = (tnx - tnx.shift(60)) * 100
    M["tnx_z20"] = (tnx - tnx.shift(20)) / (tnx.diff().rolling(250, min_periods=120).std() * np.sqrt(20))
    M["curve"] = tnx - irx; M["curve_chg20"] = (M["curve"] - M["curve"].shift(20)) * 100
    M["fvx_chg20"] = (fvx - fvx.shift(20)) * 100
    M["move"] = move; M["move_pct"] = rk(move, 252); M["move_chg20"] = np.log(move / move.shift(20))
    # --- dollar / FX ---
    dxy = series("DX-Y.NYB", cal); jpy = series("JPY=X", cal); krw = series("KRW=X", cal); cny = series("CNY=X", cal)
    M["dxy_chg20"] = np.log(dxy / dxy.shift(20)); M["dxy_chg5"] = np.log(dxy / dxy.shift(5))
    M["dxy_z20"] = M["dxy_chg20"] / (np.log(dxy).diff().rolling(250, min_periods=120).std() * np.sqrt(20))
    M["jpy_chg10"] = np.log(jpy / jpy.shift(10)); M["jpy_chg20"] = np.log(jpy / jpy.shift(20))
    M["jpy_z10"] = M["jpy_chg10"] / (np.log(jpy).diff().rolling(250, min_periods=120).std() * np.sqrt(10))
    M["krw_chg20"] = np.log(krw / krw.shift(20))
    # --- commodities ---
    oil = series("CL=F", cal); brent = series("BZ=F", cal); gold = series("GC=F", cal); silver = series("SI=F", cal); cu = series("HG=F", cal)
    oil = oil.where(oil > 1)  # 2020-04 negative print
    M["oil_chg20"] = np.log(oil / oil.shift(20)); M["oil_chg60"] = np.log(oil / oil.shift(60)); M["oil_chg5"] = np.log(oil / oil.shift(5))
    M["oil_z20"] = M["oil_chg20"] / (np.log(oil).diff().rolling(250, min_periods=120).std() * np.sqrt(20))
    M["oil_pos252"] = (oil - oil.rolling(252).min()) / (oil.rolling(252).max() - oil.rolling(252).min())
    M["gold_chg20"] = np.log(gold / gold.shift(20)); M["gold_chg60"] = np.log(gold / gold.shift(60)); M["gold_chg5"] = np.log(gold / gold.shift(5))
    M["silver_chg20"] = np.log(silver / silver.shift(20)); M["silver_chg5"] = np.log(silver / silver.shift(5))
    M["agau_chg20"] = M["silver_chg20"] - M["gold_chg20"]
    M["cuau_chg20"] = np.log(cu / cu.shift(20)) - M["gold_chg20"]; M["cuau_chg60"] = np.log(cu / cu.shift(60)) - M["gold_chg60"]
    M["auspx_chg20"] = M["gold_chg20"] - np.log(spx / spx.shift(20))
    btc = series("BTC-USD", cal); M["btc_chg20"] = np.log(btc / btc.shift(20))
    # --- index state ---
    for nm, px in (("spx", spx), ("ndx", ndx), ("sox", sox), ("smh", smh)):
        lr = np.log(px).diff()
        M[f"{nm}_r5"] = np.log(px / px.shift(5)); M[f"{nm}_r20"] = np.log(px / px.shift(20)); M[f"{nm}_r60"] = np.log(px / px.shift(60))
        M[f"{nm}_d50"] = px / px.rolling(50).mean() - 1; M[f"{nm}_d200"] = px / px.rolling(200).mean() - 1
        M[f"{nm}_dd"] = px / px.rolling(252, min_periods=60).max() - 1
        M[f"{nm}_z5"] = M[f"{nm}_r5"] / (lr.rolling(60).std() * np.sqrt(5))
    M["rsp_spy20"] = np.log(series("RSP", cal) / series("RSP", cal).shift(20)) - np.log(spy / spy.shift(20))
    hb, lv = series("SPHB", cal), series("SPLV", cal)
    M["hb_lv20"] = np.log(hb / hb.shift(20)) - np.log(lv / lv.shift(20))
    ks = series("^KS11", cal); tw = series("^TWII", cal)
    M["kospi_r20"] = np.log(ks / ks.shift(20)); M["twii_r20"] = np.log(tw / tw.shift(20))
    M["kospi_r5"] = np.log(ks / ks.shift(5))
    # --- breadth from equity panel ---
    if eq_panel is not None:
        C = eq_panel["C"]; n = C.notna().sum(axis=1).where(lambda x: x >= 30)
        for k in (20, 50, 200):
            s = C.rolling(k, min_periods=k).mean()
            M[f"br{k}"] = (C > s).sum(axis=1) / (s.notna() & C.notna()).sum(axis=1).where(lambda x: x >= 30)
        lo20 = C.rolling(20).min(); hi20 = C.rolling(20).max()
        M["br_low20"] = (C <= lo20).sum(axis=1) / n; M["br_high20"] = (C >= hi20).sum(axis=1) / n
        r1 = np.log(C).diff()
        M["br_adv5"] = ((r1 > 0).sum(axis=1) / n).rolling(5).mean()
        M["br_mean_r5"] = np.log(C / C.shift(5)).mean(axis=1)
        M["br_disp20"] = np.log(C / C.shift(20)).std(axis=1)
    # --- seasonality ---
    idx = pd.Series(cal, index=cal)
    mo = idx.dt.month; nxt = idx.shift(-1); prv = idx.shift(1)
    last_day = (nxt.dt.month != mo)
    pos_in_month = idx.groupby([idx.dt.year, mo]).cumcount()
    M["tom"] = (last_day | (pos_in_month <= 2)).astype(float)
    M["month"] = mo.astype(float)
    return pd.DataFrame(M, index=cal)

def cot_features(cal):
    cot = pd.read_pickle(os.path.join(DT, "cot.pkl"))
    out = {}
    def align(s):
        s = s.copy(); s.index = s.index + pd.Timedelta(days=6)   # Tue positions → usable from next Monday
        return s.reindex(cal.union(s.index)).sort_index().ffill(limit=10).reindex(cal)
    eq = None
    for k in ("ES", "NQ"):
        d = cot[k]
        eq = d if eq is None else eq.add(d, fill_value=0)
    def tff(d, nm):
        oi = d["open_interest_all"]
        lev = (d["lev_money_positions_long"] - d["lev_money_positions_short"]) / oi
        am = (d["asset_mgr_positions_long"] - d["asset_mgr_positions_short"]) / oi
        dl = (d["dealer_positions_long_all"] - d["dealer_positions_short_all"]) / oi
        for a, s in (("lev", lev), ("am", am), ("dlr", dl)):
            out[f"cot_{nm}_{a}"] = align(s)
            out[f"cot_{nm}_{a}_z"] = align((s - s.rolling(156, min_periods=52).mean()) / s.rolling(156, min_periods=52).std())
            out[f"cot_{nm}_{a}_chg4"] = align(s - s.shift(4))
    tff(eq, "eq"); tff(cot["VX"], "vx"); tff(cot["ZN"], "zn"); tff(cot["JY"], "jy")
    for k in ("CL", "GC", "SI", "HG"):
        d = cot[k]; oi = d["open_interest_all"]
        mm = (d["m_money_positions_long_all"] - d["m_money_positions_short_all"]) / oi
        out[f"cot_{k.lower()}_mm"] = align(mm)
        out[f"cot_{k.lower()}_mm_z"] = align((mm - mm.rolling(156, min_periods=52).mean()) / mm.rolling(156, min_periods=52).std())
    return pd.DataFrame(out, index=cal)
