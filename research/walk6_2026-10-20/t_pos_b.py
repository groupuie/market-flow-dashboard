# 對照(偷看未來):分數 = 12 個月答案 + 雜訊 → H1 / H2 應該很顯著
import sys, numpy as np, pandas as pd
src = open("l2b_eval.py").read().split("if NPL:")[0].replace("SC, OUT = sys.argv[1], sys.argv[2]", "SC, OUT = 'out/scen_long.pkl', None")
ns = {}; exec(src, ns); S, pick, panel_timing, fm_ic = ns["S"], ns["pick"], ns["panel_timing"], ns["fm_ic"]
V = pick("m12"); E, K = V[V.etf], V[~V.etf]; rng = np.random.default_rng(1)
for sd in (0.3, 1.0):
    le = E["f_m12"].values + rng.normal(0, sd, len(E)); lk = K["f_m12"].values + rng.normal(0, sd, len(K))
    print("雜訊", sd, "H1", panel_timing(E, np.sign(le), E["f_m12"].values), "H2", fm_ic(K, lk, K["f_m12"].values))
