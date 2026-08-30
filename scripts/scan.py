#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全市場掃描引擎(P6;純 stdlib;2026-08-01)
對 gist 內全部 kline_*.json 批次跑既有引擎(auto_trendline / patterns / cta_trend)+ 價量統計,
產出 data/scan.json 供前端「掃描」卡片讀取(零 token、可排序可過濾)。

每檔輸出:
  {sym, d, px, chg1d, chg5d, chg20d, vol_pace,
   trendline_break:{side,broken_d,touches}?,    # 近 5 日內趨勢線被突破
   near_line:{name,px,dist_pct}?,               # 現價距最近的 CTA 煞車線 <2%
   pattern_hits:[{type,state,dir}],             # 古典型態(patterns.py)
   candle_hits:[{d,name,dir}],                  # 近 3 日蠟燭型態
   fib_zone:{lab,px,dist_pct}?,                 # 現價貼近某 Fib 水平 <1.5%
   hi52,lo52,pct_from_hi52,is_52w_high,is_52w_low,
   rv_pct, cta_score, cta_events:[...],         # cta_trend 六訊號分數 + RV 百分位
   squeeze, gex_bn,                             # 取自現行 signals.json(若有)
   score, why:[...]}

分數(透明加權;僅為排序用,非買賣建議):
  趨勢線突破 confirmed +3 / 型態 confirmed +3(forming +1)/ 52週新高低 +2 /
  近煞車線 <2% +2 / CTA 分數翻轉區(|score|<=33) +1 / RV≥80 +1 / 擠壓≥70 +1 /
  近 3 日蠟燭方向一致 +1 / Fib 關鍵位(38.2/50/61.8)<1.5% +1

用法:
  python3 scan.py --kline-dir data --out data/scan.json            # 讀本地 kline_*.json
  python3 scan.py --config config.json --symbols SPY,QQQ,... --out data/scan.json   # 自 gist 抓
  [--signals data/signals.json] [--limit 0]
