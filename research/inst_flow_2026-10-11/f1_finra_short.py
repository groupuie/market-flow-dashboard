# f1:FINRA 場外放空量比例(SVR5)→ 之後 2 週 / 波段報酬 —— 完全照 f1_prereg_finra_short.md(commit d597067)執行。
# 不論通過與否,結果都存 f1_finra_short.log / .json。主判定:h = 10 的 Q1 − Q5(市場中性)、訊號 2018-08-01~2026-07-31。
#
# 跑之前就決定、寫在這裡的執行細節(登記文件沒寫死的地方;看結果前定案,看結果後不改):
#   A. 名單:與 t30 v2 完全相同(meta.json 中 Yahoo instrumentType = EQUITY、日K ≥ 60 根 → 266 檔);價格 = 同一個 load()。
#   B. 日曆:SPY 交易日。FINRA 某天缺檔或某股當天沒列 → 該股該日比例 = 缺值(算進「5 天至少 4 天」的規則)。
#      股票改名前的 FINRA 代號對不到(例如 FB→META)→ 那段只是少樣本,不補對照表。
#   C. 分組:每天取「訊號有值且該期限結果有值」的股票;少於 25 檔的日子不分組。按訊號由小到大排(同值按欄位順序),
#      第 k 名(0 起算)→ 組別 floor(k × 5 ÷ N);0 = Q1(放空比例最低)、4 = Q5(最高)。
#   D. 市場中性:減掉同一天「名單內所有該期限結果有值的股票」的等權平均(不管有沒有訊號)。
#   E. 區塊自助法:區塊 = 日曆序號 ÷ 區塊長度(與 t30 v2 相同的切法),只用期間內、當天 Q1 − Q5 有值的日子;
#      每次有放回地抽 K 個區塊(K = 期間內區塊數),統計量 = 抽到的日子的 Q1 − Q5 平均(依天數加權)。
#   F. 給使用者看的數字:每筆 = 單一股票單一訊號日;淨報酬 = exp(G) − 1 − 0.20%(每邊 10 bp);賺錢 = 淨報酬 > 0;
#      「平均賺」= 賺錢那些的平均、「平均賠」= 其餘的平均。訊號天天有、持有期重疊,筆數不是獨立樣本。
#   G. 期間、四小段都按「訊號日」切。
import numpy as np, pandas as pd, json, os, glob, sys, warnings; warnings.filterwarnings("ignore")
DT = os.environ.get("T30_DT", "/home/claude/work/t30")
FD = os.environ.get("F1_FINRA", "/home/claude/work/finra/days")
HERE = os.path.dirname(os.path.abspath(__file__))
START = "2004-01-01"
PA = ("2018-08-01", "2022-12-31"); PB = ("2023-01-01", "2026-07-31"); ALL = ("2018-08-01", "2026-07-31")
SUBS = [("2018-08~2019", "2018-08-01", "2019-12-31"), ("2020~2021", "2020-01-01", "2021-12-31"),
        ("2022~2023", "2022-01-01", "2023-12-31"), ("2024~2026-07", "2024-01-01", "2026-07-31")]
COST_RT = 0.0040        # 判定第 4 條:兩邊各一買一賣、每邊 10 bp
FEE_TRADE = 0.0020      # 單筆來回(每邊 10 bp)
MIN_N = 25; REPS = 2000; SEED = 0

def load(s):   # 與 t30_volume_v2.py 的 load 同一式
    p = os.path.join(DT, "yh", s.replace("^", "_").replace("=", "_") + ".pkl")
    if not os.path.exists(p): return None
    df = pd.read_pickle(p); df = df[df.index >= START]
    f = (df["ac"] / df["c"]).replace([np.inf, -np.inf], np.nan).fillna(1.0)
    out = pd.DataFrame({"o": df["o"] * f, "h": df["h"] * f, "l": df["l"] * f, "c": df["ac"], "v": df["v"]})
    for k in ("o", "h", "l"):
        bad = out[k].isna() | (out[k] <= 0); out.loc[bad, k] = out.loc[bad, "c"]
    out["h"] = out[["h", "o", "c"]].max(axis=1); out["l"] = out[["l", "o", "c"]].min(axis=1)
    return out

LOG = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); LOG.append(s)

