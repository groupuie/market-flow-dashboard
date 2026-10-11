# 把 Astra v0.3 研究帳本轉成網站用的「只標日期」事件檔 astra-v03-events.json(網站根目錄)。
# 依 Astra v0.4.0 §5:在 K 線下方另畫只表示事件日期的研究軌道,沒有價格座標、不是本圖成交價。
#   ・來源檔逐位元核對 Astra 在 v0.3.1 彙編裡公布的 SHA-256,不一致就停。
#   ・只搬「日期、動作、原因、這一輪的研究結果」;不搬價格(網站不畫研究價格)。
#   ・顯示的是 Astra 的診斷模型(只用價格的邏輯迴歸,門檻 0.55);事前選定的模型評估期 0 筆,一併寫進檔案說明。
import hashlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(HERE, "source")
EXPECT = {   # Astra v0.3.1「完整研究彙編」逐檔列出的 SHA-256
    "logistic_C1_standardized__price_only__trades.json": "3582a3ab5f9a2dc23c1f509c4830fb0ece43fc1013dac45b8b7d0b84a546e7f6",
    "research-results.json": "c2ef719eb84837f4792979b8c099e3c93dd446aeb37adb28e330731b35fd2d37",
    "selected__trades.json": "ea3913ee9cf3a1434611f13414fe4cc60518956b87da7c5999eb79c06f544e00",
}
ORIG = {"logistic_C1_standardized__price_only__trades.json": "astra-v0.3/evidence/diagnostics/logistic_C1_standardized__price_only/trades.json",
        "research-results.json": "astra-v0.3/evidence/research-results.json", "selected__trades.json": "astra-v0.3/evidence/trades.json"}

def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()

for f, h in EXPECT.items():
    got = sha(os.path.join(SRC, f))
    if got != h: sys.exit(f"SHA-256 不符:{f} {got} != {h}")

T = json.load(open(os.path.join(SRC, "logistic_C1_standardized__price_only__trades.json")))
RR = json.load(open(os.path.join(SRC, "research-results.json")))
SEL = json.load(open(os.path.join(SRC, "selected__trades.json")))
assert T["modelId"] == "logistic_C1_standardized__price_only" and T["diagnosticOnly"] is True and T["selectedForPrimaryEvaluation"] is False
assert SEL["modelId"] == RR["selectedModelId"] and SEL["trades"] == []
ev = {e["modelId"]: e for e in RR["evaluation"]}
M = ev[T["modelId"]]["evaluationMetrics"]
universe = [s for s in RR["datasetDiagnostics"] if s not in ("SPY", "QQQ")]   # SPY/QQQ 只當大盤對照,不交易

camps = {}
for c in sorted(T["trades"], key=lambda c: (c["symbol"], c["entryDate"])):
    fills = [[f["kind"], f["executionDate"], f["reason"]] for f in c["fills"]]
    assert fills[0][0] == "ENTRY" and fills[-1][0] == "EXIT" and [f[1] for f in fills] == sorted(f[1] for f in fills)
    camps.setdefault(c["symbol"], []).append({"id": c["tradeId"], "sig": c["signalDate"], "f": fills,
                                             "ret": round(c["netReturn"] * 100, 2), "hold": c["holdingBars"], "exit": c["exitReason"]})
n = sum(len(v) for v in camps.values()); wins = sum(1 for v in camps.values() for c in v if c["ret"] > 0)
assert n == M["N"] == 57 and wins == M["wins"] == 30

out = {
    "schema": 1,
    "note": "Astra v0.3 研究事件(只有日期)。研究用 Alpaca 只除權價格,和網站 K 線口徑不同 → 網站不畫價格、不是本圖成交價。不是買賣建議。",
    "source": {"astra": "v0.3.1 完整研究彙編(研究 v0.3.0)", "files": {ORIG[f]: EXPECT[f] for f in EXPECT},
               "datasetSha256": T["datasetSha256"], "protocolSha256": T["protocolSha256"], "createdAt": RR["createdAt"]},
    "model": {"id": T["modelId"], "label": "診斷模型:只用價格的邏輯迴歸", "threshold": T["threshold"], "diagnosticOnly": True,
              "selectedForPrimaryEvaluation": False},
    "selected": {"id": RR["selectedModelId"], "label": "事前選定的模型:梯度提升樹(價格+量的代理指標)", "threshold": 0.75, "evaluationCampaigns": 0},
    "period": {"evaluationSignals": RR["signalDateRanges"]["evaluation"], "dataThrough": "2026-10-09"},
    "summary": {"n": M["N"], "wins": M["wins"], "losses": M["losses"], "winRate": round(M["netWinRate"] * 100, 2),
                "wilson95": [round(x * 100, 1) for x in M["wilson95"]], "meanNet": round(M["meanNetReturn"] * 100, 2),
                "medianNet": round(M["medianNetReturn"] * 100, 2), "meanHold": round(M["meanHoldingBars"], 1), "costBpsPerSide": 10},
    "rules": {"ENTRY": "模型分數過門檻 → 隔天開盤建倉;停損 = 進場價 − 2 ATR",
              "REDUCE": "持有 ≥10 天、有賺,且漲多(≥ 進場 + 2 ATR)或出現出貨量 → 隔天開盤減 1/3",
              "ADD": "減碼後回檔、又重新轉強 → 用減碼拿回的錢回補(最多 1/3)",
              "EXIT": "連兩天收在 20 日線下且資金轉負 / 碰到停損 / 開盤跳空跌破停損 / 滿 63 天"},
    "symbols": universe,
    "campaigns": camps,
}
dst = os.path.join(REPO, "astra-v03-events.json")
open(dst, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n")
print("寫出", dst, os.path.getsize(dst), "bytes;", n, "輪 /", len(camps), "檔有事件 / 名單", len(universe), "檔;sha256", sha(dst))
