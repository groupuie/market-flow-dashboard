#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""吸籌偵測引擎(2026-08-03;純 stdlib;fail-open)
「⑦ 全單資金持續入場 × 價格相對低位」的每日機械篩選 + 前瞻追蹤。
源起:使用者觀察 SOXL/ASML/ASTS/COHR/APP/AVGO/MSFT —— 股價跌或低位震盪、
現金池累積線卻一直爬升,懷疑是波段選股法。以 MSFT 2026-03 案例校準定義後,
對 301 檔 ×250 個交易日回測(詳 claude/accum_backtest_2026-08.md)。

訊號定義(全機械、與前端顯示一致):
  A 持續入場: Σ全單(60日)>0 且 Σ全單(20日)>0(全單 = 大單m+中小單r,同⑦現金池累積線)
  S 量體門檻: 吸收率 = Σ全單60 / Σ成交額60 ≥ 0.2%(排除微弱噪音)
  B 相對低位: 收盤位於 120 日高低區間 ≤50%
  C 尚未上噴: 近 20 日漲幅 <10%
  ⚠ 吸收率 ≥1.0% 為「極端吸收」——回測顯示歷史偏空(x40≈−8%),單獨警示列出

回測參考(2025-08-05→2026-07-31,241 檔個股,SPY 調整):
  此型態 40 日內最大漲幅≥15% 頻率 43.7%(基準 39.9%)、40日超額 +1.6%、
  達 +15% 者中位 12 個交易日;增益溫和、遠非必然。
  ⚠ 歷史頻率非未來機率;僅 12 個月單一市況(含 2026-07 股災);宇宙=追蹤清單
  (選樣偏誤);⑦大單分類為券商近似。不構成買賣建議。
