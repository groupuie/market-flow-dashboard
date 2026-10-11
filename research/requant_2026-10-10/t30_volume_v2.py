# t30 v2:「量縮盤整、幾天沒再創低」—— 完全照 t30_prereg_volume_v2.md(commit b086ffc)執行。
# 不論通過與否,結果都存 t30_volume_v2.log。主判定:每邊 10 bp、只用 2026-07-31 以前的訊號。
#
# 跑之前就決定、寫在這裡的執行細節(登記文件沒寫死的地方;看結果前定案,看結果後不改):
#   A. 名單:登記寫「259 檔 = 現在的追蹤名單」,但 10-09 那份名單沒存檔。本次照網站同一規則重建
#      (daily_flows + ext_flows 250 日內出現過、非「現金」類 ∪ ext_universe ∪ custom_symbols → Yahoo instrumentType=EQUITY)。
#   B. 冷卻「前 10 根內沒有候選日」:以「已成立的候選日」計(qlib.cool,k=10)。另列「前 10 根內 ①② 都沒成立過」
#      (first)的寫法當敏感度,只描述、不參與判定。
#   C. 扣個股水準:每筆事件扣「該股在事件所屬 p1/p2 期間、所有日子的平均 20 日報酬」;四段、全期都沿用各事件自己的 p1/p2 基準。
#   D. 貢獻最大 5 檔:全期 VC* 事件「(扣基準後報酬)− 同層同期 NV* 平均」按股票加總,取最大 5 檔,p1、p2 各自拿掉重算。
#   E. Q2 每段回檔:以 PX 事件 t0 為一段;[t0, t0+10] 內有 VC 事件 = 等到量縮(記延遲與進場價差),沒有 = 等不到。
#   F. 層的波動:訊號日 20 日波動在當天全體股票的百分位(qlib.VQ 同一式)。
import numpy as np, pandas as pd, json, os, sys, warnings; warnings.filterwarnings("ignore")
from numpy.lib.stride_tricks import sliding_window_view as swv
DT = os.environ.get("T30_DT", "/home/claude/work/t30")
START = "2004-01-01"; CUT = "2026-07-31"

def load(s):   # 與 research/flow_climate_2026-10/lib.py 的 load 同一式
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
spy = load("SPY"); cal = spy.index[spy.index >= START]
Pd = {k: {} for k in "OHLCV"}
for s in eq:
    d = load(s)
    if d is None or len(d) < 60: continue
    d = d.reindex(cal)
    for k, c in zip("OHLCV", "ohlcv"): Pd[k][s] = d[c]
O, H, L, C, V = [pd.DataFrame(Pd[k]).astype("float64") for k in "OHLCV"]
dates = C.index; cols = list(C.columns); n, m = C.shape
Q = load("QQQ").reindex(cal)

# ---------- 型態 ①② ----------
minL10 = L.rolling(10, min_periods=10).min()
maxC20 = C.shift(10).rolling(20, min_periods=20).max()
c1 = (minL10 <= maxC20 * 0.95)
Lv = L.values; W = swv(Lv, 10, axis=0)            # (n-9, m, 10):W[i] = 第 i..i+9 根(結尾 = t = i+9)
rev = W[:, :, ::-1]                               # 0 = t、1 = t−1 …
full = ~np.isnan(W).any(axis=2)
off = np.where(full, np.argmin(np.where(np.isnan(rev), np.inf, rev), axis=2), -1)   # 反轉後第一個最小 = 原本最後一次出現
c2a = np.zeros((n, m), bool); c2a[9:] = full & (off >= 3)                           # 低點日 ≤ t−3(並列取最後一次)
c2 = pd.DataFrame(c2a, index=dates, columns=cols)
raw = (c1 & c2 & C.notna()).fillna(False)

