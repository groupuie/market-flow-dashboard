# 📍短線 v1.0 的 Python 參考實作(網站 swSeriesJS 逐行對應)
#   和 v0.9 的差別:① 頂不再分上升趨勢(網站一律原色)
#                   ② 破底計數:買點(▲底/△回檔)t 的收盤 < 20 根內買點 s 那根的最低(破底)
#                      → rep[t] = 這些 s 的 rep 最大值 +1;都沒有 = 1(網站 ≥2 才在字旁加 ②③…)
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from swing_ref_v09 import sw_py_v09

def sw_py_v10(B):
    r = sw_py_v09(B)
    D = [b[0] for b in B]; L = [b[3] for b in B]; C = [b[4] for b in B]
    idx = {d: i for i, d in enumerate(D)}
    buys = sorted(idx[d] for d in r["bot"] + r["b2"])
    k = {}
    for t in buys:
        best = 0
        for s in buys:
            if s < t - 20 or s >= t: continue
            if C[t] < L[s] and k[s] > best: best = k[s]
        k[t] = best + 1
    return {"bot": r["bot"], "top": r["top"], "b2": r["b2"], "rt": r["rt"], "rep": {D[t]: v for t, v in k.items()}}
