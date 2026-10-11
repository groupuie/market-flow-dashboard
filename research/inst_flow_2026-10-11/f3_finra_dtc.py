# f3:FINRA 空單回補天數(DTC)→ 之後 2 週 / 1 個月報酬 —— 完全照 f3_prereg_finra_dtc.md 執行(與本腳本同一個 commit、跑之前)。
# 不論通過與否,結果都存 f3_finra_dtc.log / .json。
#
# 跑之前就決定、寫在這裡的執行細節:
#   A. 名單、價格、load()、分五組方法(每個訊號日 ≥ 25 檔、穩定排序、floor(k×5÷N))、市場中性都與 f1 相同。
#   B. 結算日不在 SPY 日曆時,取其後第一個交易日當「結算日位置」,再往後數 8 個交易日 = 訊號日 t。
#   C. 同檔同結算日只有一筆 → 直接用 FINRA 的 daysToCoverQuantity;多筆 → 空單、日均量各自加總後相除。
#   D. 區塊 = 全部訊號日依時間排序後的序號 ÷ 區塊長度;只用期間內、當天 Q1 − Q5 有值的訊號日。
#   E. 資料抓取:dl_si.py(每檔一個 POST,免金鑰),原始 JSON 存在研究機外的工作資料夾,不進 repo。
import numpy as np, pandas as pd, json, os, glob, warnings; warnings.filterwarnings("ignore")
DT = os.environ.get("T30_DT", "/home/claude/work/t30")
SD = os.environ.get("F3_SI", "/home/claude/work/finra_si/raw")
HERE = os.path.dirname(os.path.abspath(__file__))
START = "2004-01-01"; LAG = 8
PA = ("2017-12-01", "2022-12-31"); PB = ("2023-01-01", "2026-07-31"); ALL = ("2017-12-01", "2026-07-31")
SUBS = [("2018~2019", "2017-12-01", "2019-12-31"), ("2020~2021", "2020-01-01", "2021-12-31"),
        ("2022~2023", "2022-01-01", "2023-12-31"), ("2024~2026-07", "2024-01-01", "2026-07-31")]
COST_RT = 0.0040; FEE_TRADE = 0.0020; MIN_N = 25; REPS = 2000; SEED = 0

def load(s):   # 與 f1 / t30_volume_v2.py 的 load 同一式
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
dates = C.index; cols = list(C.columns); n, m = C.shape; cix = {s: j for j, s in enumerate(cols)}

# ---------- 空單資料 ----------
rows = []
for f in sorted(glob.glob(os.path.join(SD, "*.json"))):
    for r in json.load(open(f)) or []:
        if r.get("symbolCode") in cix: rows.append(r)
S = pd.DataFrame(rows)
P(f"名單 {m} 檔;空單紀錄 {len(S)} 筆、{S.symbolCode.nunique()} 檔、結算日 {S.settlementDate.min()}~{S.settlementDate.max()};"
  f"FINRA 更正旗標 {int(S.revisionFlag.notna().sum())} 筆")
S["si"] = pd.to_numeric(S.currentShortPositionQuantity, errors="coerce"); S["adv"] = pd.to_numeric(S.averageDailyVolumeQuantity, errors="coerce")
S["prev"] = pd.to_numeric(S.previousShortPositionQuantity, errors="coerce"); S["dtc0"] = pd.to_numeric(S.daysToCoverQuantity, errors="coerce")
g = S.groupby(["settlementDate", "symbolCode"])
A = g.agg(si=("si", "sum"), adv=("adv", "sum"), prev=("prev", "sum"), dtc0=("dtc0", "first"), k=("si", "size")).reset_index()
A["dtc"] = np.where(A.k == 1, A.dtc0, np.where(A.adv > 0, A.si / A.adv, np.nan))
A.loc[~(A.adv > 0), "dtc"] = np.nan
A["dsi"] = np.where((A.si > 0) & (A.prev > 0), np.log(A.si.clip(lower=1) / A.prev.clip(lower=1)), np.nan)
P(f"同檔同結算日多筆(已加總):{int((A.k > 1).sum())} 組;DTC 中位數 {A.dtc.median():.2f} 天、10%/90% 分位 {A.dtc.quantile(.1):.2f}/{A.dtc.quantile(.9):.2f}")

# 結算日 → 訊號日
setts = sorted(A.settlementDate.unique())
sig_i = {}
for sd in setts:
    p0 = int(np.searchsorted(dates, pd.Timestamp(sd)))
    if p0 + LAG < n: sig_i[sd] = p0 + LAG

