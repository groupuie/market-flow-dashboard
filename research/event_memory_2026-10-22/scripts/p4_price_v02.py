#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""價格層 v0.2(契約 v0.2 §2b):重抓 walk7 同一批代號的 Yahoo 日 K,**保存原始回應**,缺值留空、不補。
和 walk7 d3_daily.py 同一個網址與參數(2014-06-01 起、日 K、含拆分與配息、含 adjclose);差別:
  1. 原始回應 gzip 存檔 + SHA-256 + 抓取時間(SCRATCH/pv2/raw/,不進 repo)
  2. 原始開高低收量的缺值(null 或 ≤ 0)保留成 NaN,另存旗標;還原價 = 原始價 × adjclose / close,缺的就缺
  3. 不做任何補值、不用收盤補開盤
輸出:SCRATCH/pv2/bars_v02.pkl.gz、SCRATCH/pv2/manifest.json(每檔指紋與失敗清單)。抓下來的檔是外部資料,只用 json 解析。
用法:python3 -I p4_price_v02.py SCRATCH"""
import concurrent.futures as cf, datetime as dt, gzip, hashlib, json, os, pickle, sys, time, urllib.parse, urllib.error
from zoneinfo import ZoneInfo
import numpy as np
sys.path.insert(0, "/home/claude/market-flow-dashboard/scripts")
import astra_data as AD

ROOT = sys.argv[1]; PV = os.path.join(ROOT, "pv2"); RAW = os.path.join(PV, "raw"); os.makedirs(RAW, exist_ok=True)
SYMS = sorted(pickle.load(gzip.open(os.path.join(ROOT, "w7", "data", "daily.pkl.gz")))["bars"].keys())
P1 = int(dt.datetime(2014, 6, 1, tzinfo=dt.timezone.utc).timestamp()); P2 = int(time.time()) + 86400
Q = f"?period1={P1}&period2={P2}&interval=1d&events=div%2Csplit&includeAdjustedClose=true"


def job(s):
    for k in range(4):
        try:
            raw = AD.http_get(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(s)}{Q}", 40, 1, AD.YH_H)
            got = dt.datetime.now(dt.timezone.utc).isoformat()
            with gzip.open(os.path.join(RAW, f"{s}.json.gz"), "wb") as fh:
                fh.write(raw)
            r = json.loads(raw)["chart"]["result"][0]; ts = r.get("timestamp") or []
            if not ts:
                return s, None, {"err": "空的", "sha256": hashlib.sha256(raw).hexdigest(), "retrieved_utc": got}
            qd = r["indicators"]["quote"][0]; adj = ((r["indicators"].get("adjclose") or [{}])[0]).get("adjclose") or [None] * len(ts)
            tz = ZoneInfo(r["meta"].get("exchangeTimezoneName") or "America/New_York")

            def arr(key):
                v = qd.get(key) or [None] * len(ts)
                return np.array([np.nan if (x is None or not (x > 0)) else float(x) for x in v])
            o, h, l, c = arr("open"), arr("high"), arr("low"), arr("close")
            vol = np.array([np.nan if x is None else float(x) for x in (qd.get("volume") or [None] * len(ts))])
            ac = np.array([np.nan if (x is None or not (x > 0)) else float(x) for x in adj])
            d = [dt.datetime.fromtimestamp(t, tz).strftime("%Y-%m-%d") for t in ts]
            ev = r.get("events") or {}
            return s, {"d": d, "raw": np.c_[o, h, l, c, vol], "adjclose": ac, "name": r["meta"].get("longName") or r["meta"].get("shortName") or "",
                       "type": r["meta"].get("instrumentType"), "tz": str(tz), "splits": ev.get("splits"), "dividends": ev.get("dividends")}, \
                {"sha256": hashlib.sha256(raw).hexdigest(), "retrieved_utc": got, "n": len(d)}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return s, None, {"err": "404"}
            time.sleep(5 * (k + 1))
        except Exception as e:
            time.sleep(3 * (k + 1)); last = repr(e)[:200]
    return s, None, {"err": "失敗"}


t0 = time.time(); B, M = {}, {}
with cf.ThreadPoolExecutor(6) as ex:
    for n, (s, b, meta) in enumerate(ex.map(job, SYMS)):
        M[s] = meta
        if b is not None:
            B[s] = b
        if (n + 1) % 100 == 0:
            print(n + 1, "/", len(SYMS), "失敗", sum(1 for v in M.values() if "err" in v), round(time.time() - t0), "秒", flush=True)
blob = pickle.dumps({"bars": B, "fetched_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "query": Q}, protocol=4)
with gzip.open(os.path.join(PV, "bars_v02.pkl.gz"), "wb") as fh:
    fh.write(blob)
json.dump({"sha256_pickle": hashlib.sha256(blob).hexdigest(), "n_ok": len(B), "n_sym": len(SYMS), "per_symbol": M,
           "欄位": "raw = [原始開, 高, 低, 收, 量](缺值 = NaN,不補);adjclose = Yahoo 還原收盤;還原價 = 原始 × adjclose / 原始收盤"},
          open(os.path.join(PV, "manifest.json"), "w"), ensure_ascii=False, indent=1)
print("完成", len(B), "/", len(SYMS), round(time.time() - t0), "秒")
