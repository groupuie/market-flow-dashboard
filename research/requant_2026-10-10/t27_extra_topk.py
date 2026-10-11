# t27:頂K「額外候選」(Codex v0.2)— 完全照 t27_prereg.md(commit dbb19ce,2026-10-11 08:33:58 台灣)執行。
# 不論通過與否,結果都存 t27_extra_topk.log。成本 10 bp 為主判定;其他只描述。
import numpy as np, pandas as pd, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qlib import O, H, L, C, dates, cols, dix, VQ, topk
END = str(dates[-1].date())
# ---------- 定義(與 tkSeriesJS 同公式)----------
mid = C.rolling(20).mean(); sd = C.rolling(20).std(ddof=0); up = mid + 2 * sd; touch = H >= up
tr = np.maximum(H - L, np.maximum((H - C.shift()).abs(), (L - C.shift()).abs())); atr = tr.rolling(14, min_periods=10).mean()
r20 = C / C.shift(20) - 1; dA = (C - mid) / atr; ext = C / C.rolling(50).mean() - 1
hot = (r20 >= 0.30) | (dA >= 3) | (ext >= 0.25)
off = 1 - C / H; atr1 = atr.shift(1)
ORIG = hot & touch & (off >= 0.05)
assert ORIG.equals(topk().fillna(False).astype(bool)) or (ORIG == topk().fillna(False).astype(bool)).all().all(), "ORIG 與 qlib.topk() 不一致"
def extra(k): return hot & touch & (off < 0.05) & (atr1 > 0) & ((H - C) >= k * atr1)
EXTRA = extra(1.0); UNION = ORIG | EXTRA; REST = hot & touch & ~ORIG & ~EXTRA
GROUPS = {"ORIG 現行頂K": ORIG, "EXTRA 候選": EXTRA, "UNION 兩者": UNION, "REST 同前提回落小": REST}
# ---------- 交易:t+1 開盤賣;t+2..t+11 限價 0.97×賣價;沒成交 t+12 開盤買回 ----------
def trade(sell, first, last, forced):
    lim = 0.97 * sell; B = pd.DataFrame(np.nan, index=C.index, columns=C.columns); filled = pd.DataFrame(False, index=C.index, columns=C.columns)
    fillk = pd.DataFrame(np.nan, index=C.index, columns=C.columns)
    for k in range(first, last + 1):
        Ok, Lk = O.shift(-k), L.shift(-k); hit = (~filled) & (Lk <= lim)
        B = B.mask(hit, np.minimum(Ok, lim)); fillk = fillk.mask(hit, k); filled = filled | hit
    Fo = O.shift(-forced); complete = Fo.notna() & sell.notna()
    B = B.mask(~filled, Fo); fillk = fillk.mask(~filled, forced)
    edge = np.log(sell / B).where(complete)
    return edge, filled.where(complete), fillk.where(complete)
EDGE, FILLED, FILLK = trade(O.shift(-1), 2, 11, 12)           # 主規則
EDGE_C, _, _ = trade(C, 1, 10, 11)                            # 只描述:當晚收盤賣,同一套買回
FR40 = np.log(C.shift(-40) / O.shift(-1))                     # 只描述:40 日後較低
# ---------- 主對照 BASE-M:同波動十分位 × 同 20 日漲幅區間 ----------
vqb = (VQ * 10).clip(0, 9.999).apply(np.floor)
r20b = pd.DataFrame(np.select([r20 < 0, r20 < 0.1, r20 < 0.2, r20 < 0.3, r20 >= 0.3], [0, 1, 2, 3, 4], default=-1), index=C.index, columns=C.columns).where(r20.notna())
cell = (vqb * 10 + r20b).where(vqb.notna() & r20b.notna())
PER = {"p1": ("2009-07-01", "2017-12-31"), "p2": ("2018-01-01", END), "all": ("2009-07-01", END)}
SUB4 = [("2009-07-01", "2013-12-31"), ("2014-01-01", "2018-12-31"), ("2019-01-01", "2022-12-31"), ("2023-01-01", END)]
def pm(a, b): return (dates >= a) & (dates <= b)
def stk(X, mask): s = X.where(mask).stack(); return s[s.notna()]
def cellmeans(a, b):
    m = pm(a, b); df = pd.DataFrame({"e": EDGE.loc[m].stack(), "c": cell.loc[m].stack()}).dropna()
    return df.groupby("c")["e"].mean()
