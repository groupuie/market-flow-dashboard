# Research library: load Yahoo/COT/DIX data, build stock & market features, targets.
import os, json, numpy as np, pandas as pd
DT = "/tmp/claude-0/-home-claude/d0a676e0-fcd7-5eae-bc26-2609f6d7a033/scratchpad/dt"
YH = os.path.join(DT, "yh")
START = "2004-01-01"

def fn(s): return os.path.join(YH, s.replace("^", "_").replace("=", "_") + ".pkl")

def load(s):
    p = fn(s)
    if not os.path.exists(p): return None
    df = pd.read_pickle(p)
    df = df[df.index >= START]
    f = (df["ac"] / df["c"]).replace([np.inf, -np.inf], np.nan).fillna(1.0)
    out = pd.DataFrame({"o": df["o"] * f, "h": df["h"] * f, "l": df["l"] * f, "c": df["ac"], "v": df["v"]})
    # repair missing/zero o/h/l
    for k in ("o", "h", "l"):
        bad = out[k].isna() | (out[k] <= 0)
        out.loc[bad, k] = out.loc[bad, "c"]
    out["h"] = out[["h", "o", "c"]].max(axis=1); out["l"] = out[["l", "o", "c"]].min(axis=1)
    return out

def calendar():
    spy = load("SPY")
    return spy.index

def meta():
    return json.load(open(os.path.join(DT, "meta.json")))

def universe(kind="equity"):
    m = meta()
    if kind == "equity": return [s for s, v in m.items() if v.get("type") == "EQUITY"]
    return [s for s, v in m.items() if v.get("type") == kind]

def panel(syms, cal):
    O, H, L, C, V = {}, {}, {}, {}, {}
    for s in syms:
        d = load(s)
        if d is None or len(d) < 60: continue
        d = d.reindex(cal)
        O[s], H[s], L[s], C[s], V[s] = d["o"], d["h"], d["l"], d["c"], d["v"]
    return {k: pd.DataFrame(x) for k, x in zip("OHLCV", (O, H, L, C, V))}

def series(s, cal, col="c", ffill=True, limit=5):
    d = load(s)
    if d is None: return pd.Series(np.nan, index=cal)
    x = d[col].reindex(cal.union(d.index)).sort_index()
    if ffill: x = x.ffill(limit=limit)
    return x.reindex(cal)

# ---------------- stock features (wide frames) ----------------
def consec(cond):
    c = cond.astype(int)
    grp = (~cond).cumsum()
    return c.groupby(grp).cumsum() if isinstance(c, pd.Series) else c.apply(lambda col: col.groupby((~cond[col.name]).cumsum()).cumsum())

def rsi(C, n):
    d = C.diff(); g = d.clip(lower=0); l = (-d).clip(lower=0)
    ag = g.ewm(alpha=1 / n, adjust=False, min_periods=n).mean(); al = l.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + ag / al.replace(0, 1e-9))

