#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
個股籌碼 Parts 2/3 原型驗證器（在【你的 Mac】執行,連本機 OpenD 127.0.0.1:11111）
只讀行情、永不下單、永不 unlock_trade。

目的:在「不額外花錢、只用現有 Futu API」的前提下,量測三條資料源能否支撐
      「大戶/散戶籌碼均價 + 大戶籌碼數量 + 所有籌碼數量(流通股)」,並對應現金池系統:

  ① get_market_snapshot        → 流通股/發行股本(所有籌碼數量)          —— 無需訂閱,便宜
  ② get_shareholders_overview  → 機構/內部人/個人 持股占比(大戶結構)     —— F10,季頻
     get_shareholders_institutional → 機構持股數量/比例(大戶籌碼數量·13F)
  ③ get_capital_distribution   → ⑦ 大單淨流(現有現金池,交叉比對)
  ④ get_rt_ticker(num=1000)    → 逐筆成交輪詢覆蓋度(大戶/散戶均價 VWAP 可行性)
       盤中:相隔 ~65s 連抓兩次 → 量測 1000 筆的時間跨度、重疊率、成交量分桶 VWAP、主動買賣拆分
       目的:判斷「60s 輪詢」是否來得及(1000 筆窗口 > 60s?),以及大單 VWAP 是否算得出來、漏多少

