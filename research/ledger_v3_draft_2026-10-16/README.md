# 盤感測試 v3 草案(Claude;未凍結、還沒開始)

- **草案 1**(2026-10-16 早)回應 Astra v0.7.2;**草案 2**(2026-10-16 晚)回應 Astra v0.7.3;**草案 3**(2026-10-17)回應 Astra v0.7.4
- **v2 照常每天收集、答案不改,只當描述**;v3 是加在 v2 收集上面的一層唯讀驗收與唯一一次分析,不改排程、不改提示詞、不改 v2 的凍結檔;已看過的 37 筆不倒填
- 凍結順序:Astra 複核草案 3 的方法與程式 → 使用者決定 H2、最小值得採用的差距、收案長度、下市規則、未來起日 → manifest + 錨點

| 檔案 | 內容 |
|---|---|
| `PROTOCOL_v3_DRAFT.md` | 規則草案 3(估計對象、正權重重抽 + C1 區間、整批驗收、零訊號證據、收件證據、重播定義、正式模式、模擬與驗收結果、下市風險) |
| `v3_verify.py` | 草案 3 驗證程式(`VERSION = v3-draft3`);試跑要 `--dry-run`,正式要 `--formal` + 凍結的 `research/ledger_v3/v3_manifest.json`(還沒有) |
| `v3_tests.py` → `v3_tests_result.json` | 71 個離線測試(草案 2 的 39 項照新規則改寫 + Astra v0.7.4 的統計 / 工程反例 + 新功能),全部通過 |
| `v3_fullflow.py` → `v3_fullflow_result.json` | **完整正式流程驗收**:真的凍結收集程式 + 假 GitHub / Yahoo,120 天、101 檔;唯一一次判定與 12 種停止反例 |
| `sim4_calibrate.py` → `sim4_out/` | 統計判定層的流程模擬第一輪(規則先 commit 於 `0b9c7c5`):**沒有選出方法**(逐視窗紀錄全保存) |
| `sim5_round2.py` → `sim5_out/` | 第二輪(規則先 commit 於 `3215ac5`;候選看過第一輪才定):選出 **C1**;報告換第三批合成市場 |
| `sim5_tables.py` → `sim5_out/tables.md` | 兩輪選擇 + 報告的表(欄名已照 Astra v0.7.4 更正) |
| `rescale_risk_scan.py` → `rescale_risk_result.json` | 持有期間配息 / 分割時「換尺度重播」對不上的比例 |
| `evidence/run-*.json`、`evidence/PINS.json` | 兩批真實鎖定的 GitHub Actions run 原件;釘選表(離線重播用 `--pins origin/main:research/ledger_v3_draft_2026-10-16/evidence/PINS.json`) |
| `sim3_*`、`sim3b_*`、`sim_power_block.py`、`sim2_cluster.py` | 草案 1 / 2 的模擬(舊方法,只當歷史;`sim3_tables.py` 欄名已更正) |

## 重跑
```sh
python3 -I v3_tests.py <repo>                                     # 71 項,約 3 分鐘
python3 -I v3_fullflow.py <repo> <astra_v050_data> out.json       # 約 5 分鐘
python3 -I sim4_calibrate.py select <repo> <p1_events_d266.csv.gz> <astra_v050_data> sim4_out
python3 -I sim5_round2.py select <repo> <events> <dd> sim5_out; python3 -I sim5_round2.py report <repo> <events> <dd> sim5_out 0 2 (及 1 2); python3 -I sim5_round2.py merge sim5_out
python3 -I v3_verify.py status --dry-run --start 2026-10-14 --manifest-sha <v2 manifest SHA>   # 真實 37 筆(online)
```
