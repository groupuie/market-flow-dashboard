# 📍短線 底/頂 的 Python 參考實作(和網站 swSeriesJS 逐行對應;t5 內也有同一份)
#   B = [[日期, 開, 高, 低, 收], ...](日K、已收完的K)
#   底:近 3 天任一天超賣(RSI2≤10 或 收≤布林下緣(20,2) 或 九轉買 9)且 今天收盤 > 昨天最高;同方向 5 天內不重複
#   頂:近 3 天任一天超買(RSI2≥90 或 收≥布林上緣 或 九轉賣 9)且 今天收盤 < 昨天最低
#   rt:這檔的來回成績 — 底(隔天開盤買)→ 40 天內下一個頂(頂隔天開盤賣)賺 = bw/bn;頂賣 → 下一個底買回更低 = tw/tn
import math

def sw_py(B):
    n = len(B); D = [b[0] for b in B]; O = [b[1] for b in B]; H = [b[2] for b in B]; L = [b[3] for b in B]; C = [b[4] for b in B]
    r2 = [None] * n
    if n >= 4:
        g = [max(C[i] - C[i - 1], 0) for i in range(1, n)]; l = [max(C[i - 1] - C[i], 0) for i in range(1, n)]
        ag = (g[0] + g[1]) / 2; al = (l[0] + l[1]) / 2; r2[2] = 100 if al == 0 else 100 - 100 / (1 + ag / al)
        for i in range(3, n):
            ag = (ag + g[i - 1]) / 2; al = (al + l[i - 1]) / 2; r2[i] = 100 if al == 0 else 100 - 100 / (1 + ag / al)
    lo = [None] * n; up = [None] * n
    for i in range(19, n):
        w = C[i - 19:i + 1]; m = sum(w) / 20; sd = math.sqrt(sum((v - m) ** 2 for v in w) / 20); lo[i] = m - 2 * sd; up[i] = m + 2 * sd
    tb = [0] * n; ts = [0] * n
    for i in range(4, n):
        tb[i] = tb[i - 1] + 1 if C[i] < C[i - 4] else 0; ts[i] = ts[i - 1] + 1 if C[i] > C[i - 4] else 0
    os_ = lambda i: (r2[i] is not None and r2[i] <= 10) or (lo[i] is not None and C[i] <= lo[i]) or tb[i] == 9
    ob_ = lambda i: (r2[i] is not None and r2[i] >= 90) or (up[i] is not None and C[i] >= up[i]) or ts[i] == 9
    bot, top = [], []; lb = lt = -10**9
    for i in range(2, n):
        if (os_(i) or os_(i - 1) or os_(i - 2)) and C[i] > H[i - 1] and i - lb > 5: lb = i; bot.append(i)
        if (ob_(i) or ob_(i - 1) or ob_(i - 2)) and C[i] < L[i - 1] and i - lt > 5: lt = i; top.append(i)
    rt = {"bn": 0, "bw": 0, "tn": 0, "tw": 0}
    def nxt(A, i):
        for k in A:
            if k > i: return k if k - i <= 40 else None
        return None
    for i in bot:
        k = nxt(top, i)
        if k is None or k + 1 >= n or i + 1 >= n: continue
        rt["bn"] += 1; rt["bw"] += O[k + 1] > O[i + 1]
    for i in top:
        k = nxt(bot, i)
        if k is None or k + 1 >= n or i + 1 >= n: continue
        rt["tn"] += 1; rt["tw"] += O[k + 1] < O[i + 1]
    return {"bot": [D[i] for i in bot], "top": [D[i] for i in top], "rt": rt}
