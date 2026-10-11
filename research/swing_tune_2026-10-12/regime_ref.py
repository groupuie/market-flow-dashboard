# 走勢判斷(上升通道 / 下降通道 / 盤整)的 Python 參考實作 — 網站 JS 逐行對應(p1_prereg_regime.md §1)
#   H、L、C:list(日K,舊→新,已收完的K)
#   回傳 reg[t] ∈ {1 上升, -1 下降, 0 盤整}、lastH[t] / lastL[t](到 t 為止已確認的最近高點 / 低點)、
#        prevH[t] / prevL[t](再前一個)、brk_dn[t](上升跌破)、brk_up[t](下降突破)、piv(波段點:種類、位置、價格、確認日)

def atr_wilder(H, L, C, n=14):
    out = [None] * len(C); a = None
    for i in range(len(C)):
        tr = H[i] - L[i] if i == 0 else max(H[i] - L[i], abs(H[i] - C[i - 1]), abs(L[i] - C[i - 1]))
        a = tr if a is None else (a * (n - 1) + tr) / n
        out[i] = a
    return out

def zz_pivots(H, L, C, atr, k=1.5, lo=0.03, hi=0.08):
    n = len(C); piv = []
    if n < 2: return piv
    dirn = 0; hi = 0; lo = 0; ext = 0
    for t in range(1, n):
        dev = min(hi, max(lo, k * atr[t] / C[t])) if (atr[t] is not None and C[t] > 0) else 0.05
        if dirn == 0:
            if H[t] > H[hi]: hi = t
            if L[t] < L[lo]: lo = t
            if lo < hi and H[hi] >= L[lo] * (1 + dev):
                piv.append(("L", lo, L[lo], t)); dirn = 1; ext = hi
            elif hi < lo and L[lo] <= H[hi] * (1 - dev):
                piv.append(("H", hi, H[hi], t)); dirn = -1; ext = lo
            continue
        if dirn == 1:
            if H[t] >= H[ext]: ext = t
            elif L[t] <= H[ext] * (1 - dev):
                piv.append(("H", ext, H[ext], t)); dirn = -1
                m = ext + 1
                for j in range(ext + 1, t + 1):
                    if L[j] < L[m]: m = j
                ext = m
        else:
            if L[t] <= L[ext]: ext = t
            elif H[t] >= L[ext] * (1 + dev):
                piv.append(("L", ext, L[ext], t)); dirn = 1
                m = ext + 1
                for j in range(ext + 1, t + 1):
                    if H[j] > H[m]: m = j
                ext = m
    return piv

def regime(H, L, C, k=1.5, lo=0.03, hi=0.08):   # 第 2 輪 = 預設(1.5 倍 ATR、3–8%);第 3 輪通道尺度 = (3, 0.03, 0.30)
    n = len(C); atr = atr_wilder(H, L, C); piv = zz_pivots(H, L, C, atr, k, lo, hi)
    reg = [0] * n; lastH = [None] * n; lastL = [None] * n; prevH = [None] * n; prevL = [None] * n
    hs = []; ls = []; p = 0
    for t in range(n):
        while p < len(piv) and piv[p][3] <= t:
            (hs if piv[p][0] == "H" else ls).append(piv[p][2]); p += 1
        if hs: lastH[t] = hs[-1]
        if ls: lastL[t] = ls[-1]
        if len(hs) >= 2: prevH[t] = hs[-2]
        if len(ls) >= 2: prevL[t] = ls[-2]
        if len(hs) >= 2 and len(ls) >= 2:
            if hs[-1] > hs[-2] and ls[-1] > ls[-2] and C[t] >= ls[-1]: reg[t] = 1
            elif hs[-1] < hs[-2] and ls[-1] < ls[-2] and C[t] <= hs[-1]: reg[t] = -1
    brk_dn = [False] * n; brk_up = [False] * n
    for t in range(1, n):
        if reg[t - 1] == 1 and C[t] < lastL[t - 1]: brk_dn[t] = True
        if reg[t - 1] == -1 and C[t] > lastH[t - 1]: brk_up[t] = True
    return {"reg": reg, "lastH": lastH, "lastL": lastL, "prevH": prevH, "prevL": prevL, "brk_dn": brk_dn, "brk_up": brk_up, "piv": piv}