def cool(r, k=10):   # 已成立的候選日之後 k 根內不再成立(qlib.cool)
    a = r.values.astype(bool); out = np.zeros_like(a)
    for j in range(a.shape[1]):
        last = -10**9
        for i in np.flatnonzero(a[:, j]):
            if i - last > k: out[i, j] = True; last = i
    return pd.DataFrame(out, index=r.index, columns=r.columns)
def first(r, k=10):  # 前 k 根內原始條件都沒成立過(t29 的 first)
    return r & ~r.shift(1).fillna(False).astype(int).rolling(k, min_periods=1).max().astype(bool)

# ---------- 量比(只看候選日 t 當天)----------
v5 = V.rolling(5, min_periods=5).mean(); v20 = V.shift(5).rolling(20, min_periods=20).mean()
VR = (v5 / v20).where(v20 > 0)                    # 任一天缺量 → rolling 為 NaN;分母 0 → NaN = 量比未知

# ---------- 結果 / 層 ----------
G = np.log(C.shift(-20) / O.shift(-1))                                            # t+1 開盤買、t+20 收盤賣
MAE20 = np.log(L[::-1].rolling(20, min_periods=20).min()[::-1].shift(-1) / O.shift(-1))
S50, S200 = C.rolling(50).mean(), C.rolling(200).mean()
UT = ((C > S200) & (S50 > S200) & (S200 > S200.shift(20))).shift(1).fillna(False).astype(bool)
qd = (Q["c"] < Q["c"].rolling(20).mean())
QD = pd.DataFrame(np.repeat(qd.values[:, None], m, axis=1), index=dates, columns=cols)
vol20 = np.log(C).diff().rolling(20, min_periods=15).std(); VQ = vol20.rank(axis=1, pct=True)
STR = (UT.astype(int) * 4 + QD.astype(int) * 2 + (VQ >= 0.5).astype(int)).where(VQ.notna())
cost = lambda c: np.log((1 - c) / (1 + c))
dix = np.arange(n)
P1 = ("2009-07-01", "2017-12-31"); P2 = ("2018-01-01", CUT); ALL = ("2009-07-01", CUT)
SUB4 = [("2009-07-01", "2013-12-31"), ("2014-01-01", "2018-12-31"), ("2019-01-01", "2022-12-31"), ("2023-01-01", CUT)]
pm = lambda a, b: (dates >= pd.Timestamp(a)) & (dates <= pd.Timestamp(b))
per_of_i = np.where(dates < pd.Timestamp("2018-01-01"), 0, 1)                       # 0 = p1、1 = p2

# 個股基準:該股在 p1 / p2 所有日子的平均 20 日報酬
Gv = G.values
def stock_base(a, b):
    mk = pm(a, b)[:, None] & ~np.isnan(Gv); s = np.where(mk, Gv, 0).sum(0); c = mk.sum(0)
    return np.where(c > 0, s / np.maximum(c, 1), np.nan)
BASE = np.vstack([stock_base(*P1), stock_base(*P2)])                                # (2, m)

def events(cand):
    """候選日 → 事件表(只留 2009-07 起、結果完整的)"""
    A = cand.values.astype(bool).copy(); A[~pm("2009-07-01", "2099-12-31")] = False
    I, J = np.nonzero(A)
    e = pd.DataFrame({"i": I, "j": J, "date": dates[I], "tk": np.array(cols)[J], "vr": VR.values[I, J], "g": Gv[I, J],
                      "mae": MAE20.values[I, J], "s": STR.values[I, J], "per": per_of_i[I]})
    e["grp"] = np.where(e.vr.isna(), "未知", np.where(e.vr <= 0.8, "VC*", "NV*"))
    e["adj"] = e.g - BASE[e.per.values, e.j.values]
    return e

