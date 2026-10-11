# Astra資金 v0.1 接入驗收(2026-10-11)

- 來源:Astra「美股資金 Astra 獨立模組 v0.1|資金訊號初版」(2026-10-11 10:38:31,使用者轉交)
- 上線內容:網站根目錄 `astra-flow.js`、`astra-dashboard-adapter.js` = Astra 原檔(SHA-256 與交付相同,逐位元未改);`index.html` 只做接線與顯示(按鈕「Astra」預設關、`#astrastrip` 一行狀態 + ⓘ詳情、記號在所有既有圖層之後)
- 回覆文件:Claude v0.4「A資金接入」(專案 claude/ 資料夾)

## 檔案
| 檔案 | 內容 |
|---|---|
| `repro_astra_tests.log` | Astra 自帶測試在 Claude 端重跑:核心 18、回測 2、轉接 28、19 檔 251 次前綴回放;回測表逐列相同;B 路徑診斷;拆股前後成交量;速度 |
| `data-manifest_claude_fetch.json` | Claude 抓的 19 檔日K雜湊(與 Astra 的 manifest 相同) |
| `expected_events_node.json` | Node 離線、用同一份 gist 日K、截止 2026-10-09 算出的事件 → 網頁驗收的標準答案 |
| `t1_astra_integration_test.py` / `.json` / `.log` | 本機網頁驗收:舊版 vs 新版(Astra 關)全部 traces;Astra 開/關;週月年全史、槓桿/反向/範圍外、縮放、詳情窗、盤中棒、量更正、資料落後、SPY 晚到/抓不到、程式沒載入、換股、手機 |
| `t2_online_check.py` / `.json` | 部署後線上複驗(Pages):三個檔逐位元相同、真的點按鈕、記號 = Node、量化開關前後相同 |
| `shots.py`、`shot_popover.py` | 截圖工具(桌機 1440 / 手機 390) |

## 重跑
```sh
python3 t1_astra_integration_test.py <舊版 index.html> <新版 index.html> expected_events_node.json out.json
python3 t2_online_check.py 2026-10-11T07:20Z expected_events_node.json out.json
```
行情照網站從 gist 即時抓;日K檔一更新,`expected_events_node.json` 也要用新檔重算。
