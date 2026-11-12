#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk7 D3b:補抓 2026 年改代號、還在交易的成分股(BK → BNY),併進 daily.pkl.gz;ymap 加上舊代號 → 新代號
用法:python3 d3b_extra.py OUT_DIR"""
import gzip, hashlib, json, os, pickle, sys
sys.argv = [sys.argv[0], sys.argv[1]]
OUT = sys.argv[1]
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "d3_daily.py")).read().split("t0 = time.time(); B, F = {}, {}")[0]
src = src.replace('print("候選"', 'pass  # print("候選"')
ns = {"__name__": "d3b"}; exec(src, ns)
EXTRA = {"BK": "BNY"}
pk = os.path.join(OUT, "data", "daily.pkl.gz"); D = pickle.load(gzip.open(pk))
for old, new in EXTRA.items():
    s, b, err = ns["job"](new)
    print(new, "抓到", None if b is None else len(b["d"]), err)
    if b is not None:
        D["bars"][new] = b
        for k, v in list(D["ymap"].items()):
            if v == old:
                D["ymap"][k] = new
        D["cand"][new] = "S&P 500"
raw = pickle.dumps(D, protocol=4)
with gzip.open(pk, "wb") as fh:
    fh.write(raw)
mp = os.path.join(OUT, "data", "daily_manifest.json"); man = json.load(open(mp))
man["sha256_pickle"] = hashlib.sha256(raw).hexdigest(); man["n"] = len(D["bars"]); man["補抓"] = EXTRA
json.dump(man, open(mp, "w"), ensure_ascii=False, indent=1); print("更新後", man["n"], man["sha256_pickle"][:12])
