#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P7 規則回測層(純 stdlib)— webapp/index.html 前端 backtest()/btFlags() 的 Python 鏡像。

定位:前端為主(零 token、任何代號皆可即時回測);本檔為次要鏡像,供
  (a) 引擎端把預設規則組的結果寫入 signals.json 的 computed_bt,
  (b) 一致性對拍(JS 與 Python 必須逐筆同進同出)。

誠實分級(與畫面免責同步,任何引用處都必須一併呈現):
  · 歷史模擬,非績效保證
  · 含前視偏誤風險:成交價用「訊號日收盤」,而條件於當日收盤後才確定
  · 未計滑價、手續費、稅、股利、借券成本
  · 樣本 <20 筆標「樣本不足」,不具統計意義
  · 規則本身於歷史上被挑選過(選擇偏誤);不得作為買賣建議

用法:
  python3 backtest.py --symbols NVDA,MU --kline-dir data [--json out.json]
  python3 backtest.py --symbols NVDA --entry td9b --exit td9s,ctaDn,stopATR,maxHold
"""
import json, os, math, argparse

LEAD = 252          # 與前端 cockpitRows 一致:前 252 根僅供暖機,不進入 rows
MAXHOLD = 60
ATRK = 2
MIN_N = 20          # 低於此筆數標「樣本不足」

ENTRY_DEF = [
    ("td9b",   "TD買9/13 完成"),
    ("ctaUp",  "CTA 檔位翻正"),
    ("brk200", "站上 200D 煞車線"),
    ("dc20",   "突破 20 日新高"),
    ("rvLow",  "RVPOS ≤ 25(壓縮)"),
    ("cdlB",   "看多蠟燭型態"),
]
EXIT_DEF = [
    ("td9s",    "TD賣9/13 完成"),
    ("ctaDn",   "CTA 檔位翻負"),
    ("lose200", "跌破 200D 煞車線"),
    ("dcl20",   "跌破 20 日新低"),
    ("stopATR", "停損 −2×ATR20"),
    ("maxHold", "持有滿 60 日"),
]
LABEL = dict(ENTRY_DEF + EXIT_DEF)
DEFAULT_ENTRY = ["td9b"]
DEFAULT_EXIT = ["td9s", "ctaDn", "stopATR", "maxHold"]

DISCLAIMER = ("歷史模擬、含前視偏誤風險、未計滑價與交易成本、樣本數少時不具統計意義;"
              "規則經歷史挑選(選擇偏誤),不構成投資建議。")

try:
    from patterns import candle_patterns as _candles
except Exception:                       # 缺檔照跑(cdlB 條件降級為永不成立並註記)
    _candles = None


def _jround(x):                          # JS Math.round 語意(正數 half-up)
    return math.floor(x + 0.5) if x >= 0 else -math.floor(-x + 0.5)


def cockpit_rows(bars):
    """webapp cockpitRows() 的逐行鏡像:回傳含 sc/rv/tds0/tdb0/t200 的 row 陣列。"""
    if not bars or len(bars) < 260:
        return None
    n = len(bars)
    C = [float(b[4]) for b in bars]
    V = [float(b[5] or 0) for b in bars]
    P = [0.0] * (n + 1)
    PV = [0.0] * (n + 1)
    for i in range(n):
        P[i + 1] = P[i] + C[i]
        PV[i + 1] = PV[i] + V[i]
    rv = [None] * n
    for i in range(20, n):
        rets = [math.log(C[j] / C[j - 1]) for j in range(i - 19, i + 1) if C[j - 1] > 0]
        if len(rets) < 2:
            continue
        m = sum(rets) / len(rets)
        va = sum((x - m) ** 2 for x in rets) / (len(rets) - 1)
        rv[i] = math.sqrt(va) * math.sqrt(252) * 100
    rvp = [None] * n
    for i in range(n):
        if rv[i] is None:
            continue
        c = t = 0
        for j in range(max(0, i - 504), i + 1):
            if rv[j] is not None:
                t += 1
                if rv[j] <= rv[i]:
                    c += 1
        if t >= 60:
            rvp[i] = _jround(100.0 * c / t)
    tds = [0] * n
    tdb = [0] * n
    for i in range(4, n):
        tds[i] = tds[i - 1] + 1 if C[i] > C[i - 4] else 0
        tdb[i] = tdb[i - 1] + 1 if C[i] < C[i - 4] else 0
    rows = []
    for i in range(LEAD, n):
        s50 = (P[i + 1] - P[i + 1 - 50]) / 50
        s100 = (P[i + 1] - P[i + 1 - 100]) / 100
        s200 = (P[i + 1] - P[i + 1 - 200]) / 200
        sc = ((1 if C[i] > s50 else -1) + (1 if C[i] > s100 else -1) + (1 if C[i] > s200 else -1)
              + (1 if C[i] > C[i - 63] else -1) + (1 if C[i] > C[i - 126] else -1)
              + (1 if C[i] > C[i - 252] else -1))
        rows.append({
            "d": bars[i][0], "o": float(bars[i][1]), "h": float(bars[i][2]),
            "l": float(bars[i][3]), "c": C[i], "v": V[i],
            "sc": _jround(100.0 * sc / 6), "rv": rvp[i],
            "t200": (P[i] - P[i - 199]) / 199,
            "tds0": tds[i], "tdb0": tdb[i],
        })
    return rows


def bt_flags(rows):
    """逐根算出所有原子條件(與前端 btFlags 逐項對應)。"""
    n = len(rows)
    tr, atr = [], []
    for i in range(n):
        pc = rows[i - 1]["c"] if i else rows[i]["o"]
        tr.append(max(rows[i]["h"] - rows[i]["l"],
                      abs(rows[i]["h"] - pc), abs(rows[i]["l"] - pc)))
        seg = tr[max(0, i - 19):i + 1]
        atr.append(sum(seg) / len(seg))
    cdl = {}
    if _candles:
        try:
            for p in _candles(rows):
                cdl[p["i"]] = cdl.get(p["i"], 0) + p["dir"]
        except Exception:
            pass
    F = []
    for i in range(n):
        r = rows[i]
        p = rows[i - 1] if i else None
        seg = rows[max(0, i - 19):i + 1]
        hi20 = max(x["c"] for x in seg)
        lo20 = min(x["c"] for x in seg)
        F.append({
            "td9b": r["tdb0"] in (9, 13),
            "td9s": r["tds0"] in (9, 13),
            "ctaUp": bool(p and r["sc"] >= 0 and p["sc"] < 0),
            "ctaDn": bool(p and r["sc"] < 0 and p["sc"] >= 0),
            "brk200": bool(p and r["c"] > r["t200"] and p["c"] <= p["t200"]),
            "lose200": bool(p and r["c"] < r["t200"] and p["c"] >= p["t200"]),
            "dc20": i >= 19 and r["c"] >= hi20,
            "dcl20": i >= 19 and r["c"] <= lo20,
            "rvLow": r["rv"] is not None and r["rv"] <= 25,
            "cdlB": cdl.get(i, 0) > 0,
            "cdlS": cdl.get(i, 0) < 0,
            "atr": atr[i],
        })
    return F


def backtest(rows, entry=None, exit_=None):
    """單一部位、不重疊、不加碼、不做空;進場 AND、出場 OR(先到先出)。"""
    if not rows or len(rows) < 60:
        return None
    entry = list(entry or DEFAULT_ENTRY)
    exit_ = list(exit_ or DEFAULT_EXIT)
    if not entry:
        return {"trades": [], "err": "未選任何進場條件"}
    if not exit_:
        return {"trades": [], "err": "未選任何出場條件"}
    F = bt_flags(rows)
    T, pos = [], None
    for i in range(1, len(rows)):
        if pos:
            why = None
            for k in exit_:
                if k == "maxHold":
                    if i - pos["i"] >= MAXHOLD:
                        why = "持有滿 %d 日" % MAXHOLD
                elif k == "stopATR":
                    if rows[i]["c"] <= pos["px"] - ATRK * pos["atr"]:
                        why = "停損 −%d×ATR20" % ATRK
                elif F[i].get(k):
                    why = LABEL.get(k, k)
                if why:
                    break
            if why:
                T.append({"i0": pos["i"], "i1": i, "d0": rows[pos["i"]]["d"], "d1": rows[i]["d"],
                          "px0": round(pos["px"], 4), "px1": round(rows[i]["c"], 4),
                          "hold": i - pos["i"],
                          "ret": round((rows[i]["c"] / pos["px"] - 1) * 100, 2),
                          "why": why})
                pos = None
            continue
        if all(F[i].get(k) for k in entry):
            pos = {"i": i, "px": rows[i]["c"], "atr": F[i]["atr"]}
    last = rows[-1]["c"]
    op = None
    if pos:
        op = {"i0": pos["i"], "d0": rows[pos["i"]]["d"], "px0": round(pos["px"], 4),
              "hold": len(rows) - 1 - pos["i"], "ret": round((last / pos["px"] - 1) * 100, 2)}
    n = len(T)
    st = {"n": n, "open": op, "first": T[0]["d0"] if n else None,
          "last": T[-1]["d1"] if n else None, "few": n < MIN_N}
    if n:
        w = [t for t in T if t["ret"] > 0]
        l = [t for t in T if t["ret"] <= 0]
        st["win"] = round(100.0 * len(w) / n, 1)
        st["avg"] = round(sum(t["ret"] for t in T) / n, 2)
        st["avgW"] = round(sum(t["ret"] for t in w) / len(w), 2) if w else 0
        st["avgL"] = round(sum(t["ret"] for t in l) / len(l), 2) if l else 0
        st["hold"] = round(sum(t["hold"] for t in T) / n, 1)
        st["best"] = max(t["ret"] for t in T)
        st["worst"] = min(t["ret"] for t in T)
        gp = sum(t["ret"] for t in w)
        gl = -sum(t["ret"] for t in l)
        st["pf"] = round(gp / gl, 2) if gl > 0 else None
        eq = pk = 1.0
        mdd = 0.0
        for t in T:
            eq *= (1 + t["ret"] / 100.0)
            pk = max(pk, eq)
            mdd = min(mdd, (eq / pk - 1) * 100)
        st["eq"] = round((eq - 1) * 100, 1)
        st["mdd"] = round(mdd, 1)
        st["bh"] = round((rows[T[-1]["i1"]]["c"] / rows[T[0]["i0"]]["c"] - 1) * 100, 1)
    return {"trades": T, "stat": st, "inK": entry, "outK": exit_,
            "disclaimer": DISCLAIMER, "cdl_available": bool(_candles)}


def backtest_for(bars, entry=None, exit_=None):
    """對外:gist kline 原始陣列 → 回測結果(歷史不足回 None,呼叫端 fail-open)。"""
    rows = cockpit_rows(bars)
    if not rows:
        return None
    return backtest(rows, entry, exit_)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="NVDA,MU,NOW,SNDK,WDC,SPY")
    ap.add_argument("--kline-dir", default="data")
    ap.add_argument("--entry", default=",".join(DEFAULT_ENTRY))
    ap.add_argument("--exit", dest="exit_", default=",".join(DEFAULT_EXIT))
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    entry = [s.strip() for s in a.entry.split(",") if s.strip()]
    exit_ = [s.strip() for s in a.exit_.split(",") if s.strip()]
    OUT = {}
    print("進場 AND:", " ＋ ".join(LABEL.get(k, k) for k in entry))
    print("出場 OR :", " ／ ".join(LABEL.get(k, k) for k in exit_))
    print("⚠", DISCLAIMER)
    for sym in [s.strip().upper() for s in a.symbols.split(",") if s.strip()]:
        p = os.path.join(a.kline_dir, "kline_%s.json" % sym)
        if not os.path.exists(p):
            print("%-6s 無 kline 檔" % sym)
            continue
        try:
            bars = json.load(open(p))["bars"]
        except Exception as e:
            print("%-6s 讀檔失敗 %s" % (sym, e))
            continue
        res = backtest_for(bars, entry, exit_)
        OUT[sym] = res
        if not res:
            print("%-6s 歷史不足" % sym)
            continue
        if res.get("err"):
            print("%-6s %s" % (sym, res["err"]))
            continue
        s = res["stat"]
        if not s["n"]:
            print("%-6s 無完整交易(條件過嚴)" % sym)
            continue
        print("%-6s n=%-3d 勝率%5.1f%% 期望%+6.2f%% 持有%5.1f日 MDD%6.1f%% PF=%-5s 複利%+8.1f%% 買持%+8.1f%%%s"
              % (sym, s["n"], s["win"], s["avg"], s["hold"], s["mdd"], s["pf"], s["eq"], s["bh"],
                 "  ⚠樣本不足" if s["few"] else ""))
    if a.json:
        json.dump(OUT, open(a.json, "w"), ensure_ascii=False)
        print("json ->", a.json)


if __name__ == "__main__":
    main()
