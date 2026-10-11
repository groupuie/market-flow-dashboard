import sys
import numpy as np
import pandas as pd

sys.path.insert(0, sys.argv[1])
import ind  # noqa: E402

rng = np.random.default_rng(7)
n = 1500
idx = pd.bdate_range("2019-01-01", periods=n)
ret = rng.normal(0.0004, 0.018, n)
close = 100 * np.exp(np.cumsum(ret))
openp = close * np.exp(rng.normal(0, 0.006, n))
high = np.maximum(openp, close) * np.exp(np.abs(rng.normal(0, 0.008, n)))
low = np.minimum(openp, close) * np.exp(-np.abs(rng.normal(0, 0.008, n)))
df = pd.DataFrame({"o": openp, "h": high, "l": low, "c": close}, index=idx)
vix = pd.Series(18 * np.exp(np.cumsum(rng.normal(0, 0.05, n)) * 0.2), index=idx)


def all_series(d, v):
    h, l, c = d.h, d.l, d.c
    out = {}
    out["rsi2"] = ind.rsi(c, 2)
    out["ibs"] = ind.ibs(h, l, c)
    out["wr5"] = ind.williams_r(h, l, c, 5)
    e, x = ind.double7(c)
    out["d7_entry"] = e.astype(float)
    out["d7_exit"] = x.astype(float)
    out["crsi"] = ind.connors_rsi(c)
    wvf, spike, trig = ind.vix_fix(h, l, c)
    out["wvf"] = wvf
    out["wvf_trig"] = trig.astype(float)
    bb, st, lvl = ind.vix_stress(v)
    out["vix_bb"] = bb.astype(float)
    out["vix_stretch"] = st.astype(float)
    wt1, wt2 = ind.wavetrend(h, l, c)
    out["wt1"] = wt1
    out["wt2"] = wt2
    f, trg = ind.fisher(h, l)
    out["fisher"] = f
    out["lrsi"] = ind.laguerre_rsi(c)
    out["ce"] = ind.chandelier_long(h, l, c)
    dr, line = ind.supertrend(h, l, c)
    out["st_dir"] = dr
    out["st_line"] = line
    ts, b, s = ind.ut_bot(h, l, c)
    out["ut_ts"] = ts
    out["td13_sell"] = ind.td_countdown13(h, l, c, "sell").astype(float)
    out["td13_buy"] = ind.td_countdown13(h, l, c, "buy").astype(float)
    g, r = ind.elder_impulse(c)
    out["elder_red"] = r.astype(float)
    return out


full = all_series(df, vix)

# 1) range checks
assert full["ibs"].between(0, 1).all()
assert full["crsi"].dropna().between(0, 100).all()
assert full["lrsi"].dropna().between(0, 1).all()
assert full["wr5"].dropna().between(-100, 0).all()
print("range checks ok")

# 2) causality / non-repaint check: value at bar k-1 computed on data[:k] == value on full data
#    (EWM-based series converge, so compare after warm-up with tolerance)
bad = {}
for k in [400, 650, 900, 1200, 1499]:
    part = all_series(df.iloc[:k], vix.iloc[:k])
    for name, s in part.items():
        a, b = s.iloc[-1], full[name].iloc[k - 1]
        if (pd.isna(a) and pd.isna(b)):
            continue
        if not np.isclose(a, b, rtol=1e-9, atol=1e-9):
            bad.setdefault(name, []).append((k, a, b))
print("non-repaint check:", "ok" if not bad else bad)

# 3) signal frequencies (synthetic random walk, just sanity)
c = df.c
freq = {
    "ibs<0.2": (full["ibs"] < 0.2).mean(),
    "wr5<-90": (full["wr5"] < -90).mean(),
    "crsi<10": (full["crsi"] < 10).mean(),
    "d7_entry": full["d7_entry"].mean(),
    "wvf_trig": full["wvf_trig"].mean(),
    "wt cross up < -53": (((full["wt1"] > full["wt2"]) & (full["wt1"].shift(1) <= full["wt2"].shift(1))) & (full["wt1"] < -53)).mean(),
    "lrsi cross up 0.2": ((full["lrsi"] > 0.2) & (full["lrsi"].shift(1) <= 0.2)).mean(),
    "close<chandelier": (c < full["ce"]).mean(),
    "supertrend down": (full["st_dir"] == -1).mean(),
    "td13 sell": full["td13_sell"].mean(),
    "td13 buy": full["td13_buy"].mean(),
    "elder red": full["elder_red"].mean(),
}
for k_, v_ in freq.items():
    print(f"{k_:22s} {v_:.4f}")

# 4) ConnorsRSI spot check of streak logic
s = ind.updown_streak(pd.Series([1, 2, 3, 3, 2, 1, 1.5]))
assert s.tolist() == [0, 1, 2, 0, -1, -2, 1], s.tolist()
print("streak ok")
