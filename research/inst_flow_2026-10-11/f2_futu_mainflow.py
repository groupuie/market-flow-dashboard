# f2:網站 ⑦「主力(大單)淨流」強度 F20 → 之後 2 週報酬 —— 完全照 f2_prereg_futu_mainflow.md 執行(與本腳本同一個 commit、跑之前)。
# 不論通過與否,結果都存 f2_futu_mainflow.log / .json。
#
# 跑之前就決定、寫在這裡的執行細節:
#   A. 名單、價格、load()、分五組方法(每天 ≥ 25 檔、穩定排序、floor(k×5÷N))、市場中性、區塊切法都與 f1 相同。
#   B. ⑦ 缺值日:Σm 與 Σ成交額都只加「⑦ 有值的那些天」;中小單 r 缺值當 0(與 index.html chipDaily 同)。
#   C. 訊號期起點 = 第一個 F20 有值的日子;終點 2026-09-25。
#   D. C▲ 成績單:index.html csigCompute 逐行移植(rows = 該股 Yahoo 全歷史日K;fx = (m, m+r));覆蓋 ≥ 60 天才用滿窗語意。
#      價格用 Yahoo 調整後,網站核心股用 Futu 前復權 → 門檻邊緣的個別訊號可能跟網站差一兩天,成績單照算、註明。
import numpy as np, pandas as pd, json, os, sys, warnings; warnings.filterwarnings("ignore")
DT = os.environ.get("T30_DT", "/home/claude/work/t30")
GD = os.environ.get("F2_GIST", "/home/claude/work")
HERE = os.path.dirname(os.path.abspath(__file__))
START = "2004-01-01"; END_SIG = "2026-09-25"; HALF = "2026-03-31"
CSIG_FROM = "2026-08-07"
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
Pd = {k: {} for k in "OHLCV"}
for s in eq:
    d = load(s)
    if d is None or len(d) < 60: continue
    d = d.reindex(cal)
    for k, c in zip("OHLCV", "ohlcv"): Pd[k][s] = d[c]
O, H, L, C, V = [pd.DataFrame(Pd[k]).astype("float64") for k in "OHLCV"]
dates = C.index; cols = list(C.columns); n, m = C.shape
DV = C * V / 1e6

# ---------- ⑦ ----------
FL = {}
for fn in ("gist_ext_flows.json", "gist_daily_flows.json"):   # core 後蓋 ext(同 accum.py)
    d = json.load(open(os.path.join(GD, fn)))["daily_flows"]
    for day, row in d.items():
        for s, v in (row or {}).items():
            if s in Pd["C"] and isinstance(v, dict) and v.get("m") is not None:
                FL[(day, s)] = (float(v["m"]), float(v.get("r") or 0.0))
fdf = pd.DataFrame([(pd.Timestamp(k[0]), k[1], v[0], v[1]) for k, v in FL.items()], columns=["d", "s", "m", "r"])
Mf = fdf.pivot(index="d", columns="s", values="m").reindex(index=dates, columns=cols)
Rf = fdf.pivot(index="d", columns="s", values="r").reindex(index=dates, columns=cols)
fdays = pd.DatetimeIndex(sorted(fdf.d.unique()))
P(f"名單 {m} 檔;⑦ {fdays[0].date()}~{fdays[-1].date()}({len(fdays)} 天;不在 SPY 日曆 {len(fdays.difference(dates))} 天);有 ⑦ 的股票 {int(Mf.notna().any().sum())} 檔")

mask = Mf.notna()
DVm = DV.where(mask)
def intensity(num, w, mn):
    s = num.rolling(w, min_periods=mn).sum(); dv = DVm.rolling(w, min_periods=mn).sum()
    return (s / dv).where(dv > 0)
SIG = {"F20": intensity(Mf, 20, 16), "F5": intensity(Mf, 5, 4), "F60": intensity(Mf, 60, 48),
       "A20": intensity(Mf + Rf.where(mask, 0.0).fillna(0.0).where(mask), 20, 16)}
def G_of(h): return np.log(C.shift(-h) / O.shift(-1))
GH = {h: G_of(h) for h in (10, 20)}
GMN = {h: g.sub(g.mean(axis=1), axis=0) for h, g in GH.items()}

