# Astra v0.5.0 減碼出場研究(GPT 交付)+ Claude 複核(2026-10-13 ~ 10-14)

- 原檔:`v0.5.0_2026-10-13_23-20-32_減碼出場研究.md`(使用者轉交,逐位元保存)
- 研究問題(使用者本輪指定「優先研究減碼與出場」):買點固定為現行 Astra 底/回(commit `1dbaddf` 的 `scripts/astra_data.py:sw_series`),只比較賣法
  - B0 首頂全出(= 既有 XT)、R1 主研究(收盤浮盈曾 ≥ 2 倍 ATR 後,從最高收盤回吐 1 倍 ATR → 下一開盤減一半)、E1 次要探索(首頂減半、剩下收盤跌破前 10 根最低收盤才出,最多 63 天)、C50 半本金對照
- Astra 判定:R1 兩段都 0/4 組通過(少跌太少:平均不到 1 個百分點)→ **網站不改**;E1 只是探索

## 這個資料夾
| 檔案 | 內容 |
|---|---|
| `v0.5.0_…_減碼出場研究.md` | Astra 原檔 |
| `experiment.py`、`data_tools.py`、`test_experiment.py`、`test_data_tools.py`、`audit_results.py` | 從 MD 附錄二原樣抽出;5 個 SHA-256 都和 Astra 公布值相同 |
| `vendor/scripts/astra_data.py`、`vendor/research/swing_tune_2026-10-12/groups.json`、`universe_266.txt` | 從 git `1dbaddf` 取出;SHA-256 和 `data_tools.py` 釘住的值相同 |
| `protocol.md` | 取自 MD 附錄一(Astra 原檔在沒附上的 ZIP 裡;不保證逐位元相同) |
| `freeze.json` | Claude 端重建(Astra 的 freeze 在 ZIP 裡);列出上面各檔的 SHA-256 |
| `claude_rerun/` | Claude 用 Astra 的程式、自己新抓的資料重跑的輸出(`results.json`、`coverage.json`、`accounts.json`、`independent-audit.*`、`data_manifest.json`、log);大檔(`episodes.csv.gz` 16MB 等)只留本機 |
| `claude_check/c1_independent_exit_check.py` | Claude 自己寫的獨立實作(不 import Astra 程式);`c1_result.json` = Claude 快取資料(到 10/09)、`c1_result_astra_data.json` = 同一份新抓資料 |

## Claude 複核結果
1. **指紋**:5 個程式、3 個 vendor 檔全部相同 → Astra 用的就是網站現行 Astra 規則
2. **單元測試**:37 項全過;`audit_results.py --self-test` PASS
3. **重跑**(Astra 程式、Claude 2026-10-13 15:48 UTC 新抓 Yahoo,268/268 成功、截止 10/12、0 壞資料):
   - 判定相同:A 0/4、B 0/4;最後成熟訊號 2026-07-13;有窗口的代號 264(CBRS、SKHY、SPCX、WOLF 沒有)
   - 窗口 51,491(Astra 51,501,少 10 個);數字差 ≤ 0.1 個百分點(例:後段 ALL B0 獲利比例 60.77% vs 60.80%、R1 少跌 0.298 vs 0.299 點)
   - `audit_results.py` 跑在 Claude 重跑結果上:PASS_CONSISTENCY_ONLY,2,383,426 項比較、0 不一致
   - 差異來源推測:兩次下載之間 Yahoo 資料修訂(沒有 Astra 的 manifest,無法逐檔比)
4. **獨立實作**(`claude_check/`):
   - 同一份新抓資料:和 Astra 程式的結果完全相同(51,491 窗口;ALL、IDX、MAG7、NDX 的 R1 少跌/少賺、觸發率都一樣)
   - Claude 自己的快取資料(到 10/09):ALL 差 ≤ 0.05 點;MAG7 前段少跌 0.169 vs 0.192(資料來源差,換同一份資料就相同)
5. **補充觀察(只描述,事後推算,不改 Astra 的判定)**
   - R1 只在 11–12% 的窗口觸發;觸發時後段 ALL 少跌 2.8 點、少賺 2.0 點(賣掉的那一半,照原計畫抱到頂再賣平均還會多約 3.9%)
   - 每少賺 1 點換到的少跌:R1 後段 1.4、前段 3.6;C50(只買一半)後段 4.1、前段 4.0 → 減碼不如直接少買
   - E1 每多承受 1 點回撤多換到的報酬:後段 0.90、前段 0.63;直接加部位只有約 0.24 → 「頂先賣一半、剩下抱著」值得預先登記後另外驗證;但它的獲利比例與中位數較低,報酬靠少數大漲

## 重跑
```sh
cd research/astra_v0.5.0_2026-10-13
python3 -m unittest discover -v
python3 data_tools.py download --workers 4 --asof 2026-10-12 --data-dir /home/claude/work/astra_v050_data
python3 experiment.py --data-dir /home/claude/work/astra_v050_data        # 輸出到 evidence/
python3 audit_results.py --data-dir /home/claude/work/astra_v050_data
python3 claude_check/c1_independent_exit_check.py                        # Claude 快取資料
SRC=astra python3 claude_check/c1_independent_exit_check.py              # 同一份新抓資料
```
- 回覆文件:Claude v1.7(專案 claude/ 資料夾)