meta = json.load(open(os.path.join(DT, "meta.json")))
eq = sorted(s for s, v in meta.items() if v.get("type") == "EQUITY")
spy = load("SPY"); cal = spy.index[spy.index >= START]
Pd = {"O": {}, "C": {}}
for s in eq:
    d = load(s)
    if d is None or len(d) < 60: continue
    d = d.reindex(cal); Pd["O"][s] = d["o"]; Pd["C"][s] = d["c"]
O = pd.DataFrame(Pd["O"]).astype("float64"); C = pd.DataFrame(Pd["C"]).astype("float64")
dates = C.index; cols = list(C.columns); n, m = C.shape
P(f"名單 {m} 檔;日曆 {dates[0].date()}~{dates[-1].date()}({n} 天)")

# ---------- FINRA 每日比例 ----------
fs = sorted(glob.glob(os.path.join(FD, "*.csv")))
parts = []
for f in fs:
    x = pd.read_csv(f, sep="|", dtype={"Date": str, "Symbol": str})
    parts.append(x[["Date", "Symbol", "ShortVolume", "TotalVolume"]])
F = pd.concat(parts, ignore_index=True)
F["Date"] = pd.to_datetime(F["Date"], format="%Y%m%d")
F = F[F.Symbol.isin(cols) & (F.TotalVolume > 0)]
F = F.groupby(["Date", "Symbol"], as_index=False)[["ShortVolume", "TotalVolume"]].sum()   # 保險:同日同股合併
F["r"] = F.ShortVolume / F.TotalVolume
fin_days = pd.DatetimeIndex(sorted(F.Date.unique()))
off_cal = fin_days.difference(dates)
R = F.pivot(index="Date", columns="Symbol", values="r").reindex(index=dates, columns=cols)
P(f"FINRA 檔 {len(fs)} 個;{fin_days[0].date()}~{fin_days[-1].date()};不在 SPY 日曆的 FINRA 日 {len(off_cal)} 個 {list(map(str, off_cal.date))[:5]}")
cal_in = dates[(dates >= fin_days[0]) & (dates <= fin_days[-1])]
P(f"同期 SPY 交易日 {len(cal_in)} 天;FINRA 缺的交易日 {len(cal_in.difference(fin_days))} 個 {list(map(str, cal_in.difference(fin_days).date))[:8]}")
P(f"比例 r 全體:中位數 {np.nanmedian(R.values):.3f}、10%/90% 分位 {np.nanpercentile(R.values, 10):.3f}/{np.nanpercentile(R.values, 90):.3f}")

# ---------- 訊號 ----------
SVR5 = R.rolling(5, min_periods=4).mean()
SVR20 = R.rolling(20, min_periods=15).mean()
DSVR = SVR5 - R.shift(5).rolling(60, min_periods=45).mean()
SIG = {"SVR5": SVR5, "SVR20": SVR20, "ΔSVR": DSVR}

# ---------- 結果 ----------
def G_of(h): return np.log(C.shift(-h) / O.shift(-1))
GH = {h: G_of(h) for h in (10, 20, 40)}
GMN = {h: g.sub(g.mean(axis=1), axis=0) for h, g in GH.items()}

i_lo = np.searchsorted(dates, pd.Timestamp(ALL[0])); i_hi = np.searchsorted(dates, pd.Timestamp(ALL[1]), side="right") - 1
px_ok = C.notna() & O.shift(-1).notna()
cov = (SVR5.notna() & px_ok).iloc[i_lo:i_hi + 1].values.sum() / max(px_ok.iloc[i_lo:i_hi + 1].values.sum(), 1)
P(f"訊號期 {dates[i_lo].date()}~{dates[i_hi].date()}:有價格的股票日中,SVR5 有值的比例 {cov * 100:.1f}%")

