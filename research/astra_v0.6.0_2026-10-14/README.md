# Astra v0.6.0 期望目標複核(GPT 交付)+ Claude 核對(2026-10-14)

- 原檔:`v0.6.0_2026-10-14_22-24-21_期望目標複核.md`(106,291 bytes,SHA-256 `fc72fccdb0d2c3b02e8ec2c0224cc450e75231914fb197679759cdbeac539a49`;掃過沒有個人資訊,原樣保存;使用者 22:42 傳了兩次,內容逐位元相同)
- 回覆:Claude v2.1「目標重評估」、v2.2「任務改向」
- 回覆文件:Claude v2.3(專案 claude/ 資料夾)

## Astra 這輪的重點
1. 支持把「勝率 70%」改成「扣成本、相對公平基準、有可信的超額期望值,並控制帳戶風險」;不承諾每筆獲利。
2. Claude x2 的四個交易池筆數、均值完全重現;但補上 126 日區塊 95% 區間後,強日 +1.557 點 [−0.782, +4.165]、其他日 −0.152 點 [−0.684, +0.426],都跨 0。
3. 改成同日、固定持有(t+1 → t+20 開盤)的公平比較,強日的正負會隨日期權重翻轉(日期等權 −1.054、訊號數加權 +0.894),區間都跨 0。
4. 指出 v2.1 / v2.2 的錯:基準寫法、成本只扣一邊、「強」不是前一天就全知道、345 檔不是強日因子的新樣本、賺賠比 ≥ 1 不是必要條件、p05 不是最大虧損、兩倍 ETF 不能直接乘 2、DSR 不是「> 0」門檻。
5. 請 Claude 提供第 6 輪(r6)實際跑過的股票名單。

## `astra/`:從 MD 抽出的 10 個檔(SHA-256 全部和附錄七相同)
`expectancy_audit.py`、`replay_bootstrap.py`、`audit-results.json`、`code-audit.md`、`protocol-review.md`、`literature-review.md`、`trials_ledger.md`、`audit-plan.md`、`source-audit/source-review.md`、`source-audit/selection-exposure.json`
- MD 文件嵌入時標題降了兩級,還原後指紋相同。
- 沒收到(在 ZIP):`daily-aggregates.json`、`input-bars-sha256.json`、凍結紀錄 3 檔、`source-audit/audit_metadata.py`、`source-audit/download-manifest.json`、`universe_candidate.json`;所以 `replay_bootstrap.py` 在這裡跑不了。

## `claude_check/`:Claude 這輪做的
| 檔案 | 內容 |
|---|---|
| `expectancy_audit_claude_pin.py` | Astra `expectancy_audit.py` 的副本,**只改第 9 行**:原始 manifest 指紋換成 Claude 10/13 快照的(`e8e8e145…`),其他一字不改;只用來在 Claude 的資料上跑同一支程式,不冒充重現 Astra 原件 |
| `audit-results_on_claude_1013_snapshot.json` | 上面那支在 Claude 10/13 快照上的輸出 |

**結果**:8 個均值與 95% 區間(強日 / 其他日 × 4 種比較)和 Astra 的 `audit-results.json` 到小數第 3 位完全相同;配對日期 103 / 1,217、訊號 2,145 / 18,345、跳空排除 0 都相同;自我測試 5 項全過。
- 第 6 輪實際名單與 345 的重疊:見 `research/expectancy_2026-10-14/x3_r6_overlap.py` / `x3_r6_overlap.json`(604 檔 = 舊 266 的 262 + 345 的 339 + SPY、QQQ + ARGX)。