def strat(e, a, b, val="adj", min_n=10, drop=None):
    """分層加權 VC* − NV*(以 VC* 筆數加權);某層任一組 < min_n → 未配對"""
    x = e[(e.date >= a) & (e.date <= b) & e.g.notna() & (e.grp != "未知")]
    if drop: x = x[~x.tk.isin(drop)]
    unm_s = x[x.s.isna()]; x = x[x.s.notna()]
    num = den = 0.0; unm = len(unm_s); nv = nn = 0; layers = []
    for s, g in x.groupby("s"):
        a_ = g[g.grp == "VC*"][val].dropna(); b_ = g[g.grp == "NV*"][val].dropna()
        if len(a_) < min_n or len(b_) < min_n: unm += len(g); continue
        num += len(a_) * (a_.mean() - b_.mean()); den += len(a_); nv += len(a_); nn += len(b_)
        layers.append((int(s), len(a_), len(b_), a_.mean() * 100, b_.mean() * 100))
    return {"diff": num / den * 100 if den else np.nan, "nVC": nv, "nNV": nn, "unmatched": unm, "layers": layers}

def boot_ci(e, a, b, blk, reps=2000, seed=0, min_n=10):
    """日期區塊自助法:事件和用來扣的個股基準日一起重抽、重算(登記 v2 第 3.3 條)"""
    sel = (dix >= np.searchsorted(dates, pd.Timestamp(a))) & (dix <= np.searchsorted(dates, pd.Timestamp(b), side="right") - 1)
    B = dix // blk; ub = np.unique(B[sel]); bi = {b_: k for k, b_ in enumerate(ub)}; K = len(ub)
    # 個股日:各區塊 × 期間 × 股票 的 G 合計與筆數(只算 sel 期間內)
    SB = np.zeros((K, 2, m)); NB = np.zeros((K, 2, m))
    for i in np.flatnonzero(sel):
        g = Gv[i]; ok = ~np.isnan(g); k = bi[B[i]]; p = per_of_i[i]
        SB[k, p, ok] += g[ok]; NB[k, p, ok] += 1
    x = e[(e.date >= a) & (e.date <= b) & e.g.notna() & (e.grp != "未知") & e.s.notna()].copy()
    x["k"] = [bi[B[i]] for i in x.i]; x["gi"] = (x.grp == "NV*").astype(int); x["si"] = x.s.astype(int)
    SG = np.zeros((K, 8, 2)); CN = np.zeros((K, 8, 2)); NJ = np.zeros((K, 8, 2, 2, m))
    for r in x.itertuples():
        SG[r.k, r.si, r.gi] += r.g; CN[r.k, r.si, r.gi] += 1; NJ[r.k, r.si, r.gi, r.per, r.j] += 1
    rng = np.random.default_rng(seed); out = []
    NJf = NJ.reshape(K, -1)
    for _ in range(reps):
        w = np.bincount(rng.integers(0, K, K), minlength=K).astype(float)
        nb = np.tensordot(w, NB, 1); base = np.where(nb > 0, np.tensordot(w, SB, 1) / np.maximum(nb, 1), 0.0)   # (2, m)
        sg = np.tensordot(w, SG, 1); cn = np.tensordot(w, CN, 1)
        sub = (w @ NJf).reshape(8, 2, 2, m); adj = sg - (sub * base[None, None]).sum(axis=(2, 3))
        num = den = 0.0
        for s in range(8):
            if cn[s, 0] < min_n or cn[s, 1] < min_n: continue
            num += cn[s, 0] * (adj[s, 0] / cn[s, 0] - adj[s, 1] / cn[s, 1]); den += cn[s, 0]
        if den: out.append(num / den * 100)
    return tuple(np.percentile(out, [5, 95])), len(out)

def tail(e, a, b, drop=None):   # 分層加權「MAE20 跌 ≥10%」比例差(VC* − NV*)
    x = e.copy(); x["t10"] = (x.mae <= np.log(0.9)).astype(float).where(x.mae.notna())
    return strat(x, a, b, val="t10", drop=drop)