輸出:ticker_probe.json 推到同一個 gist(雲端可直接讀),並在終端印出判讀。
用法:python probe_ticker.py --config config.json
"""
import json, os, sys, time, argparse, urllib.request
from datetime import datetime, timezone

def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)

# ---- 代表性標的:一支超熱 megacap、一支超熱 ETF、一支中量、一支冷門 ----
# (熱門股逐筆最密→最容易漏;冷門股→輪詢綽綽有餘。涵蓋兩端才知門檻在哪)
PROBE_SYMS = ["US.NVDA", "US.SPY", "US.MU", "US.AAOI"]
# 成交金額分桶(USD)—— 看單筆成交的大小分布,決定「大單」門檻該設多少才有意義
TURN_BUCKETS = [0, 1e4, 5e4, 2e5, 5e5, 1e6, float("inf")]
BUCKET_LBL   = ["<1萬", "1-5萬", "5-20萬", "20-50萬", "50-100萬", "≥100萬"]

def market_session():
    """粗略 US 時段(美東):rth / pre / after / closed。只為標註,不精算假日。"""
    try:
        from zoneinfo import ZoneInfo
        n = datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        n = datetime.utcnow()  # 退化:當 UTC 處理(僅標註用)
    if n.weekday() >= 5: return "closed"
    hm = n.hour * 60 + n.minute
    if 9*60+30 <= hm < 16*60: return "rth"
    if 4*60 <= hm < 9*60+30:  return "pre"
    if 16*60 <= hm < 20*60:   return "after"
    return "closed"

def _f(x):
    try:
        if x is None: return None
        v = float(x)
        return None if (v != v) else v   # NaN → None
    except Exception:
        return None

def rows_of(df):
    """DataFrame → list[dict],容錯(有些欄位是 numpy 型別)。"""
    if df is None: return []
    try:
        n = len(df)
    except Exception:
        return []
    out = []
    for i in range(n):
        r = df.iloc[i] if hasattr(df, "iloc") else df[i]
        d = {}
        for c in (list(df.columns) if hasattr(df, "columns") else r.keys()):
            v = r.get(c) if hasattr(r, "get") else r[c]
            try:
                json.dumps(v)  # 能序列化就留原值
                d[c] = v
            except Exception:
                d[c] = str(v)
        out.append(d)
    return out

def tick_key(t):
    """逐筆去重鍵:優先 sequence,否則 (time, price, volume, direction)。"""
    seq = t.get("sequence")
    if seq not in (None, "", 0):
        return ("seq", seq)
    return ("tpv", t.get("time"), t.get("price"), t.get("volume"), t.get("ticker_direction"))

def analyze_ticks(ticks, thr):
    """對一批逐筆(已去重)做:分桶 VWAP、主動買賣拆分、大單(≥thr 金額)彙總。"""
    buckets = [{"n": 0, "vol": 0, "turn": 0.0} for _ in BUCKET_LBL]
    big = {"n": 0, "vol": 0, "turn": 0.0, "buy_vol": 0, "sell_vol": 0, "buy_turn": 0.0, "sell_turn": 0.0}
    small = {"n": 0, "vol": 0, "turn": 0.0, "buy_vol": 0, "sell_vol": 0}
    allsum = {"n": 0, "vol": 0, "turn": 0.0}
    for t in ticks:
        p = _f(t.get("price")); v = _f(t.get("volume"))
        if p is None or v is None: continue
        turn = _f(t.get("turnover"))
        if turn is None or turn == 0: turn = p * v
        d = str(t.get("ticker_direction") or "").upper()
        allsum["n"] += 1; allsum["vol"] += v; allsum["turn"] += turn
        # 分桶
        for bi in range(len(BUCKET_LBL)):
            if TURN_BUCKETS[bi] <= turn < TURN_BUCKETS[bi+1]:
                buckets[bi]["n"] += 1; buckets[bi]["vol"] += v; buckets[bi]["turn"] += turn
                break
        # 大 / 小(金額門檻)
        tgt = big if turn >= thr else small
        tgt["n"] += 1; tgt["vol"] += v; tgt["turn"] += turn
        if "BUY" in d:
            tgt["buy_vol"] += v
            if tgt is big: big["buy_turn"] += turn
        elif "SELL" in d:
            tgt["sell_vol"] += v
            if tgt is big: big["sell_turn"] += turn
    def vwap(s): return round(s["turn"]/s["vol"], 4) if s.get("vol") else None
    return {
        "thr_usd": thr,
        "all":  {**allsum, "vwap": vwap(allsum)},
        "big":  {**big,   "vwap": vwap(big),
                 "net_vol": big["buy_vol"] - big["sell_vol"],
                 "buy_vwap": round(big["buy_turn"]/big["buy_vol"],4) if big["buy_vol"] else None,
                 "sell_vwap": round(big["sell_turn"]/big["sell_vol"],4) if big["sell_vol"] else None},
        "small": {**small, "vwap": vwap(small), "net_vol": small["buy_vol"] - small["sell_vol"]},
        "buckets": [dict(lbl=BUCKET_LBL[i], **buckets[i],
                         vwap=(round(buckets[i]["turn"]/buckets[i]["vol"],4) if buckets[i]["vol"] else None))
                    for i in range(len(BUCKET_LBL))],
    }

def probe_ticker(q, code, sess):
    """訂閱 TICKER → 抓一次(盤中再抓第二次量測覆蓋度)。回傳量測 dict。"""
    from futu import SubType, RET_OK
    out = {"code": code, "polls": []}
    ret, msg = q.subscribe([code], [SubType.TICKER])
    if ret != RET_OK:
        out["error"] = f"subscribe: {msg}"; return out
    time.sleep(1.2)  # 給推送鋪底
    def one_poll(tag):
        ret, d = q.get_rt_ticker(code, num=1000)
        if ret != RET_OK:
            return {"tag": tag, "error": str(d)[:120]}
        recs = rows_of(d)
        # 正規化欄位名(price/volume/turnover/ticker_direction/sequence/time)
        norm = []
        for r in recs:
            norm.append({
                "time": r.get("time"),
                "price": _f(r.get("price")),
                "volume": _f(r.get("volume")),
                "turnover": _f(r.get("turnover")),
                "ticker_direction": r.get("ticker_direction"),
                "sequence": r.get("sequence"),
                "type": r.get("type"),
            })
        times = [r["time"] for r in norm if r.get("time")]
        seqs = [r["sequence"] for r in norm if r.get("sequence") not in (None, "", 0)]
        return {"tag": tag, "n": len(norm), "cols": (list(d.columns) if hasattr(d,"columns") else []),
                "t_first": (min(times) if times else None), "t_last": (max(times) if times else None),
                "has_sequence": bool(seqs), "seq_min": (min(seqs) if seqs else None),
                "seq_max": (max(seqs) if seqs else None), "_ticks": norm}
    p1 = one_poll("poll1"); out["polls"].append({k:v for k,v in p1.items() if k!="_ticks"})
    ticks_union = {}
    for t in p1.get("_ticks", []): ticks_union[tick_key(t)] = t
    span1 = None
    if sess == "rth" and "error" not in p1:
        time.sleep(65)                       # 模擬 60s 輪詢節奏
        p2 = one_poll("poll2");
        # 覆蓋度:poll2 有多少筆在 poll1 已見過(重疊)? 0 重疊=中間有缺口(漏資料)
        k1 = set(tick_key(t) for t in p1.get("_ticks", []))
        new_in_p2 = sum(1 for t in p2.get("_ticks", []) if tick_key(t) not in k1)
        overlap = p2.get("n",0) - new_in_p2
        out["polls"].append({**{k:v for k,v in p2.items() if k!="_ticks"},
                             "new_vs_poll1": new_in_p2, "overlap_vs_poll1": overlap})
        for t in p2.get("_ticks", []): ticks_union[tick_key(t)] = t
        out["coverage"] = {
            "gap_detected": overlap == 0 and p2.get("n",0) > 0,   # 完全無重疊=兩次之間漏了
            "overlap": overlap, "new_in_65s": new_in_p2,
            "note": "overlap>0=1000筆窗口>65s→輪詢跟得上;overlap=0=窗口<65s→有漏,需更快輪詢或改串流"
        }
    # 1000 筆時間跨度(秒)
    def parse_t(s):
        if not s: return None
        for fmt in ("%Y-%m-%d %H:%M:%S:%f", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try: return datetime.strptime(s, fmt)
            except Exception: continue
        return None
    if p1.get("t_first") and p1.get("t_last"):
        a, b = parse_t(p1["t_first"]), parse_t(p1["t_last"])
        if a and b:
            span1 = abs((b - a).total_seconds())
            out["window_span_sec"] = round(span1, 2)
            out["n_ticks_poll1"] = p1.get("n")
            if span1 and p1.get("n"):
                # 推估:整個 RTH(23400s)約多少逐筆;要不漏,輪詢間隔須 < window_span
                out["est_full_rth_ticks"] = int(p1["n"] * (23400.0 / span1)) if span1 > 0 else None
                out["poll_interval_must_be_under_sec"] = round(span1, 1)
    # 成交量分桶 VWAP + 大單彙總(取兩個門檻看敏感度)
    uticks = list(ticks_union.values())
    out["n_ticks_union"] = len(uticks)
    out["analysis_thr_200k"] = analyze_ticks(uticks, 2e5)
    out["analysis_thr_500k"] = analyze_ticks(uticks, 5e5)
    return out

def probe_snapshot(q, codes):
    """get_market_snapshot → 全欄位(找 流通股/發行股本)。回傳全欄位 + 抽取候選。"""
    from futu import RET_OK
    ret, d = q.get_market_snapshot(codes)
    if ret != RET_OK:
        return {"error": str(d)[:160]}
    recs = rows_of(d)
    cols = list(d.columns) if hasattr(d, "columns") else (list(recs[0].keys()) if recs else [])
    # 找可能表達「流通股/發行股本/流通市值」的欄位
    share_cols = [c for c in cols if any(k in c.lower() for k in
                  ("share", "circular", "issued", "outstanding", "market_val", "float"))]
    picked = {}
    for r in recs:
        code = r.get("code")
        sub = {c: r.get(c) for c in share_cols}
        sub["last_price"] = r.get("last_price")
        # 若無直接流通股欄位,用 流通市值/價 反推
        cmv = _f(r.get("circular_market_val")); lp = _f(r.get("last_price"))
        if cmv and lp: sub["_float_from_cmv/price"] = int(cmv/lp)
        picked[code] = sub
    return {"columns": cols, "share_related_columns": share_cols,
            "per_symbol": picked, "sample_full_row": recs[0] if recs else None}

def probe_holders(q, code):
    """股權結構(機構/內部人/個人 占比)+ 機構持股數量(13F)。大戶籌碼數量的結構源。"""
    out = {"code": code}
    from futu import RET_OK
    # 股權結構匯總
    try:
        ret, data = q.get_shareholders_overview(code)
        if ret == RET_OK and isinstance(data, dict):
            ht = data.get("holder_type")
            out["holder_type"] = rows_of(ht)   # 名稱(機構/個人/內部人)+ holder_pct
        else:
            out["holder_type_err"] = str(data)[:120]
    except Exception as e:
        out["holder_type_err"] = f"{type(e).__name__}: {str(e)[:100]}"
    # 機構持股(13F)
    try:
        ret, d = q.get_shareholders_institutional(code, num=1)
        if ret == RET_OK and len(d):
            r = d.iloc[0]
            out["institutional"] = {c: (str(r.get(c)) if not isinstance(r.get(c), (int, float, type(None))) else r.get(c))
                                    for c in (list(d.columns) if hasattr(d, "columns") else [])}
    except Exception as e:
        out["institutional_err"] = f"{type(e).__name__}: {str(e)[:100]}"
    return out

def probe_capdist(q, code):
    from futu import RET_OK
    try:
        ret, d = q.get_capital_distribution(code)
        if ret == RET_OK and len(d):
            r = d.iloc[0]
            return {c: r.get(c) if isinstance(r.get(c), (int, float, type(None))) else str(r.get(c))
                    for c in (list(d.columns) if hasattr(d, "columns") else [])}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:100]}"}
    return {"error": "no data"}

def push_gist(cfg, files):
    gid = cfg["gist_id"]; tok = cfg["gist_token"]
    body = json.dumps({"files": {k: {"content": json.dumps(v, ensure_ascii=False)} for k, v in files.items()}}).encode()
    req = urllib.request.Request(f"https://api.github.com/gists/{gid}", data=body, method="PATCH",
        headers={"Authorization": f"token {tok}", "Accept": "application/vnd.github+json", "User-Agent": "probe-ticker"})
    urllib.request.urlopen(req, timeout=25).read()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"))
    ap.add_argument("--syms", default="", help="逗號分隔覆蓋預設代表清單,如 US.TSLA,US.COHR")
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args()
    cfg = json.load(open(a.config)) if os.path.exists(a.config) else {}
    syms = [s.strip() for s in a.syms.split(",") if s.strip()] or PROBE_SYMS
    sess = market_session()
    log(f"session={sess}  symbols={syms}")
    if sess != "rth":
        log("⚠ 非盤中:逐筆輪詢覆蓋度量不準(無新成交),但欄位/流通股/持股結構仍可驗證。建議盤中(9:30-16:00 ET)再跑一次。")

    from futu import OpenQuoteContext
    q = OpenQuoteContext(host=cfg.get("opend_host", "127.0.0.1"), port=int(cfg.get("opend_port", 11111)))
    report = {"ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
              "session": sess, "symbols": syms, "purpose": "個股籌碼 Parts2/3 原型驗證",
              "tickers": {}, "snapshot": {}, "holders": {}, "capdist": {}}
    try:
        # ① 流通股/發行股本(所有籌碼數量)
        log("① snapshot(流通股/發行股本)…")
        report["snapshot"] = probe_snapshot(q, syms)
        # ②③④ 逐標的
        for s in syms:
            log(f"④ ticker 輪詢覆蓋度 {s}…")
            report["tickers"][s] = probe_ticker(q, s, sess)
            log(f"②  持股結構(大戶) {s}…")
            report["holders"][s] = probe_holders(q, s)
            log(f"③  ⑦ 資金分布(交叉比對) {s}…")
            report["capdist"][s] = probe_capdist(q, s)
    finally:
        q.close()

    # ---- 判讀 ----
    verdict = []
    snp = report["snapshot"]
    if snp.get("share_related_columns"):
        verdict.append(f"✓ 流通股可得:snapshot 有 {snp['share_related_columns']}")
    else:
        verdict.append("✗ snapshot 無明顯流通股欄位(可能權限;改用 shareholders_overview 或流通市值/價反推)")
    for s in syms:
        tk = report["tickers"].get(s, {})
        cov = tk.get("coverage"); span = tk.get("window_span_sec"); nu = tk.get("n_ticks_union")
        big = (tk.get("analysis_thr_200k") or {}).get("big", {})
        line = f"[{s}] union={nu}筆"
        if span is not None: line += f" 1000筆跨{span}s"
        if tk.get("est_full_rth_ticks"): line += f" 估全日≈{tk['est_full_rth_ticks']}筆"
        if cov:
            line += " 覆蓋:" + ("⚠有缺口(窗口<65s→需更快輪詢/串流)" if cov.get("gap_detected") else "✓跟得上(重疊>0)")
        if big.get("vwap"): line += f" 大單VWAP≈{big['vwap']} 淨{big.get('net_vol')}股"
        verdict.append(line)
    report["verdict"] = verdict

    # 精簡版(去掉逐筆明細,只留量測)——推 gist / 存檔
    slim = json.loads(json.dumps(report))  # 已無 _ticks(未放入 report)
    out_path = os.path.join(os.path.dirname(os.path.abspath(a.config)), "ticker_probe.json")
    json.dump(slim, open(out_path, "w"), ensure_ascii=False, indent=1)
    log(f"寫入 {out_path}")
    if not a.no_push and cfg.get("gist_id") and cfg.get("gist_token"):
        try:
            push_gist(cfg, {"ticker_probe.json": slim}); log("✓ 已推 ticker_probe.json 到 gist(雲端可讀)")
        except Exception as e:
            log("推送失敗(可手動貼上 ticker_probe.json):", type(e).__name__, e)

    print("\n" + "=" * 64 + "\n判讀 VERDICT\n" + "=" * 64)
    for v in verdict: print(" ", v)
    print("=" * 64)

if __name__ == "__main__":
    main()
