# f13_datalayer:13F 大資金持股資料層 DL1(只有資料與品質,沒有任何報酬或預測)

- 規格:`DL1_SPEC.md`(v1.0 先寫、v1.1 記下跑的過程中改的 4 處與原因)。
- 資料:SEC Form 13F Data Sets 54 個 zip(申報日 2013-05-20 ~ 2026-08-31,約 3.05 GB;SHA-256 在 `out/dl1_zip_manifest.json`;原檔與中間 parquet 太大不放)。
- 程式(依序):`scripts/dl_zips.sh`(下載;SEC 要求的聯絡方式只從本機檔案讀進請求標頭)→ `a_small.py` → `b_infotable.py` → `c_snapshots.py`(版本、單位、標準快照)→ `d_series.py`(三條序列,CUSIP 層級)→ `e_mapping.py`(CUSIP → 產業的可行性抽查)。需要 `duckdb`、`pyarrow`。
- 結果:`out/dl1_quality.json`(每季覆蓋與品質)、`out/dl1_quarterly_summary.csv`(每季一列)、`out/dl1_series_quality.json`(拆股判定與序列品質)、`out/dl1_mapping_probe.json`。
- 驗算:Berkshire 2022Q3 / Q4 的可口可樂、雪佛龍,標準快照的股數與市值和原始 XML(`sector_rotation_2026-10-23/out/f13_probe_result.json`)逐位相同。
- 產業對照 CM1(`scripts/f_cusipmap.py`):任一季占乾淨股票持股 ≥ 0.003% 的 6,057 個 CUSIP;EDGAR 全文檢索 SC 13D / 13G(兩輪:連寫與分段寫法)→ 標的公司 CIK 與當時的 SIC;OpenFIGI + SEC 代號表當備援與 ETF 判定;覆蓋率 `out/cm1_coverage.csv`(每季對到產業 84.9–92.3%、ETF 4.4–12.0%)。
- **FL1 預先登記**(`PROTOCOL_FL1.md`、`scripts/fl1_run.py`;登記 `9629975`,對照程式更正 `6136e90`):結果 `out/fl1_results.json`、`out/fl1_decisions.csv`(假報酬除錯:`out/*_synthetic.*`)。
- 還沒做:主動 / 被動分類、合併報告與其他經理人的重複計算、ADR / 特別股 / 債券的對照。

不是投資建議。
