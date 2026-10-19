# s6:採集器兩處修正的離線單元測試(不連富途、不推 gist)
#   ① yahoo_hist:Yahoo 美東 20–22 點把當天日棒 close 清成 null → 用 meta.regularMarketPrice 補;盤前那根(regularMarketTime 在前一天)照舊跳過;正常資料不變
#   ② refresh_klines 日更段重設看門狗:只有在 main() 裝了 SIGALRM 處理器時才重設;沒裝(SIG_DFL)不動
#   用法:python3 s6_collector_unit.py <market_export.py 路徑> <實抓的 NVDA 3mo 日K JSON(美東晚上 close=null 那段時間抓的)>
import json, sys, copy, importlib.util, signal, time, datetime as dt
spec = importlib.util.spec_from_file_location("me", sys.argv[1]); me = importlib.util.module_from_spec(spec); spec.loader.exec_module(me)
raw = json.load(open(sys.argv[2]))
def run(payload):
    me.http_json = lambda url, timeout=15, retries=3: payload
    return me.yahoo_hist("NVDA")
ok = True
r = raw["chart"]["result"][0]; m = r["meta"]; q = r["indicators"]["quote"][0]
print("實抓:最後一根", dt.datetime.fromtimestamp(r["timestamp"][-1] + m["gmtoffset"], dt.timezone.utc).date(), "close", q["close"][-1], "| meta.regularMarketPrice", m["regularMarketPrice"])
# ① 晚上 null 窗:補成 regularMarketPrice
c, v, _ = run(copy.deepcopy(raw))
print("① null 窗:最後收盤", round(c[-1], 4), "量", v[-1], "→ 應 = regularMarketPrice、量 = 當天量");  ok &= abs(c[-1] - m["regularMarketPrice"]) < 1e-9 and v[-1] == q["volume"][-1]
# ② 正常(close 有值)→ 與舊邏輯完全相同
p = copy.deepcopy(raw); p["chart"]["result"][0]["indicators"]["quote"][0]["close"][-1] = 217.23
c2, v2, _ = run(p); old = [x for x in p["chart"]["result"][0]["indicators"]["quote"][0]["close"] if x is not None]
print("② 正常:新舊收盤序列相同 =", c2 == old);  ok &= c2 == old
# ③ 盤前:最後一根 null、regularMarketTime 在前一天 → 跳過(= 舊行為)
p = copy.deepcopy(raw); rr = p["chart"]["result"][0]; rr["meta"]["regularMarketTime"] = rr["timestamp"][-2] + 6.5 * 3600
c3, _, _ = run(p); old3 = [x for x in rr["indicators"]["quote"][0]["close"] if x is not None]
print("③ 盤前那根:跳過 =", c3 == old3, "最後收盤", round(c3[-1], 4));  ok &= c3 == old3
# ④ meta 缺 regularMarketPrice → 舊行為
p = copy.deepcopy(raw); p["chart"]["result"][0]["meta"].pop("regularMarketPrice", None)
c4, _, _ = run(p); print("④ meta 缺價:跳過 =", c4[-1] == old3[-1]);  ok &= c4[-1] == old3[-1]
# ⑤ 看門狗重設:裝了處理器 → alarm 被重設成 420;沒裝 → 不動
def snippet():
    try:
        import signal as _sg
        if callable(_sg.getsignal(_sg.SIGALRM)): _sg.alarm(420)
    except Exception: pass
signal.signal(signal.SIGALRM, signal.SIG_DFL); signal.alarm(0); snippet(); left = signal.alarm(0)
print("⑤a 沒裝處理器:剩餘 alarm =", left, "(應 0,不動)");  ok &= left == 0
signal.signal(signal.SIGALRM, lambda s, f: None); signal.alarm(30); snippet(); left = signal.alarm(0)
print("⑤b 裝了處理器、原本剩 30 秒:重設後剩", left, "(應 420)");  ok &= left == 420
src = open(sys.argv[1], encoding="utf-8").read()
print("⑤c 程式碼內確實是同一段:", "if callable(_sg.getsignal(_sg.SIGALRM)): _sg.alarm(420)" in src)
print("全部通過" if ok else "有失敗")
