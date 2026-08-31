#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技術判斷模組(手冊 v0.2)— 確定性規則引擎(2026-08-31 上線;純 stdlib、零 token、fail-open)

對追蹤清單每檔股票,以「已收盤的完整日 K」計算手冊 v0.2 的進出場規則,產出 data/tech_judge.json
供駕駛艙「技術判斷」卡片渲染。所有判斷由固定公式算出,不做 AI 臨場判讀、不改門檻值。

規則摘要(完整定義=專案 claude/tech_judge_module.md;門檻值凍結,改版需重跑 MRVL 驗收):
  指標:SMA20/SD20(ddof=0)/布林±2σ、%B、帶寬、squeeze(帶寬≤近60日最低)、SMA50 regime、
       TD買賣計數(連續 C<C[-4]/C>C[-4],破則歸零,不設 9 上限)、
       flow20(⑦特大+大單淨流入跨日累加 20 日差,除以 20 日均量標準化)、
       五日斜率=近5個交易日⑦淨額(=現金池累計線5日變化;2026-08-31 使用者裁定之手冊定義)、
       吸籌/出貨背離、財報否決(未來 5 個交易日內財報)。
  進場三路徑:趨勢/循環/災後(逐項 pass/fail);共同否決:財報否決、增發/ATM 手動旗標。
  出貨證據:近3日TD賣≥9且當日%B>0.8;出貨背離。
資料源:gist kline_SYM.json(富途前復權日K;僅完整已收盤日)+ daily_flows.json(⑦ 250日)
       + signals.json(next_earnings;可被 data/tech_overrides.json 手動覆蓋)。
排除未收盤 bar:美東 16:00 前,任何日期=今日(ET)的 bar 一律剔除;⑦ 當日盤中累計值同樣剔除。
驗收:python3 tech_judge.py --selftest   (MRVL 2026-08-28 向量,通過才可部署)
用法:python3 scripts/tech_judge.py [--symbols A,B,...] [--out data/tech_judge.json]
      [--config config.json] [--kline-dir <dir>] [--asof YYYY-MM-DD]
