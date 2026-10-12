# 擴大範圍資料檢查 2:已追蹤的股票,網站K線(gist,富途前復權)和 astra-data(Yahoo 還原)算出來的 Astra 記號差多少
#   → 「今天訊號清單」(Yahoo)和K線圖(gist)對不上的機率
import json, os, sys, urllib.request, concurrent.futures as cf
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts")); import astra_data as AD
OUT = sys.argv[1]
G = "https://gist.githubusercontent.com/groupuie/147672e7493b26aec57f42f5e12cb524/raw/kline_{}.json"
SY = "AAPL MSFT NVDA AMZN GOOGL META TSLA AVGO AMD MU INTC QCOM MRVL ARM TSM ASML AMAT LRCX KLAC SNDK WDC STX ANET CSCO COHR LITE CRDO ALAB DELL SMCI VRT ORCL PLTR NOW CRM SNOW CRWD PANW NET APP CRWV NBIS IREN SPY QQQ".split()
def gj(s):
    try: return s, json.loads(urllib.request.urlopen(urllib.request.Request(G.format(s), headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read())
    except Exception as e: return s, None
with cf.ThreadPoolExecutor(6) as ex: GI = dict(ex.map(gj, SY))
tot = {"both": 0, "only_gist": 0, "only_yahoo": 0}; per = {}; last = {}
for s in SY:
    g = GI.get(s); kf = os.path.join(OUT, "k", s + ".json")
    if not g or not os.path.exists(kf): continue
    yb = json.load(open(kf))["bars"]; gb = [b[:6] for b in g["bars"]]
    d0 = max(gb[0][0], yb[0][0]); d1 = min(gb[-1][0], yb[-1][0])
    Wg, Wy = AD.sw_series(gb), AD.sw_series(yb)
    st = lambda W: {(W["D"][j], k) for k, A in (("底", W["bot"]), ("回", W["b2"]), ("頂", W["top"])) for j in A if d0 <= W["D"][j] <= d1 and j >= 250}
    a, b = st(Wg), st(Wy)
    # 只比兩邊都有 250 根暖身之後(B2 要 200 日線)、而且兩邊日期都涵蓋的區間
    lo = max(Wg["D"][250], Wy["D"][250]); a = {x for x in a if x[0] >= lo}; b = {x for x in b if x[0] >= lo}
    per[s] = {"both": len(a & b), "only_gist": len(a - b), "only_yahoo": len(b - a), "gist_src": g.get("src"), "range": [lo, d1]}
    for k in tot: tot[k] += per[s][k]
    last[s] = sorted(a ^ b)[-3:]
tot["agree_pct"] = round(100 * tot["both"] / max(1, tot["both"] + tot["only_gist"] + tot["only_yahoo"]), 2)
json.dump({"total": tot, "per": per, "last_diff": last}, open(os.path.join(HERE, "c2_gist_vs_yahoo.json"), "w"), ensure_ascii=False, indent=1)
print(tot); print({s: v for s, v in per.items() if v["only_gist"] or v["only_yahoo"]})
