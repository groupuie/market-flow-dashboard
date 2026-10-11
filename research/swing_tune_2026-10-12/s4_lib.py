# 短線 底/頂 調整第 1 輪 — 共用:資料、訊號、出場、統計(規則見 p0_prereg.md;結果出來前已 commit)
import os, sys, json, math, pickle, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "research", "tools_scan_2026-10-12")); sys.path.insert(0, os.path.join(REPO, "scripts"))
import ind                                    # 外部候選公式(工具掃描 A)
DT = "/home/claude/work/t30"; EXT = "/home/claude/work/ext"; CACHE = "/home/claude/work/swing_tune"; os.makedirs(CACHE, exist_ok=True)
START = "2004-01-01"; S0, S1 = "2010-01-01", "2026-07-31"
PERIODS = {"前段": ("2010-01-01", "2017-12-31"), "後段": ("2018-01-01", "2026-07-31"), "近期": ("2023-01-01", "2026-07-31"),
           "全期": ("2010-01-01", "2026-07-31")}   # 全期 = 給網站滑過說明用的總數(決定只看前段/後段)
G = json.load(open(os.path.join(HERE, "groups.json")))
COST = 0.002          # 來回 0.20%(每邊 0.10%)
COOL = 5

def load(s):
    p = os.path.join(DT, "yh", s.replace("^", "_").replace("=", "_") + ".pkl")
    if not os.path.exists(p): return None
    df = pd.read_pickle(p); df = df[df.index >= START]
    f = (df["ac"] / df["c"]).replace([np.inf, -np.inf], np.nan).fillna(1.0)
    out = pd.DataFrame({"o": df["o"] * f, "h": df["h"] * f, "l": df["l"] * f, "c": df["ac"], "v": df["v"]})
    for k in ("o", "h", "l"):
        bad = out[k].isna() | (out[k] <= 0); out.loc[bad, k] = out.loc[bad, "c"]
    out["h"] = out[["h", "o", "c"]].max(axis=1); out["l"] = out[["l", "o", "c"]].min(axis=1)
    return out.dropna(subset=["c"])

# ---------- 短線 底/頂(與網站 swSeriesJS、swing_ref.sw_py 同式;numpy 版)----------
def rsi2_wilder(C):
    n = len(C); r = np.full(n, np.nan)
    if n < 4: return r
    d = np.diff(C); g = np.maximum(d, 0); l = np.maximum(-d, 0)
    ag = (g[0] + g[1]) / 2; al = (l[0] + l[1]) / 2; r[2] = 100 if al == 0 else 100 - 100 / (1 + ag / al)
    for i in range(3, n):
        ag = (ag + g[i - 1]) / 2; al = (al + l[i - 1]) / 2; r[i] = 100 if al == 0 else 100 - 100 / (1 + ag / al)
    return r

def bb_pop(C, n=20, k=2.0):
    s = pd.Series(C); m = s.rolling(n).mean(); sd = s.rolling(n).std(ddof=0)
    return (m - k * sd).to_numpy(), (m + k * sd).to_numpy()

def td_runs(C):
    n = len(C); tb = np.zeros(n, int); ts = np.zeros(n, int)
    for i in range(4, n):
        tb[i] = tb[i - 1] + 1 if C[i] < C[i - 4] else 0; ts[i] = ts[i - 1] + 1 if C[i] > C[i - 4] else 0
    return tb, ts

def cooldown(sig, gap=COOL):
    out = np.zeros(len(sig), bool); last = -10**9
    for i in np.flatnonzero(sig):
        if i - last > gap: out[i] = True; last = i
    return out

def swing(O, H, L, C):
    n = len(C); r2 = rsi2_wilder(C); lo, up = bb_pop(C); tb, ts = td_runs(C)
    with np.errstate(invalid="ignore"):
        os_ = (np.nan_to_num(r2, nan=50) <= 10) | (C <= np.where(np.isnan(lo), -np.inf, lo)) | (tb == 9)
        ob_ = (np.nan_to_num(r2, nan=50) >= 90) | (C >= np.where(np.isnan(up), np.inf, up)) | (ts == 9)
    os3 = os_.copy(); ob3 = ob_.copy()
    os3[1:] |= os_[:-1]; os3[2:] |= os_[:-2]; ob3[1:] |= ob_[:-1]; ob3[2:] |= ob_[:-2]
    rawb = np.zeros(n, bool); rawt = np.zeros(n, bool)
    rawb[2:] = os3[2:] & (C[2:] > H[1:-1]); rawt[2:] = ob3[2:] & (C[2:] < L[1:-1])
    return cooldown(rawb), cooldown(rawt), {"r2": r2, "lo": lo, "up": up}