⚠ 規則引擎輸出=機械條件描述,非投資建議;歷史條件不代表未來報酬。
"""
import json, os, sys, time, argparse, urllib.request
from datetime import datetime, timezone, timedelta

UA = {"User-Agent": "tech-judge"}
DQ = []
def dq(src, ok, note=""): DQ.append({"source": src, "ok": bool(ok), "note": str(note)[:120]})
def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)
def utcs(): return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

# 2026 美股休市(SPEC §2);半日(11-27、12-24)視為交易日
HOLIDAYS = {"2026-01-01","2026-01-19","2026-02-16","2026-04-03","2026-05-25","2026-06-19",
            "2026-07-03","2026-09-07","2026-11-26","2026-12-25",
            "2027-01-01","2027-01-18","2027-02-15"}

def _et_now():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.now(timezone.utc) - timedelta(hours=4)

def is_trading_day(d):  # d = date
    return d.weekday() < 5 and d.strftime("%Y-%m-%d") not in HOLIDAYS

def latest_completed_session():
    """最近一個『已收盤』的美股交易日(ET 16:00 後當日才算完成;半日保守亦以 16:00 計)"""
    et = _et_now(); d = et.date()
    if not (is_trading_day(d) and et.hour >= 16):
        d = d - timedelta(days=1)
        while not is_trading_day(d): d = d - timedelta(days=1)
    return d.strftime("%Y-%m-%d")

def next_trading_days(from_d, n):
    """from_d(YYYY-MM-DD)之後的未來 n 個交易日(不含 from_d)"""
    d = datetime.strptime(from_d, "%Y-%m-%d").date(); out = []
    while len(out) < n:
        d = d + timedelta(days=1)
        if is_trading_day(d): out.append(d.strftime("%Y-%m-%d"))
    return out

def http_json(url, timeout=25, retries=2):
    req = urllib.request.Request(url, headers=UA)
    last = None
    for a in range(retries):
        try:
            return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace"))
        except Exception as e:
            last = e; time.sleep(0.6*(a+1))
    raise last

def load_kline(sym, kdir, gist_base):
    if kdir:
        p = os.path.join(kdir, "kline_%s.json" % sym)
        if os.path.exists(p):
            try: return json.load(open(p))
            except Exception: pass
    if gist_base:
        try: return http_json(gist_base + "kline_%s.json?t=%d" % (sym, time.time()))
        except Exception: return None
    return None

def rnd(x, d=3): return None if x is None else round(float(x), d)

# ---------------- 核心計算(全部只用已收盤完整日K) ----------------
def compute_symbol(bars, flow_by_date, asof=None):
    """bars=[[d,o,h,l,c,v,tor],...](已依日期排序、僅完整日);flow_by_date={date:m($M)}
       回傳判讀 dict;bars<70 → {'insufficient':True,...}"""
    if asof:
        bars = [b for b in bars if b[0] <= asof]
    n = len(bars)
    if n < 70:
        return {"insufficient": True, "bars_n": n,
                "asof": bars[-1][0] if bars else None,
                "conclusion": "資料不足(日K %d 根 < 70),不判讀" % n}
    D = [b[0] for b in bars]; C = [b[4] for b in bars]; V = [b[5] for b in bars]
    i = n - 1
    # --- SMA/布林(母體標準差 ddof=0) ---
    def sma_at(vals, w, j):
        if j + 1 < w: return None
        return sum(vals[j-w+1:j+1]) / w
    sma20 = [sma_at(C, 20, j) for j in range(n)]
    sd20  = [None]*n
    for j in range(19, n):
        m = sma20[j]; seg = C[j-19:j+1]
        sd20[j] = (sum((x-m)**2 for x in seg)/20.0) ** 0.5
    upper = [None if sma20[j] is None else sma20[j] + 2*sd20[j] for j in range(n)]
    lower = [None if sma20[j] is None else sma20[j] - 2*sd20[j] for j in range(n)]
    pctb = [None]*n; bw = [None]*n
    for j in range(19, n):
        w = upper[j] - lower[j]
        pctb[j] = (C[j] - lower[j]) / w if w else None
        bw[j] = w / sma20[j] if sma20[j] else None
    # squeeze:當日帶寬 ≤ 近60日(含當日)最低帶寬
    def squeeze_at(j):
        if bw[j] is None: return None
        win = [x for x in bw[max(0, j-59):j+1] if x is not None]
        return bool(win) and bw[j] <= min(win)
    sqz = [squeeze_at(j) for j in range(n)]
    # --- SMA50 regime ---
    sma50 = [sma_at(C, 50, j) for j in range(n)]
    def regime_at(j):
        if sma50[j] is None or j < 10 or sma50[j-10] is None: return None
        return "trend" if (C[j] > sma50[j] and sma50[j] > sma50[j-10]) else "cycle"
    regime = regime_at(i)
    # --- TD 計數(連續滿足;破則歸零;無上限) ---
    tdb = [0]*n; tds = [0]*n
    for j in range(4, n):
        tdb[j] = tdb[j-1] + 1 if C[j] < C[j-4] else 0
        tds[j] = tds[j-1] + 1 if C[j] > C[j-4] else 0
    # --- ⑦ flow20(跨日累加 20 日差 ÷ 20日均量) ---
    m_ser = [flow_by_date.get(d_) for d_ in D]
    cum = [0.0]*n; run = 0.0
    for j in range(n):
        run += (m_ser[j] or 0.0); cum[j] = run
    def vol20_at(j): return sum(V[j-19:j+1]) / 20.0 if j >= 19 else None
    def f20raw_at(j): return (cum[j] - cum[j-20]) if j >= 20 else None
    def f20_at(j):
        r = f20raw_at(j); v = vol20_at(j)
        return (r*1e6) / v if (r is not None and v) else None   # m 單位=$M → 還原$再除股數
    f20_now, f20_raw = f20_at(i), f20raw_at(i)
    # 五日斜率=近5個交易日⑦淨額(現金池累計線的5日變化;$M)——2026-08-31 使用者裁定
    slope5 = (cum[i] - cum[i-5]) if i >= 5 else None
    cov20 = sum(1 for x in m_ser[i-19:i+1] if x is not None) if i >= 19 else 0
    flow_ok = cov20 >= 15   # 近20日 ⑦ 覆蓋 <15 天=資金流不判讀(誠實缺格)
    # --- 背離 ---
    chg20 = (C[i]/C[i-20] - 1) if i >= 20 else None
    max20 = max(C[i-19:i+1])
    accum_div = bool(flow_ok and f20_now is not None and f20_now > 0 and chg20 is not None and chg20 <= 0.02)
    dist_div  = bool(flow_ok and f20_now is not None and C[i] >= max20*0.99 and f20_now <= 0)
    # --- 視窗事件(供路徑) ---
    def win_any(pred, w):  # 近 w 個交易日(含當日)內任一日成立
        return any(pred(j) for j in range(max(0, i-w+1), i+1))
    trend_items = [
        {"k": "regime=趨勢", "ok": regime == "trend",
         "v": "trend" if regime == "trend" else ("cycle" if regime == "cycle" else "n/a")},
        {"k": "近10日 TD買計數≥6", "ok": win_any(lambda j: tdb[j] >= 6, 10), "v": "max=%d" % max(tdb[i-9:i+1])},
        {"k": "近10日 %B≤0.35或squeeze", "ok": win_any(lambda j: (pctb[j] is not None and pctb[j] <= 0.35) or sqz[j], 10),
         "v": "min%%B=%.2f" % min(x for x in pctb[i-9:i+1] if x is not None)},
        {"k": "近10日 flow20>0", "ok": bool(flow_ok) and win_any(lambda j: (f20_at(j) or 0) > 0 if f20_at(j) is not None else False, 10),
         "v": "now=%s" % (rnd(f20_now, 4) if f20_now is not None else "n/a")},
    ]
    cyc_today = {
        "pb": (pctb[i] is not None and pctb[i] <= 0.2) or bool(sqz[i]),
        "td9_5d": win_any(lambda j: tdb[j] >= 9, 5),
        "accum": accum_div,
    }
    cycle_items = [
        {"k": "regime=循環", "ok": regime == "cycle", "v": regime or "n/a"},
        {"k": "當日 %B≤0.2或squeeze", "ok": cyc_today["pb"], "v": "%%B=%.2f sq=%s" % (pctb[i], sqz[i])},
        {"k": "近5日 TD買計數曾達9", "ok": cyc_today["td9_5d"], "v": "max=%d" % max(tdb[i-4:i+1])},
        {"k": "當日吸籌背離", "ok": cyc_today["accum"],
         "v": "flow20=%s,20日漲跌=%.1f%%" % (rnd(f20_now, 4), (chg20 or 0)*100)},
    ]
    below_low_10d = win_any(lambda j: lower[j] is not None and C[j] < lower[j], 10)
    dis_items = [
        {"k": "近10日 TD買計數曾達9", "ok": win_any(lambda j: tdb[j] >= 9, 10), "v": "max=%d" % max(tdb[i-9:i+1])},
        {"k": "近10日 曾收盤跌破下軌", "ok": below_low_10d, "v": ""},
        {"k": "當日收盤回到下軌之上", "ok": C[i] > lower[i], "v": "C=%.2f 下軌=%.2f" % (C[i], lower[i])},
        {"k": "五日斜率>0(近5日⑦淨額)", "ok": bool(flow_ok and slope5 is not None and slope5 > 0),
         "v": "%s$M" % rnd(slope5, 1)},
    ]
    exit_a = {"k": "近3日TD賣曾達9 且 當日%B>0.8",
              "ok": win_any(lambda j: tds[j] >= 9, 3) and pctb[i] is not None and pctb[i] > 0.8,
              "v": "maxTD賣=%d,%%B=%.2f" % (max(tds[i-2:i+1]), pctb[i])}
    exit_b = {"k": "出貨背離(收盤≥近20日最高收盤×0.99 且 flow20≤0)", "ok": dist_div,
              "v": "C=%.2f,max20×0.99=%.2f,flow20=%s" % (C[i], max20*0.99, rnd(f20_now, 4))}
    return {
        "insufficient": False, "bars_n": n, "asof": D[i],
        "close": rnd(C[i]), "sma20": rnd(sma20[i]), "sd20": rnd(sd20[i]),
        "upper": rnd(upper[i]), "lower": rnd(lower[i]),
        "sma50": rnd(sma50[i]), "sma50_10ago": rnd(sma50[i-10]),
        "pctb": rnd(pctb[i], 4), "bw": rnd(bw[i], 4), "squeeze": bool(sqz[i]),
        "bw_min60": rnd(min(x for x in bw[max(0, i-59):i+1] if x is not None), 4),
        "regime": regime, "td_buy": tdb[i], "td_sell": tds[i],
        "flow": {"cov20": cov20, "ok": flow_ok, "flow20_musd": rnd(f20_raw, 1),
                 "flow20_norm": rnd(f20_now, 4), "slope5_musd": rnd(slope5, 1),
                 "vol20": rnd(vol20_at(i), 0)},
        "div": {"accum": accum_div, "dist": dist_div, "chg20_pct": rnd((chg20 or 0)*100, 2),
                "max20_close": rnd(max20)},
        "paths": {"trend": trend_items, "cycle": cycle_items, "disaster": dis_items},
        "exit": {"a": exit_a, "b": exit_b},
        "_dbg": {"tdb_tail": tdb[-15:], "tds_tail": tds[-15:], "dates_tail": D[-15:],
                 "closes_tail": [rnd(x) for x in C[-25:]]},
    }

def apply_verdicts(node, earnings_date, atm_flag, latest_sess):
    """加上財報否決/ATM 否決、路徑總結、出貨燈、資料新鮮度與一句話結論"""
    if node.get("insufficient"):
        node["stale"] = bool(node.get("asof") and node["asof"] < latest_sess)
        return node
    asof = node["asof"]
    # 財報否決:未來 5 個交易日內有財報(以 asof 為基準)
    e_veto = False; e_days = None
    if earnings_date:
        nxt5 = next_trading_days(asof, 5)
        e_veto = earnings_date in nxt5 or (asof < earnings_date <= nxt5[-1])
        try:
            d0 = datetime.strptime(asof, "%Y-%m-%d").date()
            d1 = datetime.strptime(earnings_date, "%Y-%m-%d").date()
            e_days = (d1 - d0).days
        except Exception: pass
    veto = []
    if e_veto: veto.append("財報否決(未來5交易日內:%s)" % earnings_date)
    if atm_flag: veto.append("增發/ATM 執行中(手動旗標)")
    node["earnings"] = {"date": earnings_date, "days_cal": e_days, "veto": e_veto}
    node["atm_flag"] = bool(atm_flag)
    node["vetoed"] = bool(veto); node["veto_reason"] = ";".join(veto)
    def all_ok(items): return all(x["ok"] for x in items)
    p = node["paths"]
    node["path_pass"] = {k: (all_ok(p[k]) and not veto) for k in ("trend", "cycle", "disaster")}
    node["path_raw_pass"] = {k: all_ok(p[k]) for k in ("trend", "cycle", "disaster")}
    node["exit_on"] = bool(node["exit"]["a"]["ok"] or node["exit"]["b"]["ok"])
    node["stale"] = asof < latest_sess
    # 一句話結論(純規則模板)
    reg_zh = {"trend": "趨勢", "cycle": "循環", None: "—"}[node["regime"]]
    hits = [k for k, v in node["path_pass"].items() if v]
    zh = {"trend": "趨勢路徑", "cycle": "循環路徑", "disaster": "災後路徑"}
    parts = ["%s regime" % reg_zh]
    if veto:
        parts.append("進場全數被否決(%s)" % node["veto_reason"])
    elif hits:
        parts.append("+".join(zh[k] for k in hits) + " 成立")
    else:
        parts.append("三條路徑皆不成立,空手觀望")
    if node["exit_on"]:
        parts.append("⚠ 出場警戒燈亮")
    if not hits and not veto and node["regime"] == "cycle" and node.get("lower"):
        parts.append("災後路徑觀察價位=下軌 %.0f 附近" % node["lower"])
    node["conclusion"] = ";".join(parts)
    return node

# ---------------- 驗收(MRVL 2026-08-28) ----------------
def selftest(kd_bars, flow_by_date):
    node = compute_symbol(kd_bars, flow_by_date, asof="2026-08-28")
    node = apply_verdicts(node, None, False, "2026-08-28")
    exp = {"close": (216.62, 0.005), "sma20": (224.2, 0.5), "sma50": (228.6, 0.5),
           "pctb": (0.37, 0.02), "bw": (0.255, 0.01)}
    rows = []; ok_all = True
    for k, (v, tol) in exp.items():
        got = node[k]; ok = got is not None and abs(got - v) <= tol
        ok_all &= ok; rows.append((k, v, got, ok))
    checks = [
        ("squeeze=False", node["squeeze"] is False),
        ("TD買=1", node["td_buy"] == 1), ("TD賣=0", node["td_sell"] == 0),
        ("regime=循環", node["regime"] == "cycle"),
        ("三路徑全fail", not any(node["path_raw_pass"].values())),
        ("出貨證據不亮", not node["exit_on"]),
        ("flow20<0", (node["flow"]["flow20_norm"] or 0) < 0),
        ("五日斜率<0", (node["flow"]["slope5_musd"] or 0) < 0),
    ]
    print("== MRVL 2026-08-28 驗收 ==")
    for k, v, got, ok in rows:
        print("  %-6s 預期≈%-8s 算得=%-10s %s" % (k, v, got, "✓" if ok else "✗"))
    for k, ok in checks:
        ok_all &= ok; print("  %-28s %s" % (k, "✓" if ok else "✗"))
    print("  paths raw:", node["path_raw_pass"], "| exit:", node["exit"]["a"]["ok"], node["exit"]["b"]["ok"])
    print("  flow20_musd=%s norm=%s slope5=%s$M cov20=%d" % (
        node["flow"]["flow20_musd"], node["flow"]["flow20_norm"], node["flow"]["slope5_musd"], node["flow"]["cov20"]))
    print("== 對照用逐日(近15日) ==")
    dbg = node["_dbg"]
    for d_, tb, ts_ in zip(dbg["dates_tail"], dbg["tdb_tail"], dbg["tds_tail"]):
        print("   %s TD買=%d TD賣=%d" % (d_, tb, ts_))
    print("  近25收盤:", dbg["closes_tail"])
    print("  SD20=%s 上軌=%s 下軌=%s bw_min60=%s" % (node["sd20"], node["upper"], node["lower"], node["bw_min60"]))
    print("驗收結果:", "全部通過 ✅" if ok_all else "未通過 ❌(勿調公式湊答案;逐日數據見上)")
    return 0 if ok_all else 1

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="MU,SNDK,WDC,MRVL,LITE,COHR,AAOI,NVDA,AVGO,SMH,SOXX,SPY,QQQ")
    ap.add_argument("--out", default="data/tech_judge.json")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--kline-dir", default=None)
    ap.add_argument("--signals", default="data/signals.json")
    ap.add_argument("--overrides", default="data/tech_overrides.json")
    ap.add_argument("--asof", default=None, help="只用 ≤ 此日期的日K(驗收/重放用)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    cfg = {}
    if os.path.exists(a.config):
        try: cfg = json.load(open(a.config))
        except Exception: pass
    gist_base = None
    mdu = cfg.get("market_data_url")
    if mdu: gist_base = mdu.rsplit("/", 1)[0] + "/"
    # ⑦ 日頻(gist daily_flows.json 250日;m=特大+大單淨流入 $M)
    flows = {}
    try:
        dfj = http_json(gist_base + "daily_flows.json?t=%d" % time.time()) if gist_base else {}
        flows = dfj.get("daily_flows") or {}
        dq("daily_flows", bool(flows), "days=%d" % len(flows))
    except Exception as e:
        dq("daily_flows", False, e)
    latest_sess = latest_completed_session()
    et = _et_now(); today_et = et.strftime("%Y-%m-%d")
    intraday = today_et > latest_sess   # 今日尚未收盤 → 今日的 bar/⑦ 一律排除
    def flow_map(sym):
        out = {}
        for d_, day in flows.items():
            if intraday and d_ >= today_et: continue   # 排除未收盤當日累計
            e = day.get(sym)
            if e and e.get("m") is not None: out[d_] = float(e["m"])
        return out
    # 財報日:signals.json next_earnings;data/tech_overrides.json 手動覆蓋(earnings/atm)
    sig = {}
    try: sig = (json.load(open(a.signals)) or {}).get("symbols", {}) if os.path.exists(a.signals) else {}
    except Exception: pass
    ovr = {}
    try: ovr = json.load(open(a.overrides)) if os.path.exists(a.overrides) else {}
    except Exception: pass
    syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    if a.selftest:
        raw = load_kline("MRVL", a.kline_dir, gist_base)
        if not raw: print("selftest:抓不到 MRVL 日K"); sys.exit(2)
        bars = [b for b in raw["bars"] if not (intraday and b[0] >= today_et)]
        sys.exit(selftest(bars, flow_map("MRVL")))
    out = {"updated_utc": utcs(), "spec": "手冊 v0.2 技術判斷(確定性規則引擎)",
           "latest_session": latest_sess, "symbols": {},
           "disclaimer": "規則引擎輸出=機械條件描述,非投資建議;財報日/增發旗標可能缺漏,以公司公告為準。"}
    for s in syms:
        try:
            raw = load_kline(s, a.kline_dir, gist_base)
            if not raw or not raw.get("bars"):
                out["symbols"][s] = {"insufficient": True, "bars_n": 0, "asof": None, "stale": True,
                                     "conclusion": "無日K資料,不判讀"}
                dq("kline %s" % s, False, "無資料"); continue
            bars = [b for b in raw["bars"] if not (intraday and b[0] >= today_et)]
            node = compute_symbol(bars, flow_map(s), asof=a.asof)
            o = ovr.get(s) or {}
            e_date = o.get("earnings") or (sig.get(s) or {}).get("next_earnings")
            node = apply_verdicts(node, e_date, bool(o.get("atm")), a.asof or latest_sess)
            node["earnings_src"] = "override" if o.get("earnings") else ((sig.get(s) or {}).get("earnings_src") or ("無" if not e_date else "signals"))
            node.pop("_dbg", None)
            out["symbols"][s] = node
            dq("judge %s" % s, True, node.get("conclusion", ""))
        except Exception as e:
            out["symbols"][s] = {"insufficient": True, "bars_n": 0, "asof": None, "stale": True,
                                 "conclusion": "計算失敗:%s" % str(e)[:60]}
            dq("judge %s" % s, False, e)
    out["data_quality"] = DQ
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    json.dump(out, open(a.out, "w"), ensure_ascii=False, indent=1)
    log("tech_judge -> %s (%d 檔; latest_session=%s)" % (a.out, len(syms), latest_sess))
    for s in syms:
        n = out["symbols"][s]
        log("%-5s %s" % (s, n.get("conclusion", "")))

if __name__ == "__main__":
    main()
