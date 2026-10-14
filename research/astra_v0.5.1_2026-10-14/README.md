# Astra v0.5.1 複核資料補齊(GPT 交付)+ Claude 指紋比對與 41.26 / 41.00 定位(2026-10-14)

- 原檔:`v0.5.1_2026-10-14_09-30-49_複核資料補齊.md`(使用者轉交)
- 本輪性質:v0.5.0 的事後複核與資料交接;不是新的 E1 回測、不是新規則。網站沒改。
- 回覆文件:Claude v1.8(專案 claude/ 資料夾)

## 公開 repo 版的兩處改動(其他逐位元不變)
repo 是公開的,所以拿掉兩處個人資訊:
1. `compare_snapshots.py` 與 MD 附錄六裡的 Mac 使用者資料夾路徑 → 改成 `Path.home()/'Downloads'`(功能相同)
2. MD 第三節的 ChatGPT 私人頁面連結 → 改成文字說明

| 檔案 | Astra 原檔 SHA-256 | repo 版 SHA-256 |
|---|---|---|
| `v0.5.1_…_複核資料補齊.md` | `f179f7416024705c7eaf0aa2bb2b327d6cfa3abe44a5bfb7e22f6711f82c83c9`(108,006 bytes) | `57e5332300f726194a8cf710f04cc074bfb153dfcb3909e243e6410b822884b8`(107,979 bytes) |
| `astra/compare_snapshots.py` | `5bd71c8ddd7c9575902df3554e3065adf9556e3cbcaa1369abad8ff8812c35af`(= Astra 公布值) | `ea80e25a…`(3,910 bytes) |

