# t27 自我核對:不用 t27_extra_topk.py 的向量化寫法,改用逐筆迴圈重算 ORIG / EXTRA 的交易優勢與連續操作版,
# 比對 t27_extra_topk.log 的數字(0bp 平均、筆數、連續操作每檔每年合計)。
import numpy as np, pandas as pd, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qlib import O, H, L, C, dates
o, h, l, c = (X.values for X in (O, H, L, C)); n, m = c.shape; END = str(dates[-1].date())
def tr_at(k, j): return np.max([h[k, j]-l[k, j], abs(h[k, j]-c[k-1, j]), abs(l[k, j]-c[k-1, j])])   # 任何一項缺 → NaN(與 np.maximum 相同)
def atr_end(e, j):   # 以第 e 根結尾的 14 根 TR 平均,至少 10 根有值
    t = [tr_at(k, j) for k in range(e-13, e+1)]; t = [x for x in t if not np.isnan(x)]
    return np.mean(t) if len(t) >= 10 else np.nan
def sig_at(i, j, kind):
    w = c[i-19:i+1, j]
    if np.isnan(w).any(): return False                      # 沒有布林 → 不可能碰上緣
    mid = w.mean(); up = mid + 2 * w.std(ddof=0)
    if not h[i, j] >= up: return False                       # 先看碰上緣(省時間;結果不變)
    atr = atr_end(i, j); atr1 = atr_end(i-1, j)
    r20 = c[i, j]/c[i-20, j]-1; w50 = c[i-49:i+1, j]; ext = c[i, j]/w50.mean()-1 if not np.isnan(w50).any() else np.nan
    hot = (r20 >= 0.30) or ((c[i, j]-mid)/atr >= 3) or (ext >= 0.25)   # NaN 比較一律 False(與 pandas 相同)
    touch = h[i, j] >= up; off = 1 - c[i, j]/h[i, j]
    if kind == "ORIG": return bool(hot and touch and off >= 0.05)
    return bool(hot and touch and off < 0.05 and atr1 > 0 and h[i, j]-c[i, j] >= atr1)
def edge(i, j):
    if i + 12 >= n or np.isnan(o[i+1, j]) or np.isnan(o[i+12, j]): return None, None
    S = o[i+1, j]; lim = 0.97 * S
    for k in range(2, 12):
        if l[i+k, j] <= lim:
            b = min(o[i+k, j], lim) if not np.isnan(o[i+k, j]) else np.nan
            return (None, None) if np.isnan(b) else (np.log(S / b), k)
    return np.log(S / o[i+12, j]), 12
i0 = int(np.searchsorted(dates, pd.Timestamp("2009-07-01"))); i1 = int(np.searchsorted(dates, pd.Timestamp("2018-01-01")))
for kind in ("ORIG", "EXTRA"):
    ev = {"p1": [], "p2": []}; seq = {"p1": [], "p2": []}
    for j in range(m):
        nb = -1
        for i in range(i0, n):
            if np.isnan(c[i, j]) or not sig_at(i, j, kind): continue
            e, k = edge(i, j)
            if e is None: continue
            per = "p1" if i < i1 else "p2"; ev[per].append(e)
            if i >= nb: seq[per].append(e); nb = i + k
    sy = {"p1": np.isfinite(c[i0:i1]).sum() / 252, "p2": np.isfinite(c[i1:]).sum() / 252}
    for per in ("p1", "p2"):
        x = np.array(ev[per]); s = np.array(seq[per])
        print(f"{kind} {per}:事件 n={len(x)} 0bp 平均 {x.mean()*100:+.2f}% | 連續操作 {len(s)} 筆,10bp 合計每檔每年 {(s-0.001).sum()/sy[per]*100:+.3f}%", flush=True)
