# 全球資金氣候 + ▲抄底/▼減碼 — 研究腳本(2026-10-09)

上線版本是 `scripts/flow_climate.py`(純標準庫)與 `index.html` 的 `fcSeriesJS`;本資料夾是**研究用**腳本
(需要 pandas / numpy / scikit-learn,不在 GitHub Actions 執行)。完整結論見專案文件 `claude/flow_climate_2026-10.md`。

腳本內的 `DT`(資料暫存路徑)指向當時的沙盒,重跑前請改成自己的資料夾。

## 執行順序

| 步驟 | 腳本 | 做什麼 |
|---|---|---|
| 1 | `fetch_yh.py` / `fetch_cot.py` / `fetch_meta.py` | 下載 Yahoo 日K全史(追蹤清單 345 檔 + 總經/跨資產 ~80 檔)、CFTC COT(TFF+分類持倉 2006 起)、標的類型;DIX.csv 另以 curl 下載 |
| 2 | `build.py` → `long.py` | 個股特徵 / 前瞻報酬(隔日開盤進場)/ 市場特徵;攤平成 92.6 萬列個股日資料 |
| 3 | `base_eval.py` | 現有 ◆★ 在 2007–2026 長史的表現(≈擲硬幣) |
| 4 | `sscreen.py` `gaps.py` `dips.py` | 個股技術面單因子 / 跳空量能 / 「上升趨勢中拉回買」:皆≈基準 |
| 5 | `mscreen.py` `mevents.py` `stab.py` | 市場層 181 個特徵 × 4 個子期間穩定度;找出方向一致者 |
| 6 | `yen.py` | 日圓套利(CFTC JPY)持倉的區塊自助法信賴區間與分期五分位 |
| 7 | `climate*.py` `robust.py` `stock_climate.py` | 氣候組合、煞車變體、144 組參數敏感度、個股層分桶 |
| 8 | `ml_wf.py` `ml_eval*.py` `ml_imp*.py` `ml_cs.py` | 梯度提升樹逐年前推(walk-forward)當天花板對照;分組置換重要度(含不偷看 2018+ 的巢狀驗證) |
| 9 | `combo.py` `grid.py` `tops.py` `rules.py` | 氣候 × 個股轉折(技判「出」/ 深跌站回)與門檻網格 |
| 10 | `prod_eval.py` `final_eval.py` `confirm.py` `stats_final.py` | 上線口徑逐年表、兩半期自助法 CI、確認條件測試、hover 用統計(`final_stats.json`) |

## 上線口徑(與研究完全相同)
- 氣候 = rank756( ( (1−rank756(CFTC 日圓交易商淨部位 z156)) + ((1−rank756(5Y 殖利率 20日變化)) + (1−rank756(美元 CTA 趨勢)))/2 ) / 2 )
- ▼ = 近 20 日 max(收盤/50日線−1) ≥ 15% 且今日首次收破 20 日線(冷卻 20 日,以轉折計),且氣候 ≤ 35%
- ▲ = 近 20 日 min(收盤/50日線−1) ≤ −10% 且今日首次站回 20 日線(冷卻 20 日),且 min ≤ −15%、氣候 ≥ 80%
- 驗證:上線 Python 與研究序列 4362 日逐日一致;JS↔Python 332 檔 1406 事件逐筆一致。

## 2026-10-10 補充(📊量化整合層用)
- `raw_nontight.py`:同型「漲多後跌破20日線」轉折在全球資金不緊(>35%)時 n=3101,20日後較低 42.6% vs 平常 43.7%、40日平均 +4.6% vs +2.1% → 圖上不標;只有氣候≤35%(=🌐▼)才標「出」。
