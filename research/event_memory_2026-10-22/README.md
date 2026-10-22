# event_memory:財報後五天的快速發動 × 經驗記憶(新研究路線)

- 版本:v0.1|2026-10-22 00:35:59(台灣)|簡述:路線索引
- 起因:Astra Ultra「給 Claude:把盤感研究改成可驗證的事件與記憶試驗」v1.0(2026-10-21 23:22:33)
- 狀態:**協定草案 + 開發檢查**;沒有做任何 Claude 判讀、沒有凍結。舊研究全部保留不動;不改網站、不下單、不加排程或 GitHub Actions。

## 先看哪個

1. `research_contract_v0.1.md` — 要做什麼、怎麼評分、要幾季、花多少、待決定事項
2. `evidence_map.md` — 舊研究對這條路線的意思 + 這次 E0–E8 的發現(含給 v4.2 的更正;E6–E8 回應 Codex)
3. `data_provenance.md` — 資料欄位、四個時間、SEC 時間戳的坑

## Astra 清單對照

| Astra 交付物 | 在這裡 | 狀態 |
|---|---|---|
| research_contract_v0.1.md | `research_contract_v0.1.md` | ✓ 草案 |
| evidence_map.md | `evidence_map.md` | ✓ |
| preregistration_draft.md | 契約 §5 | ✓ 草案 |
| label_spec.md | 契約 §3 | ✓ 草案(尺待定:建議 ATR60) |
| data_dictionary.md | `data_provenance.md` §1–2 | ✓ |
| provenance_audit.md | `data_provenance.md` §3 | ✓(20 檔 × 4 份試抓) |
| case_schema.json | `case_schema.json` | ✓ 草案 |
| decision_schema.json | `decision_schema.json` | ✓ 草案 |
| one_day_example.md | 契約 §8「試做一輪」 | ⏳ 要先同意判讀成本(約 300–350 萬 tokens) |
| analysis_plan.md | 契約 §5 | ✓ 草案 |
| replay_validation.md | `evidence_map.md` E4 | ◐ 答案重算 ✓;資料包重建要等試做一輪 |
| null_simulation_report.md | `evidence_map.md` E4 | ◐ 日期層級 ✓;反應週層級還沒模擬(主檢定凍結前用模擬挑定) |
| power_plan.md | 契約 §6(E2、E4) | ◐ 要等試做一輪量出 B、C 差多少 |
| trial_manifest.json | `trial_manifest.json` | ✓(E0–E8 + 計畫中的三個) |
| freeze_manifest.json | — | ⏳ 凍結時產生 |

## 重跑

- 程式都是 `python3 -I scripts/<名字>.py SCRATCH`;SCRATCH 底下要有:
  - `w7/`:walk7 工作資料夾(`out/S7.pkl`、`data/daily.pkl.gz`、x6 另外要 `out/pred_M2_real.pkl`;由 `research/walk7_2026-10-21/` 的 d0–d3、w1 重建;日 K 解壓後 SHA-256 `0a0fd080…` = `research/walk7_2026-10-21/data/daily_manifest.json`)
  - `w8/`:walk8 工作資料夾(`out/ea_events.pkl`、`data/cik_map.json`、`raw/subs/`;由 `research/walk8_2026-10-21/` 的 e0、f2 重建)
  - `w8/.sec_ua`:SEC 要求的 User-Agent(含聯絡 email;只存在本機,不進 repo)
- 順序:x1 → x2(產生 `em/out/fl3_rows.pkl`,8,400 萬位元組,不進 repo)→ x3、x4 → x5、x5b、x6、x7;p1b 獨立(會抓 SEC,約 160 次請求);p2 讀 `SCRATCH/em/r2tag/r2_events_408.json`(= repo 的 `codex_r2/r2_events_408.json`,Codex 提供的事件清單)、`w8/`(CIK 對照、`.sec_ua`)與 `w7/data/daily.pkl.gz`(只用 SPY 的日期),抓 SEC 標註,不用任何股價結果;p3 讀 p2 的輸出,逐份抓 SGML 檔頭做時間戳稽核。
- 輸入檔指紋見 `trial_manifest.json`。

不是投資建議。
