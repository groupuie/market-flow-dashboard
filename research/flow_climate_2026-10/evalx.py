import numpy as np, pandas as pd
from lib import DT

PERIODS = {"IS": ("2007-07-01", "2017-12-31"), "OOS": ("2018-01-01", "2026-12-31")}

def load_long():
    L = pd.read_pickle(DT + "/long.pkl")
    return L

def episodes(sig, gap=10):
    """first day of each signal cluster per symbol (signals within `gap` trading days merge)."""
    s = sig[sig].reset_index()[["date", "sym"]]
    if s.empty: return sig & False
    s["di"] = s["date"].map(DATEIDX)
    s = s.sort_values(["sym", "di"])
    prev = s.groupby("sym")["di"].shift()
    first = prev.isna() | ((s["di"] - prev) > gap)
    keep = pd.MultiIndex.from_frame(s.loc[first, ["date", "sym"]])
    out = pd.Series(False, index=sig.index); out.loc[keep] = True
    return out

DATEIDX = None
def set_dateidx(L):
    global DATEIDX
    d = L.index.get_level_values(0).unique().sort_values()
    DATEIDX = pd.Series(np.arange(len(d)), index=d)

def symmean(L, col, period):
    a, b = PERIODS[period]
    d = L.index.get_level_values(0)
    sub = L[(d >= a) & (d <= b)]
    return sub.groupby(level=1)[col].mean()

def stats(L, sig, period, side="bot", ep=True, hs=(10, 20)):
    a, b = PERIODS[period]
    d = L.index.get_level_values(0)
    pm = (d >= a) & (d <= b)
    base = L[pm]
    s = sig & pm
    if ep: s = episodes(s)
    ev = L[s]
    r = {"n": int(len(ev)), "nsym": int(ev.index.get_level_values(1).nunique()), "ndates": int(ev.index.get_level_values(0).nunique())}
    for h in hs:
        f = f"f{h}"
        e = ev[f].dropna(); bb = base[f].dropna()
        sm = base.groupby(level=1)[f].mean()
        exs = (e - sm.reindex(e.index.get_level_values(1)).values)
        if side == "bot":
            r[f"hit{h}"] = (e > 0).mean() * 100; r[f"base{h}"] = (bb > 0).mean() * 100
        else:
            r[f"hit{h}"] = (e < 0).mean() * 100; r[f"base{h}"] = (bb < 0).mean() * 100
        r[f"mu{h}"] = e.mean() * 100; r[f"bmu{h}"] = bb.mean() * 100
        r[f"exs{h}"] = exs.mean() * 100            # same-stock excess
        r[f"x{h}"] = ev[f"x{h}"].mean() * 100       # excess vs SPY
    r["mae20"] = ev["mae20"].mean() * 100
    r["dd15"] = (ev["mae20"] <= np.log(0.85)).mean() * 100; r["bdd15"] = (base["mae20"] <= np.log(0.85)).mean() * 100
    return r

def cluster_ci(L, sig, period, col="f20", side="bot", B=500, seed=0, ep=True):
    """date-block bootstrap CI for hit rate (resample event dates in 20-day blocks)."""
    a, b = PERIODS[period]
    d = L.index.get_level_values(0)
    s = sig & (d >= a) & (d <= b)
    if ep: s = episodes(s)
    ev = L.loc[s, [col]].dropna().copy()
    if len(ev) < 10: return (np.nan, np.nan)
    ev["blk"] = (ev.index.get_level_values(0).map(DATEIDX) // 20).values
    g = ev.groupby("blk")[col]
    hits = (g.apply(lambda x: ((x > 0) if side == "bot" else (x < 0)).sum())).values
    ns = g.size().values
    rng = np.random.default_rng(seed); k = len(ns); out = []
    for _ in range(B):
        idx = rng.integers(0, k, k)
        out.append(hits[idx].sum() / ns[idx].sum() * 100)
    return tuple(np.percentile(out, [5, 95]).round(1))

def show(name, rs):
    keys = ["n", "nsym", "ndates", "hit10", "base10", "hit20", "base20", "mu20", "bmu20", "exs20", "x20", "mae20", "dd15", "bdd15"]
    print(f"{name:34s} " + " ".join(f"{k}={rs.get(k, np.nan):.1f}" if isinstance(rs.get(k), float) else f"{k}={rs.get(k)}" for k in keys))
