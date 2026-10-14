#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪 Astra 買 / 賣(一次一筆、每個買配一個賣)= index.html swTradesJS 同式

2026-10-14 使用者「全做」(Claude v2.4 的 I1 + I2):
  買 = ▲底 或 △回(scripts/astra_data.py sw_series 的 bot / b2;同一根兩個都有 → 算「底」)
  賣法(I2,看正股 / 指數本身):
    丙(SPY、QQQ 和它們的槓桿 ETF):第一個 ▼頂 → 隔天開盤賣;訊號後 40 根內沒有頂 → 第 40 根收盤後、隔天開盤賣
    乙(其他全部):第一個 ▼頂、或收盤 ≤ 買價 × 0.92(買價 = 訊號隔天開盤)、或訊號後第 20 根,先到先賣(都是隔天開盤)
  一次一筆:賣掉之前的新買點不算;新的買點要在「賣出決定那根」之後才算
只用已收盤的日K;所有判斷看收盤、成交用隔天開盤。這支只做計算,不抓資料、不寫檔。
"""

STY = {"c": {"key": "c", "name": "丙", "lim": 40, "stop": None},
       "b": {"key": "b", "name": "乙", "lim": 20, "stop": 0.08}}
IDX = ("SPY", "QQQ")


def style_of(sym):
    """sym = 正股 / 指數本身(槓桿 ETF 先換成正股)"""
    return STY["c"] if sym in IDX else STY["b"]


def buy_points(W):
    """[(i, '底' | '回')],依 i 排序;同一根兩個都有 → '底'"""
    k = {i: "回" for i in W["b2"]}
    for i in W["bot"]:
        k[i] = "底"
    return sorted(k.items())


def exit_of(W, O, i, sty, tops=None):
    """訊號在第 i 根(收盤)的這一筆 → (d, why):d = 賣出決定那根(隔天開盤賣),還沒決定 → (None, None)"""
    n = W["n"]; C = W["C"]
    tops = set(W["top"]) if tops is None else tops
    e = i + 1
    if e >= n:
        return None, None
    stop_px = O[e] * (1 - sty["stop"]) if sty["stop"] else None
    for j in range(e, min(i + sty["lim"], n - 1) + 1):
        if j in tops:
            return j, "頂"
        if stop_px is not None and C[j] <= stop_px:
            return j, "停損"
    if i + sty["lim"] <= n - 1:
        return i + sty["lim"], "到期"
    return None, None


def trades(W, O, sty):
    """一次一筆 → [{i, k, e, d, why, x}];最後一筆可能還沒賣(d 或 x 為 None / x ≥ n)"""
    n = W["n"]; tops = set(W["top"]); out = []; free = -1
    for i, k in buy_points(W):
        if i <= free:
            continue
        d, why = exit_of(W, O, i, sty, tops)
        out.append({"i": i, "k": k, "e": i + 1 if i + 1 < n else None, "d": d, "why": why,
                    "x": d + 1 if d is not None else None})
        if d is None or d + 1 >= n:
            break
        free = d
    return out


def ret(O, e, x, cost=0.0):
    """隔天開盤買 → 賣出那天開盤賣;cost = 每邊成本(0.001 = 0.1%)"""
    if O[e] is None or O[x] is None:
        return None
    return (O[x] * (1 - cost)) / (O[e] * (1 + cost)) - 1


def lev_open_close(O, C, L):
    """每天 L 倍的合成槓桿(不含管理費、融資成本):收盤 = 前收 ×(1 + L × 正股日報酬);開盤用隔夜跳空 × L"""
    # 單日跌幅 ≥ 1/L(例如 3 倍遇到 −34%)→ 合成價格歸零:之後都當作沒有(None)
    y = [C[0]]
    for i in range(1, len(C)):
        v = None if y[-1] is None else y[-1] * (1 + L * (C[i] / C[i - 1] - 1))
        y.append(v if (v is not None and v > 0) else None)
    yo = [y[0]]
    for i in range(1, len(C)):
        v = None if y[i - 1] is None else y[i - 1] * (1 + L * (O[i] / C[i - 1] - 1))
        yo.append(v if (v is not None and v > 0 and y[i] is not None) else None)
    return yo, y


def _self_test():
    # 小例子:手算對照
    W = {"n": 30, "C": [100.0] * 30, "bot": [2, 12], "b2": [2, 25], "top": [6, 20]}
    O = [100.0] * 30
    W["C"][14] = 91.0   # 第 12 根買(13 開盤 100)→ 第 14 根收 91 ≤ 92 → 停損
    t = trades(W, O, STY["b"])
    assert [(x["i"], x["k"], x["d"], x["why"]) for x in t[:2]] == [(2, "底", 6, "頂"), (12, "底", 14, "停損")], t
    assert t[2]["i"] == 25 and t[2]["d"] is None, t
    t = trades(W, O, STY["c"])
    assert [(x["i"], x["d"], x["why"]) for x in t] == [(2, 6, "頂"), (12, 20, "頂"), (25, None, None)], t
    W2 = {"n": 70, "C": [100.0] * 70, "bot": [1], "b2": [], "top": []}
    assert exit_of(W2, [100.0] * 70, 1, STY["c"]) == (41, "到期")
    assert exit_of(W2, [100.0] * 70, 1, STY["b"]) == (21, "到期")
    print("astra_trades self-test ok")


if __name__ == "__main__":
    _self_test()
