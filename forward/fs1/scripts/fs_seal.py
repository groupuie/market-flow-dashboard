#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FS1 第 3 步:檢查通過才封存 —— 資料卡與資料包原樣存進 cards/、packets/,ledger.jsonl 追加一列(含雜湊鏈),commit 並推上 sector-forward-ledger。
已封存的月份不能再封存或改寫。用法:python3 -I forward/fs1/scripts/fs_seal.py pending/{t}.card.json [--no-git]"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fs_common as C
from fs_validate import validate

cp = sys.argv[1]; nogit = "--no-git" in sys.argv; pp = cp.replace(".card.json", ".packet.json")
cb, pb = open(cp, "rb").read(), open(pp, "rb").read()
pk = json.loads(pb.decode("utf-8")); t = pk["decision_month"]
led = C.read_ledger(); prev = led[-1]["card_sha256"] if led else None
if any(e["decision_month"] == t for e in led) or os.path.exists(os.path.join(C.CARDS, f"{t}.json")):
    print(json.dumps({"status": "錯誤", "原因": f"{t} 已經封存過,不能再封存或改寫"}, ensure_ascii=False)); sys.exit(2)
errs = validate(cb, pb, prev)
if errs:
    print(json.dumps({"status": "檢查沒過", "errors": errs}, ensure_ascii=False, indent=1)); sys.exit(1)
card = json.loads(cb.decode("utf-8")); sealed = C.now_utc()
late = sealed > C.parse_time(pk["first_open_utc"]) or C.parse_time(pk["cutoff_utc"]) > C.parse_time(pk["first_open_utc"])
os.makedirs(C.CARDS, exist_ok=True); os.makedirs(C.PACKETS, exist_ok=True)
open(os.path.join(C.CARDS, f"{t}.json"), "wb").write(cb); open(os.path.join(C.PACKETS, f"{t}.json"), "wb").write(pb)
row = {"decision_month": t, "card_sha256": C.sha256_bytes(cb), "prev_card_sha256": prev, "packet_sha256": C.sha256_bytes(pb),
       "cutoff_utc": pk["cutoff_utc"], "first_open_utc": pk["first_open_utc"], "sealed_utc": C.iso(sealed), "late": bool(late),
       "model": card["model"], "s0_window": pk["s0"]["window"], "french_ind49_vintage": pk["french"]["ind49_vintage"]}
with open(C.LEDGER, "a", encoding="utf-8") as f:
    f.write(json.dumps(row, ensure_ascii=False) + "\n")
for x in (cp, pp):
    os.remove(x)
head = None
if not nogit:
    head = C.git_commit_push([os.path.join(C.CARDS, f"{t}.json"), os.path.join(C.PACKETS, f"{t}.json"), C.LEDGER],
                             f"fs1:封存 {t} 板塊判斷(card sha256 {row['card_sha256'][:16]},late={late})")
print(json.dumps({"status": "已封存", **row, "commit": head}, ensure_ascii=False))
