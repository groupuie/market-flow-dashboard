# t25 對拍(Codex v0.1 修正 B):「加」排除「當日 + 前 10 根」有出 —— pandas/Python 端。
#   出 = scripts/flow_climate.py 的 fc_events(上線 Python 版,與前端 fcSeriesJS 同口徑)+ data/flow_climate.json 的氣候序列
#   加 = 與 t23h_jscheck.py 同公式,再加上出的排除;舊版排除 [i-10, i-1]、新版 [i-10, i]
# 用法:python3 t25_jscheck.py <資料夾(kline_<代號>.json、kline_QQQ.json、flow_climate.json)> 代號...
# 輸出 JSON,應與 node t25_jscheck.js <index.html> <資料夾> 代號... 逐字相同(只比 new;old 是給對照用)
import json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
import flow_climate as fc
d0 = sys.argv[1]; syms = sys.argv[2:]
clim = json.load(open(os.path.join(d0, "flow_climate.json")))
ser = clim["series"]; cm = {d: c / 100 for d, c in zip(ser["d"], ser["c"]) if c is not None}
lastc = [c for c in ser["c"] if c is not None][-1] / 100; lastd = [d for d, c in zip(ser["d"], ser["c"]) if c is not None][-1]
def clim_of(d): return cm.get(d, lastc if d > lastd else None)          # 與 fcClimOf 同:晚於序列 → 沿用最新;早於 → None
th = clim.get("th") or fc.TH
q = pd.DataFrame([x[:5] for x in json.load(open(os.path.join(d0, "kline_QQQ.json")))["bars"]], columns=list("dohlc")).set_index("d")["c"].astype(float)
qd = (q < q.rolling(20).mean()).where(q.rolling(20).mean().notna())
out = {}
for s in syms:
    bars = json.load(open(os.path.join(d0, f"kline_{s}.json")))["bars"]
    df = pd.DataFrame([x[:5] for x in bars], columns=list("dohlc")).set_index("d").astype(float)
    C, L = df.c, df.l
    ev, _ = fc.fc_events(list(df.index), list(C.values), clim_of, th)
    chu = pd.Series(False, index=df.index); chu.iloc[[e["i"] for e in ev if e["k"] == "trim"]] = True
    S50, S100, S200 = C.rolling(50).mean(), C.rolling(100).mean(), C.rolling(200).mean()
    u = (C > S200) & (S50 > S200) & (S200 > S200.shift(20)); ma3 = (S50 > S100) & (S100 > S200)
    hi = C.rolling(252, min_periods=200).max(); nh = C >= hi
    UTS = u.shift(1, fill_value=False) & ma3.shift(1, fill_value=False) & (nh.astype(int).rolling(40, min_periods=1).max().shift(1).fillna(0) > 0)
    d = C.diff(); g = d.clip(lower=0); l = (-d).clip(lower=0)
    ag = g.ewm(alpha=1 / 14, adjust=False).mean(); al = l.ewm(alpha=1 / 14, adjust=False).mean(); R = 100 - 100 / (1 + ag / al.replace(0, np.nan))
    rsiX = (R <= 40) & (R.shift(1) > 40)
    lo = C.rolling(20).mean() - 2 * C.rolling(20).std(ddof=0)
    lob = (L <= lo) & ((L > lo).astype(int).rolling(10, min_periods=10).sum().shift(1) == 10)
    mk = qd.reindex(df.index)
    base = (UTS & (rsiX | lob) & (mk == True)).fillna(False).astype(bool)
    res = {"chu": [i for i in df.index[chu.values]]}
    for tag, win, sh in (("new", 11, 0), ("old", 10, 1)):          # new:[i-10,i];old:[i-10,i-1]
        c10 = chu.astype(int).rolling(win, min_periods=1).max().shift(sh).fillna(0).astype(bool)
        raw = base & ~c10
        sig = raw & ~(raw.shift(1, fill_value=False).astype(int).rolling(10, min_periods=1).max() > 0)
        res[tag] = [f"{i}|{'R' if rsiX[i] else ''}{'L' if lob[i] else ''}" for i in df.index[sig.values]]
        res[tag + "_raw"] = int(raw.sum())
    res["ut"] = int(UTS.sum())
    out[s] = res
print(json.dumps(out, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
