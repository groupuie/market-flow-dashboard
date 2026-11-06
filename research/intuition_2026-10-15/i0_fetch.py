#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盤感訓練 I0:抓 268 檔(盤感測試名單)2009 起的日K,照網站四捨五入,存成快照 + 指紋

用法:python3 research/intuition_2026-10-15/i0_fetch.py OUT_DIR
- 和正式盤感測試同一套(scripts/astra_data.py 的 yahoo()、rp());只是起點拉到 2009-01-01(經驗庫要 2010 起)
- 不改任何正式程式;只讀公開資料
"""
import concurrent.futures as cf, datetime as dt, gzip, hashlib, json, os, sys, time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import astra_data as AD

OUT = sys.argv[1]
U = [s.strip() for s in open("/tmp/astra-ledger-wt/universe.txt") if s.strip() and not s.startswith("#")]
p1 = int(dt.datetime(2009, 1, 1, tzinfo=dt.timezone.utc).timestamp()); now = int(time.time())


def job(s):
    for k in range(3):
        try:
            b = AD.yahoo(s, p1, now + 86400)
            return s, [[x[0], AD.rp(x[1]), AD.rp(x[2]), AD.rp(x[3]), AD.rp(x[4]), x[5]] for x in b], None
        except Exception as e:
            err = str(e)[:120]; time.sleep(3)
    return s, None, err


BARS, FAIL = {}, {}
with cf.ThreadPoolExecutor(8) as ex:
    for s, b, err in ex.map(job, U):
        if err or not b:
            FAIL[s] = err or "沒有資料"
        else:
            BARS[s] = b
raw = json.dumps(BARS, separators=(",", ":")).encode()
with gzip.open(os.path.join(OUT, "bars.json.gz"), "wb") as fh:
    fh.write(raw)
man = {"fetched_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "n": len(BARS), "fail": FAIL,
       "sha256": hashlib.sha256(raw).hexdigest(), "last_date": {s: b[-1][0] for s, b in BARS.items() if s in ("SPY", "QQQ")},
       "first_date_min": min(b[0][0] for b in BARS.values()), "short_history": sorted(s for s, b in BARS.items() if b[0][0] > "2010-06-01")}
json.dump(man, open(os.path.join(OUT, "manifest.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: (v if k != "short_history" else len(v)) for k, v in man.items()}, ensure_ascii=False))
