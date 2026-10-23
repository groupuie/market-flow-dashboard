# sector_rotation:板塊輪動(中期盤感)

- SR1(`PROTOCOL_SR1.md`):高手式板塊輪動規則 × 量化(Ridge、MLP)× 預先固定的融合,French 12 / 49 產業月報酬,持有月 1975-01 ~ 2026-06;另有「分批逢低」子研究 AC1。
- 協定與程式先推上 GitHub,之後才用真實資料跑;結果寫在 `out/` 與報告。
- 資料:`data_manifest.json`(French 資料庫、FRED;只存指紋,原檔可照網址重抓)。
- 重跑:把 French 三個 zip 解壓到 `SCRATCH/sr/unz/`、FRED 四個 CSV 放 `SCRATCH/sr/raw/fred_{代號}.csv`,`python3 -I scripts/sr1_run.py SCRATCH`(約 3 分鐘)。

不是投資建議。
