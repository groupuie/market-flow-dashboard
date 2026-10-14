# Alpha Vantage 財報資料獨立審查

- 作者：Astra；查核日期：2026-10-14（台灣時間）。
- 對象：Claude v1.8／v1.9 的資料主張；本文件是資料審查，沒有執行財報選股回測。
- 本輪只用 Alpha Vantage 官方 IBM 公開 demo 與官方文件／公司公告／SEC；沒有讀取使用者金鑰、呼叫使用者連接器、回補 266 檔、付費或改網站。

**結論：同意「有歷史財報與歷史季度預估列」，但目前不足以認定「2017 年以後可以做無前視偏誤的預估修正回測」。財報驚喜值得研究；正式檢驗前必須先證明共識數值在事件當時已存在，並處理預告、分割和 EPS 口徑。**

## 1. 本輪直接確認的事

| 檢查 | 本輪結果 | 可推論範圍 |
|---|---|---|
| 官方 `EARNINGS` IBM demo | 122 季，1996-03-31 至 2026-06-30；含實際、預估、驚喜、公布日期與時段 | 確認 IBM 有歷史列；不能外推 NVDA／AAOI 或所有股票的完整度 |
| 官方 `EARNINGS_ESTIMATES` IBM demo | 41 列＝39 季＋2 年度；季度自 2017-06-30 起，含未來季度 | 確認舊季度與 7／30／60／90 天欄位存在 |
| 預估的時間版本 | 回傳沒有每列觀測時間、共識截點、首次可取得時間或修訂版本 | **尚不能重建歷史某日投資人實際看得到的完整預估** |
| 免費用量 | 官方支援頁目前仍寫 25 API 次／日 | 這是公開方案說明，非本輪對使用者帳號的驗證 |

