# s1:短線「底 / 頂」候選規則比較(使用者 2026-10-11 23:40:要日K的短期底、短期頂,做槓桿 ETF 成本調節;
#     QQQ、SPY、七巨頭、科技大型股、資金追捧的熱門股要準;70% 是目標、不是上線門檻)
# 只用大家都在看的指標:RSI(2)、布林(20,2)、九轉 TD setup 9;外加「隔天真的轉向」確認。
# 量:隔天開盤進場,5 / 10 天後的收盤;底 = 比較高的比例、頂 = 比較低的比例;和同組「所有日子」比。
# 期間:訊號 2010-01 ~ 2026-07,分前段 2010–2017、後段 2018–2026。只描述;挑規則看兩段一致 + 次數夠。
import numpy as np, pandas as pd, json, os, sys, warnings; warnings.filterwarnings("ignore")
DT = "/home/claude/work/t30"; START = "2004-01-01"; S0, S1, MID = "2010-01-01", "2026-07-31", "2018-01-01"
def load(s):
    p = os.path.join(DT, "yh", s.replace("^", "_").replace("=", "_") + ".pkl")
    if not os.path.exists(p): return None
    df = pd.read_pickle(p); df = df[df.index >= START]
    f = (df["ac"] / df["c"]).replace([np.inf, -np.inf], np.nan).fillna(1.0)
    out = pd.DataFrame({"o": df["o"] * f, "h": df["h"] * f, "l": df["l"] * f, "c": df["ac"], "v": df["v"]})
    for k in ("o", "h", "l"):
        bad = out[k].isna() | (out[k] <= 0); out.loc[bad, k] = out.loc[bad, "c"]
    out["h"] = out[["h", "o", "c"]].max(axis=1); out["l"] = out[["l", "o", "c"]].min(axis=1)
    return out
meta = json.load(open(os.path.join(DT, "meta.json")))
eq = sorted(s for s, v in meta.items() if v.get("type") == "EQUITY")
IDX = ["SPY", "QQQ"]; MAG7 = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA"]
spy = load("SPY"); cal = spy.index[spy.index >= START]
syms = IDX + eq
Pd = {k: {} for k in "OHLC"}
for s in syms:
    d = load(s)
    if d is None or len(d) < 260: continue
    d = d.reindex(cal)
    for k, c in zip("OHLC", "ohlc"): Pd[k][s] = d[c]
O, H, L, C = [pd.DataFrame(Pd[k]).astype("float64") for k in "OHLC"]
cols = list(C.columns); dates = C.index; n, m = C.shape
print("檔數", m, "其中七巨頭", [s for s in MAG7 if s in cols])

def rsi_w(c, p=2):   # Wilder RSI(p),逐檔
    out = np.full(c.shape, np.nan)
    for j in range(c.shape[1]):
        x = c[:, j]; ok = ~np.isnan(x); idx = np.flatnonzero(ok)
        if len(idx) < p + 2: continue
        xs = x[idx]; d = np.diff(xs); g = np.maximum(d, 0); l = np.maximum(-d, 0)
        ag = g[:p].mean(); al = l[:p].mean(); r = np.full(len(xs), np.nan)
        r[p] = 100 if al == 0 else 100 - 100 / (1 + ag / al)
        for i in range(p + 1, len(xs)):
            ag = (ag * (p - 1) + g[i - 1]) / p; al = (al * (p - 1) + l[i - 1]) / p
            r[i] = 100 if al == 0 else 100 - 100 / (1 + ag / al)
        out[idx, j] = r
    return out
def td_setup(c):   # 九轉 setup 計數:buy = 收盤 < 4 根前收盤 連續幾根;sell 相反(到 9 為完成,之後繼續數但只看 ==9 那根)
    b = np.zeros(c.shape, int); s = np.zeros(c.shape, int)
    for i in range(4, c.shape[0]):
        lt = c[i] < c[i - 4]; gt = c[i] > c[i - 4]
        b[i] = np.where(lt, b[i - 1] + 1, 0); s[i] = np.where(gt, s[i - 1] + 1, 0)
    return b, s
Cv, Ov, Hv, Lv = C.values, O.values, H.values, L.values
R2 = rsi_w(Cv, 2)
mid = C.rolling(20, min_periods=20).mean().values; sd = C.rolling(20, min_periods=20).std(ddof=0).values
lo, up = mid - 2 * sd, mid + 2 * sd
s200 = C.rolling(200, min_periods=200).mean().values
tb, ts = td_setup(np.nan_to_num(Cv, nan=-1e18))   # NaN 期間不會成立(和 -1e18 比較後計數會斷)
tb[np.isnan(Cv)] = 0; ts[np.isnan(Cv)] = 0
td9b = tb == 9; td9s = ts == 9
def lastk(x, k=3):   # 最近 k 根(含今天)內有沒有成立
    out = x.copy()
    for s in range(1, k): out[s:] |= x[:-s]
    return out
