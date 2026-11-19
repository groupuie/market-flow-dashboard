#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""事後描述(沒有預先登記;不是 EP 策略重現,只用日 K;回應 Codex R2「資訊缺口」):
大型股名單裡,「財報大跳空」之後有沒有延續?Qullamaggie EP 原文的幾個條件能不能用日 K 近似:
  跳空 = 反應日開盤 ÷ 前一天收盤 − 1;量 = walk8 的反應日量比 vspk;「橫盤」= 前 126 天報酬在 ±15% 內;「守住」= 反應日收盤 ≥ 開盤。
進場 = 反應日 r 收盤判斷、r+1 開盤買(同 event_memory 協定);結果 = FL3_A60(d0)、之後 5 / 20 / 60 天收盤報酬,
超額 = 減掉同一天全名單(walk7 某檔某天)同樣算法的平均;95% 區間以反應日為群。
只用反應日 2016-10 ~ 2026-03(60 天結果在 2026-06 底前結束;**不碰保留季 H = 2026-07 ~ 09 的價格**,也不碰之後);反應日與事件用 walk8 規則。
用法:python3 -I x7_ep_gaps.py SCRATCH   → SCRATCH/em/out/x7_ep_gaps.json"""
import gzip, json, os, pickle, sys
import numpy as np, pandas as pd

ROOT = sys.argv[1]; OUT = os.path.join(ROOT, "em", "out")
FL = pd.read_pickle(os.path.join(OUT, "fl3_rows.pkl"))[["sym", "date", "i", "FL3_A60", "ev_lag", "ev_r"]]
B = pickle.load(gzip.open(os.path.join(ROOT, "w7", "data", "daily.pkl.gz")))["bars"]
EA = pd.read_pickle(os.path.join(ROOT, "w8", "out", "ea_events.pkl"))[["sym", "r", "vspk"]]
H = (5, 20, 60)

# 全名單每列:r+1 開盤進、r+k 收盤出的報酬(之後減同日平均用)
parts = []
for s, g in FL.groupby("sym", sort=False):
    x = B[s]["x"]; o, c = x[:, 0], x[:, 3]; n = len(c); I = g["i"].values
    d = {"row": g.index.values}
    for k in H:
        j = I + k; ok = j < n
        v = np.full(len(I), np.nan); v[ok] = c[j[ok]] / o[I[ok] + 1] - 1; d[f"f{k}"] = v * 100
    parts.append(pd.DataFrame(d))
F = pd.concat(parts).set_index("row"); FL = FL.join(F)
for k in H:
    FL[f"x{k}"] = FL[f"f{k}"] - FL.groupby("date")[f"f{k}"].transform("mean")

E = FL[(FL.ev_lag == 0) & (FL.date < "2026-04-01")].copy()
E = E.merge(EA, left_on=["sym", "ev_r"], right_on=["sym", "r"], how="left")
gap, day, r126 = [], [], []
for t in E.itertuples():
    x = B[t.sym]["x"]; o, c = x[:, 0], x[:, 3]; r = int(t.i)
    gap.append(o[r] / c[r - 1] - 1); day.append(c[r] / o[r] - 1); r126.append(c[r - 1] / c[r - 127] - 1 if r >= 127 else np.nan)
E["gap"] = np.array(gap) * 100; E["day"] = np.array(day) * 100; E["r126"] = np.array(r126) * 100


def ci(v, g):
    m = np.isfinite(v); v, g = v[m], g[m]; n = len(v)
    if n < 3:
        return [round(float(np.nanmean(v)), 2) if n else None, None, None]
    mu = v.mean(); codes, inv = np.unique(g, return_inverse=True); G = len(codes)
    sg = np.bincount(inv, weights=v - mu); se = np.sqrt(G / max(G - 1, 1) * (sg ** 2).sum()) / n
    return [round(float(mu), 2), round(float(mu - 1.96 * se), 2), round(float(mu + 1.96 * se), 2)]


base_fl3 = float(E.FL3_A60.mean())


def row(g):
    r = {"n": int(len(g)), "反應日數": int(g.date.nunique()), "FL3_A60%": round(float(g.FL3_A60.mean()) * 100, 1)}
    for k in H:
        r[f"{k} 天超額%(平均, 95% 下, 上)"] = ci(g[f"x{k}"].values, g.date.values)
    r["20 天報酬為正%"] = round(float((g.f20 > 0).mean()) * 100, 1)
    return r


big = E.gap >= 10; sideways = E.r126.abs() <= 15; vol3 = E.vspk >= 3; held = E.day >= 0
groups = {
    "全部財報事件": pd.Series(True, index=E.index),
    "跳空 +5% ~ +10%": (E.gap >= 5) & (E.gap < 10),
    "跳空 ≥ +10%": big,
    "跳空 ≥ +10% 且量比 ≥ 3": big & vol3,
    "跳空 ≥ +10% 且前 6 個月橫盤(±15%)": big & sideways,
    "跳空 ≥ +10% 且當天守住(收 ≥ 開)": big & held,
    "EP 近似:跳空 ≥ +10% + 量比 ≥ 3 + 橫盤 + 守住": big & vol3 & sideways & held,
    "跳空 ≤ −10%(對照)": E.gap <= -10,
}
res = {"說明": __doc__.split("\n")[0], "期間": [str(E.date.min()), str(E.date.max())], "全部事件 FL3_A60 基準%": round(base_fl3 * 100, 1), "分組": {}}
for nm, m in groups.items():
    res["分組"][nm] = row(E[m.values])
    print(nm, json.dumps(res["分組"][nm], ensure_ascii=False), flush=True)

def ci_q(v, dates):
    q = pd.PeriodIndex(pd.to_datetime(pd.Series(dates)), freq="Q").astype(str).values
    return ci(v, q)


res["60 天超額:以季為群的 95% 區間(窗口重疊,較保守)"] = {nm: ci_q(E[m.values]["x60"].values, E[m.values].date.values) + [int(pd.PeriodIndex(pd.to_datetime(E[m.values].date), freq="Q").nunique())] for nm, m in groups.items()}
print(json.dumps(res["60 天超額:以季為群的 95% 區間(窗口重疊,較保守)"], ensure_ascii=False))
ep = E[(big & vol3 & sideways & held).values]
res["EP 近似 每年件數"] = ep.date.str[:4].value_counts().sort_index().to_dict()
res["跳空 ≥ +10% 每年件數"] = E[big.values].date.str[:4].value_counts().sort_index().to_dict()
res["註"] = "日 K 近似;沒有盤中進場、沒有新聞內容與市場共識、沒有營收成長條件;多個子集一起看,不是檢定。大型股名單(walk7),不是 Qullamaggie 常做的中小型成長股。"
json.dump(res, open(os.path.join(OUT, "x7_ep_gaps.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: res[k] for k in ("EP 近似 每年件數", "跳空 ≥ +10% 每年件數")}, ensure_ascii=False))

# 功效:跳空 ≥ +10% 的 60 天超額,單件標準差與「要幾件才看得出 3.3%」(80% 功效、雙尾 5%;不含群聚,偏樂觀)
g = E[big.values]["x60"].dropna()
sd = float(g.std(ddof=1)); need = (2.8 * sd / 3.3) ** 2
res["功效(跳空 ≥ +10%,60 天超額)"] = {"單件標準差%": round(sd, 2), "看出 +3.3% 要幾件(不含群聚)": int(round(need)), "2024–2025 每年件數": [int((E[big.values].date.str[:4] == y).sum()) for y in ("2024", "2025")]}
print(json.dumps(res["功效(跳空 ≥ +10%,60 天超額)"], ensure_ascii=False))
json.dump(res, open(os.path.join(OUT, "x7_ep_gaps.json"), "w"), ensure_ascii=False, indent=1)
