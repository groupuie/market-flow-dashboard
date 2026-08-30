#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自動趨勢線偵測 — 引擎鏡像(純 stdlib;2026-08-01)
TrendSpider 式自動畫線:pivot 滑窗極值 → 兩兩成線 O(pivot²) → 沿線觸及計數
(容忍 max(0.6%, 0.25×ATR14/價)) → K棒實體穿越>1%=突破(線止於突破日)
→ 評分(觸及+近期權重−誤差−距離)取每側前 2 + 水平 S/R 群聚(0.5%)。
與 webapp/index.html 的 autoTrendlines() 同參數同演算法(一致性驗證:同 bars 端點
價差 <0.1%、觸及數相同)。前端為主(全標的自算)、本模組為輔(排程場次 Claude 判讀引用)。

視窗鏡像 cockpit 預設:rows 自第 252 根起(cockpitRows 前置需求),R=rows[-200:]。
輸出 schema(寫入 computed_tech.trendlines):
  [{x1_d,y1,x2_d,y2,side:"sup"|"res",kind:"line"|"hline",touches,err_pct,score,active,broken_d?}]
用法(獨立測試):python3 auto_trendline.py --kline-dir data --symbols NVDA,MU [--win 200] [--json out.json]
"""
import json, os, math, argparse

TL_WIN = 200      # 鏡像駕駛艙預設視窗
LEAD   = 252      # cockpitRows 前置根數(rows 自第 252 根起)

def _jround(x):   # JS Math.round 語意(正數 half-up;Python round 是 half-even)
    return int(math.floor(x + 0.5))

def detect(R):
    """R=[{d,o,h,l,c},...](=前端渲染視窗切片)。N<50 回 None(不啟用)。"""
    N = len(R)
    if N < 50:
        return None
    W = max(3, min(7, _jround(N / 40)))            # pivot 滑窗半徑
    BRK = 0.01                                     # 實體穿越 >1% = 突破
    MINSPAN = max(5, W)                            # 兩 pivot 最小間距
    MAXPER = 2                                     # 每側最多 2 條
    STALE = max(12, _jround(N * 0.12))             # 突破陳舊門檻(基準)
    DISTCAP = 0.18                                 # active 線端點距現價 >18% 不顯示
    atr = 0.0; cnt = 0
    for a in range(max(1, N - 14), N):
        tr = max(R[a]["h"] - R[a]["l"], abs(R[a]["h"] - R[a-1]["c"]), abs(R[a]["l"] - R[a-1]["c"]))
        atr += tr; cnt += 1
    atr = atr / cnt if cnt else 0.0
    px = R[N-1]["c"]
    TOL = max(0.006, 0.25 * atr / max(px, 1e-9))   # 觸及容忍 max(0.6%, 0.25×ATR14/價)
    pivH = []; pivL = []
    for i in range(W, N - W):
        hi = True; lo = True
        for k in range(i - W, i + W + 1):
            if k == i: continue
            if R[k]["h"] > R[i]["h"]: hi = False
            if R[k]["l"] < R[i]["l"]: lo = False
            if not hi and not lo: break
        if hi: pivH.append(i)
        if lo: pivL.append(i)

    def scan(i, y1, slope, side):   # 沿線觸及計數(連續併一次)+ 實體穿越判突破;tIdx=各觸及群首根索引
        touches = 0; err_sum = 0.0; last_touch = -1; run = False; brk_idx = -1; t_idx = []
        for k in range(i, N):
            ly = y1 + slope * (k - i)
            if ly <= 0: return None
            body = min(R[k]["o"], R[k]["c"]) if side == "sup" else max(R[k]["o"], R[k]["c"])
            d_brk = (ly - body) / ly if side == "sup" else (body - ly) / ly
            if d_brk > BRK:
                brk_idx = k; break
            pv = R[k]["l"] if side == "sup" else R[k]["h"]
            d = abs(pv - ly) / ly
            if d <= TOL:
                if not run:
                    touches += 1; err_sum += d; last_touch = k; t_idx.append(k)
                elif k > last_touch:
                    last_touch = k
                run = True
            else:
                run = False
        return {"touches": touches, "err": (err_sum / touches) if touches else 1.0,
                "lastTouch": last_touch, "brkIdx": brk_idx, "tIdx": t_idx}

    def mk_line(kind, side, i, j, y1, y2):
        slope = (y2 - y1) / (j - i) if j > i else 0.0
        s = scan(i, y1, slope, side)
        if not s or s["touches"] < 3: return None
        active = s["brkIdx"] < 0
        stale_allow = min(STALE * (1 + min(1, (s["touches"] - 3) / 4)), 30)   # 大結構多留;上限 ~6 週
        if not active and (N - 1 - s["brkIdx"]) > stale_allow: return None
        end_idx = N - 1 if active else s["brkIdx"]
        y_end = y1 + slope * (end_idx - i)
        dist = abs(y_end / px - 1)
        if active and dist > DISTCAP: return None              # 離戰場太遠的延伸線=雜訊
        score = (s["touches"] + 2.0 * (s["lastTouch"] / (N - 1)) + (0.6 if active else 0)
                 - (s["err"] / TOL) - (1.2 * min(1, dist / DISTCAP) if active else 0))
        return {"kind": kind, "side": side, "i": i, "j": j, "y1": float(y1), "slope": slope,
                "endIdx": end_idx, "yEnd": float(y_end), "touches": s["touches"],
                "err_pct": round(s["err"] * 100, 3), "score": round(score, 3),
                "active": active, "brkIdx": s["brkIdx"], "x1_d": R[i]["d"], "x2_d": R[end_idx]["d"],
                "y2": float(y_end), "broken_d": None if active else R[s["brkIdx"]]["d"],
                "lastTouch": s["lastTouch"], "tIdx": s["tIdx"]}

    def slants(pivs, side):   # pivot 兩兩成線 O(pivot²)
        out = []
        for a2 in range(len(pivs)):
            for b2 in range(a2 + 1, len(pivs)):
                i2, j2 = pivs[a2], pivs[b2]
                if j2 - i2 < MINSPAN: continue
                y1 = R[i2]["l"] if side == "sup" else R[i2]["h"]
                y2 = R[j2]["l"] if side == "sup" else R[j2]["h"]
                L = mk_line("line", side, i2, j2, y1, y2)
                if L: out.append(L)
        return out

    def hlines(pivs, side):   # 水平 S/R:pivot 價位群聚(容忍 0.5%)
        pts = sorted([{"i": i2, "p": (R[i2]["l"] if side == "sup" else R[i2]["h"])} for i2 in pivs],
                     key=lambda x: x["p"])
        out = []; cur = []
        def flush():
            if len(cur) >= 3:
                mean = sum(x["p"] for x in cur) / len(cur)
                idxs = sorted(x["i"] for x in cur)
                L = mk_line("hline", side, idxs[0], idxs[-1], mean, mean)
                if L: out.append(L)
        for t in range(len(pts)):
            if not cur:
                cur.append(pts[t]); continue
            mean = sum(x["p"] for x in cur) / len(cur)
            if abs(pts[t]["p"] - mean) / mean <= 0.005:
                cur.append(pts[t])
            else:
                flush(); cur = [pts[t]]
        flush()
        return out

    def similar(A, B):   # 同走廊去重(1.5×TOL×3 取樣點);同起點同一次突破事件亦視為同線
        if A["side"] != B["side"]: return False
        if A["i"] == B["i"] and not A["active"] and not B["active"] and abs(A["brkIdx"] - B["brkIdx"]) <= 6:
            return True
        s = max(A["i"], B["i"]); e = min(A["endIdx"], B["endIdx"])
        if e <= s: return False
        for k in (s, (s + e) >> 1, e):
            ya = A["y1"] + A["slope"] * (k - A["i"])
            yb = B["y1"] + B["slope"] * (k - B["i"])
            if abs(ya - yb) / max(ya, 1e-9) > 1.5 * TOL: return False
        return True

    def pick(cands):
        cands = sorted(cands, key=lambda x: -x["score"])   # 穩定排序,平分保生成順序(同 JS)
        out = []
        for c in cands:
            if len(out) >= MAXPER: break
            if all(not similar(c, u) for u in out):
                out.append(c)
        return out

    supL = pick(slants(pivL, "sup")); resL = pick(slants(pivH, "res"))
    supH = pick(hlines(pivL, "sup")); resH = pick(hlines(pivH, "res"))
    def drop_dup(hs, ls):   # 水平線與已選斜線同走廊 → 略
        return [h for h in hs if all(not similar(h, u) for u in ls)]
    supH = drop_dup(supH, supL); resH = drop_dup(resH, resL)
    return {"lines": supL + resL + supH + resH,
            "meta": {"w": W, "tol": TOL, "px": px}}

def trendlines_for(bars, win=TL_WIN):
    """bars=gist kline 原始陣列 [[d,o,h,l,c,v,tor],...] → computed_tech.trendlines 條目。
    鏡像 cockpit 視窗;歷史不足(rows<50)回 None(呼叫端只缺 trendlines 欄,fail-open)。"""
    rows = bars[LEAD:] if len(bars) > LEAD else []
    if len(rows) < 50: return None
    seg = rows[-min(win, len(rows)):]
    R = [{"d": b[0], "o": float(b[1]), "h": float(b[2]), "l": float(b[3]), "c": float(b[4])} for b in seg]
    res = detect(R)
    if not res: return None
    out = []
    for L in res["lines"]:
        e = {"x1_d": L["x1_d"], "y1": round(L["y1"], 3), "x2_d": L["x2_d"], "y2": round(L["y2"], 3),
             "side": L["side"], "kind": L["kind"], "touches": L["touches"], "err_pct": L["err_pct"],
             "score": L["score"], "active": L["active"]}
        if not L["active"]: e["broken_d"] = L["broken_d"]
        out.append(e)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="NVDA,MU,SNDK,WDC,SMH,SPY")
    ap.add_argument("--kline-dir", default="data")
    ap.add_argument("--win", type=int, default=TL_WIN)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    OUT = {}
    for sym in [s.strip().upper() for s in a.symbols.split(",") if s.strip()]:
        p = os.path.join(a.kline_dir, f"kline_{sym}.json")
        if not os.path.exists(p):
            print(f"{sym}: 無 kline 檔"); continue
        bars = json.load(open(p))["bars"]
        tl = trendlines_for(bars, a.win)
        OUT[sym] = tl
        print(f"\n== {sym} win={a.win}(bars={len(bars)})")
        for L in (tl or []):
            print(f"  {L['side']} {L['kind']} {L['x1_d']}→{L['x2_d']} y:{L['y1']}→{L['y2']} "
                  f"觸及{L['touches']} err{L['err_pct']}% score{L['score']} "
                  f"{'active' if L['active'] else '✂'+L.get('broken_d','')}")
        if tl is None: print("  (歷史不足,不啟用)")
    if a.json:
        json.dump(OUT, open(a.json, "w"), ensure_ascii=False)
        print("\njson ->", a.json)

if __name__ == "__main__":
    main()
