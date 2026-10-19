# s7:scripts/flow_climate.py 的 yahoo() 修正驗收(Yahoo 美東晚上把當天 close/adjclose 清成 null → 用 meta.regularMarketPrice 補)
#   ① 離線:用 s6 抓到的 NVDA 實際回應(close 與 adjclose 最後一根都是 null)→ 最後一天 = regularMarketPrice,其餘日期與舊碼相同
#   ② 離線:正常 / 盤前那根(regularMarketTime 在前一天)/ meta 缺價 → 與舊碼完全相同
#   ③ 線上(有網路時):QQQ / HYG / IEF 新舊碼最後日期(在美東 20–22 點跑,舊碼應少最後一天)
#   用法:python3 s7_flow_climate_unit.py <flow_climate.py 新版> <flow_climate.py 舊版> <NVDA 回應 JSON> [--live]
import json, sys, copy, importlib.util
def load(p, name):
    s = importlib.util.spec_from_file_location(name, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
new, old = load(sys.argv[1], "fc_new"), load(sys.argv[2], "fc_old")
raw = json.load(open(sys.argv[3]))
def run(mod, payload):
    mod.http = lambda u, **k: payload
    return mod.yahoo("NVDA")
ok = True
r = raw["chart"]["result"][0]
adj = ((r["indicators"].get("adjclose") or [{}])[0] or {}).get("adjclose")
print("回應:close 最後", r["indicators"]["quote"][0]["close"][-1], "| adjclose 最後", (adj or [None])[-1], "| regularMarketPrice", r["meta"]["regularMarketPrice"])
a, b = run(new, copy.deepcopy(raw)), run(old, copy.deepcopy(raw))
la, lb = max(a), max(b)
print("① null 窗:新碼最後", la, a[la], "| 舊碼最後", lb, b[lb]);  ok &= a[la] == r["meta"]["regularMarketPrice"] and la > lb and all(a[k] == b[k] for k in b)
p = copy.deepcopy(raw); rr = p["chart"]["result"][0]
for arr in (rr["indicators"]["quote"][0]["close"], ((rr["indicators"].get("adjclose") or [{}])[0] or {}).get("adjclose") or []):
    if arr: arr[-1] = 217.23
print("② 正常:新舊相同 =", run(new, copy.deepcopy(p)) == run(old, copy.deepcopy(p)));  ok &= run(new, copy.deepcopy(p)) == run(old, copy.deepcopy(p))
p = copy.deepcopy(raw); rr = p["chart"]["result"][0]; rr["meta"]["regularMarketTime"] = rr["timestamp"][-2] + 6 * 3600
print("③ 盤前那根:新舊相同 =", run(new, copy.deepcopy(p)) == run(old, copy.deepcopy(p)));  ok &= run(new, copy.deepcopy(p)) == run(old, copy.deepcopy(p))
p = copy.deepcopy(raw); p["chart"]["result"][0]["meta"].pop("regularMarketPrice", None)
print("④ meta 缺價:新舊相同 =", run(new, copy.deepcopy(p)) == run(old, copy.deepcopy(p)));  ok &= run(new, copy.deepcopy(p)) == run(old, copy.deepcopy(p))
if "--live" in sys.argv:
    new2, old2 = load(sys.argv[1], "fc_new2"), load(sys.argv[2], "fc_old2")
    for s in ("QQQ", "HYG", "IEF", "^GSPC"):
        try:
            x, y = new2.yahoo(s), old2.yahoo(s); print(f"⑤ 線上 {s}: 新碼最後 {max(x)} {x[max(x)]:.4f} | 舊碼最後 {max(y)} {y[max(y)]:.4f}")
        except Exception as e: print("⑤ 線上", s, "失敗", type(e).__name__, e)
print("全部通過" if ok else "有失敗")
