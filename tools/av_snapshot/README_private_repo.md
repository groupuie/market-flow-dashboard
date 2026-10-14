# market-flow-private(私人資料,不公開、不轉載)

`market-flow-dashboard` 研究用的第三方資料原始快照。目前只有 Alpha Vantage。

- **為什麼另開私人 repo**:Alpha Vantage 的條款可能不允許公開轉載原始資料,所以不放進公開的 `market-flow-dashboard`。
- **金鑰**:只放在本 repo 的 GitHub 秘密設定 `ALPHAVANTAGE_API_KEY`。任何檔案、log、紀錄的網址都不含金鑰(`scripts/av_snapshot.py` 自我測試會檢查)。

## 目的(2026-10-14 起)
回答 Astra v0.5.2 提出的資料時間問題:Alpha Vantage 的共識 EPS 和「N 天前」的預估,是不是**當時就看得到**的數字。

| 每天存什麼 | 為什麼 |
|---|---|
| `EARNINGS_CALENDAR`(未來 3 個月,全部公司):美東收盤後一次、週一到週五開盤前一次 | 1 次查詢就有 4,500 多家公司「當天」的共識 EPS。公司公布財報後,拿最後一份公布前的快照,和 `EARNINGS` 事後寫的 `estimatedEPS` 對照 |
| `EARNINGS_ESTIMATES`:固定 4 檔(NVDA、MSFT、TSLA、AAOI)每天一次 | 看「7 / 30 / 60 / 90 天前」到底以哪天為基準、已過季度的數字會不會被改 |
| `EARNINGS`:每天最多約 14 檔 | ①研究名單裡剛公布財報的(公布後盡快抓一次)②從沒抓過的(回補 266 檔)③公布後只抓過一次、已滿 21 天的(再抓一次,看舊資料有沒有被改) |

一天合計最多 20 次查詢(免費版每天 25 次,留 5 次給連接器臨時查詢)。

## 存放方式
```
raw/<功能>/<代號或 ALL>/<功能>_<代號>_<UTC 時間>.<csv|json>      回應原封不動(位元組不改)
raw/.../*.meta.json                                               功能、參數(不含金鑰)、抓取時間、HTTP 狀態、大小、SHA-256
manifest/YYYY-MM.jsonl                                            每個檔一行
logs/YYYY-MM.jsonl                                                額度用完、錯誤訊息、每輪摘要(錯誤訊息不當資料存)
state/earnings_fetched.json                                       每檔 EARNINGS 抓過的時間
config/universe_266.txt                                           研究名單(公開 repo research/inst_flow_2026-10-11/ 同一份)
```
- 舊檔永不覆蓋;每次都是新檔。
- 第一份行事曆(2026-10-14T13:20:02Z)是 Claude 透過 Alpha Vantage 連接器取得(`data_url` 下載),不是直接 API;`.meta.json` 有註明。

## 排程(`.github/workflows/av-snapshot.yml`)
- UTC 22:30 每天:行事曆 + 4 檔預估 + EARNINGS 佇列
- UTC 13:00 週一到週五:只存行事曆
- 手動執行:Actions → av-snapshot → Run workflow(evening / morning / selftest)
- 沒有金鑰時自動略過,不會失敗;碰到額度用完就停,寫進 logs。

## 使用規則
- 只給 Claude / Astra 做研究;不轉貼原始資料到公開地方。研究報告只放彙總結果。
- 要用這些快照做回測前,先看 Astra v0.5.2 附錄四的資料品質門檻(共識時間、事件配對、EPS 口徑、分割單位)。
