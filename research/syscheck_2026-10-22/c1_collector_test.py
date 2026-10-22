# 2026-10-22 採集器修正的單元測試(假的富途 OpenD + 假的 Yahoo 回應)
import sys, os, json, types, time, tempfile, importlib.util
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
# 假 futu 模組
fut = types.ModuleType("futu"); fut.RET_OK = 0; fut.RET_ERROR = -1
CALLS = []
class FakeQ:
    mode = "ok"; bad = set()
    def __init__(self, host=None, port=None): pass
    def close(self): pass
    def get_market_snapshot(self, fs):
        CALLS.append(len(fs))
        if FakeQ.mode == "net": return -1, "網絡中斷"
        b = [c for c in fs if c in FakeQ.bad]
        if b: return -1, "未知股票 " + b[0].replace("US.", "")
        import pandas as pd
        rows = [{"code": c, "update_time": "2026-10-21 15:59:59", "open_price": 10, "high_price": 11, "low_price": 9, "last_price": 10.5, "volume": 100, "turnover_rate": 1.0} for c in fs]
        return 0, pd.DataFrame(rows)
fut.OpenQuoteContext = FakeQ
sys.modules["futu"] = fut
spec = importlib.util.spec_from_file_location("me", os.path.join(REPO, "market_export.py")); me = importlib.util.module_from_spec(spec); spec.loader.exec_module(me)
_real_sleep = time.sleep
me.time.sleep = lambda s: None          # 不真的睡(注意:這會改到全域 time 模組)
me.snap_trade_date = lambda: "2026-10-21"
ok = True
def check(name, cond, info=""):
    global ok; ok &= bool(cond); print(("PASS " if cond else "FAIL ") + name, info)
syms = ["S%03d" % i for i in range(340)]
tmp = tempfile.mkdtemp(dir=os.path.dirname(os.path.abspath(__file__))); args = types.SimpleNamespace(config=os.path.join(tmp, "config.json"))
# 1) 斷線:不拆批、不標壞、只記一筆錯誤/批
FakeQ.mode = "net"; me.ERRORS.clear(); CALLS.clear()
out = me.snapshot_today(syms, args)
sb = json.load(open(args.config + ".snapbad.json")) if os.path.exists(args.config + ".snapbad.json") else {}
check("斷線:沒有標壞代號", not sb and not me.SNAP_BAD, f"snapbad={len(sb)}")
check("斷線:每批只打 1 次(不拆)", CALLS == [200, 140], f"calls={CALLS}")
check("斷線:錯誤 2 筆、寫明下一輪再抓", len(me.ERRORS) == 2 and "下一輪" in str(me.ERRORS[0]), str(me.ERRORS[:1])[:120])
# 2) 一檔真的壞代號:照舊拆批隔離,其他照常
FakeQ.mode = "ok"; FakeQ.bad = {"US.S007"}; me.ERRORS.clear(); CALLS.clear()
out = me.snapshot_today(syms, args)
sb = json.load(open(args.config + ".snapbad.json"))
check("壞代號:只有 S007 被標", list(sb) == ["S007"], f"{list(sb)}")
check("壞代號:其他 339 檔都有當日棒", len(out) == 339 and "S007" not in out, f"n={len(out)}")
# 3) 舊版斷網誤標(同一時間戳 170 檔)→ 載入時清掉;真的壞代號(另一個時間戳)保留
t0 = time.time() - 3600
bad = {"S%03d" % i: t0 for i in range(170)}; bad["S300"] = time.time() - 7200
json.dump(bad, open(args.config + ".snapbad.json", "w"))
FakeQ.bad = {"US.S300"}; me.ERRORS.clear(); CALLS.clear()
out = me.snapshot_today(syms, args)
sb = json.load(open(args.config + ".snapbad.json"))
check("誤標清除:170 檔放回、S300 仍擋", list(sb) == ["S300"] and len(out) == 339, f"snapbad={list(sb)} n={len(out)}")
# 4) Yahoo 日K:最後一根 close=null 且同一美東日 → 用 regularMarketPrice
def fake_chart(last_close, rmt_day_offset=0):
    import datetime as _d
    ts = [int(_d.datetime(2026,10,d,13,30,tzinfo=_d.timezone.utc).timestamp()) for d in (20,21,22)]   # 10/20、10/21、10/22 09:30 ET
    rmt = ts[-1] + 6*3600 + rmt_day_offset*86400
    return {"chart": {"result": [{"timestamp": ts, "meta": {"gmtoffset": -14400, "regularMarketPrice": 101.5, "regularMarketTime": rmt},
        "indicators": {"quote": [{"open": [99, 100, 100.5], "high": [101, 102, 102.5], "low": [98, 99, 99.5], "close": [100, 101, last_close], "volume": [1, 2, 3]}],
                       "adjclose": [{"adjclose": [100, 101, last_close]}]}}]}}
me.last_done_session = lambda: "2026-10-22"
me.http_json = lambda u, t=15, *a, **k: fake_chart(None)
b = me.yahoo_ohlc("STX", "3mo", adjust=True, complete_only=True)
check("Yahoo null 收盤:補上當天(10-22,101.5)", b[-1][0] == "2026-10-22" and b[-1][4] == 101.5, str(b[-1]))
me.http_json = lambda u, t=15, *a, **k: fake_chart(None, rmt_day_offset=-1)
b = me.yahoo_ohlc("STX", "3mo", adjust=True, complete_only=True)
check("Yahoo null 收盤但報價是前一天:照舊跳過", b[-1][0] == "2026-10-21", str(b[-1]))
me.http_json = lambda u, t=15, *a, **k: fake_chart(102.0)
b = me.yahoo_ohlc("STX", "3mo", adjust=True, complete_only=True)
check("Yahoo 正常收盤:不變", b[-1][4] == 102.0 and len(b) == 3, str(b[-1]))
# 5) 防睡:Linux → n/a;假裝 macOS + 假 caffeinate → ok,且真的開了一個獨立程式
me.CAF_STAT.clear(); me.keep_awake(); check("Linux:caf=n/a", me.CAF_STAT.get("caf") == "n/a", str(me.CAF_STAT))
fake = os.path.join(tmp, "caffeinate"); mark = os.path.join(tmp, "caf_args.txt")
open(fake, "w").write("#!/bin/sh\necho \"$@\" > %s\n" % mark); os.chmod(fake, 0o755)
import shutil as _sh
real_which = _sh.which; _sh.which = lambda n: fake if n == "caffeinate" else real_which(n)
plat = sys.platform; me.sys.platform = "darwin"
me.CAF_STAT.clear(); me.keep_awake(); print("CAF_STAT", me.CAF_STAT)
for _ in range(30):
    if os.path.exists(mark): break
    _real_sleep(0.2)
me.sys.platform = plat; _sh.which = real_which
check("macOS:caf=ok、參數 -i -s -t 420", me.CAF_STAT.get("caf") == "ok" and open(mark).read().split() == ["-i", "-s", "-t", "420"], str(me.CAF_STAT) + " args=" + (open(mark).read().strip() if os.path.exists(mark) else "-"))
print("ALL PASS" if ok else "SOME FAIL")
