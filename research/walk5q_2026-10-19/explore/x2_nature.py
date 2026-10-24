# 事後描述(沒有預先登記):模型抓到的是「方向」還是「波動」? — 只用逐年往前 2021–2025 的預測
import gzip, json, numpy as np, pandas as pd
B = json.load(gzip.open("../walk4/data/bars.json.gz"))["bars"]
P = pd.read_pickle("out/real_preds.pkl"); P = P[P.split == "wf"]
A = {}
for s in P.sym.unique():
    x = np.array([[float(b[k]) for k in range(1, 6)] for b in B[s]]).T; A[s] = x
def three(s, i, side):
    o, h, l, c, v = A[s]; C = c[i]
    tr = [max(h[k], c[k-1]) - min(l[k], c[k-1]) for k in range(i-19, i+1)]; a = sum(tr)/20/C
    U, D = (C*(1+2*a), C*(1-1.5*a)) if side == "b" else (C*(1+1.5*a), C*(1-2*a))
    for j in range(1, 11):
        if side == "b":
            if l[i+j] <= D: return "洗"
            if h[i+j] >= U: return "對"
        else:
            if h[i+j] >= U: return "軋"
            if l[i+j] <= D: return "對"
    return "沒"
out = {}
for t, side in (("T1b", "b"), ("T1s", "s")):
    g = P[P.target == t].copy()
    g["r3"] = [three(s, i, side) for s, i in zip(g.sym, g.i)]
    g["fwd10"] = [100*(A[s][3][i+10]/A[s][3][i]-1) for s, i in zip(g.sym, g.i)]
    g["dec"] = pd.qcut(g.p_m2.rank(method="first"), 10, labels=False)
    def row(h): 
        vc = h.r3.value_counts(normalize=True)*100
        return {k: round(float(vc.get(k, 0)), 1) for k in (["對", "洗", "沒"] if side == "b" else ["對", "軋", "沒"])} | {"10天後漲跌%平均": round(float(h.fwd10.mean()), 2), "中位數": round(float(h.fwd10.median()), 2), "張數": len(h)}
    out[t] = {"全部": row(g), "M2 最高一成": row(g[g.dec == 9]), "M2 最低一成": row(g[g.dec == 0]), "十分位 對%": [round(100*float((g[g.dec == d].r3 == "對").mean()), 1) for d in range(10)],
              "十分位 沒%": [round(100*float((g[g.dec == d].r3 == "沒").mean()), 1) for d in range(10)], "十分位 10天漲跌%": [round(float(g[g.dec == d].fwd10.mean()), 2) for d in range(10)]}
# 同一個情境:買點分數和賣點分數的相關
b = P[P.target == "T1b"].set_index(["sym", "i"]).p_m2; s_ = P[P.target == "T1s"].set_index(["sym", "i"]).p_m2
j = pd.concat([b, s_], axis=1, keys=["b", "s"]).dropna(); out["買分數 vs 賣分數 相關(Spearman)"] = round(float(j.b.rank().corr(j.s.rank())), 3)
json.dump(out, open("out/x2_nature.json", "w"), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))