def G_of(h): return np.log(C.shift(-h) / O.shift(-1))
GH = {h: G_of(h).values for h in (10, 20)}
GMN = {h: GH[h] - np.nanmean(GH[h], axis=1, keepdims=True) for h in GH}

def build(sig, h):
    """每個結算日 → (訊號日序號 i, Q1 平均, Q5 平均, D, N, 分組表)"""
    out = []; trades = []
    for sd in setts:
        if sd not in sig_i: continue
        i = sig_i[sd]; x = A[A.settlementDate == sd]
        js = np.array([cix[s] for s in x.symbolCode]); v = x[sig].values
        ok = ~np.isnan(v) & ~np.isnan(GH[h][i, js])
        js, v = js[ok], v[ok]
        if len(js) < MIN_N: continue
        order = np.argsort(v, kind="stable"); jo = js[order]
        q = (np.arange(len(jo)) * 5) // len(jo)
        q1 = GMN[h][i, jo[q == 0]].mean(); q5 = GMN[h][i, jo[q == 4]].mean()
        out.append({"sd": sd, "i": i, "date": dates[i], "q1": q1, "q5": q5, "D": q1 - q5, "N": len(jo),
                    "lv1": float(v[order][q == 0].mean()), "lv5": float(v[order][q == 4].mean())})
        for qq, j in zip(q, jo): trades.append((i, j, qq))
    T = pd.DataFrame(out); T["ord"] = np.arange(len(T)); return T, np.array(trades)

def pmean(T, a, b, col="D"):
    x = T[(T.date >= pd.Timestamp(a)) & (T.date <= pd.Timestamp(b))][col].dropna(); return x.mean() * 100, len(x)
