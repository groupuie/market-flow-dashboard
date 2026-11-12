#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""開發資料描述(沒有預先登記;只用來估基準率、事件數、群聚與成本,不看任何預測的好壞):
Astra 盤感路線 v1.0 的「快速發動」草案標籤 FL3:
  t 日收盤做判斷,e = t+1 開盤價,A = t 日的 ATR20(價格單位)。
  進場日起 3 個交易日內(t+1 ~ t+3),依序看每一天:最低 ≤ e − A → 0(同一天先檢查最低,所以同日跌破又收高算失敗);
  收盤 ≥ e + A → 1;3 天都沒有 → 0。
另算換尺的版本:±ATR60、±ATR250、固定 ±2%;以及之後 3 / 10 / 20 天的最大逆行(最低 ÷ e − 1)、10 天內收盤低於 e 的天數。
事件窗:walk8 的財報事件(反應日 r),決定日 r ~ r+4 共 5 個交易日,且那天在 walk7 名單內。
用法:python3 -I x2_fast_launch.py SCRATCH   → SCRATCH/em/out/x2_fast_launch.json"""
import gzip, json, os, pickle, sys
import numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as swv

ROOT = sys.argv[1]; W7 = os.path.join(ROOT, "w7"); OUT = os.path.join(ROOT, "em", "out"); os.makedirs(OUT, exist_ok=True)
S = pd.read_pickle(os.path.join(W7, "out", "S7.pkl"))[["sym", "date", "i", "year"]]
B = pickle.load(gzip.open(os.path.join(W7, "data", "daily.pkl.gz")))["bars"]
EA = pd.read_pickle(os.path.join(ROOT, "w8", "out", "ea_events.pkl"))[["sym", "r", "pe", "fdate"]]


def sma(x, w):
    cs = np.cumsum(np.insert(np.nan_to_num(x), 0, 0.0)); o = np.full(len(x), np.nan); o[w - 1:] = (cs[w:] - cs[:-w]) / w; return o


def fl3(o, h, l, c, I, A):
    """回傳 y(0/1)與發動日(1..3,沒發動 = 0)"""
    e = o[I + 1]; up, dn = e + A, e - A
    y = np.zeros(len(I)); day = np.zeros(len(I), int); done = np.zeros(len(I), bool)
    for k in (1, 2, 3):
        j = I + k
        fail = (~done) & (l[j] <= dn); done |= fail
        win = (~done) & (c[j] >= up); y[win] = 1; day[win] = k; done |= win
    return y, day


ev_idx = {}
for s, g in EA.groupby("sym"):
    ev_idx[s] = g.r.values.astype(int)

parts = []
for s, g in S.groupby("sym", sort=False):
    x = B[s]["x"]; o, h, l, c = x[:, 0], x[:, 1], x[:, 2], x[:, 3]; n = len(c)
    pc = np.r_[np.nan, c[:-1]]
    tr = np.where(np.isnan(pc), h - l, np.maximum(h, pc) - np.minimum(l, pc))
    a20, a60, a250 = sma(tr, 20), sma(tr, 60), sma(tr, 250)
    I = g["i"].values; e = o[I + 1]
    d = {"row": g.index.values}
    d["FL3_A20"], d["day_A20"] = fl3(o, h, l, c, I, a20[I])
    d["FL3_A60"], _ = fl3(o, h, l, c, I, a60[I])
    d["FL3_A250"], _ = fl3(o, h, l, c, I, a250[I])
    d["FL3_FIX2"], _ = fl3(o, h, l, c, I, 0.02 * e)
    d["bw_A20"] = a20[I] / e * 100
    for H in (3, 10, 20):
        lmin = swv(l, H).min(1); d[f"mae{H}"] = (lmin[I + 1] / e - 1) * 100
    d["below10"] = (swv(c, 10)[I + 1] < e[:, None]).sum(1)
    # 財報事件窗:決定日 = r ~ r+4
    lag = np.full(len(I), -1)
    if s in ev_idx:
        for r in ev_idx[s]:
            for k in range(5):
                lag[I == r + k] = k
    d["ev_lag"] = lag
    ev_id = np.full(len(I), -1)
    if s in ev_idx:
        for r in ev_idx[s]:
            ev_id[(I >= r) & (I <= r + 4)] = r
    d["ev_r"] = ev_id
    parts.append(pd.DataFrame(d))
F = pd.concat(parts).set_index("row"); S = S.join(F)
S[["sym", "date", "i", "FL3_A20", "FL3_FIX2", "FL3_A60", "ev_lag", "ev_r", "mae10", "below10"]].to_pickle(os.path.join(OUT, "fl3_rows.pkl"))


def rates(g):
    r = {"n": int(len(g))}
    for k in ("FL3_A20", "FL3_A60", "FL3_A250", "FL3_FIX2"):
        r[k + "%"] = round(float(g[k].mean()) * 100, 1)
    r["門檻寬(ATR20 ÷ e,中位 %)"] = round(float(g.bw_A20.median()), 2)
    r["發動在第1/2/3天(佔 FL3_A20=1 的 %)"] = [round(float((g.day_A20 == k).sum()) / max(1, int((g.FL3_A20 == 1).sum())) * 100, 1) for k in (1, 2, 3)]
    for H in (3, 10, 20):
        r[f"最大逆行{H}天(中位 %)"] = round(float(g[f"mae{H}"].median()), 2)
    r["10天內收盤低於 e 的天數(平均)"] = round(float(g.below10.mean()), 2)
    return r


res = {"說明": "開發資料描述,不是檢定;只為功效、成本與標籤設計", "全部某檔某天": {}, "財報事件窗": {}}
per = {"全期 2016-10~2026-09": S.date.notna(), "2021~2025": (S.date >= "2021-01-01") & (S.date <= "2025-12-31")}
for nm, m in per.items():
    g = S[m]
    res["全部某檔某天"][nm] = {"全部": rates(g), "非事件窗": rates(g[g.ev_lag < 0]), "事件窗(r~r+4)": rates(g[g.ev_lag >= 0])}
    for k in range(5):
        res["全部某檔某天"][nm][f"事件窗第 {k} 天(r+{k})"] = rates(g[g.ev_lag == k])

# 事件數、每季、每天群聚、同一事件內的相關
E = S[S.ev_lag == 0][["sym", "date", "year"]].copy()
E["q"] = pd.PeriodIndex(pd.to_datetime(E.date), freq="Q").astype(str)
perq = E.groupby("q").size()
perday = E.groupby("date").size()
res["財報事件窗"]["事件數(反應日在名單內)"] = int(len(E))
res["財報事件窗"]["每季事件數(2017Q1~2026Q2 中位 / 最小 / 最大)"] = [int(perq.loc["2017Q1":"2026Q2"].median()), int(perq.loc["2017Q1":"2026Q2"].min()), int(perq.loc["2017Q1":"2026Q2"].max())]
res["財報事件窗"]["每天事件數(有事件的日子:中位 / 90 分位 / 最大)"] = [int(perday.median()), int(perday.quantile(0.9)), int(perday.max())]
top = perday.sort_values(ascending=False)
res["財報事件窗"]["一季裡最忙的 10 天佔該季事件比例(中位 %)"] = round(float(E.assign(n=1).groupby("q").apply(lambda z: z.groupby("date").size().sort_values(ascending=False).head(10).sum() / len(z)).loc["2017Q1":"2026Q2"].median() * 100), 1)
W = S[S.ev_lag >= 0][["sym", "ev_r", "ev_lag", "FL3_A20", "FL3_FIX2"]]
key = W.sym + "_" + W.ev_r.astype(str)
for k in ("FL3_A20", "FL3_FIX2"):
    m_ev = W.groupby(key)[k].transform("mean"); p = W[k].mean()
    tot = ((W[k] - p) ** 2).mean(); within = ((W[k] - m_ev) ** 2).mean()
    res["財報事件窗"][f"同一事件 5 天的變異拆解({k}):事件間佔 %"] = round(float((tot - within) / tot * 100), 1)
# 成本估計:每季事件數 × 5 天 × 3 組 Claude(A/B/C)× 每次 token
med_q = int(perq.loc["2017Q1":"2026Q2"].median())
res["成本估計(每季,假設)"] = {f"每次判讀 {t:,} tokens": {"全名單": round(med_q * 5 * 3 * t / 1e6, 1), "成交金額前 150 左右(約 30%)": round(med_q * 0.3 * 5 * 3 * t / 1e6, 1)} for t in (4000, 8000)}
res["成本估計(每季,假設)"]["單位"] = "百萬 tokens;實際每次判讀長度要等 one_day_example 量過"
print(json.dumps(res, ensure_ascii=False, indent=1))
json.dump(res, open(os.path.join(OUT, "x2_fast_launch.json"), "w"), ensure_ascii=False, indent=1)