def run(cand, tag, verdict=True):
    e = events(cand)
    out = {"tag": tag}
    print(f"\n==== {tag} ====")
    cnt = e[(e.date <= CUT)].groupby("grp").size().to_dict()
    print(f"候選日(2009-07~{CUT}):{sum(cnt.values())} 筆;VC* {cnt.get('VC*', 0)}、NV* {cnt.get('NV*', 0)}、量比未知 {cnt.get('未知', 0)}")
    R = {}
    for nm, (a, b) in (("p1", P1), ("p2", P2), ("全期", ALL)):
        r = strat(e, a, b); R[nm] = r
        print(f"  {nm:4s} 分層加權 VC*−NV* {r['diff']:+.2f}%(VC* {r['nVC']}、NV* {r['nNV']},未配對 {r['unmatched']})")
        for s, a_, b_, ma, mb in r["layers"]:
            print(f"        層 UT={s // 4} QQQ<20日={(s // 2) % 2} 高波動={s % 2}:VC* {a_} 筆 {ma:+.2f}% / NV* {b_} 筆 {mb:+.2f}%")
    out["R"] = {k: {kk: vv for kk, vv in v.items() if kk != "layers"} for k, v in R.items()}
    if not verdict: return e, out
    ci = {}
    for blk in (40, 60):
        ci[blk], nrep = boot_ci(e, *ALL, blk); print(f"  全期 90% 區間({blk} 日區塊,2000 次,seed 0,有效 {nrep}):[{ci[blk][0]:+.2f}%, {ci[blk][1]:+.2f}%]")
    sub = []
    for a, b in SUB4:
        r = strat(e, a, b); ok = r["nVC"] >= 50 and r["nNV"] >= 50; sub.append((r["diff"], ok, r["nVC"], r["nNV"]))
        print(f"  {a[:7]}~{b[:7]}:VC*−NV* {r['diff']:+.2f}%(VC* {r['nVC']}、NV* {r['nNV']}{'' if ok else ',任一組 <50 → 算沒過'})")
    T = {nm: tail(e, a, b) for nm, (a, b) in (("p1", P1), ("p2", P2))}
    for nm in T: print(f"  {nm} 跌≥10% 比例 分層加權 VC*−NV* {T[nm]['diff']:+.2f} 個百分點")
    # 貢獻最大 5 檔(全期)
    x = e[(e.date >= ALL[0]) & (e.date <= ALL[1]) & e.g.notna() & (e.grp != "未知") & e.s.notna()].copy()
    nvm = x[x.grp == "NV*"].groupby(["per", "s"]).adj.mean()
    vc = x[x.grp == "VC*"].copy(); vc["ex"] = vc.adj - [nvm.get((p, s), np.nan) for p, s in zip(vc.per, vc.s)]
    top5 = list(vc.groupby("tk").ex.sum().sort_values(ascending=False).index[:5])
    D5 = {nm: strat(e, a, b, drop=top5) for nm, (a, b) in (("p1", P1), ("p2", P2))}
    print(f"  貢獻最大 5 檔 {top5};拿掉後 p1 {D5['p1']['diff']:+.2f}%、p2 {D5['p2']['diff']:+.2f}%")
    N25 = {}
    for nm, (a, b) in (("p1", P1), ("p2", P2)):
        y = e[(e.date >= a) & (e.date <= b) & (e.grp == "VC*") & e.g.notna()]
        N25[nm] = (y.g + cost(0.0025)).mean() * 100; n10 = (y.g + cost(0.001)).mean() * 100; w10 = ((y.g + cost(0.001)) > 0).mean() * 100
        wins = (y.g + cost(0.001))[(y.g + cost(0.001)) > 0]; loss = (y.g + cost(0.001))[(y.g + cost(0.001)) <= 0]
        print(f"  {nm} VC* 淨報酬 10bp {n10:+.2f}%(賺的比例 {w10:.1f}%,平均賺 {wins.mean() * 100:+.2f}% / 平均賠 {loss.mean() * 100:+.2f}%)、25bp {N25[nm]:+.2f}%(n={len(y)})")
        z = e[(e.date >= a) & (e.date <= b) & (e.grp == "NV*") & e.g.notna()]
        print(f"  {nm} NV* 淨報酬 10bp {(z.g + cost(0.001)).mean() * 100:+.2f}%(賺的比例 {((z.g + cost(0.001)) > 0).mean() * 100:.1f}%,n={len(z)})")
    enough = all(R[k]["nVC"] >= 200 and R[k]["nNV"] >= 200 for k in ("p1", "p2"))
    crit = [
        ("1 分層加權 VC*−NV* > 0(p1、p2)", R["p1"]["diff"] > 0 and R["p2"]["diff"] > 0, f"{R['p1']['diff']:+.2f}% / {R['p2']['diff']:+.2f}%"),
        ("2 全期 90% 區間下緣 > 0(40、60 日區塊)", ci[40][0] > 0 and ci[60][0] > 0, f"40日 {ci[40][0]:+.2f}%、60日 {ci[60][0]:+.2f}%"),
        ("3 四段至少 3 段 > 0(任一組 <50 算沒過)", sum(1 for d, ok, _, _ in sub if ok and d > 0) >= 3, " / ".join(f"{d:+.2f}%" + ("" if ok else "(樣本不足)") for d, ok, _, _ in sub)),
        ("4 跌≥10% 比例:VC* 不高於 NV*(p1、p2)", T["p1"]["diff"] <= 0 and T["p2"]["diff"] <= 0, f"{T['p1']['diff']:+.2f} / {T['p2']['diff']:+.2f} 個百分點"),
        ("5 拿掉前 5 檔仍 > 0,且每邊 25bp VC* 淨報酬 > 0(p1、p2)", D5["p1"]["diff"] > 0 and D5["p2"]["diff"] > 0 and N25["p1"] > 0 and N25["p2"] > 0,
         f"拿掉後 {D5['p1']['diff']:+.2f}% / {D5['p2']['diff']:+.2f}%;25bp {N25['p1']:+.2f}% / {N25['p2']:+.2f}%"),
    ]
    print(f"\n  樣本下限(p1、p2 各 VC* ≥200、NV* ≥200,扣掉未知與未配對):{'夠' if enough else '不夠'}"
          f"(p1 {R['p1']['nVC']}/{R['p1']['nNV']}、p2 {R['p2']['nVC']}/{R['p2']['nNV']})")
    print("  判定(登記 v2 第 4 節,5 條全部要過):")
    for k, ok, v in crit: print(f"    {'過' if ok else '沒過'}  {k}:{v}")
    passed = enough and all(ok for _, ok, _ in crit)
    print("  結論:" + ("樣本不足,不判定" if not enough else ("全部通過 → 只寫成提案,由使用者決定;網站不改" if passed else "未取得符合門檻的增量證據")))
    out.update(ci=ci, sub=sub, tail={k: v["diff"] for k, v in T.items()}, top5=top5, drop5={k: v["diff"] for k, v in D5.items()},
               net25=N25, enough=enough, crit=[(k, ok, v) for k, ok, v in crit], passed=passed)
    return e, out

