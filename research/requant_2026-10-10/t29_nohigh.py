# t29:「加」單因素試驗 —— 拿掉「近 40 根內創過一年新高」。完全照 t29_prereg.md(commit 7f65728,2026-10-11 10:00:49 台灣)執行。
# 不論通過與否,結果都存 t29_nohigh.log。主判定:每邊 10 bp、只用 2026-07-31 以前的訊號。
import numpy as np, pandas as pd, os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); os.chdir(os.path.dirname(os.path.abspath(__file__)))
from t23_dip import *          # C,O,H,L,V,S50,S100,S200,UT,nh,UTS,R14,lo,above_n,first,qdip,X(=chu),FR,MAE,VQ,dates,cols,dix,Q,cr,cool,load …
from t10lib import _pm
END = str(dates[-1].date()); CUT = "2026-07-31"
# ---------- 兩個版本(只差狀態)----------
ma3p = ((S50 > S100) & (S100 > S200)).shift(1).fillna(False).astype(bool)
nh40p = nh.astype(int).rolling(40, min_periods=1).max().shift(1).fillna(0).astype(bool)
UTM = UT & ma3p                                      # NOHIGH 狀態
assert UTS.equals(UT & ma3p & nh40p), "UTS 與 t23 定義不一致"
rsi40 = (R14 <= 40) & (R14.shift(1) > 40); lob = (L <= lo) & above_n(L, lo, 10); trig = rsi40 | lob
recentCHU = X.fillna(False).astype(bool).astype(int).rolling(11, min_periods=1).max().astype(bool)   # 當天 + 前 10 根(修正 B)
rawO = trig & UTS & qdip & ~recentCHU; rawN = trig & UTM & qdip & ~recentCHU
ADD_O = first(rawO, 10); ADD_N = first(rawN, 10)
# 上線版 = t23h / t26_uts_perstock 同一式
ADD_live = first(((rsi40 | lob) & UTS & qdip & ~recentCHU), 10); assert ADD_live.equals(ADD_O)
# ---------- 結果 ----------
G = FR[20]; M20 = MAE[20]; cost = lambda c: np.log((1 - c) / (1 + c))
v5 = V.rolling(5).mean(); v20p = V.shift(5).rolling(20).mean(); VR = v5 / v20p
GRP = {"共同": ADD_O & ADD_N, "新增": ADD_N & ~ADD_O, "消失": ADD_O & ~ADD_N, "ORIG 整版": ADD_O, "NOHIGH 整版": ADD_N}
def basemean(state, a, b):     # 同股、同期間、狀態 & QQQ<20日線 的平均毛報酬(≥20 天)
    m = (state & qdip).values & _pm(a, b)[:, None] & ~np.isnan(G.values)
    s = np.where(m, G.values, 0).sum(0); n = m.sum(0)
    return pd.Series(np.where(n >= 20, s / np.maximum(n, 1), np.nan), index=cols)
PER = {"p1": ("2009-07-01", "2017-12-31"), "p2": ("2018-01-01", CUT), "全期": ("2009-07-01", CUT), "近兩年": ("2024-08-01", CUT), "2026-08 後": ("2026-08-01", END)}
SUB4 = [("2009-07-01", "2013-12-31"), ("2014-01-01", "2018-12-31"), ("2019-01-01", "2022-12-31"), ("2023-01-01", CUT)]
B1 = {k: basemean(UTM, a, b) for k, (a, b) in list(PER.items()) + [(f"s{i}", s) for i, s in enumerate(SUB4)]}
B2a = {k: basemean(UTM & ~nh40p, a, b) for k, (a, b) in PER.items()}; B2o = {k: basemean(UTS, a, b) for k, (a, b) in PER.items()}
def boot(vals, blk, reps=2000, seed=0):
    g = pd.DataFrame({"b": blk, "v": vals}).groupby("b")["v"].agg(["sum", "count"]); rng = np.random.default_rng(seed); k = len(g)
    if k < 2: return (np.nan, np.nan)
    s, n = g["sum"].values, g["count"].values
    return tuple(np.percentile([s[ii].sum() / n[ii].sum() for ii in (rng.integers(0, k, k) for _ in range(reps))], [5, 95]))