# ---------- 每檔:全部訊號 ----------
def stock_signals(df):
    O, H, L, C, V = (df[k].to_numpy(dtype="float64") for k in "ohlcv")
    h, l, c = df["h"], df["l"], df["c"]
    b0, t0, aux = swing(O, H, L, C)
    S = {"B0": b0, "T0": t0}
    ibs = ind.ibs(h, l, c).to_numpy()
    S["B1r"] = cooldown(ibs < 0.20)
    b1c = np.zeros(len(C), bool); b1c[1:] = (ibs[:-1] < 0.20) & (C[1:] > H[:-1]); S["B1c"] = cooldown(b1c)
    e7, _ = ind.double7(c); S["B2"] = cooldown(e7.to_numpy())
    S["B2n"] = cooldown((c <= c.rolling(7).min()).to_numpy())
    wr = ind.williams_r(h, l, c, 5).to_numpy()
    with np.errstate(invalid="ignore"): S["B3"] = cooldown(np.nan_to_num(wr, nan=0) < -90)
    crsi = ind.connors_rsi(c).to_numpy(); S["_crsi"] = crsi
    _, _, trig = ind.vix_fix(h, l, c); S["B6"] = cooldown(trig.to_numpy())
    # 頂
    atr10 = ind.atr(h, l, c, 10).to_numpy(); e20 = ind.ema(c, 20).to_numpy(); r14 = ind.rsi(c, 14).to_numpy()
    with np.errstate(invalid="ignore"):
        ext = (C > e20 + 2.5 * atr10) | (np.nan_to_num(r14, nan=50) >= 80)
    ext3 = ext.copy(); ext3[1:] |= ext[:-1]; ext3[2:] |= ext[:-2]
    S["T4"] = t0 & ext3
    S["T5"] = ind.td_countdown13(h, l, c, "sell").to_numpy()
    ch = ind.chandelier_long(h, l, c, 22, 3.0).to_numpy()
    with np.errstate(invalid="ignore"):
        below = C < ch
    t2 = np.zeros(len(C), bool); t2[1:] = below[1:] & ~below[:-1] & ~np.isnan(ch[:-1]); S["T2"] = t2
    d, _ = ind.supertrend(h, l, c, 10, 3.0); d = d.to_numpy(); t3 = np.zeros(len(C), bool); t3[1:] = (d[1:] == -1) & (d[:-1] == 1)
    t3[:30] = False; S["T3"] = t3
    gr, rd = ind.elder_impulse(c); gr = gr.to_numpy(); rd = rd.to_numpy()
    t6 = np.zeros(len(C), bool); run = 0
    for i in range(len(C)):
        if gr[i]: run += 1; continue
        if rd[i] and run >= 3: t6[i] = True
        run = 0
    t6[:40] = False; S["T6"] = t6
    S["atr14"] = ind.atr(h, l, c, 14).to_numpy()
    return S

# ---------- 出場 ----------
def next_true_after(mask):
    """nx[t] = 最小的 k > t 使 mask[k];沒有 = n"""
    n = len(mask); nx = np.full(n, n, int); nxt = n
    for i in range(n - 1, -1, -1):
        nx[i] = nxt
        if mask[i]: nxt = i
    return nx

class RMQ:   # 區間最小/最大(sparse table)
    def __init__(self, a, op):
        self.op = op; self.t = [a.copy()]; k = 1
        while (1 << k) <= len(a):
            p = self.t[-1]; h = 1 << (k - 1); q = p.copy(); q[:len(a) - h] = op(p[:len(a) - h], p[h:]); self.t.append(q); k += 1
    def q(self, lo, hi):   # 含 lo、hi;陣列
        ln = np.maximum(hi - lo + 1, 1); k = np.floor(np.log2(ln)).astype(int)
        res = np.empty(len(lo))
        for kk in np.unique(k):
            m = k == kk; t = self.t[kk]; res[m] = self.op(t[lo[m]], t[hi[m] - (1 << kk) + 1])
        return res

def exits(O, H, L, C, top_mask):
    n = len(C); idx = np.arange(n)
    nt = next_true_after(top_mask)
    xt = np.where(nt - idx <= 40, nt + 1, idx + 41)
    x10 = idx + 11
    up = np.zeros(n, bool); up[1:] = C[1:] > H[:-1]
    nu = next_true_after(up); xq = np.minimum(nu + 1, idx + 11)
    return {"XT": xt, "X10": x10, "XQ": xq}

def trades(O, L, ent_days, ex_idx, rmq_min):
    """ent_days = 訊號日 t 的陣列;回傳 (有效 mask, 淨報酬, 持有根數, 最大不利)"""
    n = len(O); t = ent_days; e = ex_idx[t]
    ok = (t + 1 < n) & (e < n) & (e > t + 1)
    t, e = t[ok], e[ok]
    net = O[e] / O[t + 1] - 1 - COST
    mae = rmq_min.q(t + 1, e - 1) / O[t + 1] - 1
    return ok, net, e - (t + 1), mae

# ---------- 轉折(只評分,事後才知道)----------
def pivots(H, L, atr, k=3.0, w=10, s=20):
    n = len(L); pl = np.zeros(n, bool); ph = np.zeros(n, bool)
    for p in range(s, n - s):
        a = atr[p]
        if not np.isfinite(a) or a <= 0: continue
        lw = L[p - w:p + w + 1]
        if L[p] < L[p - w:p].min() and L[p] <= L[p + 1:p + w + 1].min():
            if H[p - s:p].max() - L[p] >= k * a and H[p + 1:p + s + 1].max() - L[p] >= k * a: pl[p] = True
        if H[p] > H[p - w:p].max() and H[p] >= H[p + 1:p + w + 1].max():
            if H[p] - L[p - s:p].min() >= k * a and H[p] - L[p + 1:p + s + 1].min() >= k * a: ph[p] = True
    return pl, ph

def near(mask_a, mask_b, r=3):
    """a 的每個 True,前後 r 根內 b 有沒有 True"""
    n = len(mask_b); cb = np.concatenate([[0], np.cumsum(mask_b)])
    ia = np.flatnonzero(mask_a); lo = np.clip(ia - r, 0, n); hi = np.clip(ia + r + 1, 0, n)
    return ia, (cb[hi] - cb[lo]) > 0
