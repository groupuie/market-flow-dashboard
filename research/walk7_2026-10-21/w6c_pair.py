#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk7:一個子代理判兩批(同一種做法)的提示詞 —— 判讀內容(圖的說明、問題、基準、範例)和 PROMPT.md 逐字相同,
只改「讀哪些檔、答案寫到哪」(省 token:少一輪、範例只看一次)。b01、b03 是試跑,照原本一批一個子代理。
用法:python3 -I w6c_pair.py OUT_DIR bAA [bBB]   → judge/pairs/bAA_bBB.txt 並印出"""
import json, os, sys

OUT = os.path.abspath(sys.argv[1]); BS = sys.argv[2:]
T = open(os.path.join(OUT, "judge", "PROMPT.md")).read(); plan = json.load(open(os.path.join(OUT, "judge", "plan.json")))
v = {plan["batches"][b]["variant"] for b in BS}; assert len(v) == 1; v = v.pop(); EX = os.path.join(OUT, "judge", "examples")
n = 25 * len(BS)
R = os.path.join(OUT, "judge")
where = f"(R = {R})\n" + "\n".join(f"- 第 {k + 1} 批 {b}:資料夾 R/{b},編號 {plan['batches'][b]['ids'][0]} ~ {plan['batches'][b]['ids'][-1]}(25 張連號)" for k, b in enumerate(BS))
assert all(plan["batches"][b]["ids"] == [f"{int(plan['batches'][b]['ids'][0]) + k:04d}" for k in range(25)] for b in BS)
head = T.split("每張圖 = ")[0]
head = (head.replace("資料夾:{DIR}\n這批 25 張圖的編號:{IDS}(檔名 q編號.png)", f"這次有 {len(BS)} 批、共 {n} 張圖(同一種做法,一起做;檔名 q編號.png):\n{where}")
            .replace("規則:只讀這 25 張圖{EXRULE}", "規則:只讀上面這些圖" + (",和範例資料夾 R/examples 裡的 8 張範例(e1.png–e8.png)" if v == "B2" else "")))
body = "每張圖 = " + T.split("每張圖 = ")[1].split("做法:")[0]
if v == "B1":
    body = body.replace("{EXAMPLES}", "")
else:
    lines = "\n".join(f"- {e['id']}:買方 {e['買方結果']};賣方 {e['賣方結果']};20 天後 {e['20 天後']}" for e in plan["examples"])
    body = body.replace("{EXAMPLES}", f"\n先看 8 張範例(同一類股票、2016–2022 年的某一天),它們之後 20 個交易日的實際結果:\n{lines}\n看範例時想一想:之後先漲的圖和先跌的圖,畫面上有什麼不一樣。\n")
reads = f"{n + (8 if v == 'B2' else 0)} 個 Read" + ("(8 張範例 + " + str(n) + " 張考題)" if v == "B2" else "")
files = "\n".join(f"- R/{b}/answers.json:只放 {b} 的 25 筆" for b in BS) + "\n每個檔的格式:" + '{"batch":"批號","variant":"' + v + '","items":[{"id":"編號","buy":"買點 或 再等","p_up":整數,"sell":"賣點 或 再等","p_dn":整數,"why":"10–25 字","rec":""}, …25 筆,照編號順序]}'
files = files.replace("R/", R + "/") if False else files
tail = f"做法:先用一則訊息同時呼叫 {reads},一次讀進來;然後在同一則訊息裡用 {len(BS)} 個 Write 寫答案檔:\n{files}\n寫完只回覆一行「完成 {' '.join(BS)}」,不要在回覆裡重複答案。\n"
txt = head + body + tail
os.makedirs(os.path.join(OUT, "judge", "pairs"), exist_ok=True); open(os.path.join(OUT, "judge", "pairs", "_".join(BS) + ".txt"), "w").write(txt)
print(txt)
