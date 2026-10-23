# forward/fs1:Claude 每月板塊判斷的往前封存(帳本分支 `sector-forward-ledger`)

- 協定:`PROTOCOL_FS1.md`(v1.0,第一張卡之前凍結)。排程提示原文:`schedule_prompt.txt`。
- 每月 1 日 08:41(台灣)排程執行(20:41 再跑一次備援,已封存就只評分):`scripts/fs_prep.py` → Claude 寫資料卡 → `scripts/fs_validate.py` → `scripts/fs_seal.py`(commit + push)→ `scripts/fs_score.py`。
- 封存結果:`cards/{t}.json`(Claude 的資料卡,原樣)、`packets/{t}.json`(同時封存的資料包,含 S0_fwd 排序)、`ledger.jsonl`(指紋與雜湊鏈,只追加)。
- 評分:`scores/scores.jsonl`(只追加)、`scores/summary.md`(描述性);主要檢定 `scores/final_primary.json` 只在 2029-12 的 French 資料出來後算一次。
- 自我測試(只用假資料、不用網路、不碰 git):`python3 -I forward/fs1/scripts/fs_selftest.py`。
- 這個分支**不要合併到 main**;它只加 `forward/` 資料夾,不動網站與任何 workflow。

不是投資建議。
