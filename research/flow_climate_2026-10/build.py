import time, numpy as np, pandas as pd, pickle, warnings
warnings.filterwarnings("ignore")
from lib import *
from market import market_features, cot_features
t0=time.time()
cal = calendar(); cal = cal[cal >= "2004-01-01"]
eq = universe("equity")
P = panel(eq, cal)
print("panel", P["C"].shape, "%.0fs"%(time.time()-t0))
spx_ret = np.log(series("SPY", cal)).diff()
F = stock_features(P, spx_ret)
print("features", len(F), "%.0fs"%(time.time()-t0))
T = targets(P)
M = market_features(cal, P)
CT = cot_features(cal)
print("market", M.shape, CT.shape, "%.0fs"%(time.time()-t0))
f32 = lambda d: {k: v.astype("float32") for k, v in d.items()}
pickle.dump({"P": f32(P), "F": f32(F), "T": f32(T)}, open(DT + "/stock.pkl", "wb"), protocol=4)
pd.concat([M, CT], axis=1).to_pickle(DT + "/market.pkl")
# index targets
I = {}
for s in ("SPY", "QQQ", "SMH", "IWM"):
    d = load(s).reindex(cal)
    Pi = {"O": d[["o"]].rename(columns={"o": s}), "H": d[["h"]].rename(columns={"h": s}), "L": d[["l"]].rename(columns={"l": s}), "C": d[["c"]].rename(columns={"c": s})}
    for k, v in targets(Pi).items(): I[f"{s}_{k}"] = v[s]
pd.DataFrame(I).to_pickle(DT + "/idx_targets.pkl")
print("saved %.0fs"%(time.time()-t0))