osold10 = np.nan_to_num(R2, nan=50) <= 10; osold5 = np.nan_to_num(R2, nan=50) <= 5
obought90 = np.nan_to_num(R2, nan=50) >= 90; obought95 = np.nan_to_num(R2, nan=50) >= 95
belowLB = Cv <= lo; aboveUB = Cv >= up
revUp = np.zeros_like(belowLB); revUp[1:] = Cv[1:] > Hv[:-1]          # 收盤站上昨天最高
revDn = np.zeros_like(belowLB); revDn[1:] = Cv[1:] < Lv[:-1]          # 收盤跌破昨天最低
upC = np.zeros_like(belowLB); upC[1:] = Cv[1:] > Cv[:-1]
dnC = np.zeros_like(belowLB); dnC[1:] = Cv[1:] < Cv[:-1]
uptr = Cv > s200

def cool(sig, k=5):
    out = np.zeros_like(sig)
    for j in range(sig.shape[1]):
        last = -10**9
        for i in np.flatnonzero(sig[:, j]):
            if i - last > k: out[i, j] = True; last = i
    return out
G = {h: np.log(np.roll(Cv, -h, axis=0) / np.roll(Ov, -1, axis=0)) for h in (5, 10)}
for h in G: G[h][-h:] = np.nan
per = (dates >= pd.Timestamp(S0)) & (dates <= pd.Timestamp(S1)); half2 = dates >= pd.Timestamp(MID)
groups = {"指數 SPY/QQQ": [c in IDX for c in cols], "七巨頭": [c in MAG7 for c in cols], "全部追蹤股": [c not in IDX for c in cols]}

def stat(mask, side, gm):
    out = {}
    for nm, ps in (("前段", per & ~half2), ("後段", per & half2), ("全期", per)):
        sel = mask & ps[:, None] & np.array(gm)[None, :]
        for h in (5, 10):
            g = G[h][sel]; g = g[~np.isnan(g)]
            base = G[h][ps[:, None] & np.array(gm)[None, :]]; base = base[~np.isnan(base)]
            hit = (g > 0).mean() * 100 if side == "底" else (g < 0).mean() * 100
            bhit = (base > 0).mean() * 100 if side == "底" else (base < 0).mean() * 100
            out[f"{nm}{h}"] = (len(g), round(hit, 1), round(bhit, 1), round(np.mean(g) * 100, 2) if len(g) else None)
    yrs = per.sum() / 252; nst = sum(gm)
    out["每檔每年"] = round(out["全期10"][0] / max(1, nst) / yrs, 1)
    return out

CAND = {
  ("底", "RSI2≤10"): osold10, ("底", "RSI2≤10 且在200日線上"): osold10 & uptr, ("底", "RSI2≤5 且在200日線上"): osold5 & uptr,
  ("底", "收盤≤布林下緣"): belowLB, ("底", "九轉買9"): td9b,
  ("底", "近3天超賣(任一)+收盤>昨高"): lastk(osold10 | belowLB | td9b) & revUp,
  ("底", "近3天超賣(任一)+收盤>昨高+200日線上"): lastk(osold10 | belowLB | td9b) & revUp & uptr,
  ("底", "近3天超賣(任一)+收盤上漲"): lastk(osold10 | belowLB | td9b) & upC,
  ("頂", "RSI2≥90"): obought90, ("頂", "RSI2≥95"): obought95, ("頂", "收盤≥布林上緣"): aboveUB, ("頂", "九轉賣9"): td9s,
  ("頂", "近3天超買(任一)+收盤<昨低"): lastk(obought90 | aboveUB | td9s) & revDn,
  ("頂", "近3天超買(任一)+收盤<昨低+200日線下"): lastk(obought90 | aboveUB | td9s) & revDn & ~uptr,
  ("頂", "近3天超買(任一)+收盤下跌"): lastk(obought90 | aboveUB | td9s) & dnC,
}
res = {}
for (side, nm), sig in CAND.items():
    sig = cool(np.nan_to_num(sig, nan=0).astype(bool) & ~np.isnan(Cv), 5)
    res[f"{side}|{nm}"] = {g: stat(sig, side, gm) for g, gm in groups.items()}
for k, v in res.items():
    print(f"\n== {k}")
    for g, s in v.items():
        print(f"  {g:<10} 每檔每年 {s['每檔每年']:>5}|10天 前段 {s['前段10'][1]}%(平常 {s['前段10'][2]})後段 {s['後段10'][1]}%(平常 {s['後段10'][2]})"
              f" 全期 {s['全期10'][1]}% n={s['全期10'][0]} 平均 {s['全期10'][3]}%|5天 全期 {s['全期5'][1]}%(平常 {s['全期5'][2]})")
json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "s1_candidates.json"), "w"), ensure_ascii=False, indent=1)
