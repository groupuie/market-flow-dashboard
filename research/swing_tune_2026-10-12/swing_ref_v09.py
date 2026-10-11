# 📍短線 v0.9 的 Python 參考實作(網站 swSeriesJS 逐行對應)
#   和 v0.8 的差別:① 來回成績成本 0(使用者 Firstrade 免手續費):賺 = 出場價 > 進場價;買回更便宜 = 買回價 < 賣價
#                   ② 每個頂標「上升趨勢」:50 日均線 > 200 日均線,而且 50 日均線比 20 根前高(逐根相加)→ 網站畫灰色
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "swing_marks_2026-10-11"))
from swing_ref import sw_py as _sw_v07

def sw_py_v09(B):
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
        rt["bn"] += 1; rt["bw"] += O[e] > O[i + 1]
    for i in b2:
        e = ex(top, i)
        if e >= n or i + 1 >= n: continue
        rt["b2n"] += 1; rt["b2w"] += O[e] > O[i + 1]
    for i in top:
        e = ex(bot, i)
        if e >= n or i + 1 >= n: continue
        rt["tn"] += 1; rt["tw"] += O[e] < O[i + 1]
    def ma(i, k):
        if i - k + 1 < 0: return None
        s = 0.0
        for q in range(i - k + 1, i + 1): s += C[q]
        return s / k
    tup = {}
    for i in top:
        a, b, c = ma(i, 50), ma(i, 200), ma(i - 20, 50)
        tup[D[i]] = bool(a is not None and b is not None and c is not None and a > b and a > c)
    return {"bot": r["bot"], "top": r["top"], "b2": [D[i] for i in b2], "rt": rt, "tup": tup}
