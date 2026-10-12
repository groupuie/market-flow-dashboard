# 擴大範圍資料檢查 1:scripts/astra_data.py 的 sw_series(照抄網站 swSeriesJS)
#   (a) 和研究 s4_lib(swing + B2,numpy/pandas)在同一批發布日K上的 底/頂/回 是否相同
#   (b) 和網站 index.html 的 swSeriesJS(node 直接跑原始碼)逐位元比對:底/頂/回、原因、破底計數
# 用法:python3 c1_signal_check.py <astra 輸出資料夾>
import json, os, re, subprocess, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts")); sys.path.insert(0, os.path.join(REPO, "research", "swing_tune_2026-10-12"))
import astra_data as AD
from s4_lib import swing, cooldown
OUT = sys.argv[1]; KD = os.path.join(OUT, "k")
syms = sorted(f[:-5] for f in os.listdir(KD) if f.endswith(".json"))
res = {"n": len(syms), "a_mismatch": [], "b_mismatch": [], "n_sig": 0}
PY_OUT = {}
for s in syms:
    B = json.load(open(os.path.join(KD, s + ".json")))["bars"]
    if len(B) < 30: continue
    W = AD.sw_series(B); PY_OUT[s] = {"bot": W["bot"], "top": W["top"], "b2": W["b2"], "why": {str(k): v for k, v in W["why"].items()}, "rep": {str(k): v for k, v in W["rep"].items()}}
    res["n_sig"] += len(W["bot"]) + len(W["top"]) + len(W["b2"])
    O, H, L, C = (np.array([b[k] for b in B], float) for k in (1, 2, 3, 4))
    b0, t0, _ = swing(O, H, L, C); cs = pd.Series(C); b2 = cooldown(((cs > cs.rolling(200).mean()) & (cs <= cs.rolling(7).min())).to_numpy())
    if list(np.flatnonzero(b0)) != W["bot"] or list(np.flatnonzero(t0)) != W["top"] or list(np.flatnonzero(b2)) != W["b2"]:
        res["a_mismatch"].append({"s": s, "bot": [len(W["bot"]), int(b0.sum())], "top": [len(W["top"]), int(t0.sum())], "b2": [len(W["b2"]), int(b2.sum())]})
# (b) node:從 index.html 取出 swSeriesJS 原始碼
html = open(os.path.join(REPO, "index.html"), encoding="utf-8").read()
m = re.search(r"function swSeriesJS\(B\)\{.*?\n\}\n", html, re.S); assert m, "找不到 swSeriesJS"
js = m.group(0) + """
const fs=require('fs');const dir=process.argv[2];const out={};
for(const f of fs.readdirSync(dir)){if(!f.endsWith('.json'))continue;const B=JSON.parse(fs.readFileSync(dir+'/'+f)).bars;if(B.length<30)continue;
  const W=swSeriesJS(B);out[f.slice(0,-5)]={bot:W.bot,top:W.top,b2:W.b2,why:W.why,rep:W.rep};}
fs.writeFileSync(process.argv[3],JSON.stringify(out));"""
tmp = os.path.join(OUT, "_c1.js"); open(tmp, "w").write(js)
subprocess.run(["node", tmp, KD, os.path.join(OUT, "_c1_js.json")], check=True)
JS = json.load(open(os.path.join(OUT, "_c1_js.json")))
for s, p in PY_OUT.items():
    j = JS.get(s)
    if j is None or j["bot"] != p["bot"] or j["top"] != p["top"] or j["b2"] != p["b2"] or j["why"] != p["why"] or {k: int(v) for k, v in j["rep"].items()} != p["rep"]:
        res["b_mismatch"].append(s)
os.remove(tmp); os.remove(os.path.join(OUT, "_c1_js.json"))
res["a_mismatch_n"] = len(res["a_mismatch"]); res["b_mismatch_n"] = len(res["b_mismatch"])
json.dump(res, open(os.path.join(HERE, "c1_signal_check.json"), "w"), ensure_ascii=False, indent=1)
print({k: v for k, v in res.items() if k not in ("a_mismatch",)}, res["a_mismatch"][:5])
