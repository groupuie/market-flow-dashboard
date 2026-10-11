# f4(只描述、不判定):「勝率 70%」要付出什麼 —— 同一批進場點,只換出場方式,看賺錢比例和每筆賺賠怎麼互換。
# 回答使用者 2026-10-11 19:29 第 3 點(70% 是目標,把可能性找出來;波段或 2 星期打帶跑)。
# 這不是找最佳參數:出場組合在跑之前就固定在下面(QUICK = 2 週、SWING = 2 個月),結果不論好壞全列。
#
# 進場點:f1 的兩組 —— 「全部」(每天有分組的股票日)與「Q1 = 場外放空比例最低 20%」;訊號 2018-08-01~2026-07-31。
# 規則:t+1 開盤買;停利 = 盤中最高價碰到 → 以停利價賣(跳空開在停利價之上 → 以開盤價賣);
#       停損 = 盤中最低價碰到 → 以停損價賣(跳空開在停損價之下 → 以開盤價賣);同一天兩個都碰到 → 當作先停損(保守);
#       都沒碰到 → 第 N 天收盤賣。每邊 10 bp。每筆 = 一檔一天,持有期重疊,筆數不是獨立樣本。
import numpy as np, pandas as pd, json, os, sys, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
QUICK = [("只看時間", None, None), ("+3% 停利 / −10% 停損", 0.03, 0.10), ("+5% / −5%", 0.05, 0.05), ("+10% / −5%", 0.10, 0.05)]
SWING = [("只看時間", None, None), ("+5% 停利 / −15% 停損", 0.05, 0.15), ("+10% / −10%", 0.10, 0.10), ("+20% / −8%", 0.20, 0.08)]
FEE = 0.0010

# 共用 f1 的資料與分組(直接載入 f1 腳本的前半段;不重算統計、不存 f1 的檔)
src = open(os.path.join(HERE, "f1_finra_short.py"), encoding="utf-8").read().split("OUT = {")[0]
ns = {"__file__": os.path.join(HERE, "f1_finra_short.py")}; exec(compile(src, "f1_head", "exec"), ns)
O, C, dates, n, m = ns["O"], ns["C"], ns["dates"], ns["n"], ns["m"]
ld = lambda s: ns["load"](s)
Hh = {}; Ll = {}
for s in ns["cols"]:
    d = ld(s).reindex(ns["cal"]); Hh[s] = d["h"]; Ll[s] = d["l"]
H = pd.DataFrame(Hh)[ns["cols"]].values; L = pd.DataFrame(Ll)[ns["cols"]].values; Ov = O.values; Cv = C.values
q10 = ns["quint"](ns["SIG"]["SVR5"], 10)[0]; q40 = ns["quint"](ns["SIG"]["SVR5"], 40)[0]

def sim(I, J, N, tp, sl):
    e = Ov[I + 1, J]; ret = np.full(len(I), np.nan); held = np.full(len(I), float(N)); done = np.zeros(len(I), bool)
    tv = e * (1 + tp) if tp is not None else None; lv = e * (1 - sl) if sl is not None else None
    for k in range(1, N + 1):   # k = 1 是進場當天(開盤 = 進場價,所以跳空判斷對第 1 天不會成立)
        r = I + k; o, h, l, c = Ov[r, J], H[r, J], L[r, J], Cv[r, J]
        px = np.full(len(I), np.nan)
        if tp is not None:
            g = ~done & (o >= tv); px[g] = o[g]                          # 開盤就跳過停利價 → 開盤賣
        if sl is not None:
            g = ~done & np.isnan(px) & (o <= lv); px[g] = o[g]           # 開盤就跌破停損價 → 開盤賣
            g = ~done & np.isnan(px) & (l <= lv); px[g] = lv[g]          # 盤中碰停損(同日兩個都碰 → 先算停損)
        if tp is not None:
            g = ~done & np.isnan(px) & (h >= tv); px[g] = tv[g]          # 盤中碰停利
        hit = ~done & ~np.isnan(px)
        ret[hit] = np.log(px[hit] / e[hit]); held[hit] = k; done |= hit
        if k == N:
            live = ~done; ret[live] = np.log(c[live] / e[live])
    ok = ~np.isnan(ret)
    net = np.exp(ret[ok]) - 1 - 2 * FEE; w = net > 0
    return {"筆數": int(ok.sum()), "賺錢比例": float(w.mean() * 100), "平均賺": float(net[w].mean() * 100), "平均賠": float(net[~w].mean() * 100),
            "每筆平均": float(net.mean() * 100), "平均持有天數": float(held[ok].mean())}

LOG = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); LOG.append(s)
OUT = {}
for lab, N, grid, q in (("2 週打帶跑(最多 10 天)", 10, QUICK, q10), ("波段(最多 40 天)", 40, SWING, q40)):
    P(f"\n==== {lab} ====")
    for gname, mk in (("全部", q >= 0), ("Q1 放空比例最低", q == 0)):
        I, J = np.nonzero(mk); okp = (I + N < n) & ~np.isnan(Ov[np.minimum(I + 1, n - 1), J]) & ~np.isnan(Cv[np.minimum(I + N, n - 1), J])
        I, J = I[okp], J[okp]
        for name, tp, sl in grid:
            r = sim(I, J, N, tp, sl); OUT[f"{lab}|{gname}|{name}"] = r
            P(f"  {gname:<10} {name:<18} 筆數 {r['筆數']:>7}|賺錢比例 {r['賺錢比例']:5.1f}%|平均賺 {r['平均賺']:+6.2f}%|平均賠 {r['平均賠']:+6.2f}%"
              f"|每筆平均 {r['每筆平均']:+6.3f}%|平均持有 {r['平均持有天數']:4.1f} 天")
json.dump(OUT, open(os.path.join(HERE, "f4_winrate_tradeoff.json"), "w"), ensure_ascii=False, indent=1)
open(os.path.join(HERE, "f4_winrate_tradeoff.log"), "w").write("\n".join(LOG) + "\n")