print(f"資料:Yahoo 調整後日K {dates[0].date()}~{dates[-1].date()};股票 {m} 檔(名單重建,見檔頭 A);判定只用 ≤{CUT} 的訊號;"
      f"報酬 = t+1 開盤買、t+20 收盤賣(log)")
CAND = cool(raw, 10)
e_main, OUT = run(CAND, "Q1 主判定(冷卻 = 前 10 根內沒有已成立的候選日)")
# 2026-10-11 19:40 看完主判定後追加(事後決定,只描述、不改主判定):原版 v1 寫「同一段只算第一天」,冷卻寫法有兩種讀法,
# 敏感度也照 5 條完整算一次,兩種結果並列。
e_alt, OUT2 = run(first(raw, 10), "敏感度(事後追加,只描述、不參與判定):冷卻 = 前 10 根內 ①② 都沒成立過(原版 v1「同一段只算第一天」)", verdict=True)

# ---------- 2026-08 以後(看過案例的期間;只單獨列)----------
x = e_main[(e_main.date >= "2026-08-01")]
print(f"\n2026-08 以後(只單獨列):候選日 {len(x)};VC* {int((x.grp == 'VC*').sum())}、NV* {int((x.grp == 'NV*').sum())};"
      f"已有 20 日結果:VC* {x[(x.grp == 'VC*') & x.g.notna()].g.mean() * 100:+.2f}%(n={int(((x.grp == 'VC*') & x.g.notna()).sum())})、"
      f"NV* {x[(x.grp == 'NV*') & x.g.notna()].g.mean() * 100:+.2f}%(n={int(((x.grp == 'NV*') & x.g.notna()).sum())})(毛報酬)")

