# 描述(沒有預先登記):「變安靜的股票」(波動收縮比 ≤ 0.96)vs 其他,在 2021–2025 的買點三種結果與 10 天報酬
import json, numpy as np, pandas as pd
P = pd.read_pickle("out/real_preds.pkl"); P = P[(P.split == "wf") & (P.target == "T1b")]
nat = json.load(open("out/x2_nature.json"))
S = pd.read_pickle("out/scen.pkl")[["sym", "i", "atr20_60", "vr20_60"]]
g = P.merge(S, on=["sym", "i"])
import gzip
B = json.load(gzip.open("../walk4/data/bars.json.gz"))["bars"]; A = {s: np.array([[float(b[k]) for k in range(1, 6)] for b in B[s]]).T for s in g.sym.unique()}
def three(s, i):
    o, h, l, c, v = A[s]; C = c[i]; tr = [max(h[k], c[k-1]) - min(l[k], c[k-1]) for k in range(i-19, i+1)]; a = sum(tr)/20/C
    for j in range(1, 11):
        if l[i+j] <= C*(1-1.5*a): return "洗"
        if h[i+j] >= C*(1+2*a): return "對"
    return "沒"
g["r3"] = [three(s, i) for s, i in zip(g.sym, g.i)]; g["f10"] = [100*(A[s][3][i+10]/A[s][3][i]-1) for s, i in zip(g.sym, g.i)]
def row(h):
    vc = h.r3.value_counts(normalize=True)*100; d = {k: round(float(vc.get(k, 0)), 1) for k in ("對", "洗", "沒")}
    d["有動%"] = round(d["對"] + d["洗"], 1); d["動的裡面先往上%"] = round(100*d["對"]/(d["對"]+d["洗"]), 1); d["10天報酬平均%"] = round(float(h.f10.mean()), 2); d["張數"] = len(h); return d
out = {"全部": row(g), "變安靜(波動收縮比 ≤ 0.96)": row(g[g.atr20_60 <= 0.96]), "其他": row(g[g.atr20_60 > 0.96]),
       "量縮(近 20 天均量 ÷ 前 60 天 ≤ 0.85)": row(g[g.vr20_60 <= 0.85]), "量增(≥ 1.2)": row(g[g.vr20_60 >= 1.2])}
json.dump(out, open("out/x4_quiet.json", "w"), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))