CM = {k: cellmeans(*v) for k, v in PER.items()}; CM4 = [cellmeans(a, b) for a, b in SUB4]
def boot(vals, blk, reps=2000, seed=0):
    g = pd.DataFrame({"b": blk, "v": vals}).groupby("b")["v"].agg(["sum", "count"]); rng = np.random.default_rng(seed); k = len(g)
    if k < 2: return (np.nan, np.nan)
    s, n = g["sum"].values, g["count"].values; out = []
    for _ in range(reps):
        ii = rng.integers(0, k, k); out.append(s[ii].sum() / n[ii].sum())
    return tuple(np.percentile(out, [5, 95]))
def stockyears(a, b): return C.loc[pm(a, b)].notna().values.sum() / 252
def stats(sig, a, b, cm, ci=True):
    m = pd.DataFrame(False, index=C.index, columns=C.columns); m.loc[pm(a, b)] = sig.loc[pm(a, b)].fillna(False).astype(bool)
    nsig = int(m.values.sum()); e = stk(EDGE, m); n = len(e)
    r = {"nsig": nsig, "n": n, "incomplete": nsig - n, "rate": nsig / stockyears(a, b)}
    if n == 0: return r
    c = stk(cell, m).reindex(e.index); base = c.map(cm); ok = base.notna(); d = (e - base)[ok]
    r.update({"m0": e.mean() * 100, "m10": (e - 0.001).mean() * 100, "m25": (e - 0.0025).mean() * 100, "med10": (e - 0.001).median() * 100,
              "win10": ((e - 0.001) > 0).mean() * 100, "fill": stk(FILLED.astype(float), m).reindex(e.index).mean() * 100,
              "t5": ((e - 0.001) <= -0.05).mean() * 100, "t10": ((e - 0.001) <= -0.10).mean() * 100,
              "base": base[ok].mean() * 100, "diff": d.mean() * 100, "nb": int(ok.sum())})
    f40 = stk(FR40, m); r["low40"] = (f40 < 0).mean() * 100 if len(f40) else np.nan
    ec = stk(EDGE_C, m); r["mc10"] = (ec - 0.001).mean() * 100 if len(ec) else np.nan
    if ci and ok.sum() > 20:
        di = dix.reindex(d.index.get_level_values(0)).values
        r["ci40"] = tuple(x * 100 for x in boot(d.values, di // 40)); r["ci60"] = tuple(x * 100 for x in boot(d.values, di // 60))
    return r
def line(name, per, r):
    if r["n"] == 0: return f"{name:16s} {per:4s} 事件 {r['nsig']}(全部未完成)"
    s = (f"{name:16s} {per:4s} n={r['n']:5d}(未完成 {r['incomplete']},每檔每年 {r['rate']:.2f})| 優勢 0bp {r['m0']:+.2f}% / 10bp {r['m10']:+.2f}% / 25bp {r['m25']:+.2f}%"
         f" | 中位 {r['med10']:+.2f}% 賺的比例 {r['win10']:.0f}% 限價成交 {r['fill']:.0f}% | ≤−5% {r['t5']:.0f}% ≤−10% {r['t10']:.1f}%"
         f" | 對照(同波動×同漲幅){r['base']:+.2f}% 差 {r['diff']:+.2f}%")
    if "ci40" in r: s += f" [40日 {r['ci40'][0]:+.2f},{r['ci40'][1]:+.2f}][60日 {r['ci60'][0]:+.2f},{r['ci60'][1]:+.2f}]"
    s += f" | 40日後較低 {r['low40']:.0f}% | 當晚收盤賣版 10bp {r['mc10']:+.2f}%"
    return s
print(f"資料 {dates[0].date()} ~ {END};259 檔;ORIG 與 qlib.topk() 一致(assert 通過)")
print("優勢 = ln(賣價/買回價) − 成本(正 = 比一直抱著好)。差 = 平均優勢 − 同波動×同漲幅隨便一天做同一套交易。[ ] = 日期區塊自助法 90%。\n")
R = {}
for g, sig in GROUPS.items():
    for per, (a, b) in PER.items():
        R[(g, per)] = stats(sig, a, b, CM[per]); print(line(g, per, R[(g, per)]), flush=True)
    print()
print("四段(EXTRA 差,0bp;n<30 算沒過)")
sub = []
for (a, b), cm in zip(SUB4, CM4):
    r = stats(EXTRA, a, b, cm, ci=False); sub.append(r); print(f"  {a[:7]}~{b[:7]} n={r['n']} 差 {r.get('diff', float('nan')):+.2f}% 平均 10bp {r.get('m10', float('nan')):+.2f}%")
# ---------- 連續操作版(不重疊)----------
def sequential(sig):
    sg = sig.fillna(False).values.astype(bool); ev = EDGE.values; fk = FILLK.values; rows = []
    for j in range(sg.shape[1]):
        nb = -1
        for i in np.flatnonzero(sg[:, j]):
            if i < nb: continue
            if np.isnan(ev[i, j]): continue   # 結果未完成(太近期或缺資料)→ 不開倉
            rows.append((i, j, ev[i, j])); nb = i + int(fk[i, j])
    return pd.DataFrame(rows, columns=["i", "j", "e"])
SO, SU = sequential(ORIG), sequential(UNION)
print("\n連續操作版(不重疊;成本 10 bp)")
seq = {}
for per, (a, b) in PER.items():
    ia, ib = dix[dates[pm(a, b)][0]], dix[dates[pm(a, b)][-1]]; sy = stockyears(a, b)
    o = SO[(SO.i >= ia) & (SO.i <= ib)]; u = SU[(SU.i >= ia) & (SU.i <= ib)]
    to, tu = (o.e - 0.001).sum(), (u.e - 0.001).sum()
    allb = np.arange(ia // 40, ib // 40 + 1); so = (o.e - 0.001).groupby(o.i // 40).sum().reindex(allb, fill_value=0); su = (u.e - 0.001).groupby(u.i // 40).sum().reindex(allb, fill_value=0)
    dd = (su - so).values; rng = np.random.default_rng(0); bs = [dd[rng.integers(0, len(dd), len(dd))].sum() / sy * 100 for _ in range(2000)]
    allb6 = np.arange(ia // 60, ib // 60 + 1); so6 = (o.e - 0.001).groupby(o.i // 60).sum().reindex(allb6, fill_value=0); su6 = (u.e - 0.001).groupby(u.i // 60).sum().reindex(allb6, fill_value=0)
    dd6 = (su6 - so6).values; rng = np.random.default_rng(0); bs6 = [dd6[rng.integers(0, len(dd6), len(dd6))].sum() / sy * 100 for _ in range(2000)]
    seq[per] = (tu - to) / sy * 100
    print(f"  {per:4s} ORIG {len(o)} 筆(每檔每年 {len(o)/sy:.2f})每筆 {(o.e-0.001).mean()*100:+.2f}% 合計每檔每年 {to/sy*100:+.3f}% | "
          f"UNION {len(u)} 筆({len(u)/sy:.2f})每筆 {(u.e-0.001).mean()*100:+.2f}% 合計每檔每年 {tu/sy*100:+.3f}% | 增量 {seq[per]:+.3f}% "
          f"[40日 {np.percentile(bs,5):+.3f},{np.percentile(bs,95):+.3f}][60日 {np.percentile(bs6,5):+.3f},{np.percentile(bs6,95):+.3f}]")
# ---------- 集中度:拿掉 EXTRA 合計優勢最大的 5 檔 ----------
ea = stk(EDGE - 0.001, EXTRA.fillna(False) & pd.DataFrame(np.repeat(pm(*PER["all"])[:, None], C.shape[1], axis=1), index=C.index, columns=C.columns))
top5 = ea.groupby(level=1).sum().sort_values(ascending=False).head(5)
print(f"\n集中度:EXTRA 合計優勢最大的 5 檔 {', '.join(f'{s} {v*100:+.1f}%' for s, v in top5.items())}")
drop = {}
for per in ("p1", "p2"):
    a, b = PER[per]; x = ea[(ea.index.get_level_values(0) >= a) & (ea.index.get_level_values(0) <= b)]
    x2 = x[~x.index.get_level_values(1).isin(top5.index)]; drop[per] = x2.mean() * 100
    print(f"  {per} 全部 {x.mean()*100:+.2f}%(n={len(x)})→ 拿掉後 {drop[per]:+.2f}%(n={len(x2)})")
# ---------- 每檔(只描述)----------
print("\n每檔(2009-07~;只描述):")
for g in ("ORIG 現行頂K", "EXTRA 候選"):
    x = stk(EDGE - 0.001, GROUPS[g].fillna(False) & pd.DataFrame(np.repeat(pm(*PER["all"])[:, None], C.shape[1], axis=1), index=C.index, columns=C.columns))
    ps = x.groupby(level=1).agg(["mean", "count"]); ps = ps[ps["count"] >= 3]
    print(f"  {g}:≥3 次的 {len(ps)} 檔,平均 >0 的 {(ps['mean']>0).mean()*100:.0f}%")
for s in ("MU", "SNDK"):
    print(f"  {s}:", end="")
    for g in ("ORIG 現行頂K", "EXTRA 候選", "UNION 兩者"):
        m = GROUPS[g][[s]].fillna(False) & pd.DataFrame(pm(*PER["all"])[:, None], index=C.index, columns=[s])
        x = stk(EDGE[[s]], m); f = stk(FILLED[[s]].astype(float), m)
        print(f" {g.split()[0]} n={len(x)}" + (f" 10bp {(x-0.001).mean()*100:+.2f}% 賺 {((x-0.001)>0).mean()*100:.0f}% 成交 {f.mean()*100:.0f}%" if len(x) else ""), end=";")
    print()
# ---------- 敏感度(只描述,不拿來挑)----------
print("\n敏感度:ATR 倍數(只描述,不拿來挑;判定只看 1.0)")
for k in (0.75, 1.0, 1.25, 1.5):
    sg = extra(k); parts = []
    for per in ("p1", "p2"):
        r = stats(sg, *PER[per], CM[per], ci=False); parts.append(f"{per} n={r['n']}({r['rate']:.2f}/檔年)10bp {r.get('m10', float('nan')):+.2f}% 差 {r.get('diff', float('nan')):+.2f}%")
    print(f"  {k:.2f}×ATR:" + " | ".join(parts))
# ---------- 判定 ----------
E1, E2 = R[("EXTRA 候選", "p1")], R[("EXTRA 候選", "p2")]; EA = R[("EXTRA 候選", "all")]
crit = [
    ("1 EXTRA 平均優勢 10bp >0(p1、p2)", E1.get("m10", -1) > 0 and E2.get("m10", -1) > 0, f"{E1.get('m10', float('nan')):+.2f}% / {E2.get('m10', float('nan')):+.2f}%"),
    ("2 EXTRA − 對照 >0(p1、p2)且全期 90% 下緣 >0(40、60 日)", E1.get("diff", -1) > 0 and E2.get("diff", -1) > 0 and EA.get("ci40", (-1,))[0] > 0 and EA.get("ci60", (-1,))[0] > 0,
     f"{E1.get('diff', float('nan')):+.2f}% / {E2.get('diff', float('nan')):+.2f}%;全期 [40日 {EA.get('ci40', (float('nan'),)*2)[0]:+.2f}] [60日 {EA.get('ci60', (float('nan'),)*2)[0]:+.2f}]"),
    ("3 四段至少 3 段差 >0(n<30 算沒過)", sum(1 for r in sub if r["n"] >= 30 and r.get("diff", -1) > 0) >= 3, " / ".join(f"{r.get('diff', float('nan')):+.2f}%(n={r['n']})" for r in sub)),
    ("4 連續操作 UNION−ORIG 每檔每年增量 >0(p1、p2)", seq["p1"] > 0 and seq["p2"] > 0, f"{seq['p1']:+.3f}% / {seq['p2']:+.3f}%"),
    ("5 EXTRA 25bp ≥0(p1、p2)", E1.get("m25", -1) >= 0 and E2.get("m25", -1) >= 0, f"{E1.get('m25', float('nan')):+.2f}% / {E2.get('m25', float('nan')):+.2f}%"),
    ("6 拿掉前 5 檔後 p1、p2 平均 >0", drop["p1"] > 0 and drop["p2"] > 0, f"{drop['p1']:+.2f}% / {drop['p2']:+.2f}%"),
]
print("\n判定(事前設定 dbb19ce 的 6 條,全部要過):")
for k, ok, v in crit: print(f"  {'過' if ok else '沒過'}  {k}:{v}")
print("結論:" + ("全部通過 → 只寫成提案,網站不改,由使用者決定" if all(ok for _, ok, _ in crit) else "不通過 → 不上線,這輪不換門檻重試"))