- 2026-10-14 13:07 使用者又轉來一份同名 MD(108,007 bytes,SHA-256 `4ddfe97c19ea5eb5228940409cf96447fbc0181193c6077219e5649cb9f7cac6`):和上面的原檔逐行比對,只差 17 行程式碼框符號(`~~~` 改成 ```)和結尾多一個換行,文字與附錄程式內容完全相同,所以沒有另存。

## `astra/`:從 MD 附錄抽出的 7 個檔(原檔 SHA-256 全部和 Astra 公布值相同)
`freeze.json`(原件,commit `7d36a68f…`)、`protocol.md`(原件,和 Claude v1.7 重建的那份剛好逐位元相同)、`bars_manifest.py`、`economic-bars.csv`(Astra 268 檔純價量指紋)、`independent_accounts.py`、`compare_snapshots.py`、`recompute_interpretation.py`

## `claude_check/`:Claude 這輪做的
| 檔案 | 內容 |
|---|---|
| `astra-economic-bars-from-csv.json` | 從 Astra CSV 重建的對照檔(CSV 沒有日曆指紋 → `calendarDatesSha256 = null`) |
| `claude-economic-bars.json/.csv`、`claude-economic-bars-comparison.json` | `bars_manifest.py` 跑在 Claude 10/13 15:48 UTC 那份資料(v1.7 用的)的指紋與比對 |
| `claude-redl-1014-economic-bars.json/.csv` | 10/14 另存新資料夾重抓一次(沒覆蓋舊的)的指紋 |
| `c2_bar_diff.py` → `c2_result.json`、`c2_log.txt` | Claude 兩次下載逐根比較:哪些日期、哪個欄位、差多少 |
| `c3_signal_flip.py` → `c3_result.json`、`c3_log.txt` | 兩次下載的底 / 回 / 頂差在哪一天 |
| `c4_flip_census.py` → `c4_result.json`(未四捨五入)、`c4_result_rounded.json`(照網站四捨五入) | 268 檔全部:訊號差幾個、差的那天原始價格是不是剛好平手 |
| `run_rounded.py` | 診斷用:Astra 程式不動,只把「算訊號的價格」照網站四捨五入,成交價仍用原價 |
| `c5_account_stability.py` → `c5_result.json` | 兩次下載 × 是否四捨五入,帳戶中位數與 ADI / PWR / TJX 等個股 |
| `interpretation_formulas_on_claude_rerun.json` | Astra `recompute_interpretation.py` 跑在 Claude v1.7 重跑結果上 |

## 結果
1. `bars_manifest.py --self-test`:PASS(5 項)。268 檔根數、第一天、最後一天全部相同;123 檔純價量指紋完全相同,145 檔不同。
   - 145 檔全部是有配息紀錄的股票;相同的 123 檔裡 117 檔沒配過息。
   - Claude 日曆 dates-only 指紋:`99be666ac4b579dae46f7e8b882f0eaac5b760beae83018a89832a5bdfaa0607`(5,730 天;兩次下載相同)。Astra 的 dates-only 指紋在 ZIP 的 JSON 裡、MD 沒有,請 Astra 對。
2. **原因**:Yahoo 的還原收盤價(adjclose)只有 float32 精度,而且每次下載差中位數 2 個 float32 最小單位(相對約 1e-7),只發生在最後一次除息日以前的 K 棒;沒配息的股票價格每次都一樣(10/14 那次有 70 檔只多了 10/12 成交量的事後修正)。
   - 例外:ACN 10/13 除息,`asof 2026-10-12` 的 10/14 下載仍把它算進還原價(事件清單看不到;10/12 調整係數 0.99204),整段約差 0.8% → 同一個 asof、不同天下載,還原價可能整段不同。
3. **這麼小的差,為什麼會讓帳戶差到幾個百分點**:原始價格常常剛好平手(例如今天收盤 = 昨天最高價,都是 88.64)。「收盤 > 昨高」這種比較,遇到平手時,結果就看還原價最後幾位的雜訊。
   - Claude 兩次下載之間:底 345 個、頂 456 個、回 1 個日期不同(全部約 10.9 萬個訊號的 0.7%);其中 572 個當天原始價格剛好平手,其餘多半是 5 根冷卻期往後推一格的連鎖。
   - 帳戶診斷是「上一筆的 t+64 結束才能接下一筆」,一個訊號變了,後面整串都會變 → 1,352 個帳戶裡 75 個的最大回撤差超過 0.1 點(最大 TJX 19.01% → 42.55%)。
   - 配對窗口平均幾乎不受影響:兩次下載各組各段差 ≤ 0.11 點(獲利比例)、R1 少跌差 ≤ 0.005 點;votes 都是 A 0 / B 0。
4. **41.26 / 41.00 定位**(Claude 10/13 資料,未四捨五入 vs 四捨五入的訊號差;Astra 原始資料的行為是由帳戶值一致推定,待 Astra 用原檔確認):
   - ADI:2018-11-09(頂;原始收盤 87.59 = 昨低 87.59)和 2018-12-11(底;原始收盤 88.64 = 昨高 88.64)兩個平手日;四捨五入版改在 2018-11-12 出頂。
   - PWR:2018-10-18(頂;32.31 = 昨低)和 2021-11-05(底;117.42 = 昨高);四捨五入版改在 2021-11-08 出底。
   - 訊號價格照網站四捨五入後,Claude 兩次下載都得到:ADI 42.0131%(Astra 原始 42.01310189%)、PWR 23.7376% / 報酬 206.186%(Astra 23.7376% / 206.1862%)、B0 中位 41.2634%(Astra 41.26343064%)。
   - 四捨五入後,兩次下載之間超過 0.1 點的帳戶:75 → 0(最大差 0.0002 點);訊號差:802 → 7。
5. `recompute_interpretation.py` 跑在 Claude 重跑結果上:後段 E1 0.896 ÷ B0 0.235 = 3.817(Astra 3.812);R1 1.431 / C50 4.125(全部窗口)、1.431 / 0.655(R1 真的減碼的窗口);前段比值 2.575。和 Astra 一致。

## 重跑
```sh
cd research/astra_v0.5.1_2026-10-14
python3 -I astra/bars_manifest.py --self-test
python3 -I astra/bars_manifest.py --data-dir /home/claude/work/astra_v050_data --output claude_check/claude-economic-bars.json --expect claude_check/astra-economic-bars-from-csv.json
python3 -I claude_check/c4_flip_census.py /home/claude/work/astra_v050_data /home/claude/work/astra_v051_redl claude_check/c4_result.json
python3 -I claude_check/c4_flip_census.py /home/claude/work/astra_v050_data /home/claude/work/astra_v051_redl claude_check/c4_result_rounded.json round
# 帳戶:Astra v0.5.0 資料夾副本(放 astra/freeze.json 原件 + protocol.md)裡跑 experiment.py 或 claude_check/run_rounded.py,再跑 c5
```
- 行情資料(兩次下載)只留本機 `/home/claude/work/astra_v050_data`、`/home/claude/work/astra_v051_redl`,不進 repo。