def stats(sig, key, a, b, base=None, ci=False, cols_mask=None):
    m = sig.values & _pm(a, b)[:, None]
    if cols_mask is not None: m = m & cols_mask[None, :]
    I, J = np.nonzero(m); g = G.values[I, J]; ok = ~np.isnan(g); r = {"nsig": len(I), "n": int(ok.sum()), "inc": int((~ok).sum())}
    if r["n"] == 0: return r
    I, J, g = I[ok], J[ok], g[ok]; mae = M20.values[I, J]
    r.update(net0=g.mean() * 100, net10=(g + cost(0.001)).mean() * 100, net25=(g + cost(0.0025)).mean() * 100,
             win10=((g + cost(0.001)) > 0).mean() * 100, med10=np.median(g + cost(0.001)) * 100,
             mae=np.nanmean(mae) * 100, mae10=np.nanmean(mae <= np.log(0.9)) * 100, rate=len(I) / (C.loc[_pm(a, b)].notna().values.sum() / 252))
    bs = (base if base is not None else B1[key]).values[J]; okb = ~np.isnan(bs); d = g[okb] - bs[okb]
    r.update(nb=int(okb.sum()), base=bs[okb].mean() * 100 if okb.any() else np.nan, diff=d.mean() * 100 if okb.any() else np.nan)
    if ci and okb.sum() > 20:
        di = I[okb]; r["ci40"] = tuple(x * 100 for x in boot(d, di // 40)); r["ci60"] = tuple(x * 100 for x in boot(d, di // 60))
    r["_IJd"] = (I[okb], J[okb], d)
    return r
def line(nm, per, r):
    if r["n"] == 0: return f"  {nm:9s} {per:8s} 事件 {r['nsig']}(全部未完成)"
    s = (f"  {nm:9s} {per:8s} n={r['n']:5d}(未完成 {r['inc']},每檔每年 {r['rate']:.2f})| 淨報酬 0/10/25bp {r['net0']:+.2f}/{r['net10']:+.2f}/{r['net25']:+.2f}%"
         f" 中位 {r['med10']:+.2f}% 賺 {r['win10']:.0f}% | 對照 {r['base']:+.2f}% 差 {r['diff']:+.2f}%(n={r['nb']})")
    if "ci40" in r: s += f" [40日 {r['ci40'][0]:+.2f},{r['ci40'][1]:+.2f}][60日 {r['ci60'][0]:+.2f},{r['ci60'][1]:+.2f}]"
    return s + f" | MAE 平均 {r['mae']:+.1f}% 跌≥10% {r['mae10']:.1f}%"
print(f"資料 {dates[0].date()}~{END};259 檔;判定只用 ≤{CUT} 的訊號;報酬 = t+1 開盤買、t+20 收盤賣(log);成本每邊扣;差 = 毛報酬 − 同股同狀態(NOHIGH 狀態且 QQQ<20日線)平均")
print("檢查:UTS = t23 定義 ✓;ORIG = 上線版(t23h)同一式 ✓\n")
R = {}
for per, (a, b) in PER.items():
    for nm, sig in GRP.items():
        R[(nm, per)] = stats(sig, per, a, b, ci=(per == "全期" or per in ("p1", "p2")) and nm in ("新增", "共同", "消失"))
        print(line(nm, per, R[(nm, per)]), flush=True)
    print()
print("次對照 B2(新增 → NOHIGH 狀態但近 40 根沒新高;共同/消失 → ORIG 狀態;只描述)")
for per in ("p1", "p2"):
    a, b = PER[per]
    for nm, base in (("新增", B2a[per]), ("共同", B2o[per]), ("消失", B2o[per])):
        r = stats(GRP[nm], per, a, b, base=base); print(f"  {nm} {per} 差(對 B2){r.get('diff', float('nan')):+.2f}%(n={r.get('nb', 0)})")
print("\n四段(新增,差;n<30 算沒過)")
sub = []
for i, (a, b) in enumerate(SUB4):
    r = stats(GRP["新增"], f"s{i}", a, b); sub.append(r); print(f"  {a[:7]}~{b[:7]} n={r['n']} 差 {r.get('diff', float('nan')):+.2f}% 淨10bp {r.get('net10', float('nan')):+.2f}%")
print("\n分組(新增,全期 2009-07~2026-07;只描述)")
a, b = PER["全期"]
for nm, mask in (("低波動(VQ<0.5)", (VQ < 0.5)), ("高波動(VQ≥0.5)", (VQ >= 0.5)), ("量縮(量比≤0.8)", (VR <= 0.8)), ("沒量縮(量比>0.8)", (VR > 0.8))):
    for gg in ("新增", "共同"):
        r = stats(GRP[gg] & mask.fillna(False), "全期", a, b); print(f"  {nm} {gg}:n={r['n']} 淨10bp {r.get('net10', float('nan')):+.2f}% 差 {r.get('diff', float('nan')):+.2f}% 跌≥10% {r.get('mae10', float('nan')):.1f}%")
# 集中度
I, J, d = R[("新增", "全期")]["_IJd"]; contrib = pd.Series(d, index=J).groupby(level=0).sum().sort_values(ascending=False)
top5 = [cols[j] for j in contrib.index[:5]]; drop = {}
for per in ("p1", "p2"):
    I_, J_, d_ = R[("新增", per)]["_IJd"]; keep = ~np.isin([cols[j] for j in J_], top5); drop[per] = d_[keep].mean() * 100
print(f"\n集中度:新增事件「差」合計最大的 5 檔 {top5};拿掉後 p1 {drop['p1']:+.2f}%、p2 {drop['p2']:+.2f}%")
ps = pd.DataFrame({"j": J, "d": d}).groupby("j")["d"].agg(["mean", "count"]); ps = ps[ps["count"] >= 3]
print(f"每檔:新增 ≥3 次的 {len(ps)} 檔,「差」>0 的 {(ps['mean'] > 0).mean() * 100:.0f}%")
# ---------- ETF(SPY、QQQ;同公式;只描述)----------
def etf_frame():
    E = {s: load(s).reindex(dates) for s in ("SPY", "QQQ")}
    c, o, h, l = [pd.DataFrame({s: E[s][k] for s in E}) for k in ("c", "o", "h", "l")]
    s20, s50, s100, s200 = [c.rolling(k).mean() for k in (20, 50, 100, 200)]
    u = (c > s200) & (s50 > s200) & (s200 > s200.shift(20)); ut = u.shift(1).fillna(False).astype(bool)
    m3 = ((s50 > s100) & (s100 > s200)).shift(1).fillna(False).astype(bool)
    hi = c.rolling(252, min_periods=200).max(); nh_ = (c >= hi); n40 = nh_.astype(int).rolling(40, min_periods=1).max().shift(1).fillna(0).astype(bool)
    d_ = c.diff(); ag = d_.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean(); al = (-d_).clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean(); r14 = 100 - 100 / (1 + ag / al.replace(0, np.nan))
    lo_ = s20 - 2 * c.rolling(20).std(ddof=0); lb = (l <= lo_) & ((l > lo_).astype(int).rolling(10, min_periods=10).sum().shift(1) == 10)
    tg = ((r14 <= 40) & (r14.shift(1) > 40)) | lb
    qd = pd.DataFrame({s: (Q.c < Q.c.rolling(20).mean()) for s in E})
    rel = c / s50 - 1; xx = (c < s20) & (c.shift(1) >= s20.shift(1)); ch = cool((rel.rolling(20).max() >= 0.15) & xx, 20) & pd.DataFrame({s: cr <= 0.35 for s in E})
    rc = ch.fillna(False).astype(bool).astype(int).rolling(11, min_periods=1).max().astype(bool)
    fst = lambda x: x & ~x.shift(1).fillna(False).astype(int).rolling(10, min_periods=1).max().astype(bool)
    aO = fst(tg & ut & m3 & n40 & qd & ~rc); aN = fst(tg & ut & m3 & qd & ~rc)
    g20 = np.log(c.shift(-20) / o.shift(-1)); mae = np.log(l[::-1].rolling(20, min_periods=20).min()[::-1].shift(-1) / o.shift(-1))
    return aO, aN, g20, mae
aO, aN, g20, maeE = etf_frame()
print("\nETF(SPY、QQQ;Yahoo 調整後;只描述;2009-07~2026-07)")
for s in ("SPY", "QQQ"):
    for nm, sg in (("ORIG", aO[s]), ("NOHIGH", aN[s]), ("新增", aN[s] & ~aO[s]), ("消失", aO[s] & ~aN[s])):
        x = sg[(sg.index >= "2009-07-01") & (sg.index <= CUT)]; dd = x[x].index; g = g20[s].reindex(dd).dropna(); mm = maeE[s].reindex(dd).dropna()
        print(f"  {s} {nm:6s} n={len(dd)} 淨10bp {(g + cost(0.001)).mean() * 100 if len(g) else float('nan'):+.2f}% 賺 {((g + cost(0.001)) > 0).mean() * 100 if len(g) else float('nan'):.0f}% 跌≥10% {(mm <= np.log(0.9)).mean() * 100 if len(mm) else float('nan'):.0f}%"
              + (f" 日期 {[str(t.date()) for t in dd]}" if nm in ("新增", "消失") else ""))
# ---------- 與網頁 JS(t28,網站同一份日K)比:SPY、QQQ(ETF 版)、AMD、PLTR、AVGO,2022-09-01~2026-07-31 ----------
T28 = json.load(open("t28_buydiag.json", encoding="utf-8"))["window"]
print("\n與網頁 JS 比(2022-09-01~2026-07-31;研究 = Yahoo,網頁 = 富途/Yahoo 擴充;只報一致率)")
for s in ("SPY", "QQQ", "AMD", "PLTR", "AVGO"):
    for nm, js_key in (("ORIG", "addAllOrig"), ("NOHIGH", "addAllNoHigh")):
        sg = (aO if nm == "ORIG" else aN)[s] if s in ("SPY", "QQQ") else (ADD_O if nm == "ORIG" else ADD_N)[s]
        rs = set(str(t.date()) for t in sg[(sg.index >= "2022-09-01") & (sg.index <= CUT) & sg].index)
        js = set(d for d in T28[s][js_key] if "2022-09-01" <= d <= CUT)
        print(f"  {s} {nm}:研究 {len(rs)}、網頁 {len(js)}、相同 {len(rs & js)};只在研究 {sorted(rs - js)};只在網頁 {sorted(js - rs)}")
# ---------- 判定 ----------
N1, N2, NA = R[("新增", "p1")], R[("新增", "p2")], R[("新增", "全期")]
V1o, V2o, V1n, V2n = R[("ORIG 整版", "p1")], R[("ORIG 整版", "p2")], R[("NOHIGH 整版", "p1")], R[("NOHIGH 整版", "p2")]
g_ = lambda r, k: r.get(k, float("nan"))
crit = [
    ("1 新增 淨報酬 10bp >0(p1、p2)", g_(N1, "net10") > 0 and g_(N2, "net10") > 0, f"{g_(N1, 'net10'):+.2f}% / {g_(N2, 'net10'):+.2f}%"),
    ("2 新增 差 >0(p1、p2)且全期 90% 下緣 >0(40、60 日)", g_(N1, "diff") > 0 and g_(N2, "diff") > 0 and NA.get("ci40", (-1,))[0] > 0 and NA.get("ci60", (-1,))[0] > 0,
     f"{g_(N1, 'diff'):+.2f}% / {g_(N2, 'diff'):+.2f}%;全期下緣 40日 {NA.get('ci40', (float('nan'),))[0]:+.2f}%、60日 {NA.get('ci60', (float('nan'),))[0]:+.2f}%"),
    ("3 新增 四段 ≥3 段差 >0(n<30 算沒過)", sum(1 for r in sub if r["n"] >= 30 and g_(r, "diff") > 0) >= 3, " / ".join(f"{g_(r, 'diff'):+.2f}%(n={r['n']})" for r in sub)),
    ("4 整版不變差:NOHIGH 淨報酬 ≥ ORIG,且跌≥10% 比例 ≤ ORIG(p1、p2)", g_(V1n, "net10") >= g_(V1o, "net10") and g_(V2n, "net10") >= g_(V2o, "net10") and g_(V1n, "mae10") <= g_(V1o, "mae10") and g_(V2n, "mae10") <= g_(V2o, "mae10"),
     f"淨 {g_(V1n, 'net10'):+.2f} vs {g_(V1o, 'net10'):+.2f}% / {g_(V2n, 'net10'):+.2f} vs {g_(V2o, 'net10'):+.2f}%;跌≥10% {g_(V1n, 'mae10'):.1f} vs {g_(V1o, 'mae10'):.1f}% / {g_(V2n, 'mae10'):.1f} vs {g_(V2o, 'mae10'):.1f}%"),
    ("5 拿掉前 5 檔後新增差 >0(p1、p2)", drop["p1"] > 0 and drop["p2"] > 0, f"{drop['p1']:+.2f}% / {drop['p2']:+.2f}%"),
    ("6 每邊 25bp 新增淨報酬 >0(p1、p2)", g_(N1, "net25") > 0 and g_(N2, "net25") > 0, f"{g_(N1, 'net25'):+.2f}% / {g_(N2, 'net25'):+.2f}%"),
]
print("\n判定(事前設定 7f65728 的 6 條,全部要過):")
for k, ok, v in crit: print(f"  {'過' if ok else '沒過'}  {k}:{v}")
print("結論:" + ("全部通過 → 只寫成提案,網站這輪不改,由使用者決定" if all(ok for _, ok, _ in crit) else "不通過 → 維持原版(近 40 根新高照舊),這輪不換回看天數重試"))
