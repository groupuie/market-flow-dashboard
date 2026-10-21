# 盤感測試 v3 草案(Claude;未凍結、還沒開始)

- **草案 1**(2026-10-16 早)回應 Astra v0.7.2;**草案 2**(2026-10-16 晚)回應 Astra v0.7.3;**草案 3**(2026-10-17)回應 Astra v0.7.4;**草案 4**(2026-10-21 凌晨)回應 Astra v0.7.5(統計方法不變;半日市時間、正式模式遇到本機快取故障要停、開跑登記 + 決定性重播、結案截止、模擬表一列標籤、下市段落解讀);**草案 5**(2026-10-21 下午)回應 Astra v0.7.6(統計方法不變;結案截止改成「截止視圖」= GitHub 在第 51 個交易日收盤前已收到的帳本狀態、缺漏用完整時間、截止 + 24 小時後才能登記、試跑同語義、登記記收件 run ID;main 引擎檢查與收不到收件維持嚴格政策並寫明代價)
- **v2 照常每天收集、答案不改,只當描述**;v3 是加在 v2 收集上面的一層唯讀驗收與唯一一次分析,不改排程、不改提示詞、不改 v2 的凍結檔;已看過的 37 筆不倒填
- **凍結前阻礙(草案 5 發現)**:GitHub 的 workflow run 在公開 repo 最多保留 90 天,v3 的收件證據要先換成不會過期的來源(PROTOCOL §13)
- 凍結順序:Astra 複核草案 5 的修正與收件證據的替代方案 → 使用者決定 H2、最小值得採用的差距、收案長度、缺漏(下市)政策、未來起日 → manifest + 錨點

| 檔案 | 內容 |
|---|---|
| `PROTOCOL_v3_DRAFT.md` | 規則草案 5(估計對象、正權重重抽 + C1 區間、整批驗收、零訊號證據、收件證據與快取故障、逐日開收盤、重播定義、結案截止與截止視圖、開跑登記 + 決定性重播、兩條嚴格政策的代價、模擬與驗收結果、下市解讀與終值重建前提) |
| `v3_verify.py` | 草案 5 驗證程式(`VERSION = v3-draft5`);試跑要 `--dry-run`(截止 + 24 小時後自動用截止視圖),正式要 `--formal` + 凍結的 `research/ledger_v3/v3_manifest.json`(還沒有);`repair-evidence` = 正式模式說快取壞掉時的復原 |
| `v3_tests.py` → `v3_tests_result.json` | 117 個離線測試(草案 3 的 71 項 + Astra v0.7.5 的 31 項 + Astra v0.7.6 結案截止反例與截止視圖 15 項,其中兩個反例也在草案 4 原碼上重現),全部通過 |
| `v3_fullflow.py` → `v3_fullflow_result.json` | **完整正式流程驗收**:真的凍結收集程式 + 假 GitHub / Yahoo,120 天、101 檔;截止 + 25 小時登記 → 保存失敗 → 重播保存、再跑 / 另一個 checkout 相同,15 種停止反例;和舊規則(最新 ledger + 本機時間)逐事件比分類 |
| `v3_attest.py`、`v3_attest_tests.py` → `v3_attest_result.json` | **長期收件證據 PoC**(甲1:經核驗的 Sigstore 簽證時間;離線驗證、證據鏈、封存清單;26 項測試;PROTOCOL §14)|
| `attest_poc/` | PoC 的 workflow 原檔、釘住的 sigstore 信任根、兩個隔離測試分支的 git bundle(3 筆真的簽章)|
| `sim4_calibrate.py` → `sim4_out/` | 統計判定層的流程模擬第一輪(規則先 commit 於 `0b9c7c5`):**沒有選出方法**(逐視窗紀錄全保存) |
| `sim5_round2.py` → `sim5_out/` | 第二輪(規則先 commit 於 `3215ac5`;候選看過第一輪才定):選出 **C1**;報告換第三批合成市場 |
| `sim5_tables.py` → `sim5_out/tables.md` | 兩輪選擇 + 報告的表(欄名照 Astra v0.7.4 更正;「稠密/稀疏隨機混合」照 v0.7.5 改成依每個視窗的真值分開數,從保存的逐視窗紀錄算) |
| `rescale_risk_scan.py` → `rescale_risk_result.json` | 持有期間配息 / 分割時「換尺度重播」對不上的比例 |
| `evidence/run-*.json`、`evidence/PINS.json` | 兩批真實鎖定的 GitHub Actions run 原件;釘選表(離線重播用 `--pins origin/main:research/ledger_v3_draft_2026-10-16/evidence/PINS.json`) |
| `sim3_*`、`sim3b_*`、`sim_power_block.py`、`sim2_cluster.py` | 草案 1 / 2 的模擬(舊方法,只當歷史;`sim3_tables.py` 欄名已更正) |

## 重跑
```sh
python3 -I v3_tests.py <repo>                                     # 117 項,約 5 分鐘(要有 a654145、4bfe44d、c72f2f7 的 git 物件)
python3 -I v3_fullflow.py <repo> <astra_v050_data> out.json       # 約 10 分鐘
python3 -I v3_attest_tests.py                                     # 收件證據 PoC 26 項,約 5 秒(離線;要有 gh 2.89.0 與 unshare)
python3 -I sim4_calibrate.py select <repo> <p1_events_d266.csv.gz> <astra_v050_data> sim4_out
python3 -I sim5_round2.py select <repo> <events> <dd> sim5_out; python3 -I sim5_round2.py report <repo> <events> <dd> sim5_out 0 2 (及 1 2); python3 -I sim5_round2.py merge sim5_out
python3 -I sim5_tables.py sim4_out/sim4_select.json sim5_out/sim5_select.json sim5_out/sim5_result.json sim5_out/sim5_report_0of2.json sim5_out/sim5_report_1of2.json > sim5_out/tables.md
python3 -I v3_verify.py status --dry-run --start 2026-10-14 --manifest-sha <v2 manifest SHA>   # 真實 37 筆(online)
```
