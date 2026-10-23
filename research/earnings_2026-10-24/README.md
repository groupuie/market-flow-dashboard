# earnings:產業盈餘動能(SEC 財報資料集 × French 49 產業)

- **EM1 預先登記**:`PROTOCOL_EM1.md`(盈餘轉強的產業,之後 3 個月會不會比較強;和 S0 融合有沒有加分)。
- 資料:SEC Financial Statement Data Sets 2009q1 ~ 2026q1(69 個 zip,約 5.6 GB;大小與 SHA-256 在 `out/fs_zip_manifest.json`,原檔不放);French 49 產業月報酬(同 `sector_rotation_2026-10-23/data_manifest.json`);`Siccodes49`(同 `supply_chain_2026-10-24/data_manifest.json`)。
- 程式(依序;需要 `pyarrow`、`duckdb`):
  1. `scripts/dl_fs.sh SCRATCH [清單]`:依 `scripts/fs_zips.txt` 下載(SEC 要求的聯絡方式只從本機檔案讀進請求標頭,不印出、不在 repo 裡)。
  2. `scripts/em_a_extract.py`:每季的申報清單與淨利列(`out/fs_extract_qa.json`)。
  3. `scripts/em_b_firmq.py`:每家公司每季的當季與去年同季淨利(10-K 的第 4 季 = 全年 − 9 個月)(`out/firmq_qa.json`)。
  4. `scripts/em_c_industry.py`:每個月底、每個產業的 G / B(`out/em1_signals.csv`、`out/em1_signals_qa.json`,含 Apple、Microsoft、Exxon、JPMorgan 抽查)。只用財報與申報時間,沒有報酬。
  5. `scripts/em1_run.py SCRATCH [--synthetic]` → `out/em1_results{_synthetic}.json`、`out/em1_monthly{_synthetic}.csv`;`scripts/em1_check.py SCRATCH syn|real` 用另寫的程式重算 3 個月份的 IC 與 H2 差。
- 目錄假設:`SCRATCH/ern/zips/`、`SCRATCH/ern/ext/`、`SCRATCH/ern/out/`、`SCRATCH/sc/x/Siccodes49.txt`、`SCRATCH/sr/raw/49_Industry_Portfolios_CSV.zip`。

不是投資建議。
