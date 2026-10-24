# sector_rotation:板塊輪動(中期盤感)

- SR1(`PROTOCOL_SR1.md`):高手式板塊輪動規則 × 量化(Ridge、MLP)× 預先固定的融合,French 12 / 49 產業月報酬,持有月 1975-01 ~ 2026-06;另有「分批逢低」子研究 AC1。
- SR2(`PROTOCOL_SR2.md`):產業之間的領先落後(LASSO)。
- 協定與程式先推上 GitHub,之後才用真實資料跑;結果:`REPORT_SR1_SR2.md`(更正前原樣)、`CORRECTIONS_R8.md`(2026-10-23 程式更正與 R8 核對)、`out/`。
- 程式版本:`scripts/sr1_run.py` v1.2、`scripts/sr2_run.py` v1.1(正式);`sr1_run_v1.1.py`、`sr2_run_v1.0.py` 是更正前的凍結版本(給 `sr1_r8_checks.py` 對照用)。
- 資料:`data_manifest.json`(French 資料庫、FRED;只存指紋,原檔可照網址重抓);ALFRED 歷史版本與 13F 抽查的原檔指紋在 `out/sr1_alfred_check.json`、`out/f13_probe_manifest.json`。
- 重跑:把 French 三個 zip 解壓到 `SCRATCH/sr/unz/`、FRED 四個 CSV 放 `SCRATCH/sr/raw/fred_{代號}.csv`,`python3 -I scripts/sr1_run.py SCRATCH`(約 3 分鐘)、`python3 -I scripts/sr2_run.py SCRATCH`(約 1 分鐘)、`python3 -I scripts/sr1_r8_checks.py SCRATCH`(約 1.5 分鐘)。

不是投資建議。
