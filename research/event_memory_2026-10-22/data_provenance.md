# 資料字典與來源稽核 v0.2

- 版本:v0.2|2026-10-22 11:49:10(台灣)|簡述:資料來源
- v0.1 經過兩次唯讀複核。v0.2 變更:加 `issuer_first_public_time`(回應 Codex v1.1:SEC 受理時間不等於公司第一次公開的時間)、時間戳稽核擴大到 107 家(E7)。
- 合併 Astra 清單的 data_dictionary 與 provenance_audit。稽核數字來自 E3(`scripts/p1b_sec_guidance.py`、`out/p1_sec_guidance.json`)。

## 1. 每一筆資料都要有的四個時間

| 欄位 | 意思 | 例 |
|---|---|---|
| `published_at` | 來源說的發布時間(SEC = 索引頁 Accepted,美東 → UTC) | 2026-07-30T20:30:28Z |
| `available_at` | 我們規定「從這時起可以用」;財報 = published_at;價格 = 該日 16:00 ET;案例卡 = usable_from(matured_at = r+10 收盤,usable_from = 下一個交易日收盤) | |
| `issuer_first_public_time` | 公司第一次公開(新聞稿 / 通訊社)的時間;**沒有原文證據就填 unknown**,不拿 SEC 受理時間代替。8-K 封面的「事件日」(Date of earliest event reported)可以給**日期**,不給時刻 | unknown |
| `first_seen_at` | 我們第一次抓到的時間(回溯抓的就等於 retrieved_at) | |
| `retrieved_at` | 這一份檔案這次抓下來的時間;原檔另存 SHA-256 | |

規則:決定時間 d_k(收盤)只能用 `available_at ≤ d_k` 的資料。財報用 SEC 受理時間當 available_at 是**偏保守**的(只會晚、不會早);但反應日 r 可能因此晚一天(新聞稿在收盤前、受理在收盤後),所以兩個時間都要記,不一致的列要標出來。

## 2. 資料層

| 層 | 來源 | 主要欄位 | available_at | 備註 |
|---|---|---|---|---|
| 日 K | walk7 `d3_daily.py`(專案 `scripts/astra_data.py`) | 日期、還原開高低收、只還原分割的收盤、量 | 當天 16:00 ET | 被併購 / 下市的成分股抓不到(2016 年 404 / 504 檔、2026 年 486 / 501)→ 倖存者偏差,沿用 walk7 的說明 |
| 名單 | walk7(每年 1 月 1 日 S&P 500 ∪ 前一年成交金額前 100) | 年、代號、CIK | 當年 1 月 1 日 | |
| 財報事件 | EDGAR:submissions JSON(找 8-K 2.02)+ 索引頁(時間、附件類型)+ EX-99.1 原檔(要含當季營收與 EPS,排除交車量等) | cik、accession、items、filingDate、`accepted_et`、`accepted_utc`、附件檔名、SHA-256 | `accepted_utc` | **不用** JSON 的 acceptanceDateTime(見 §3) |
| 財報摘要 | Claude 從 EX-99.1 抽取 | 營收、EPS、年增率、指引(期間 / 低 / 高 / 單位)、和上次比、重點 ≤ 5;每項附原文片段與字元位置 | = 該財報的 `accepted_utc`(內容只來自那份檔) | 另記模型 ID、提示詞指紋、抽取時間;抽取時看不到股價 |
| 案例卡 | Claude 在 r+10 收盤(d0 的 10 天結果也成熟)之後寫 | 見 `case_schema.json` | usable_from = matured_at 的下一個交易日收盤 | 只取 usable_from ≤ 決定時間的卡 |
| 判讀 | A / B / C 三組 | 見 `decision_schema.json` | — | 資料包指紋、模型 ID、判讀時間 |
| 答案 | 由日 K 計算 | FL3_A60(主)、FL3_A20、FL3_FIX2、次要結果 | t+3 收盤後 | 程式重算 0 筆不符(E4) |

## 3. 來源稽核(E3:20 檔 × 4 份 = 80 份,申報日 2025-08-01 ~ 2026-10-20)

1. **時間戳**:索引頁「Accepted」是美東時間(SGML 檔頭的 ACCEPTANCE-DATETIME 也是;Codex 獨立核對 AAPL 一例相同)。E7 擴大到 107 家、231 份 2.02 8-K:48 家 JSON 是真 UTC、59 家多 4 / 5 小時;同一家公司前後一致(0 家混用),2019–2026 每年都有兩種 → **不能用固定小時數修正,一律用索引頁 / SGML**。E8 逐份稽核(`out/sec_ts_audit_2_02.csv`):索引頁與 SGML 231 / 231 相同。E3 的 20 家:
   - 17 家(AAPL、MSFT、NVDA、AMZN、GOOGL、META、JPM、JNJ、WMT、CAT、NKE、NFLX、AMD、MU、TSLA、COST、UNH):比索引頁多 8(夏令)/ 10(冬令)小時 = 比真 UTC 多 4 / 5 小時。
   - 3 家(XOM、LMT、AVGO):比索引頁多 4 / 5 小時 = 真 UTC。
   - JSON 的日期部分可能跳到隔天(盤後財報),`filingDate` 才是美東日期。
2. **公布時段**:77 份財報新聞稿:盤前(< 09:30 ET)28、盤中 0、盤後(≥ 16:00 ET)49;另 3 份不是財報(TSLA 交車量 2 份、NKE 1 份)。
3. **附件**:80 份都找得到 EX-99 類附件;用索引頁的「文件類型」欄挑 EX-99.1,不要用檔名猜(第一版用檔名,挑到 NVDA 的財務長評論、WMT 的簡報)。
4. **數字指引**:粗略比對 50 / 80 份出現「像指引」的句子,但誤抓很多(目錄、關稅退款、負債比、節省成本目標)、也漏抓 JNJ;營收 / EPS 指引的真實比例還不知道 → 要改用模型抽取 + 原文片段 + 人工抽查。
5. **原檔**:gzip + SHA-256 存在工作區(1.9 MB,不進 repo);正式版要和指紋清單一起保存。
6. **SEC 規範**:User-Agent 放聯絡 email(存在本機檔案,不寫進程式碼、repo、報告);每 0.25 秒最多一次請求(SEC 上限每秒 10 次)。

## 4. 還沒解決

- 還原價會因之後的分割 / 配息改變;FL3 是比例,分割不影響,窗內除息有小差異 → 正式版存未還原價 + 當時已知的調整因子。
- 有些公司用 8-K Item 7.01 或別的附件發財報;海外公司(6-K)不在範圍。
- 市場共識預估、法說會逐字稿:沒有免費、可回溯時間的來源,這版不用(B 組的資訊因此比專業投資人少)。