def quint(sig, h):
    """每天分五組 → 回傳 (組別矩陣 q[n,m] = −1 不分組, 每天 Q1、Q5、全部 市場中性平均, 每天 N)"""
    S = sig.values; Gm = GMN[h].values; Gr = GH[h].values
    ok = ~np.isnan(S) & ~np.isnan(Gr)
    q = np.full((n, m), -1, int); N = ok.sum(1)
    q1 = np.full(n, np.nan); q5 = np.full(n, np.nan); mid = np.full(n, np.nan)
    for i in range(i_lo, i_hi + 1):
        if N[i] < MIN_N: continue
        js = np.flatnonzero(ok[i]); order = js[np.argsort(S[i, js], kind="stable")]
        g = (np.arange(len(order)) * 5) // len(order); q[i, order] = g
        q1[i] = Gm[i, order[g == 0]].mean(); q5[i] = Gm[i, order[g == 4]].mean()
    return q, q1, q5, N

def pmask(a, b):
    return (dates >= pd.Timestamp(a)) & (dates <= pd.Timestamp(b))

def boot(D, a, b, blk):
    sel = pmask(a, b) & ~np.isnan(D)
    idx = np.flatnonzero(sel); B = idx // blk; ub, inv = np.unique(B, return_inverse=True); K = len(ub)
    S = np.bincount(inv, weights=D[idx], minlength=K); Nn = np.bincount(inv, minlength=K).astype(float)
    rng = np.random.default_rng(SEED); out = np.empty(REPS)
    for r in range(REPS):
        w = np.bincount(rng.integers(0, K, K), minlength=K).astype(float)
        out[r] = (w @ S) / (w @ Nn)
    lo, hi = np.percentile(out, [5, 95]); return lo * 100, hi * 100, K

def pm_mean(x, a, b):
    s = pmask(a, b) & ~np.isnan(x); return (x[s].mean() * 100 if s.any() else np.nan), int(s.sum())

def summarize(sname, h, ci=True):
    q, q1, q5, N = quint(SIG[sname], h); D = q1 - q5
    res = {"sig": sname, "h": h}
    for nm, (a, b) in (("A", PA), ("B", PB), ("全期", ALL)):
        d, nd = pm_mean(D, a, b); r1, _ = pm_mean(q1, a, b); r5, _ = pm_mean(q5, a, b)
        res[nm] = {"Q1-Q5": d, "Q1": r1, "Q5": r5, "days": nd}
        if ci:
            for blk in (40, 60):
                lo, hi, K = boot(D, a, b, blk); res[nm][f"ci{blk}"] = [lo, hi]; res[nm][f"K{blk}"] = K
    res["subs"] = {}
    for nm, a, b in SUBS:
        d, nd = pm_mean(D, a, b); res["subs"][nm] = {"Q1-Q5": d, "days": nd}
    sm = pmask(*ALL)
    res["N_per_day"] = {"median": float(np.median(N[sm & (N >= MIN_N)])) if (sm & (N >= MIN_N)).any() else None,
                        "min": int(N[sm & (N >= MIN_N)].min()) if (sm & (N >= MIN_N)).any() else None}
    Sv = SIG[sname].values
    res["level"] = {"Q1": float(np.nanmean(np.where(q == 0, Sv, np.nan)[sm])), "Q5": float(np.nanmean(np.where(q == 4, Sv, np.nan)[sm]))}
    return res, q, D

def show(res, label):
    P(f"\n---- {label}(訊號 {res['sig']}、h = {res['h']};市場中性、% / 筆) ----")
    P(f"每天分組股票數:中位數 {res['N_per_day']['median']}、最少 {res['N_per_day']['min']};"
      f"組內平均訊號值 Q1 {res['level']['Q1']:.4f}、Q5 {res['level']['Q5']:.4f}")
    for nm in ("A", "B", "全期"):
        r = res[nm]; ci = "".join(f"、90% 區間({k} 日區塊) [{r[f'ci{k}'][0]:+.3f}, {r[f'ci{k}'][1]:+.3f}]" for k in (40, 60) if f"ci{k}" in r)
        P(f"  {nm:<3} Q1 − Q5 = {r['Q1-Q5']:+.3f}%(Q1 {r['Q1']:+.3f}、Q5 {r['Q5']:+.3f};{r['days']} 天){ci}")
    P("  四小段 Q1 − Q5:" + ";".join(f"{k} {v['Q1-Q5']:+.3f}%({v['days']} 天)" for k, v in res["subs"].items()))