"""
import json, os, time, urllib.request, datetime
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
P = {"W_LONG": 60, "W_SHORT": 20, "COV_LONG": 48, "COV_SHORT": 16,
     "AB_MIN": 0.002, "AB_TOX": 0.010, "PP_MAX": 0.50, "PP_WIN": 120,
     "R20_MAX": 0.10, "GAP": 5, "MIN_FLOW_DAYS": 90,
     "GRAD_LOOK": 120, "GRAD_TH": 0.15, "GRAD_H": 40}
STATS = {"asof": "2026-08-03", "period": "2025-08-05→2026-07-31", "n_sym": 241, "n_eps": 243,
         "p15": 43.7, "base_p15": 39.9, "x40": 1.6, "d15_med": 12,
         "tox_x40": -9.3, "tox_p15": 23.5, "tox_n": 28,
         # 組合矩陣(2026-08-03 追加;詳 claude/accum_backtest_2026-08.md「組合」節):
         # 觸發器=吸籌後突破前10日高才進場、+大單同向(m60>0) → 40日為正 60.7%(基準53.0)、
         # 平均+13.4%、n=84;全樣本可信天花板≈60%,75%+僅出現於後半段行情切片,不可信。
         "combo_m1": 60.7, "combo_base_m1": 53.0, "combo_f40": 13.4, "combo_n": 84,
         # AI 板塊分組(2026-08-03;使用者聚焦假設的驗證):AI集合內 觸發+大單同向 40日為正
         # 80.0%(n=25,收縮70.9%,同標的去重後13檔9勝≈69%) vs AI自身基準61.7%(增+18pt);
         # 非AI僅52.5%(增+2pt)——組合優勢幾乎全在AI板塊。⚠樣本群聚2026-03/04反彈、n小。
         "ai_m1": 80.0, "ai_m1_shrunk": 70.9, "ai_m2": 76.0, "ai_n": 25,
         "ai_base_m1": 61.7, "ai_f40": 42.5, "ai_dedup_m1": 69, "nonai_m1": 52.5}
ETFC = {"槓桿", "反向", "板塊ETF", "大盤", "國債", "信用債", "金", "油", "銀", "Crypto", "現金"}
# AI 主軸集合(2026-08-03 使用者聚焦):半導體/記憶體/光通訊/電源供應(AI基建+電力)/雲端服務
# 成員=歷史上任一日掛過 AI 類別標籤者(避免 正股/闖入 標籤蓋掉板塊) + 雲端與AI伺服器補充清單
AI_CATS = {"半導體", "記憶體", "光通信", "AI基建", "電力"}
AI_SUPP = {"MSFT", "AMZN", "GOOGL", "GOOG", "ORCL", "IBM", "SMCI", "DELL", "ANET"}
DISCLAIMER = ("歷史同型態頻率,非未來機率;回測僅 12 個月單一市況、宇宙有選樣偏誤、"
              "⑦大單分類為券商近似;吸籌不保證止跌(表列「起日以來」含大幅下跌案例);不構成買賣建議。")

def _http_json(url, timeout=25):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=timeout).read())

def _load_flows(gist_base):
    """回傳 ({sym:{date:(m,r)}}, {sym:類別}, AI集合);m/r 單位 $M;剔除現金類"""
    F, CAT, AI = {}, {}, set(AI_SUPP)
    for fn in ("ext_flows.json", "daily_flows.json"):   # core 後蓋 ext
        d = _http_json(gist_base + fn)
        for day, row in (d.get("daily_flows") or {}).items():
            for s, v in (row or {}).items():
                if not isinstance(v, dict) or v.get("m") is None: continue
                if v.get("c") == "現金": continue
                F.setdefault(s, {})[day] = (float(v["m"]), float(v.get("r") or 0))
                CAT[s] = v.get("c") or CAT.get(s)
                if v.get("c") in AI_CATS: AI.add(s)
    return F, CAT, AI

def _px_from_kline(bars):
    """gist kline(前復權):[d,o,h,l,c,v,tor] → dates/close/dollarvol($M)"""
    ds = [b[0] for b in bars]; c = [float(b[4]) for b in bars]
    dv = [float(b[4]) * float(b[5] or 0) / 1e6 for b in bars]
    return ds, c, dv

def _px_yahoo(sym):
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/%s?range=2y&interval=1d"
           % sym.replace(".", "-"))
    raw = _http_json(url)
    res = raw["chart"]["result"][0]
    ts = res["timestamp"]; q = res["indicators"]["quote"][0]
    adj = (res["indicators"].get("adjclose") or [{}])[0].get("adjclose")
    ds, c, dv = [], [], []
    for i in range(len(ts)):
        cl = q["close"][i]
        if cl is None: continue
        ds.append(datetime.datetime.utcfromtimestamp(ts[i]).strftime("%Y-%m-%d"))
        a = adj[i] if adj and adj[i] is not None else cl
        c.append(float(a)); dv.append(float(cl) * float(q["volume"][i] or 0) / 1e6)
    return ds, c, dv

def _get_px(sym, gist_base, kline_dir):
    try:
        if kline_dir:
            p = os.path.join(kline_dir, "kline_%s.json" % sym)
            if os.path.exists(p):
                return _px_from_kline(json.load(open(p))["bars"])
        if gist_base:
            try:
                return _px_from_kline(_http_json(gist_base + "kline_%s.json" % sym)["bars"])
            except Exception:
                pass
        return _px_yahoo(sym)
    except Exception:
        return None

def _metrics(dates, close, dv, fl):
    """逐日訊號指標;無法評估的日子為 None"""
    n = len(dates); out = [None] * n
    WL, WS, PW = P["W_LONG"], P["W_SHORT"], P["PP_WIN"]
    for t in range(n):
        if t < PW or t < WL: continue
        if dates[t] not in fl: continue
        d60 = [dates[k] for k in range(t - WL + 1, t + 1) if dates[k] in fl]
        d20 = [dates[k] for k in range(t - WS + 1, t + 1) if dates[k] in fl]
        if len(d60) < P["COV_LONG"] or len(d20) < P["COV_SHORT"]: continue
        a60 = sum(fl[x][0] + fl[x][1] for x in d60)
        a20 = sum(fl[x][0] + fl[x][1] for x in d20)
        m60 = sum(fl[x][0] for x in d60)
        sdv = sum(dv[t - WL + 1:t + 1]) or 1e-9
        lo = min(close[t - PW + 1:t + 1]); hi = max(close[t - PW + 1:t + 1])
        out[t] = {"a60": a60, "a20": a20, "m60": m60, "ab": a60 / sdv,
                  "pp": (close[t] - lo) / (hi - lo) if hi > lo else 0.5,
                  "r20": close[t] / close[t - WS] - 1.0}
    return out

def _sig(m, toxic_ok=False):
    if not m: return False
    base = (m["a60"] > 0 and m["a20"] > 0 and m["ab"] >= P["AB_MIN"]
            and m["pp"] <= P["PP_MAX"] and m["r20"] < P["R20_MAX"])
    if toxic_ok: return base
    return base and m["ab"] < P["AB_TOX"]

def _episodes(flags):
    runs = []; cur = None
    for i, f in enumerate(flags):
        if f: cur = [i, i] if cur is None else [cur[0], i]
        elif cur is not None: runs.append(cur); cur = None
    if cur is not None: runs.append(cur)
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] < P["GAP"]: merged[-1][1] = r[1]
        else: merged.append(list(r))
    return merged

def _short_watch(F, CAT, AI, gist_base, kline_dir):
    """短史雷達(2026-08-07;SPCX 實例揪出):流資料 15~89 日的新上市/新入列股,
       正式引擎的 90 日流門檻+185 根價門檻會整批跳過 → 「現金池進場+低位」完全隱形。
       這裡以「可用視窗」套同一組條件(Σ全單>0 兩口徑、吸收率≥0.2%、位置≤50%、近20日<+10%),
       另列展示;⚠ 未經回測、不入統計與前瞻追蹤,tox(≥1%)照紅字。fail-open。"""
    out = []
    syms = sorted(s for s in F if 15 <= len(F[s]) < P["MIN_FLOW_DAYS"])
    for s in syms[:40]:
        try:
            px = _get_px(s, gist_base, kline_dir)
            if not px: continue
            dates, close, dv = px
            n = len(dates)
            if n < 15: continue
            fl = F[s]
            t = n - 1
            while t >= 0 and dates[t] not in fl: t -= 1
            if t < 10: continue
            wl = min(P["W_LONG"], t + 1); ws = min(P["W_SHORT"], t + 1); pw = min(P["PP_WIN"], t + 1)
            d60 = [dates[k] for k in range(t - wl + 1, t + 1) if dates[k] in fl]
            d20 = [dates[k] for k in range(t - ws + 1, t + 1) if dates[k] in fl]
            if len(d60) < 10 or len(d20) < 5: continue
            a60 = sum(fl[x][0] + fl[x][1] for x in d60)
            a20 = sum(fl[x][0] + fl[x][1] for x in d20)
            m60 = sum(fl[x][0] for x in d60)
            sdv = sum(dv[t - wl + 1:t + 1]) or 1e-9
            ab = a60 / sdv
            lo = min(close[t - pw + 1:t + 1]); hi = max(close[t - pw + 1:t + 1])
            pp = (close[t] - lo) / (hi - lo) if hi > lo else 0.5
            r20 = close[t] / close[max(0, t - ws)] - 1.0
            if not (a60 > 0 and a20 > 0 and ab >= P["AB_MIN"] and pp <= P["PP_MAX"] and r20 < P["R20_MAX"]):
                continue
            out.append({"sym": s, "cat": CAT.get(s) or "", "days_flow": len(fl), "px_days": n,
                        "a60": round(a60), "m60": round(m60), "ab": round(ab * 100, 2),
                        "pp": round(pp * 100), "r20": round(r20 * 100, 1), "px": round(close[t], 2),
                        "d": dates[t], "tox": bool(ab >= P["AB_TOX"]), "ai": s in AI})
        except Exception:
            continue
    out.sort(key=lambda r: -r["a60"])
    return out[:15]

def build_accum(gist_base, kline_dir=None, log=None):
    """主入口:回傳 scan.json 的 accum 區塊。內部單檔失敗一律跳過(fail-open)。"""
    t0 = time.time()
    F, CAT, AI = _load_flows(gist_base)
    syms = sorted(s for s in F if len(F[s]) >= P["MIN_FLOW_DAYS"])
    def work(s):
        try:
            px = _get_px(s, gist_base, kline_dir)
            if not px or len(px[0]) < P["PP_WIN"] + P["W_LONG"] + 5: return None
            return (s, px)
        except Exception:
            return None
    with ThreadPoolExecutor(max_workers=8) as ex:
        got = [r for r in ex.map(work, syms) if r]
    picks, etf_picks, toxic, skipped = [], [], [], 0
    grad_hit, grad_miss, grad_pend = [], 0, 0
    grad_ai = [0, 0, 0]   # AI 集合 [hit, miss, pend]
    asof = None
    for s, (dates, close, dv) in got:
        try:
            M = _metrics(dates, close, dv, F[s])
            flags = [_sig(m, toxic_ok=True) for m in M]
            runs = _episodes(flags)
            # 今日入選:最後一個可評日訊號成立
            t = max((i for i, m in enumerate(M) if m), default=None)
            if t is None: skipped += 1; continue
            asof = max(asof or "", dates[t])
            if flags[t]:
                st = t
                for a, b in runs:
                    if a <= t <= b: st = a
                m = M[t]
                # 確認條件(2026-08-03 組合矩陣):①突破=訊號起後首次收盤越過前10日高(歷史 M1 +6pt)
                # ②大單同向 m60>0(前端由 m60 欄自判) ③靜默量=20日均額<60日均額 ④站上200D
                trig_d = None
                for k in range(st + 1, t + 1):
                    if k >= 10 and close[k] > max(close[k - 10:k]): trig_d = dates[k]; break
                v20 = sum(dv[t - 19:t + 1]) / 20 if t >= 19 else None
                v60 = sum(dv[t - 59:t + 1]) / 60 if t >= 59 else None
                ma200 = (sum(close[t - 199:t + 1]) / 200) if t >= 199 else None
                row = {"sym": s, "cat": CAT.get(s) or "", "start": dates[st], "days": t - st,
                       "chg": round((close[t] / close[st] - 1) * 100, 1),
                       "a60": round(m["a60"]), "m60": round(m["m60"]),
                       "ab": round(m["ab"] * 100, 2), "pp": round(m["pp"] * 100),
                       "r20": round(m["r20"] * 100, 1), "px": round(close[t], 2), "d": dates[t],
                       "trig": trig_d, "quiet": bool(v20 is not None and v60 is not None and v20 < v60),
                       "ma200": (None if ma200 is None else bool(close[t] > ma200)),
                       "ai": s in AI}
                if m["ab"] >= P["AB_TOX"]: toxic.append(row)
                elif CAT.get(s) in ETFC: etf_picks.append(row)
                else: picks.append(row)
            # 前瞻追蹤:近 GRAD_LOOK 日起始的 episodes(個股、非極端)
            if CAT.get(s) in ETFC: continue
            cutoff = (datetime.date.fromisoformat(dates[t])
                      - datetime.timedelta(days=int(P["GRAD_LOOK"] * 1.5))).isoformat()
            for a, b in runs:
                ma = M[a]
                if dates[a] < cutoff or not ma or ma["ab"] >= P["AB_TOX"]: continue
                hit_d = None
                for k in range(a + 1, min(a + P["GRAD_H"] + 1, len(close))):
                    if close[k] / close[a] - 1.0 >= P["GRAD_TH"]: hit_d = k - a; break
                if hit_d is not None:
                    grad_hit.append({"sym": s, "start": dates[a], "d15": hit_d, "ai": s in AI,
                                     "chg": round((close[min(a+P["GRAD_H"],len(close)-1)] / close[a] - 1) * 100, 1)})
                elif len(close) - 1 - a >= P["GRAD_H"]:
                    grad_miss += 1
                    if s in AI: grad_ai[1] += 1
                else:
                    grad_pend += 1
                    if s in AI: grad_ai[2] += 1
                if hit_d is not None and s in AI: grad_ai[0] += 1
        except Exception:
            skipped += 1
    picks.sort(key=lambda r: -r["ab"]); etf_picks.sort(key=lambda r: -r["ab"])
    toxic.sort(key=lambda r: -r["ab"])
    grad_hit.sort(key=lambda r: r["start"], reverse=True)
    out = {"updated_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), "asof": asof,
           "n_universe": len(got), "n_skip": len(syms) - len(got) + skipped,
           "params": P, "stats": STATS, "picks": picks, "etf": etf_picks, "toxic": toxic,
           "grad": {"hit": grad_hit[:40], "hit_n": len(grad_hit), "miss": grad_miss, "pend": grad_pend,
                    "ai": {"hit_n": grad_ai[0], "miss": grad_ai[1], "pend": grad_ai[2]}},
           "n_ai": len(AI),
           "note": DISCLAIMER, "elapsed_s": round(time.time() - t0, 1)}
    try:   # 短史雷達(fail-open;⚠ 未回測、不入統計/前瞻)
        out["short_watch"] = _short_watch(F, CAT, AI, gist_base, kline_dir)
    except Exception:
        out["short_watch"] = []
    if log: log("accum: %d 檔宇宙 → 個股 %d / ETF %d / 極端 %d · 前瞻 hit=%d miss=%d pend=%d · %.1fs"
                % (len(got), len(picks), len(etf_picks), len(toxic),
                   len(grad_hit), grad_miss, grad_pend, out["elapsed_s"]))
    return out

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--kline-dir", default=None)
    a = ap.parse_args()
    gb = None
    if os.path.exists(a.config):
        mdu = (json.load(open(a.config)) or {}).get("market_data_url")
        if mdu: gb = mdu.rsplit("/", 1)[0] + "/"
    r = build_accum(gb, kline_dir=a.kline_dir, log=lambda *x: print(*x))
    print(json.dumps({k: r[k] for k in ("asof", "n_universe")}, ensure_ascii=False))
    for p_ in r["picks"]:
        print("  %(sym)-6s %(cat)-6s 起%(start)s(%(days)d日,%(chg)+.1f%%) 吸%(ab).2f%% 位置%(pp)d%%" % p_)
