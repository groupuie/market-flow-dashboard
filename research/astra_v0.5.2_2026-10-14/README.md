# Astra v0.5.2 訊號時序複核(GPT 交付)+ Claude 核對(2026-10-14)

- 原檔:`v0.5.2_2026-10-14_13-23-01_訊號時序複核.md`(67,480 bytes,SHA-256 `18a63519edc76afade68bcedc7b6d11eb85abc513d56442b1cb009aa7be1b628`;掃過沒有個人資訊,原樣保存)
- 回覆:Claude v1.8「定位與資料源」、v1.9「資料源實測」
- 回覆文件:Claude v2.0(專案 claude/ 資料夾)

## Astra 這輪的重點
1. 用 Astra 自己保存的原始行情(不是重抓)核對 Claude v1.8 預測的 6 個日期:**6/6 符合**(ADI 2018-11-09 頂、2018-12-11 底,PWR 2018-10-18 頂、2021-11-05 底這 4 個平手日不觸發;ADI 2018-11-12 頂、PWR 2021-11-08 底觸發)。
2. ADI、PWR 的 B 段 B0 帳戶用凍結程式完整重播,和原值差 0(ADI 42.0131018944%、PWR 23.7375582815%)。
3. 日曆 dates-only 指紋雙方相同(`99be666a…`,5,730 天)。
4. E1 下一輪:接受 Claude 的 4 項建議,並補上精確定義(Python `round`、尾段低點維持未取位數、縮小部位要逐日重算實際曝險、A→B 校準不能用跨到 2018 的 A 帳戶)。
5. Alpha Vantage:歷史列存在,但「當時看得到」還沒驗證(IBM 7/14 先公布、7/22 才是 `reportedDate` 的例子)。
6. 更正 Claude v1.9:345 檔是 E1「設計預定」使用,還沒跑;每天 20 次查詢 ≈ 10 檔 × 2 項。

## `astra/`:從 MD 附錄抽出的 6 個檔(SHA-256 全部和附錄六相同)
| 檔案 | bytes | SHA-256 前 12 碼 |
|---|---:|---|
| `verify_original_ties.py` | 7,839 | `ac72b52ee8f2` |
| `tie-audit.json` | 11,593 | `317dbb651056` |
| `compare_fingerprints.py` | 2,016 | `daa90a8ca0fb` |
| `fingerprint-audit.json` | 718 | `cc6c8a8f5dff` |
| `earnings-data-review.md` | 11,336 | `2424c16c7eb8` |
| `e1-design-review.md` | 15,076 | `a5d1ff332d92` |

- 兩個 MD 嵌進正文時標題降了兩級(`#` → `###`),還原後指紋相同。
- 沒有收到:ZIP(`original-study/` 的 ADI、PWR 原始行情)、`claude-source/download-manifest.json`、`public-demo/`。所以 `verify_original_ties.py` 在 Claude 這邊跑不了(它釘住 Astra 原始 manifest 的指紋,這是正確的設計)。

## Claude 這輪的核對
1. `compare_fingerprints.py --self-test`:PASS(3 項)。
2. Astra 的 `fingerprint-audit.json`(123 同 / 145 異;10/14 重抓 53 / 215;日曆相同)和 Claude v1.8 自己的比對完全一致。
3. 同一個平手日(ADI 2018-12-11,原始收盤 88.64 = 前一天最高 88.64),三份快照的還原後差值:

   | 快照 | 還原收盤 − 前一天還原最高 | 底 |
   |---|---:|---|
   | Astra 原始 | −0.0000439 | 不觸發 |
   | Claude 10/13 | +0.0000020 | 觸發 |
   | Claude 10/14 | +0.0000096 | 觸發 |

4. Claude 2026-10-14T13:29Z 用公開示範金鑰重抓 IBM `EARNINGS` / `EARNINGS_ESTIMATES`:和 Astra 保存的 demo 檔**逐位元相同**(`c849fe15…`、`81757680…`)。
5. Astra 的帳戶值和 Claude v1.8 的「訊號取位數」重跑一致到小數第 4 位(ADI 42.01311792% / 42.01308011%;PWR 23.73755841% / 23.73755803%;差異來自成交價本身的雜訊)。
