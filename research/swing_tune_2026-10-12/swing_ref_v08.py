# 📍短線 底/頂/回檔 的 Python 參考實作(v0.8;和網站 swSeriesJS / ctaPosJS 逐行對應)
#   B = [[日期, 開, 高, 低, 收], ...](日K、已收完的K)
#   底 / 頂:同 v0.7(research/swing_marks_2026-10-11/swing_ref.py)
#   回檔(B2,Double 7s):收盤 > 200 日均線(當天往回 200 根,逐根相加)且 = 7 天最低收盤;冷卻 5 根
#   rt:隔天開盤成交、來回成本 0.2%;下一個反向記號的隔天開盤出場,40 根內沒有就第 i+41 根
#     bn/bw = 底 → 頂 賺;b2n/b2w = 回檔 → 頂 賺;tn/tw = 頂賣 → 下一個底(或 40 根)買回更便宜
import math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "swing_marks_2026-10-11"))
from swing_ref import sw_py as _sw_v07

def sw_py_v08(B):
    r = _sw_v07(B)
    D = [b[0] for b in B]; O = [b[1] for b in B]; C = [b[4] for b in B]; n = len(B)
    idx = {d: i for i, d in enumerate(D)}
    bot = [idx[d] for d in r["bot"]]; top = [idx[d] for d in r["top"]]
    b2 = []; l2 = -10**9
    for i in range(199, n):
        s = 0.0
        for k in range(i - 199, i + 1): s += C[k]
        m = s / 200; mn = min(C[i - 6:i + 1])
        if C[i] > m and C[i] <= mn and i - l2 > 5: l2 = i; b2.append(i)
    def ex(A, i):
        for k in A:
            if k > i: return k + 1 if k - i <= 40 else i + 41
        return i + 41
    rt = {"bn": 0, "bw": 0, "tn": 0, "tw": 0, "b2n": 0, "b2w": 0}
    for i in bot:
        e = ex(top, i)
        if e >= n or i + 1 >= n: continue
        rt["bn"] += 1; rt["bw"] += O[e] > O[i + 1] * 1.002
    for i in b2:
        e = ex(top, i)
        if e >= n or i + 1 >= n: continue
        rt["b2n"] += 1; rt["b2w"] += O[e] > O[i + 1] * 1.002
    for i in top:
        e = ex(bot, i)
        if e >= n or i + 1 >= n: continue
        rt["tn"] += 1; rt["tw"] += O[e] < O[i + 1] * 0.998
    return {"bot": r["bot"], "top": r["top"], "b2": [D[i] for i in b2], "rt": rt}