前兩列是本輪下載後自行計數，原始 demo 回應保存在 `public-demo/`；來源：[EARNINGS 官方 demo](https://www.alphavantage.co/query?function=EARNINGS&symbol=IBM&apikey=demo)、[EARNINGS_ESTIMATES 官方 demo](https://www.alphavantage.co/query?function=EARNINGS_ESTIMATES&symbol=IBM&apikey=demo)。官方文件只列功能與 `function / symbol / apikey`，沒有這兩項功能的歷史 `asof` 參數或逐列時間版本定義。[官方功能說明](https://www.alphavantage.co/documentation/)、[官方用量說明](https://www.alphavantage.co/support/)

### 不能從季度日期推定「N 天前」

這次 `EARNINGS_ESTIMATES` 有 `date=2027-12-31` 的未來年度列，同時已有 `eps_estimate_average_7_days_ago=13.1477` 等值。**因此 `date` 不能一律當作所有列的歷史快照基準日。** 它至少表示預估所屬期間；已公布季度的欄位究竟凍結在季末、財報日、供應商更新日或其他時點，公開文件沒有回答。

「某一季的 7 天前值恰好對上公司預警」是值得查的線索，不能單獨證明所有年度、季度與股票均採同一規則。這是資料可辨識性的判斷，不是已證明供應商有回填錯誤。

## 2. 新發現：IBM 本身就有「先預告，再正式公布」

本輪 demo 的 IBM 2026-06-30 季顯示：`reportedDate=2026-07-22`、實際 EPS `2.93`、預估 EPS `2.93`、驚喜 `0`。[本輪 demo 來源](https://www.alphavantage.co/query?function=EARNINGS&symbol=IBM&apikey=demo)

但 IBM **7 月 14 日**的官方投資人信已披露初步第二季數字：GAAP EPS `2.27`、operating non-GAAP EPS `2.93`。該份 8-K 包含 Item 2.02，SEC 頁面 Accepted 顯示 `2026-07-14 07:01:52`。[IBM 官方公告](https://newsroom.ibm.com/2026-07-14-Arvind-Krishnas-Letter-to-IBM-Investors)、[SEC 提交紀錄](https://www.sec.gov/Archives/edgar/data/51143/000005114326000070/0000051143-26-000070-index.htm)、[SEC 公告附件](https://www.sec.gov/Archives/edgar/data/51143/000005114326000070/ibm-20260714xex991.htm)

**影響：**若研究的是「市場第一次知道業績後的漂移」，只用 API 的 7 月 22 日會錯過初步披露。若研究的是 7 月 22 日正式公布，相對當時最新共識的零驚喜可能有意義；兩者是不同事件，不可混成同一筆。**不能把 7 月 22 日這列的共識 2.93 回填成 7 月 14 日初步公布之前的預估。** 此例不能證明 Alpha Vantage 的共識數值有錯，但已證明單一季度 `reportedDate` 不足以標記全部重大財報資訊。

也不能把 SEC GAAP EPS 直接替換 API 的實際 EPS，再減掉其分析師預估。上述 `2.27` 與 `2.93` 口徑不同；必須核實每筆共識究竟對應 GAAP、調整後、持續營運、基本或稀釋 EPS。

## 3. SEC 時間可作保守門檻，但不是原始發稿時間

Form 8-K 一般要求事件發生後四個工作日內提交；Item 2.02 處理已完成季度／年度結果的公開公告及其更新。因此 SEC 收件時間可能晚於公司發稿，且同一季度可以不止一份相關公告。不能把 `acceptanceDateTime` 直接命名為「財報發稿時間」。[SEC Form 8-K：General Instruction B、Item 2.02](https://www.sec.gov/info/edgar/forms/form8-k.pdf)

建議研究記錄三種時間：公司原始公告時間、EDGAR 收件／披露時間、資料供應商觀測時間；三者皆保留来源與原始字串。採 SEC 作保守可用門檻時，策略應在文件可取得後才形成訊號，並以匹配的附件 EPS 為準。API 更新有處理延遲，不宜假設收件當秒即可交易。[SEC API 更新說明](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)

時區必須逐筆正規化，抽查 API 值和 SEC 原始 filing index／提交 header，採 `America/New_York` 的夏令時間規則；不能只用日曆日期判斷盤前盤後。此處提出的是驗證要求，**本輪沒有全面稽核 SEC API 時區是否一致**。

只把實際 EPS 的可用時間改成 SEC 時間，仍不能證明舊共識和「N 天前」值當時可用。若只有公布日期、沒有可信時段，主檢驗可預先定義為公告日期之後第一個完整交易日收盤才形成訊號、再隔日開盤成交；另報更早執行的敏感度，但不得事後選較好的版本。

## 4. 分割、價格分母與 SUE

以下是 Astra 的研究建議，尚未採用績效選參數。

- **先對齊每股單位。** 實際 EPS、共識 EPS、過往驚喜、價格分母都要使用同一股數基準與幣別。NVIDIA 官方文件確認 2024 年十拆一，後續財報對歷史每股數字追溯調整；但這不能證明 Alpha Vantage 每個預估修訂欄位均同步調整。[NVIDIA 分割 FAQ](https://investor.nvidia.com/files/doc_downloads/2024/06/nvidia-2024-stock-split_faq_investors.pdf)、[NVIDIA 2024 年季度申報](https://www.sec.gov/Archives/edgar/data/1045810/000104581024000316/nvda-20241027.htm)
- **不能只見到數值約差十倍就自動除十。** 必須確認預估快照時點、分割生效日、供應商該欄位已調整範圍，避免重複調整。無法確認時標為不可用。
- **EPS 驚喜除以股價：** `SP=(actual-consensus)/P_before` 可避免預估 EPS 接近零造成比率暴增；但分母應是事件前、與 EPS 同一分割基準的價格。不要直接混用含現金股利回溯調整的 Yahoo Adjusted Close；報酬的還原價口徑與 EPS 的每股單位是不同問題。
- **候選 SUE：** `UE_q=actual_q-consensus_q`；`SUE_q=UE_q/std(UE_{q-8},...,UE_{q-1}, ddof=1)`。只用當時已公布的前八季，不把當季放進標準差；過往季 EPS 同樣要換成一致單位。這是本研究可登記的一個明確版本，不代表 SUE 只有此定義。
- **事先排除：** 缺共識、分析師數為零、口徑不明、分割無法對齊、過往有效季度不足八季、標準差為零或數值精度不足。缺值不能當零；SUE 不能恢復已被供應商四捨五入掉的資訊。
- 不以一個跨股票固定 EPS 門檻排除「太小數字」：未對齊分割會偏袒不同股數單位。先定義資料精度與有效位數條件，固定後才跑結果。

## 5. 採納門檻與下一步

| 門檻 | 過關證據 | 未過如何處理 |
|---|---|---|
| 共識時間 | 供應商可引用的方法定義／當時保存快照，能證明共識截點早於指定事件；抽查通過 | 歷史預估修訂只作探索描述，不稱無前視驗證 |
| 事件識別 | 匹配期間與 EPS 的初步公告、正式公告、修訂；有首度公開日期／時段及來源 | 不把季度日期或單一 reportedDate 當完整事件集 |
| EPS 單位 | 幣別、GAAP／調整後、基本／稀釋、分割換算均有明確欄位或來源 | 不計驚喜／SUE；列出排除原因 |
| 原始快照 | 保存擷取時間、請求功能與代號、來源、完整回應 SHA-256，原檔不覆蓋 | 不能聲稱另一人已完整重現 |
| 預先登記 | 名單、期間、事件時間規則、主比較、缺值排除、成本、重疊處理與信賴區間先固定 | 不發布「70% 準確率」或上線訊號 |

現階段可先整理已取到的資料，向供應商確認 `EARNINGS.estimatedEPS` 的共識截點和 `EARNINGS_ESTIMATES` 舊季度凍結／修訂規則。若沒有可信歷史時間版本，從此刻開始保存帶時間的前瞻快照，可以建立未來的有效驗證資料；它不能回頭補證 2017 年當時可用性。

**抓取排程的算術更正：**266 檔各抓 `EARNINGS` 和 `EARNINGS_ESTIMATES` 一次共 532 次。每天預留 20 次給回補，最少需 `ceil(532/20)=27` 個可用配額日，等於每日約 10 檔兩項；只抓 EARNINGS 則約 14 日。重試、其他使用者查詢、重置時區和額外事件端點會增加時間。「約四週」合理，但不能同時寫「每天 20 檔兩項、只耗 20 次」。本輪沒有建立排程或進行回補。[官方每日用量](https://www.alphavantage.co/support/)

### 選擇權資料的解讀邊界

財報 EPS 與未平倉量（OI）無法辨識做市商持倉方向。即使取得完整選擇權鏈、Gamma 和 OI，OI 也只是未平倉合約總數，每張合約同時有多方與空方，沒有告訴我們哪一方是做市商。將 call OI 一律加、put OI 一律減所得到的是帶符號假設的 Gamma 代理，不能稱為已觀測到的做市商真實淨曝險。[OCC／OIC 對 OI 的說明](https://www.optionseducation.org/referencelibrary/faq/general-information)

相對地，Cboe 的相關研究使用交易者類別、買賣方向及開平倉資訊來重建做市商部位，超過一般鏈資料提供的欄位。本輪僅指出識別限制，沒有啟動選擇權回補或新研究。[Cboe 研究第 2 節](https://cdn.cboe.com/resources/education/research_publications/gammasqueezes.pdf)

## 6. 留存的 demo 證據

| 本機檔名（相對本資料夾） | 位元組 | SHA-256 |
|---|---:|---|
| `public-demo/earnings.json` | 39172 | `c849fe15b70d74f324f226f65d55d1da033914b2a3e0e36f9d9c61d559782352` |
| `public-demo/earnings_estimates.json` | 40979 | `81757680f0cc0541e387ada2ab58ce16f6362fa222ee8eda2a57442629456b9e` |
| `public-demo/splits.json` | 247 | `e2c0de31a1b0c5ceab7ea037c0dd7d5292bbc502184519373777cd2f1652d2dd` |

demo 回應會更新；上述指紋指本輪保存的原始位元組，不承諾未來重抓仍相同。原始 demo 僅留本地供本次審查，不據此宣稱取得商業再散布授權。只在文件中列必要檢查值和來源網址。

`public-demo/manifest.json` 記錄本地保存完成時間與指紋；`public-evidence/manifest.json` 記錄公司公告、SEC 與官方文件的請求時間、HTTP 狀態及已保存回應的指紋。直接擷取若被來源拒絕，記錄失敗而不假造原始快照；網頁查核仍可沿本文官方來源連結重做。
