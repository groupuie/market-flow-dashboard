#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk8 E1:FINRA 每日空單量(Reg SHO,場外成交的放空量;CNMS 合併檔)2018-08-01 ~ 2026-10-20(CNMS 檔 2018-08-01 才開始;之前的日期 403)
只留 walk7 名單裡的股票 → data/finra_short.pkl.gz:{代號: [[日期, 放空量, 總量], …]}
用法:python3 e1_finra.py OUT_DIR W7_DIR"""
import concurrent.futures as cf, gzip, os, pickle, sys, time, urllib.error, urllib.request
import pandas as pd

OUT, W7 = sys.argv[1], sys.argv[2]
SYMS = set(pd.read_pickle(os.path.join(W7, "out", "S7.pkl")).sym.unique())
CAL = pickle.load(gzip.open(os.path.join(W7, "data", "daily.pkl.gz")))["bars"]["SPY"]["d"]
days = [d for d in CAL if "2018-08-01" <= d <= "2026-10-20"]


def job(d):
    u = f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{d.replace('-', '')}.txt"
    for k in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as r:
                txt = r.read().decode("utf-8", "ignore")
            out = {}
            for line in txt.splitlines()[1:]:
                p = line.split("|")
                if len(p) >= 5 and p[1].replace(".", "-").replace("/", "-") in SYMS:
                    try:
                        out[p[1].replace(".", "-").replace("/", "-")] = (float(p[2]), float(p[4]))
                    except ValueError:
                        pass
            return d, out, None
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                return d, None, str(e.code)
            time.sleep(3 * (k + 1))
        except Exception as e:
            time.sleep(3 * (k + 1))
    return d, None, "失敗"


R, F = {}, {}; t0 = time.time()
with cf.ThreadPoolExecutor(6) as ex:
    for n, (d, out, err) in enumerate(ex.map(job, days)):
        if err:
            F[d] = err
        else:
            for s, (sv, tv) in out.items():
                R.setdefault(s, []).append([d, sv, tv])
        if (n + 1) % 250 == 0:
            print(n + 1, "/", len(days), "失敗", len(F), round(time.time() - t0), "秒", flush=True)
with gzip.open(os.path.join(OUT, "data", "finra_short.pkl.gz"), "wb") as fh:
    pickle.dump({"short": R, "fail": F, "days": len(days)}, fh, protocol=4)
print("完成:股票", len(R), "交易日", len(days), "失敗", len(F), list(F.items())[:10])
