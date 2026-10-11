# t29 自我核對:不用 pandas 向量化,逐檔逐日迴圈重算兩版「加」(ORIG / NOHIGH)與 20 日毛報酬,比對 t29_nohigh.log 的筆數與 0bp 平均。
# 只沿用兩個輸入:研究面板 OHLC(qlib)與「出」事件 X(qlib.chu(),與網站 STATS 同一批);QQQ 收盤(t10lib 的 Q)。
import numpy as np, pandas as pd, os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); os.chdir(os.path.dirname(os.path.abspath(__file__)))
from t10lib import O, H, L, C, dates, cols, Q, chu
X = chu().fillna(False).astype(bool).values
o, l, c = O.values, L.values, C.values; n, m = c.shape
q = Q.c.values; qd = np.zeros(n, bool)
for i in range(19, n):
    w = q[i - 19:i + 1]
    if not np.isnan(w).any(): qd[i] = q[i] < w.mean()
i0 = int(np.searchsorted(dates, pd.Timestamp("2009-07-01"))); i1 = int(np.searchsorted(dates, pd.Timestamp("2018-01-01"))); i2 = int(np.searchsorted(dates, pd.Timestamp("2026-08-01")))
res = {(g, p): [] for g in ("共同", "新增", "消失") for p in ("p1", "p2")}
for j in range(m):
    cj, lj, oj = c[:, j], l[:, j], o[:, j]
    def sma(i, k):
        if i - k + 1 < 0: return math.nan
        w = cj[i - k + 1:i + 1]; return math.nan if np.isnan(w).any() else w.mean()
    S50 = np.array([sma(i, 50) for i in range(n)]); S100 = np.array([sma(i, 100) for i in range(n)]); S200 = np.array([sma(i, 200) for i in range(n)])
    lo = np.full(n, math.nan)
    for i in range(19, n):
        w = cj[i - 19:i + 1]
        if not np.isnan(w).any(): lo[i] = w.mean() - 2 * w.std(ddof=0)
    nh = np.zeros(n, bool)
    for i in range(n):
        w = cj[max(0, i - 251):i + 1]; v = w[~np.isnan(w)]
        if len(v) >= 200 and not np.isnan(cj[i]): nh[i] = cj[i] >= v.max()
    rsi = np.full(n, math.nan); ag = al = None
    for i in range(1, n):
        if np.isnan(cj[i]) or np.isnan(cj[i - 1]): continue
        d = cj[i] - cj[i - 1]; g, lo_ = max(d, 0.0), max(-d, 0.0)
        if ag is None: ag, al = g, lo_
        else: ag += (g - ag) / 14; al += (lo_ - al) / 14
        rsi[i] = 100 - 100 / (1 + ag / al) if al > 0 else math.nan
    u = np.array([(not np.isnan(S200[i])) and cj[i] > S200[i] and S50[i] > S200[i] and i >= 20 and (not np.isnan(S200[i - 20])) and S200[i] > S200[i - 20] for i in range(n)])
    ma3 = np.array([(not np.isnan(S200[i])) and S50[i] > S100[i] and S100[i] > S200[i] for i in range(n)])
    rawO = np.zeros(n, bool); rawN = np.zeros(n, bool)
    for i in range(1, n):
        if np.isnan(cj[i]): continue
        stN = u[i - 1] and ma3[i - 1]; stO = stN and nh[max(0, i - 40):i].any()
        rx = (not np.isnan(rsi[i])) and (not np.isnan(rsi[i - 1])) and rsi[i] <= 40 and rsi[i - 1] > 40
        lb = i >= 10 and (not np.isnan(lo[i])) and lj[i] <= lo[i] and all((not np.isnan(lo[k])) and lj[k] > lo[k] for k in range(i - 10, i))
        ex = X[max(0, i - 10):i + 1, j].any()
        base = (rx or lb) and qd[i] and not ex
        rawO[i] = base and stO; rawN[i] = base and stN
    sigO = np.array([rawO[i] and not rawO[max(0, i - 10):i].any() for i in range(n)])
    sigN = np.array([rawN[i] and not rawN[max(0, i - 10):i].any() for i in range(n)])
    for i in range(i0, i2):
        if not (sigO[i] or sigN[i]): continue
        if i + 20 >= n or np.isnan(oj[i + 1]) or np.isnan(cj[i + 20]): continue
        g = math.log(cj[i + 20] / oj[i + 1]); p = "p1" if i < i1 else "p2"
        res[("共同" if sigO[i] and sigN[i] else "新增" if sigN[i] else "消失", p)].append(g)
for (g, p), v in res.items():
    print(f"{g} {p}:n={len(v)} 0bp 平均 {np.mean(v) * 100:+.2f}%" if v else f"{g} {p}:n=0", flush=True)