def stock_features(P, mkt_ret=None):
    O, H, L, C, V = P["O"], P["H"], P["L"], P["C"], P["V"]
    F = {}
    lr = np.log(C).diff()
    F["r1"] = lr
    for n in (2, 3, 5, 10, 20, 60, 120, 250):
        F[f"r{n}"] = np.log(C / C.shift(n))
    sd20 = lr.rolling(20, min_periods=15).std()
    sd60 = lr.rolling(60, min_periods=40).std()
    F["sd20"], F["sd60"] = sd20, sd60
    F["z5"] = F["r5"] / (sd60 * np.sqrt(5)); F["z10"] = F["r10"] / (sd60 * np.sqrt(10)); F["z20"] = F["r20"] / (sd60 * np.sqrt(20))
    F["z1"] = lr / sd60
    tr = pd.concat([(H - L), (H - C.shift()).abs(), (L - C.shift()).abs()]).groupby(level=0).max() if False else np.maximum(H - L, np.maximum((H - C.shift()).abs(), (L - C.shift()).abs()))
    atr = tr.rolling(14, min_periods=10).mean()
    F["atrp"] = atr / C
    for n in (10, 20, 50, 100, 200):
        s = C.rolling(n, min_periods=n).mean()
        F[f"d{n}"] = (C - s) / atr        # distance in ATR units
        F[f"p{n}"] = C / s - 1             # distance in %
    sd = C.rolling(20, min_periods=20).std(); m20 = C.rolling(20, min_periods=20).mean()
    F["pctB"] = (C - (m20 - 2 * sd)) / (4 * sd)
    F["rsi2"], F["rsi14"] = rsi(C, 2), rsi(C, 14)
    F["ibs"] = ((C - L) / (H - L)).where(H > L, 0.5)
    hi252, lo252 = C.rolling(252, min_periods=200).max(), C.rolling(252, min_periods=200).min()
    F["dd252"] = C / hi252 - 1; F["pos252"] = (C - lo252) / (hi252 - lo252)
    hi20, lo20 = H.rolling(20).max(), L.rolling(20).min()
    F["pos20"] = (C - lo20) / (hi20 - lo20)
    F["dd60"] = C / C.rolling(60).max() - 1
    F["up60"] = C / C.rolling(60).min() - 1
    F["volr"] = V / V.rolling(60, min_periods=40).mean()
    F["volr5"] = V.rolling(5).mean() / V.rolling(60, min_periods=40).mean()
    rv20 = sd20 * np.sqrt(252)
    F["rvpos"] = rv20.rolling(505, min_periods=60).rank(pct=True) * 100
    sc = sum(np.sign(C - C.rolling(n, min_periods=n).mean()) for n in (50, 100, 200)) + sum(np.sign(C - C.shift(n)) for n in (63, 126, 252))
    F["sc"] = (sc / 6 * 100).where(C.shift(252).notna())
    up4, dn4 = C > C.shift(4), C < C.shift(4)
    tds = up4.astype(int).apply(lambda c: c.groupby((c == 0).cumsum()).cumsum())
    tdb = dn4.astype(int).apply(lambda c: c.groupby((c == 0).cumsum()).cumsum())
    F["tds"], F["tdb"] = tds.rolling(3).max(), tdb.rolling(3).max()
    dn1 = (C < C.shift(1)).astype(int)
    F["ndown"] = dn1.apply(lambda c: c.groupby((c == 0).cumsum()).cumsum())
    up1 = (C > C.shift(1)).astype(int)
    F["nup"] = up1.apply(lambda c: c.groupby((c == 0).cumsum()).cumsum())
    F["gap"] = np.log(O / C.shift())
    if mkt_ret is not None:
        mr = mkt_ret.reindex(C.index)
        cov = lr.rolling(120, min_periods=80).cov(mr); var = mr.rolling(120, min_periods=80).var()
        beta = cov.div(var, axis=0)
        F["beta"] = beta
        res1 = lr - beta.shift(1).mul(mr, axis=0)
        F["res5"] = res1.rolling(5).sum(); F["res20"] = res1.rolling(20).sum()
        F["zres5"] = F["res5"] / (res1.rolling(60, min_periods=40).std() * np.sqrt(5))
    # existing ◆★ (index.html cockpitRows definitions)
    TOP = (F["sc"] == 100).astype(int) + (F["rvpos"] >= 90).astype(int) + (F["tds"] >= 9).astype(int) + (F["volr5"] >= 1.5).astype(int)
    BOT = (F["tdb"] >= 9).astype(int) + (F["rvpos"] >= 80).astype(int) + ((F["volr"] >= 1.75) & (C < C.shift(5))).astype(int) + (F["sc"] < 66).astype(int)
    F["TOP"], F["BOT"] = TOP.where(F["sc"].notna()), BOT.where(F["sc"].notna())
    return F

def targets(P, hs=(5, 10, 20)):
    O, H, L, C = P["O"], P["H"], P["L"], P["C"]
    O1 = O.shift(-1)
    T = {}
    for h in hs:
        T[f"f{h}"] = np.log(C.shift(-h) / O1)
        lmin = L[::-1].rolling(h, min_periods=h).min()[::-1].shift(-1)
        hmax = H[::-1].rolling(h, min_periods=h).max()[::-1].shift(-1)
        T[f"mae{h}"] = np.log(lmin / O1); T[f"mfe{h}"] = np.log(hmax / O1)
    T["fc10"] = np.log(C.shift(-10) / C)  # close-entry variant
    return T
