# supply_chain:供應鏈傳導(BEA 投入產出表 × French 49 產業)

- **SC1 預先登記**:`PROTOCOL_SC1.md`(客戶產業這個月漲,供應商產業下個月會不會跟上;和 S0 融合有沒有加分)。
- 資料:BEA Use 表(細項 2007 / 2012 / 2017、摘要 1997–2023)、Census NAICS / SIC 對照、County Business Patterns 2012 / 2017、French `Siccodes49` 與 49 產業月報酬;來源與 SHA-256 在 `data_manifest.json`(原檔不放)。
- 程式(依序;需要 `openpyxl`、`xlrd`):
  1. `scripts/sc_map.py SCRATCH` → BEA 產業 → French 49 的對照(`out/sc1_map_detail.csv`、`out/sc1_map_summary.csv`)、49 × 49 流量表(`out/sc1_flows.npz`,每張表一個矩陣 + 各產業國內總產出)、檢查(`out/sc1_map_qa.json`)。只用表格,沒有報酬。`sc_bea_parse.py` 解析 BEA 的「NAICS Codes」表。
  2. `scripts/sc1_run.py SCRATCH [--synthetic]` → `out/sc1_results{_synthetic}.json`、`out/sc1_monthly{_synthetic}.csv`(每月一列:各 IC、前 10 名、Fama–MacBeth 係數)。
- 目錄假設:`SCRATCH/sc/bea/`(AllTablesIO.zip 解出的兩個 Use 表)、`SCRATCH/sc/raw/`(Census 對照表)、`SCRATCH/sc/cbp/`(CBP 解壓後的 txt)、`SCRATCH/sc/x/Siccodes49.txt`、`SCRATCH/sr/raw/49_Industry_Portfolios_CSV.zip`。

不是投資建議。