# ---------- Q2 政策版(只描述)----------
VCs = cool(raw & (VR <= 0.8), 10); PXs = cool(raw, 10)
print("\n==== Q2 政策版(只描述,不判定):VC(①②③ 自己冷卻)vs PX(①② 自己冷卻) ====")
for nm, (a, b) in (("p1", P1), ("p2", P2), ("全期", ALL)):
    for lab, S in (("VC", VCs), ("PX", PXs)):
        A = S.values & pm(a, b)[:, None]; I, J = np.nonzero(A); g = Gv[I, J]; ok = ~np.isnan(g); g = g[ok] + cost(0.001)
        mae = MAE20.values[I, J][ok]
        print(f"  {nm:4s} {lab}:n={len(g)} 淨報酬 10bp {g.mean() * 100:+.2f}% 賺的比例 {(g > 0).mean() * 100:.1f}%"
              f" 平均賺 {g[g > 0].mean() * 100:+.2f}% / 平均賠 {g[g <= 0].mean() * 100:+.2f}% 跌≥10% {(mae <= np.log(0.9)).mean() * 100:.1f}%")
A = PXs.values & pm(*ALL)[:, None]; I, J = np.nonzero(A); VCa = VCs.values
delay, pdiff, matched_g, unmatched_g = [], [], [], []
Ov = O.values
for i, j in zip(I, J):
    hit = np.flatnonzero(VCa[i:min(n, i + 11), j])
    g = Gv[i, j]
    if len(hit):
        k = i + hit[0]; dd = hit[0]
        pdv = Ov[k + 1, j] / Ov[i + 1, j] - 1 if (k + 1 < n and not np.isnan(Ov[k + 1, j]) and not np.isnan(Ov[i + 1, j])) else np.nan
        delay.append(dd); pdiff.append(pdv)
        if not np.isnan(g): matched_g.append(g)
    elif not np.isnan(g): unmatched_g.append(g)
delay = np.array(delay); pdiff = np.array(pdiff); later = delay > 0
print(f"  每段回檔(PX 事件 {len(I)} 段,2009-07~{CUT}):{len(delay)} 段在 10 根內等到量縮({len(delay) / max(1, len(I)) * 100:.0f}%),"
      f"其中當天就量縮 {(delay == 0).mean() * 100:.0f}%;有等的那些平均晚 {delay[later].mean():.1f} 天、進場價平均 {np.nanmean(pdiff[later]) * 100:+.2f}%(負 = 等了買得比較便宜)")
print(f"  等不到量縮的 {len(I) - len(delay)} 段:PX 之後 20 日毛報酬 {np.mean(unmatched_g) * 100:+.2f}%(n={len(unmatched_g)});"
      f"等得到的:{np.mean(matched_g) * 100:+.2f}%(n={len(matched_g)})")
json.dump({"main": {k: v for k, v in OUT.items()}, "alt": OUT2, "n_stocks": m, "data_end": str(dates[-1].date())},
          open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "t30_volume_v2.json"), "w"), ensure_ascii=False, indent=1, default=str)
