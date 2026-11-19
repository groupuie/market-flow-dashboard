#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk7:產生每一批判讀者的提示詞(PROMPT.md + plan.json;B2 多 8 張範例與它們的結果)
用法:python3 -I w6a_prompt.py OUT_DIR bNN   → 印出提示詞"""
import json, os, sys

OUT, B = sys.argv[1], sys.argv[2]; OUT = os.path.abspath(OUT)
T = open(os.path.join(OUT, "judge", "PROMPT.md")).read(); plan = json.load(open(os.path.join(OUT, "judge", "plan.json")))
b = plan["batches"][B]; D = os.path.join(OUT, "judge", B); EX = os.path.join(OUT, "judge", "examples")
if b["variant"] == "B1":
    rep = {"{EXRULE}": "", "{EXAMPLES}": "", "{HOWTO}": "先用一則訊息同時呼叫 25 個 Read,把 25 張圖一次讀進來;"}
else:
    lines = "\n".join(f"- {e['id']}:買方 {e['買方結果']};賣方 {e['賣方結果']};20 天後 {e['20 天後']}" for e in plan["examples"])
    rep = {"{EXRULE}": f",和範例資料夾 {EX} 裡的 8 張範例(e1.png–e8.png)",
           "{EXAMPLES}": f"\n先看 8 張範例(同一類股票、2016–2022 年的某一天),它們之後 20 個交易日的實際結果:\n{lines}\n看範例時想一想:之後先漲的圖和先跌的圖,畫面上有什麼不一樣。\n",
           "{HOWTO}": "先用一則訊息同時呼叫 33 個 Read(8 張範例 + 25 張考題),一次讀進來;"}
rep.update({"{DIR}": D, "{IDS}": "、".join(b["ids"]), "{B}": B, "{V}": b["variant"]})
for k, v in rep.items():
    T = T.replace(k, v)
print(T)