失敗一律 fail-open:單檔例外只跳過該檔並記進 data_quality,不影響其餘。
"""
import json, os, re, time, math, argparse, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
DQ = []
def dq(src, ok, note=""): DQ.append({"source": src, "ok": bool(ok), "note": str(note)[:140]})
def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)

try:
    from backtest import cockpit_rows
except ImportError:
    cockpit_rows = None
try:
    from auto_trendline import detect as tl_detect, LEAD as TL_LEAD
except ImportError:
    tl_detect = None; TL_LEAD = 252
try:
    from patterns import zigzag, classic_patterns, candle_patterns
except ImportError:
    zigzag = classic_patterns = candle_patterns = None
try:
    from cta_trend import compute as cta_compute
except ImportError:
    cta_compute = None

WIN = 200          # 掃描視窗 = 駕駛艙預設
FIB_R = [(0.236, "23.6%"), (0.382, "38.2%"), (0.5, "50%"), (0.618, "61.8%"), (0.786, "78.6%")]
KEY_FIB = {"38.2%", "50%", "61.8%"}

def http_json(url, timeout=20, retries=2):
    last = None
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            last = e; time.sleep(0.4 * (a + 1))
    raise last

def load_bars(sym, kdir, gist_base):
    if kdir:
        p = os.path.join(kdir, "kline_%s.json" % sym)
        if os.path.exists(p):
            try: return json.load(open(p)).get("bars") or []
            except Exception: pass
    if gist_base:
        try: return (http_json(gist_base + "kline_%s.json" % sym) or {}).get("bars") or []
        except Exception: return []
    return []

def rows_of(bars, win=WIN):
    rows = bars[TL_LEAD:] if len(bars) > TL_LEAD else []
    if len(rows) < 50: return None
    seg = rows[-min(win, len(rows)):]
    return [{"d": b[0], "o": float(b[1]), "h": float(b[2]), "l": float(b[3]),
             "c": float(b[4]), "v": float(b[5] or 0)} for b in seg]

def brake_lines(bars):
    """CTA 煞車線現值(與前端 cockpitRows 同定義:前 N−1 日收盤均值 / K 日前收盤)"""
    C = [float(b[4]) for b in bars]
    n = len(C)
    out = {}
    if n >= 51:  out["短期50D"]  = sum(C[n-50:n-1]) / 49
    if n >= 101: out["中期100D"] = sum(C[n-100:n-1]) / 99
    if n >= 201: out["長期200D"] = sum(C[n-200:n-1]) / 199
    if n >= 64:  out["動能63D"]  = C[n-64]
    return out

# ================= 歷史同條件前瞻頻率(2026-08-02)=================
# ⚠ 這**不是預測、不是機率模型**,是「歷史頻率」:
#   對該股自己的全部歷史,逐根標記一組**當根收盤即可知**的機械條件(無前視),
#   統計「條件成立那些日子,H 日後收盤較高」的比例。今日成立哪些條件,就報那些條件的歷史比例。
# 合成方式(三道防過度自信):
#   ① 收縮:每個條件的比例先往該股「無條件基準」拉(p*n + base*K)/(n+K),樣本少者自動貼近基準;
#   ② 阻尼:條件彼此高度相關(CTA≥67 與 站上200D 幾乎同時發生),log-odds 只加權 0.5,
#      不做樸素貝氏直接相加(那會輕易算出 95% 這種假精確);
#   ③ 夾限:最終值鎖在 20%–80%,並同時輸出「基準」與「相對基準的增益(edge)」——
#      基準 65% 的股票報 60% 其實是**偏空**訊號,只看單一數字會誤讀。
# 方向一律以 edge(相對自身基準)判定,不以絕對值判定。樣本 <30 標樣本不足。
FWD_H = 20          # 前瞻交易日(≈1 個月)
FWD_K = 25          # 收縮強度
FWD_W = 0.5         # log-odds 阻尼
FWD_MIN_N = 30      # 樣本不足門檻
FWD_LO, FWD_HI = 0.20, 0.80
FWD_EDGE = 3.0      # 方向判定門檻(百分點)

FWD_LABEL = {
    "cta_up": "CTA檔位≥+67", "cta_dn": "CTA檔位≤−67",
    "above200": "站在200D上方", "below200": "跌在200D下方",
    "x200up": "當日升破200D", "x200dn": "當日跌破200D",
    "rv_hi": "RVPOS≥80(高波動)", "rv_lo": "RVPOS≤25(壓縮)",
    "td_buy": "TD買9/13完成", "td_sell": "TD賣9/13完成",
    "dc_hi": "創20日新高", "dc_lo": "創20日新低",
    "near_hi52": "距52週高≤3%", "near_lo52": "距52週低≤3%",
    "volspike": "爆量≥1.75×",
}

def _logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))

def fwd_flags(rows):
    """逐根算出各機械條件(只用 ≤ 該根的資訊)。回傳與 rows 等長的 dict 陣列。"""
    n = len(rows)
    out = []
    for i in range(n):
        r = rows[i]; p = rows[i-1] if i else None
        seg = rows[max(0, i-19):i+1]
        hi20 = max(x["c"] for x in seg); lo20 = min(x["c"] for x in seg)
        w52 = rows[max(0, i-251):i+1]
        hi52 = max(x["h"] for x in w52); lo52 = min(x["l"] for x in w52)
        vseg = rows[max(0, i-60):i]
        v60 = (sum(x["v"] for x in vseg) / len(vseg)) if vseg else 0
        t200 = r.get("t200"); pt200 = p.get("t200") if p else None
        out.append({
            "cta_up": r["sc"] >= 67, "cta_dn": r["sc"] <= -67,
            "above200": bool(t200 and r["c"] > t200), "below200": bool(t200 and r["c"] < t200),
            "x200up": bool(p and t200 and pt200 and r["c"] > t200 and p["c"] <= pt200),
            "x200dn": bool(p and t200 and pt200 and r["c"] < t200 and p["c"] >= pt200),
            "rv_hi": r["rv"] is not None and r["rv"] >= 80,
            "rv_lo": r["rv"] is not None and r["rv"] <= 25,
            "td_buy": r["tdb0"] in (9, 13), "td_sell": r["tds0"] in (9, 13),
            "dc_hi": i >= 19 and r["c"] >= hi20, "dc_lo": i >= 19 and r["c"] <= lo20,
            "near_hi52": bool(hi52) and (hi52 - r["c"]) / hi52 <= 0.03,
            "near_lo52": bool(lo52) and (r["c"] - lo52) / max(lo52, 1e-9) <= 0.03,
            "volspike": bool(v60) and r["v"] >= 1.75 * v60,
        })
    return out

def fwd_forecast(bars, h=FWD_H):
    """回傳今日成立條件的歷史 h 日後上漲頻率(含基準、增益、樣本數)。歷史不足回 None。"""
    if cockpit_rows is None: return None
    rows = cockpit_rows(bars)
    if not rows or len(rows) < h + 80: return None
    F = fwd_flags(rows)
    n = len(rows)
    fwd = [None] * n
    for i in range(n - h):
        c0 = rows[i]["c"]
        if c0 > 0: fwd[i] = rows[i + h]["c"] / c0 - 1.0
    usable = [i for i in range(n - h) if fwd[i] is not None]
    if len(usable) < 60: return None
    base_n = len(usable)
    base = sum(1 for i in usable if fwd[i] > 0) / base_n
    keys = list(FWD_LABEL.keys())
    stats = {}
    for k in keys:
        idx = [i for i in usable if F[i][k]]
        if not idx: continue
        wins = sum(1 for i in idx if fwd[i] > 0)
        stats[k] = {"n": len(idx), "p": wins / len(idx),
                    "avg": sum(fwd[i] for i in idx) / len(idx)}
    active = [k for k in keys if F[n - 1][k]]
    used = [k for k in active if k in stats and stats[k]["n"] >= 8]
    z = _logit(base)
    for k in used:
        c = stats[k]
        p_sh = (c["p"] * c["n"] + base * FWD_K) / (c["n"] + FWD_K)
        z += FWD_W * (_logit(p_sh) - _logit(base))
    p_up = 1.0 / (1.0 + math.exp(-z))
    p_up = min(max(p_up, FWD_LO), FWD_HI)
    edge = (p_up - base) * 100
    n_min = min((stats[k]["n"] for k in used), default=0)
    direction = "up" if edge >= FWD_EDGE else ("down" if edge <= -FWD_EDGE else "flat")
    return {
        "h": h, "p_up": round(p_up * 100, 1), "base": round(base * 100, 1),
        "edge": round(edge, 1), "dir": direction,
        "n_base": base_n, "n_min": n_min, "few": (n_min < FWD_MIN_N or not used),
        "conds": [{"k": k, "lab": FWD_LABEL[k], "n": stats[k]["n"],
                   "p": round(stats[k]["p"] * 100, 1),
                   "avg": round(stats[k]["avg"] * 100, 2)} for k in used],
        "skipped": [FWD_LABEL[k] for k in active if k not in used],
        "note": "歷史同條件頻率,非未來機率;不構成買賣建議",
    }

def scan_symbol(sym, bars, sig_node):
    R = rows_of(bars)
    if not R: return None
    N = len(R); px = R[-1]["c"]; why = []; score = 0.0
    rec = {"sym": sym, "d": R[-1]["d"], "px": round(px, 3)}
    def chg(k): return round(100 * (px / R[-1-k]["c"] - 1), 2) if N > k and R[-1-k]["c"] else None
    rec["chg1d"], rec["chg5d"], rec["chg20d"] = chg(1), chg(5), chg(20)
    v20 = sum(r["v"] for r in R[-21:-1]) / 20 if N > 21 else 0
    rec["vol_pace"] = round(R[-1]["v"] / v20, 2) if v20 else None

    # 52 週高低(以最後 252 根計)
    w52 = R[-252:] if N >= 252 else R
    hi52 = max(r["h"] for r in w52); lo52 = min(r["l"] for r in w52)
    rec["hi52"] = round(hi52, 3); rec["lo52"] = round(lo52, 3)
    rec["pct_from_hi52"] = round(100 * (px / hi52 - 1), 2) if hi52 else None
    rec["is_52w_high"] = bool(R[-1]["h"] >= hi52 - 1e-9)
    rec["is_52w_low"] = bool(R[-1]["l"] <= lo52 + 1e-9)
    if rec["is_52w_high"]: score += 2; why.append("52週新高")
    if rec["is_52w_low"]:  score += 2; why.append("52週新低")

    # 趨勢線(近 5 日內被突破 = 事件)
    if tl_detect:
        try:
            res = tl_detect(R)
            if res:
                brk = [L for L in res["lines"] if not L["active"] and L["brkIdx"] >= N - 5]
                if brk:
                    b0 = max(brk, key=lambda L: L["touches"])
                    rec["trendline_break"] = {"side": b0["side"], "broken_d": b0["broken_d"], "touches": b0["touches"]}
                    score += 3; why.append("趨勢線突破(%s·觸及%d)" % ("支撐" if b0["side"] == "sup" else "壓力", b0["touches"]))
                act = [L for L in res["lines"] if L["active"]]
                if act:
                    nr = min(act, key=lambda L: abs(L["yEnd"] / px - 1))
                    rec["near_trendline"] = {"side": nr["side"], "px": round(nr["yEnd"], 3),
                                             "dist_pct": round(100 * (nr["yEnd"] / px - 1), 2), "touches": nr["touches"]}
        except Exception as e: dq("trendline %s" % sym, False, e)

    # 型態 + 蠟燭
    if zigzag and classic_patterns:
        try:
            piv = zigzag(R); pats = classic_patterns(R, piv)
            rec["pattern_hits"] = [{"type": p["type"], "state": p["state"], "dir": p["dir"]} for p in pats]
            for p in pats:
                if p["state"] == "confirmed": score += 3; why.append("%s 已確認" % p["type"])
                else: score += 1; why.append("%s 形成中" % p["type"])
            cds = candle_patterns(R) if candle_patterns else []
            rec3 = [c for c in cds if c["i"] >= N - 3]
            rec["candle_hits"] = [{"d": c["d"], "name": c["name"], "dir": c["dir"]} for c in rec3][-4:]
            net = sum(c["dir"] for c in rec3)
            if abs(net) >= 2: score += 1; why.append("近3日蠟燭偏%s" % ("多" if net > 0 else "空"))
        except Exception as e: dq("patterns %s" % sym, False, e)

    # CTA 煞車線距離 + 六訊號分數 / RV 百分位
    try:
        bl = brake_lines(bars)
        if bl:
            nm, lv = min(bl.items(), key=lambda kv: abs(kv[1] / px - 1))
            dist = round(100 * (lv / px - 1), 2)
            rec["near_line"] = {"name": nm, "px": round(lv, 3), "dist_pct": dist}
            if abs(dist) < 2: score += 2; why.append("距%s煞車線 %.1f%%" % (nm, dist))
    except Exception as e: dq("brake %s" % sym, False, e)
    if cta_compute:
        try:
            crows, cev = cta_compute(sym, bars)
            if crows:
                cur = crows[-1]
                rec["cta_score"] = cur["score"]; rec["rv_pct"] = cur["rv_pct"]
                cutoff = R[-10]["d"] if N >= 10 else R[0]["d"]
                rec["cta_events"] = [e["ev"] for e in cev if e.get("d", "") >= cutoff][-3:]
                if abs(cur["score"]) <= 33: score += 1; why.append("CTA分數 %+d(易翻轉區)" % cur["score"])
                if (cur["rv_pct"] or 0) >= 80: score += 1; why.append("RV第%d百分位(縮部位壓力)" % cur["rv_pct"])
                if rec["cta_events"]: score += 1; why.append("近10日CTA事件:" + "、".join(rec["cta_events"]))
        except Exception as e: dq("cta %s" % sym, False, e)

    # Fib:現價貼近關鍵回撤位
    try:
        piv2 = zigzag(R) if zigzag else []
        hi = max((p for p in piv2 if p["t"] == "H"), key=lambda p: p["px"], default=None)
        lo = min((p for p in piv2 if p["t"] == "L"), key=lambda p: p["px"], default=None)
        if hi and lo and hi["px"] > lo["px"]:
            span = hi["px"] - lo["px"]; down = hi["i"] < lo["i"]
            best = None
            for r, lab in FIB_R:
                lvl = (hi["px"] - span * r) if down else (lo["px"] + span * r)
                dp = 100 * (lvl / px - 1)
                if best is None or abs(dp) < abs(best[2]): best = (lab, lvl, dp)
            if best and abs(best[2]) < 1.5:
                rec["fib_zone"] = {"lab": best[0], "px": round(best[1], 3), "dist_pct": round(best[2], 2)}
                if best[0] in KEY_FIB: score += 1; why.append("貼近 Fib %s" % best[0])
    except Exception as e: dq("fib %s" % sym, False, e)

    # 期權擠壓/GEX(取自現行 signals.json,若該檔有)
    if sig_node:
        g = sig_node.get("gamma") or {}
        if g.get("squeeze_score") is not None:
            rec["squeeze"] = g["squeeze_score"]; rec["gex_bn"] = g.get("gex_bn")
            if g["squeeze_score"] >= 70: score += 1; why.append("擠壓分數 %d" % g["squeeze_score"])

    # 歷史同條件前瞻頻率(fail-open:算不出來就不掛這個欄位)
    try:
        fw = fwd_forecast(bars)
        if fw: rec["fwd"] = fw
    except Exception as e:
        dq("fwd %s" % sym, False, e)

    rec["score"] = round(score, 1)
    rec["why"] = why[:8]
    return rec

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=None, help="逗號分隔;省略時自 --kline-dir 掃描全部 kline_*.json")
    ap.add_argument("--kline-dir", default=None)
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--signals", default="data/signals.json")
    ap.add_argument("--out", default="data/scan.json")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    gist_base = None
    if os.path.exists(a.config):
        try:
            mdu = (json.load(open(a.config)) or {}).get("market_data_url")
            if mdu: gist_base = mdu.rsplit("/", 1)[0] + "/"
        except Exception: pass
    syms = []
    if a.symbols:
        syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    elif a.kline_dir and os.path.isdir(a.kline_dir):
        for f in sorted(os.listdir(a.kline_dir)):
            m = re.fullmatch(r"kline_([A-Z][A-Z.\-]*)\.json", f)
            if m: syms.append(m.group(1))
    if a.limit: syms = syms[:a.limit]
    sigs = {}
    if a.signals and os.path.exists(a.signals):
        try: sigs = (json.load(open(a.signals)) or {}).get("symbols") or {}
        except Exception: pass

    t0 = time.time(); out = []
    for s in syms:
        try:
            bars = load_bars(s, a.kline_dir, gist_base)
            if not bars: dq("kline %s" % s, False, "無資料"); continue
            r = scan_symbol(s, bars, sigs.get(s))
            if r: out.append(r)
            else: dq("scan %s" % s, False, "歷史不足")
        except Exception as e:
            dq("scan %s" % s, False, e)
    out.sort(key=lambda r: -r["score"])
    res = {"updated_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
           "win": WIN, "n": len(out), "elapsed_s": round(time.time() - t0, 1),
           "note": "掃描=機械條件比對(趨勢線/型態/煞車線/52週/Fib/CTA/擠壓);score 僅供排序,非買賣建議",
           "rows": out, "data_quality": DQ}
    # 吸籌偵測(2026-08-03):⑦全單持續入場×價格低位 → accum 區塊(fail-open;詳 accum.py 檔頭)
    try:
        import accum
        res["accum"] = accum.build_accum(gist_base, kline_dir=a.kline_dir, log=log)
        dq("accum", True, "picks=%d" % len(res["accum"].get("picks") or []))
    except Exception as e:
        dq("accum", False, e)
        res["data_quality"] = DQ
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    json.dump(res, open(a.out, "w"), ensure_ascii=False, indent=1)
    log("scan -> %s  標的 %d 檔 / %.1fs" % (a.out, len(out), res["elapsed_s"]))
    for r in out[:12]:
        log("  %-6s score=%-5s %s" % (r["sym"], r["score"], " | ".join(r["why"][:3])))

if __name__ == "__main__":
    main()