first_sig = SIG["F20"].notna().any(axis=1); i_lo = int(np.flatnonzero(first_sig.values)[0])
i_hi = int(np.searchsorted(dates, pd.Timestamp(END_SIG), side="right") - 1)
SIGP = (str(dates[i_lo].date()), END_SIG)
P(f"訊號期 {SIGP[0]}~{SIGP[1]};前半 ~{HALF}、後半 2026-04-01~")
x = SIG["F20"].iloc[i_lo:i_hi + 1].values
P(f"F20(主力 20 日淨流 ÷ 成交額):中位數 {np.nanmedian(x) * 100:+.3f}%、10%/90% 分位 {np.nanpercentile(x, 10) * 100:+.3f}% / {np.nanpercentile(x, 90) * 100:+.3f}%")

def pmask(a, b): return (dates >= pd.Timestamp(a)) & (dates <= pd.Timestamp(b))
def quint(sig, h):
    S = sig.values; Gm = GMN[h].values; Gr = GH[h].values
    ok = ~np.isnan(S) & ~np.isnan(Gr); N = ok.sum(1)
    q = np.full((n, m), -1, int); q1 = np.full(n, np.nan); q5 = np.full(n, np.nan)
    for i in range(i_lo, i_hi + 1):
        if N[i] < MIN_N: continue
        js = np.flatnonzero(ok[i]); order = js[np.argsort(S[i, js], kind="stable")]
        g = (np.arange(len(order)) * 5) // len(order); q[i, order] = g
        q1[i] = Gm[i, order[g == 0]].mean(); q5[i] = Gm[i, order[g == 4]].mean()
    return q, q1, q5, N