def boot(T, a, b, blk):
    x = T[(T.date >= pd.Timestamp(a)) & (T.date <= pd.Timestamp(b)) & T.D.notna()]
    ub, inv = np.unique(x.ord.values // blk, return_inverse=True); K = len(ub)
    Ssum = np.bincount(inv, weights=x.D.values, minlength=K); Nn = np.bincount(inv, minlength=K).astype(float)
    rng = np.random.default_rng(SEED); out = np.empty(REPS)
    for r in range(REPS):
        w = np.bincount(rng.integers(0, K, K), minlength=K).astype(float); out[r] = (w @ Ssum) / (w @ Nn)
    lo, hi = np.percentile(out, [5, 95]); return lo * 100, hi * 100, K

def summarize(sig, h):
    T, TR = build(sig, h); res = {"sig": sig, "h": h}
    for nm, (a, b) in (("A", PA), ("B", PB), ("全期", ALL)):
        d_, k = pmean(T, a, b); r1, _ = pmean(T, a, b, "q1"); r5, _ = pmean(T, a, b, "q5")
        res[nm] = {"Q1-Q5": d_, "Q1": r1, "Q5": r5, "dates": k}
        for blk in (4, 6):
            lo, hi, K = boot(T, a, b, blk); res[nm][f"ci{blk}"] = [lo, hi]; res[nm][f"K{blk}"] = K
    res["subs"] = {nm: {"Q1-Q5": pmean(T, a, b)[0], "dates": pmean(T, a, b)[1]} for nm, a, b in SUBS}
    sel = (T.date >= pd.Timestamp(ALL[0])) & (T.date <= pd.Timestamp(ALL[1]))
    res["N_per_date"] = {"median": float(T[sel].N.median()), "min": int(T[sel].N.min())}
    res["level"] = {"Q1": float(T[sel].lv1.mean()), "Q5": float(T[sel].lv5.mean())}
    res["first_last"] = [str(T[sel].date.min().date()), str(T[sel].date.max().date())]
    return res, T, TR

def show(res, label):
    P(f"\n---- {label}(訊號 {res['sig']}、h = {res['h']};市場中性、% / 筆) ----")
    P(f"訊號日 {res['first_last'][0]}~{res['first_last'][1]};每個訊號日分組股票數:中位數 {res['N_per_date']['median']}、最少 {res['N_per_date']['min']};"
      f"組內平均訊號 Q1 {res['level']['Q1']:.3f}、Q5 {res['level']['Q5']:.3f}")
    for nm in ("A", "B", "全期"):
        r = res[nm]; ci = "".join(f"、90% 區間({k} 個訊號日一塊,{r[f'K{k}']} 塊) [{r[f'ci{k}'][0]:+.3f}, {r[f'ci{k}'][1]:+.3f}]" for k in (4, 6))
        P(f"  {nm:<3} Q1 − Q5 = {r['Q1-Q5']:+.3f}%(Q1 {r['Q1']:+.3f}、Q5 {r['Q5']:+.3f};{r['dates']} 個訊號日){ci}")
    P("  四小段 Q1 − Q5:" + ";".join(f"{k} {v['Q1-Q5']:+.3f}%({v['dates']} 個)" for k, v in res["subs"].items()))

def user_metrics(TR, h, a, b):
    out = {}; i, j, q = TR[:, 0], TR[:, 1], TR[:, 2]
    dsel = (dates[i] >= pd.Timestamp(a)) & (dates[i] <= pd.Timestamp(b))
    for nm, mk in (("只買 Q1(回補天數最低)", q == 0), ("只買 Q5(回補天數最高)", q == 4), ("全部(有分組的)", q >= 0)):
        gsel = mk & dsel; gg = GH_cur[i[gsel], j[gsel]]; gg = gg[~np.isnan(gg)]
        net = np.exp(gg) - 1 - FEE_TRADE; w = net > 0
        out[nm] = {"筆數": int(len(net)), "賺錢比例": float(w.mean() * 100), "平均賺": float(net[w].mean() * 100),
                   "平均賠": float(net[~w].mean() * 100), "平均淨報酬": float(net.mean() * 100), "賺賠比": float(net[w].mean() / -net[~w].mean())}
    return out

OUT = {"prereg": "f3_prereg_finra_dtc.md", "universe": m, "records": int(len(S)), "symbols": int(S.symbolCode.nunique()),
       "settlement_range": [S.settlementDate.min(), S.settlementDate.max()], "revision_flags": int(S.revisionFlag.notna().sum())}
P("\n==== 主判定:H3(DTC、h = 10)====")
r10, T10, TR10 = summarize("dtc", 10); show(r10, "主假設")
A_, B_, F_ = r10["A"]["Q1-Q5"], r10["B"]["Q1-Q5"], r10["全期"]; subs = [v["Q1-Q5"] for v in r10["subs"].values()]
pos = [bool(A_ > 0 and B_ > 0), bool(F_["ci4"][0] > 0 and F_["ci6"][0] > 0), bool(sum(s > 0 for s in subs) >= 3), bool(F_["Q1-Q5"] > COST_RT * 100)]
neg = [bool(A_ < 0 and B_ < 0), bool(F_["ci4"][1] < 0 and F_["ci6"][1] < 0), bool(sum(s < 0 for s in subs) >= 3), bool(F_["Q1-Q5"] < -COST_RT * 100)]
v = ("支持:回補天數高的股票之後 2 週較弱(避開名單候選;只寫提案,網站不改)" if all(pos) else
     "反向:回補天數高的反而較強(軋空;只寫提案)" if all(neg) else "未取得符合門檻的證據")
P(f"  判定四條:①A、B 都 > 0 {pos[0]};②全期區間下緣 > 0(4、6){pos[1]};③四小段 ≥ 3 段 > 0 {pos[2]};④全期 > 0.40% {pos[3]}")
P(f"  鏡像四條:{neg}"); P(f"  ⇒ 結論:{v}")
OUT.update({"H3": r10, "H3_pass": pos, "H3_mirror": neg, "verdict": v})

P("\n==== 只描述、不判定 ====")
r20, T20, TR20 = summarize("dtc", 20); show(r20, "h = 20(約 1 個月波段)"); OUT["h20"] = r20
for h in (10, 20):
    rr, _, _ = summarize("dsi", h); show(rr, "次訊號 ΔSI(空單比上期增加多少;Q1 = 減最多)"); OUT[f"dsi_h{h}"] = rr

P("\n==== 實戰數字(原始報酬、每邊 10 bp;每筆 = 一檔一個訊號日)====")
OUT["user"] = {}
for h, TR in ((10, TR10), (20, TR20)):
    GH_cur = GH[h]
    for nm, (a, b) in (("全期", ALL), ("A", PA), ("B", PB)):
        um = user_metrics(TR, h, a, b); OUT["user"][f"h{h}_{nm}"] = um
        P(f"  h = {h}、{nm}:")
        for k, x in um.items():
            P(f"    {k:<16} 筆數 {x['筆數']:>6}|賺錢比例 {x['賺錢比例']:5.1f}%|平均賺 {x['平均賺']:+6.2f}%|平均賠 {x['平均賠']:+6.2f}%|賺賠比 {x['賺賠比']:.2f}|平均淨報酬 {x['平均淨報酬']:+6.3f}%")

json.dump(OUT, open(os.path.join(HERE, "f3_finra_dtc.json"), "w"), ensure_ascii=False, indent=1, default=float)
open(os.path.join(HERE, "f3_finra_dtc.log"), "w").write("\n".join(LOG) + "\n")
P("\n存檔:f3_finra_dtc.log / f3_finra_dtc.json")
