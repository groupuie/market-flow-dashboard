# Astra 按鈕更新:v0.3「只標日期」研究軌道(2026-10-11)

- 依據:Astra v0.4.0「資金假說複驗」§5 第 5 點(K 線下方另畫只表示事件日期的研究軌道,沒有價格座標、不是本圖成交價;不放寬原 adapter)
- 回覆文件:Claude v0.6(專案 claude/ 資料夾)
- 網站改動:`index.html`(Astra 按鈕打開時,K 線下方加細軌道 + 詳情窗改成共識文字)、`astra-v03-events.json`(網站根目錄)。Astra 關掉時版面、記號、狀態列和改版前逐項相同;📊量化 不受影響。

## 檔案
| 檔案 | 內容 |
|---|---|
| `source/` | Astra v0.3 原檔(逐位元,SHA-256 與 Astra 彙編公布值相同):診斷模型帳本、選定模型帳本(空)、research-results |
| `build_events.py` | 核對 SHA-256 → 轉出 `astra-v03-events.json`(只有日期、動作、原因、每輪研究淨報酬與持有天數;不帶價格) |
| `t3_astra_lane_test.py` / `.json` / `.log` | 本機網頁驗收:舊版(線上 BUILD 2026-10-11T07:45Z)vs 新版;8 檔 × 30/100/250 日;週月K、全史、縮放、詳情窗、滑過、手機、事件檔 404 |
| `price_basis_check.py` / `.json` / `.log` | 價格口徑逐筆表:診斷模型 130 筆成交 vs 網站同日K(取代 v0.5 無法重現的「59/104」) |
| `t4_online_check.py` / `.json` | 部署後線上複驗 |

## 重跑
```sh
python3 build_events.py                      # 重新產生網站根目錄的 astra-v03-events.json(雜湊不符就停)
python3 t3_astra_lane_test.py <舊版 index.html> <新版 index.html> out.json
python3 price_basis_check.py <網站 kline_SYM.json 所在資料夾>
```
行情照網站從 gist 即時抓;日K檔更新後,軌道的事件日期不變(研究快照),但視窗位置會跟著移動。
