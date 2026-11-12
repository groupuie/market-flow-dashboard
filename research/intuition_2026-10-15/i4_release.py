#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盤感訓練 I4:依序放出資料包(子代理寫好前一天的判讀,才把下一天的檔放進它的資料夾)

用法:python3 i4_release.py JOBS.json LOG.jsonl
JOBS.json = [{"name": .., "dir": 子代理的資料夾, "days": [d1, d2, ..], "vdir": 判讀檔的資料夾, "src": {day: 原始檔}}]
每秒檢查一次;全部放完或 6 小時後結束。每次放出記一行(時間、哪一天、因為哪個判讀檔出現)。
"""
import json, os, shutil, sys, time, datetime as dt
jobs = json.load(open(sys.argv[1])); LOG = sys.argv[2]


def log(**k):
    k["utc"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    open(LOG, "a").write(json.dumps(k, ensure_ascii=False) + "\n")


def ok(p):
    try:
        return isinstance(json.load(open(p)).get("marks"), list)
    except Exception:
        return False


for j in jobs:
    os.makedirs(j["dir"], exist_ok=True)
    d0 = j["days"][0]; dst = os.path.join(j["dir"], d0 + ".json")
    if not os.path.exists(dst):
        shutil.copy(j["src"][d0], dst); log(job=j["name"], released=d0, after="start")
t0 = time.time()
while time.time() - t0 < 6 * 3600:
    left = 0
    for j in jobs:
        for k in range(len(j["days"]) - 1):
            a, b = j["days"][k], j["days"][k + 1]; dst = os.path.join(j["dir"], b + ".json")
            if os.path.exists(dst):
                continue
            left += 1
            if ok(os.path.join(j["vdir"], a + ".json")):
                shutil.copy(j["src"][b], dst); log(job=j["name"], released=b, after=a)
    if left == 0:
        log(done=True); break
    time.sleep(1)