def boot(D, a, b, blk):
    sel = pmask(a, b) & ~np.isnan(D); idx = np.flatnonzero(sel)
    ub, inv = np.unique(idx // blk, return_inverse=True); K = len(ub)
    S = np.bincount(inv, weights=D[idx], minlength=K); Nn = np.bincount(inv, minlength=K).astype(float)
    rng = np.random.default_rng(SEED); out = np.empty(REPS)
    for r in range(REPS):
        w = np.bincount(rng.integers(0, K, K), minlength=K).astype(float); out[r] = (w @ S) / (w @ Nn)
    lo, hi = np.percentile(out, [5, 95]); return lo * 100, hi * 100, K
def pm_mean(v, a, b):
    s = pmask(a, b) & ~np.isnan(v); return (v[s].mean() * 100 if s.any() else np.nan), int(s.sum())

PER = {"前半": (SIGP[0], HALF), "後半": ("2026-04-01", END_SIG), "全期": SIGP}
def summarize(sname, h):
    q, q1, q5, N = quint(SIG[sname], h); D = q5 - q1
    res = {"sig": sname, "h": h}
    for nm, (a, b) in PER.items():
        d_, nd = pm_mean(D, a, b); r1, _ = pm_mean(q1, a, b); r5, _ = pm_mean(q5, a, b)
        res[nm] = {"Q5-Q1": d_, "Q5": r5, "Q1": r1, "days": nd}
    for blk in (10, 20):
        lo, hi, K = boot(D, *PER["全期"], blk); res["全期"][f"ci{blk}"] = [lo, hi]; res["全期"][f"K{blk}"] = K
    sm = pmask(*PER["全期"]); okd = sm & (N >= MIN_N)
    res["N_per_day"] = {"median": float(np.median(N[okd])) if okd.any() else None, "min": int(N[okd].min()) if okd.any() else None}
    Sv = SIG[sname].values
    res["level"] = {"Q1": float(np.nanmean(np.where(q == 0, Sv, np.nan)[sm])) * 100, "Q5": float(np.nanmean(np.where(q == 4, Sv, np.nan)[sm])) * 100}
    return res, q, D
def show(res, label):
    P(f"\n---- {label}(訊號 {res['sig']}、h = {res['h']};市場中性、% / 筆) ----")
    P(f"每天分組股票數:中位數 {res['N_per_day']['median']}、最少 {res['N_per_day']['min']};組內平均訊號 Q1 {res['level']['Q1']:+.3f}%、Q5 {res['level']['Q5']:+.3f}%(主力淨流 ÷ 成交額)")
    for nm in PER:
        r = res[nm]; ci = "".join(f"、90% 區間({k} 日區塊,{r[f'K{k}']} 塊) [{r[f'ci{k}'][0]:+.3f}, {r[f'ci{k}'][1]:+.3f}]" for k in (10, 20) if f"ci{k}" in r)
        P(f"  {nm} Q5 − Q1 = {r['Q5-Q1']:+.3f}%(Q5 {r['Q5']:+.3f}、Q1 {r['Q1']:+.3f};{r['days']} 天){ci}")
def user_metrics(q, h, a, b):
    Gr = GH[h].values; sm = pmask(a, b)[:, None]; out = {}
    for nm, mk in (("只買 Q5(主力流入最強)", q == 4), ("只買 Q1(主力流出最兇)", q == 0), ("全部(有分組的)", q >= 0)):
        g = Gr[mk & sm & ~np.isnan(Gr)]; net = np.exp(g) - 1 - FEE_TRADE; w = net > 0
        out[nm] = {"筆數": int(len(net)), "賺錢比例": float(w.mean() * 100), "平均賺": float(net[w].mean() * 100),
                   "平均賠": float(net[~w].mean() * 100), "平均淨報酬": float(net.mean() * 100), "賺賠比": float(net[w].mean() / -net[~w].mean())}
    return out
def show_um(um, label):
    P(f"  {label}:")
    for k, x in um.items():
        P(f"    {k:<14} 筆數 {x['筆數']:>6}|賺錢比例 {x['賺錢比例']:5.1f}%|平均賺 {x['平均賺']:+6.2f}%|平均賠 {x['平均賠']:+6.2f}%|賺賠比 {x['賺賠比']:.2f}|平均淨報酬 {x['平均淨報酬']:+6.3f}%")

OUT = {"prereg": "f2_prereg_futu_mainflow.md", "universe": m, "flow_days": len(fdays), "signal_period": SIGP}
P("\n==== 主判定:H2(F20、h = 10;Q5 − Q1 = 跟主力買、避開主力賣)====")
r10, q10, D10 = summarize("F20", 10); show(r10, "主假設")
a_, b_, f_ = r10["前半"]["Q5-Q1"], r10["後半"]["Q5-Q1"], r10["全期"]
pos = [bool(a_ > 0 and b_ > 0), bool(f_["ci10"][0] > 0), bool(f_["Q5-Q1"] > COST_RT * 100)]
neg = [bool(a_ < 0 and b_ < 0), bool(f_["ci10"][1] < 0), bool(f_["Q5-Q1"] < -COST_RT * 100)]
v = ("候選:跟主力買有一年期證據(只寫提案,等新資料確認)" if all(pos) else
     "反向:主力流入最強的之後反而較弱(只寫提案)" if all(neg) else "未取得符合門檻的證據")
P(f"  判定三條:①兩半都 > 0 {pos[0]};②全期區間下緣 > 0(10 日區塊){pos[1]};③全期 > 0.40% {pos[2]}")
P(f"  鏡像三條:{neg}"); P(f"  ⇒ 結論:{v}")
OUT.update({"H2": r10, "H2_pass": pos, "H2_mirror": neg, "verdict": v})

P("\n==== 只描述、不判定 ====")
r20, q20, _ = summarize("F20", 20); show(r20, "h = 20"); OUT["h20"] = r20
for s in ("F5", "F60", "A20"):
    rr, _, _ = summarize(s, 10); show(rr, f"次訊號 {s}"); OUT[f"{s}_h10"] = rr

P("\n==== 實戰數字(原始報酬、每邊 10 bp;每筆 = 一檔一個訊號日,持有期重疊)====")
OUT["user"] = {}
for h, q in ((10, q10), (20, q20)):
    for nm, (a, b) in PER.items():
        um = user_metrics(q, h, a, b); OUT["user"][f"h{h}_{nm}"] = um; show_um(um, f"h = {h}、{nm}")

# ---------- C▲ 上線後成績單(index.html csigCompute 逐行移植)----------
def csig_bot(s):
    c = C[s].values; h_ = H[s].values; l_ = L[s].values; vv = V[s].values; mm = Mf[s].values; rr_ = Rf[s].values
    ok = ~np.isnan(c); idx = np.flatnonzero(ok)
    if len(idx) < 30: return []
    c, h_, l_, vv, mm, rr_ = c[idx], h_[idx], l_[idx], np.nan_to_num(vv[idx]), mm[idx], rr_[idx]
    fx = [None if np.isnan(mm[k]) else (mm[k], mm[k] + (0.0 if np.isnan(rr_[k]) else rr_[k])) for k in range(len(idx))]
    cover = sum(1 for f in fx if f is not None)
    if cover < 20: return []
    nn = len(idx); shape = [False] * nn; M60 = [0.0] * nn; AB = [None] * nn
    fk = [k for k in range(nn) if fx[k] is not None]; pos_in = {k: j for j, k in enumerate(fk)}
    for t in fk:
        j = pos_in[t]; wl = fk[max(0, j - 59):j + 1]; ws = fk[max(0, j - 19):j + 1]
        if cover >= 60:
            if len(wl) < 60 or len(ws) < 20: continue
        else:
            if len(wl) < 15 or len(ws) < 5: continue
        a60 = sum(fx[k][1] for k in wl); m60 = sum(fx[k][0] for k in wl); dv = sum(c[k] * (vv[k] or 0) / 1e6 for k in wl)
        a20 = sum(fx[k][1] for k in ws); ab = a60 / (dv or 1e-9)
        pw = min(120, t + 1); lo = l_[t - pw + 1:t + 1].min(); hi = h_[t - pw + 1:t + 1].max()
        pos_ = (c[t] - lo) / (hi - lo) if hi > lo else 0.5
        iws = min(20, t); r20 = c[t] / c[t - iws] - 1 if iws > 0 else 0
        shape[t] = (a60 > 0 and a20 > 0 and ab >= 0.002 and pos_ <= 0.5 and r20 < 0.10); M60[t] = m60; AB[t] = ab
    bot = []; lastB = -9
    for t in range(10, nn):
        if AB[t] is None or AB[t] >= 0.010: continue
        if not (shape[t] or shape[t - 1] or shape[t - 2] or shape[t - 3]): continue
        if M60[t] <= 0: continue
        if c[t] > c[t - 10:t].max() and t - lastB > 5: lastB = t; bot.append(idx[t])
    return bot

ev = []
for s in cols:
    j = cols.index(s)
    for i in csig_bot(s):
        if pmask(CSIG_FROM, END_SIG)[i]:
            g = GH[10].values[i, j]
            ev.append({"sym": s, "date": str(dates[i].date()), "g10": g, "mn10": GMN[10].values[i, j]})
E = pd.DataFrame(ev)
P(f"\n==== C▲ 上線後成績單(訊號日 {CSIG_FROM}~{END_SIG};10 日、t+1 開盤進場;只描述)====")
if len(E):
    E = E[E.g10.notna()]; net = np.exp(E.g10) - 1 - FEE_TRADE; w = net > 0
    bm = pmask(CSIG_FROM, END_SIG)[:, None] & ~np.isnan(GH[10].values); gb = GH[10].values[bm]; nb = np.exp(gb) - 1 - FEE_TRADE; wb = nb > 0
    cs = {"筆數": int(len(E)), "檔數": int(E.sym.nunique()), "賺錢比例": float(w.mean() * 100), "平均賺": float(net[w].mean() * 100) if w.any() else None,
          "平均賠": float(net[~w].mean() * 100) if (~w).any() else None, "平均淨報酬": float(net.mean() * 100), "市場中性平均": float(E.mn10.mean() * 100),
          "贏過同日平均的比例": float((E.mn10 > 0).mean() * 100)}
    base = {"筆數": int(len(nb)), "賺錢比例": float(wb.mean() * 100), "平均賺": float(nb[wb].mean() * 100), "平均賠": float(nb[~wb].mean() * 100), "平均淨報酬": float(nb.mean() * 100)}
    P(f"  C▲:{cs['筆數']} 筆({cs['檔數']} 檔)|賺錢比例 {cs['賺錢比例']:.1f}%|平均賺 {cs['平均賺']:+.2f}%|平均賠 {cs['平均賠']:+.2f}%|平均淨報酬 {cs['平均淨報酬']:+.3f}%"
      f"|市場中性 {cs['市場中性平均']:+.3f}%|贏過同日平均 {cs['贏過同日平均的比例']:.1f}%")
    P(f"  同期全部股票日:{base['筆數']} 筆|賺錢比例 {base['賺錢比例']:.1f}%|平均賺 {base['平均賺']:+.2f}%|平均賠 {base['平均賠']:+.2f}%|平均淨報酬 {base['平均淨報酬']:+.3f}%")
    P("  明細:" + ";".join(f"{r.sym} {r.date[5:]} {(np.exp(r.g10) - 1 - FEE_TRADE) * 100:+.1f}%" for r in E.sort_values("date").itertuples()))
    OUT["csig"] = {"stats": cs, "base": base, "events": [{**r, "net10": float(np.exp(r["g10"]) - 1 - FEE_TRADE)} for r in E.to_dict("records")]}
else:
    P("  這段期間沒有 C▲"); OUT["csig"] = {"stats": None}

json.dump(OUT, open(os.path.join(HERE, "f2_futu_mainflow.json"), "w"), ensure_ascii=False, indent=1, default=float)
open(os.path.join(HERE, "f2_futu_mainflow.log"), "w").write("\n".join(LOG) + "\n")
P("\n存檔:f2_futu_mainflow.log / f2_futu_mainflow.json")