def verdict(res):
    A = res["A"]["Q1-Q5"]; B = res["B"]["Q1-Q5"]; F_ = res["全期"]
    subs = [v["Q1-Q5"] for v in res["subs"].values()]
    pos = [bool(A > 0 and B > 0), bool(F_["ci40"][0] > 0 and F_["ci60"][0] > 0), bool(sum(s > 0 for s in subs) >= 3), bool(F_["Q1-Q5"] > COST_RT * 100)]
    neg = [bool(A < 0 and B < 0), bool(F_["ci40"][1] < 0 and F_["ci60"][1] < 0), bool(sum(s < 0 for s in subs) >= 3), bool(F_["Q1-Q5"] < -COST_RT * 100)]
    if all(pos): v = "支持:放空比例低的股票之後 2 週較強(只寫提案,網站不改)"
    elif all(neg): v = "支持 DIX 說法:放空比例高反而較強(只寫提案,網站不改)"
    else: v = "未取得符合門檻的證據"
    return pos, neg, v

def user_metrics(q, h, a, b):
    Gr = GH[h].values; sm = pmask(a, b)[:, None]; out = {}
    for nm, mk in (("只買 Q1(放空比例最低)", q == 0), ("只買 Q5(放空比例最高)", q == 4), ("全部(有分組的)", q >= 0)):
        g = Gr[mk & sm & ~np.isnan(Gr)]; net = np.exp(g) - 1 - FEE_TRADE
        w = net > 0
        out[nm] = {"筆數": int(len(net)), "賺錢比例": float(w.mean() * 100), "平均賺": float(net[w].mean() * 100),
                   "平均賠": float(net[~w].mean() * 100), "平均淨報酬": float(net.mean() * 100),
                   "賺賠比": float(net[w].mean() / -net[~w].mean())}
    return out

OUT = {"prereg": "f1_prereg_finra_short.md @ d597067", "universe": m, "finra_files": len(fs),
       "finra_range": [str(fin_days[0].date()), str(fin_days[-1].date())], "svr5_coverage": cov}

P("\n==== 主判定:H1(SVR5、h = 10)====")
r10, q10, D10 = summarize("SVR5", 10); show(r10, "主假設")
pos, neg, v = verdict(r10)
P(f"  判定四條(正方向):①A、B 都 > 0 {pos[0]};②全期區間下緣 > 0(40 與 60){pos[1]};③四小段 ≥ 3 段 > 0 {pos[2]};④全期 > 0.40% {pos[3]}")
P(f"  鏡像四條(反方向):{neg}")
P(f"  ⇒ 結論:{v}")
OUT["H1"] = r10; OUT["H1_pass"] = pos; OUT["H1_mirror"] = neg; OUT["verdict"] = v

P("\n==== 只描述、不判定 ====")
r40, q40, D40 = summarize("SVR5", 40); show(r40, "波段期限 h = 40"); OUT["h40"] = r40
r20, _, _ = summarize("SVR5", 20); show(r20, "h = 20(只描述)"); OUT["h20"] = r20
for s in ("SVR20", "ΔSVR"):
    for h in (10, 40):
        rr, _, _ = summarize(s, h); show(rr, f"次訊號 {s}"); OUT[f"{s}_h{h}"] = rr

P("\n==== 給使用者看的實戰數字(原始報酬、每邊 10 bp;每筆 = 一檔股票一個訊號日,持有期重疊)====")
OUT["user"] = {}
for h, q in ((10, q10), (40, q40)):
    for nm, (a, b) in (("全期", ALL), ("A", PA), ("B", PB)):
        um = user_metrics(q, h, a, b); OUT["user"][f"h{h}_{nm}"] = um
        P(f"  h = {h}、{nm}:")
        for k, x in um.items():
            P(f"    {k:<16} 筆數 {x['筆數']:>7}|賺錢比例 {x['賺錢比例']:5.1f}%|平均賺 {x['平均賺']:+6.2f}%|平均賠 {x['平均賠']:+6.2f}%"
              f"|賺賠比 {x['賺賠比']:.2f}|平均淨報酬 {x['平均淨報酬']:+6.3f}%")

json.dump(OUT, open(os.path.join(HERE, "f1_finra_short.json"), "w"), ensure_ascii=False, indent=1, default=float)
open(os.path.join(HERE, "f1_finra_short.log"), "w").write("\n".join(LOG) + "\n")
P("\n存檔:f1_finra_short.log / f1_finra_short.json")
