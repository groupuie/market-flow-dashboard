#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""13F 可行性抽查(回應 Codex R8 §5;不是 13F 研究本身):抓 Berkshire 2022Q3 / Q4 的 13F 索引頁、封面與原始資訊表 XML。
SEC 要求的聯絡方式只從本機檔案讀進請求標頭,不在任何 repo 檔案、不印出。用法:python3 -I f13_probe_fetch.py SCRATCH"""
import os, sys, time, json, hashlib, urllib.request
S = sys.argv[1]; RAW = os.path.join(S, "f13", "raw")
ua = open(os.path.join(S, "w8", ".sec_ua")).read().strip()      # 只放在送給 SEC 的請求標頭裡,不印出
def get(url, fn):
    p = os.path.join(RAW, fn)
    if not os.path.exists(p):
        req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "identity"})
        with urllib.request.urlopen(req, timeout=60) as r:
            open(p, "wb").write(r.read())
        time.sleep(0.5)
    b = open(p, "rb").read()
    return {"url": url, "file": fn, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
out = []
for acc in ("000095012322012275", "000095012323002585"):
    base = f"https://www.sec.gov/Archives/edgar/data/1067983/{acc}/"
    out.append(get(base + "index.json", f"{acc}_index.json"))
    a = acc
    dash = f"{a[:10]}-{a[10:12]}-{a[12:]}"
    out.append(get(base + f"{dash}-index.htm", f"{acc}_index.htm"))
    idx = json.load(open(os.path.join(RAW, f"{acc}_index.json")))
    for it in idx["directory"]["item"]:
        n = it["name"]
        if n.lower().endswith(".xml"):
            out.append(get(base + n, f"{acc}_{n}"))
json.dump(out, open(os.path.join(S, "f13", "fetch_manifest.json"), "w"), indent=1)
for o in out: print(o["file"], o["bytes"], o["sha256"][:16])
