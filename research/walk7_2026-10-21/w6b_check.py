#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk7:檢查答案檔格式(不看答案對不對)。用法:python3 -I w6b_check.py OUT_DIR [bNN ...]"""
import json, os, sys
OUT = sys.argv[1]; plan = json.load(open(os.path.join(OUT, "judge", "plan.json")))["batches"]
bs = sys.argv[2:] or sorted(plan)
for b in bs:
    p = os.path.join(OUT, "judge", b, "answers.json")
    if not os.path.exists(p):
        print(b, "沒有答案檔"); continue
    try:
        j = json.load(open(p)); it = j["items"]; ids = [str(x["id"]).zfill(4) for x in it]
        bad = [x["id"] for x in it if x.get("buy") not in ("買點", "再等") or x.get("sell") not in ("賣點", "再等") or not (0 <= float(x["p_up"]) <= 100) or not (0 <= float(x["p_dn"]) <= 100)]
        ok = sorted(ids) == sorted(plan[b]["ids"]) and not bad and j.get("variant") == plan[b]["variant"]
        pu = [float(x["p_up"]) for x in it]; pdn = [float(x["p_dn"]) for x in it]
        print(b, plan[b]["variant"], "OK" if ok else "有問題", len(it), "筆", "壞的", bad[:5], "買點", sum(x["buy"] == "買點" for x in it), "賣點", sum(x["sell"] == "賣點" for x in it),
              "p_up 範圍", min(pu), max(pu), "p_dn 範圍", min(pdn), max(pdn), "rec 有寫", sum(1 for x in it if str(x.get("rec", "")).strip()))
    except Exception as e:
        print(b, "讀不懂", str(e)[:80])
