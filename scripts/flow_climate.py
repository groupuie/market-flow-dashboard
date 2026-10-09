#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全球資金氣候 + 抄底▲/減碼▼ 確認訊號(2026-10-09;純標準庫;零 token;GitHub Actions 盤後引擎呼叫)

為什麼是這幾個量(研究紀錄:專案文件 claude/flow_climate_2026-10.md):
  259 檔個股 × 2009–2026 回測。單看個股技術面(含現有 ◆★、RSI/布林/TD、各種「拉回買」)≈ 擲硬幣;
  原油/黃金/白銀本身沒有穩定的領先性(不同年代正負號會翻)。四個子期間(07-11/12-16/17-21/22-26)
  方向都一致的「大戶/機構資金」量只有少數幾個 → 組成「全球資金氣候」:
    ① 日圓套利交易擁擠度:CFTC 期貨持倉(TFF)— 交易商在日圓期貨的淨部位 z 分數(3 年窗)。
       投機資金大量放空日圓借錢買全球資產(套利擁擠)→ 之後美股表現差;套利已平倉 → 之後較好。
       (Brunnermeier, Nagel & Pedersen 2008「Carry Trades and Currency Crashes」同方向證據)
    ② 利率衝擊:美國 5 年期公債殖利率 20 日變化(急升=金融條件收緊)。
    ③ 美元趨勢:美元指數的趨勢基金式(CTA)趨勢強度(美元走強=全球流動性收緊)。
  分數 = 三者在近 3 年的百分位(①一半權重、②③合計一半)再取近 3 年百分位 → 0–100(高=寬鬆/順風)。
  個股訊號 = 個股K線轉折 × 氣候過濾(轉折本身≈擲硬幣,氣候才是分辨真假的關鍵):
    ▼減碼:近 20 日曾收盤高於 50 日線 ≥15%,今天第一次收盤跌破 20 日線(=技判「出」),且氣候 ≤35%。
    ▲抄底:近 20 日曾收盤低於 50 日線 ≥15%,今天第一次收盤站回 20 日線,且氣候 ≥80%。
    兩者各自 20 交易日冷卻(冷卻以「轉折」計,與氣候無關;與回測完全同口徑)。
  參考(只顯示、不計分):CTA 趨勢基金部位估計、波動控制基金曝險、VIX 期限結構、造市商 gamma(GEX)、
    暗池買盤(DIX)、10 年期殖利率、原油/黃金/白銀/銅 —— 2012–2026 有效但 2008 金融海嘯失效,或無穩定領先性。

輸出 data/flow_climate.json:series(2020-06 起逐日氣候)、now(最新各分量原始值+參考面板)、stats(回測數字,
  hover 用)、scan(全追蹤宇宙近 5 日的 ▲▼ 與「待確認」清單,需 --scan)。
資料源全部公開:Yahoo 日K(^FVX、DX-Y.NYB 等)、CFTC Socrata(publicreporting.cftc.gov)、SqueezeMetrics DIX.csv、gist K線。
用法:python3 scripts/flow_climate.py --out data/flow_climate.json [--config config.json --scan]
"""
import argparse, concurrent.futures as cf, datetime, json, math, os, sys, time, urllib.parse, urllib.request
from zoneinfo import ZoneInfo

UA = {"User-Agent": "Mozilla/5.0 (flow_climate)"}
START = "2004-01-01"
SERIES_FROM = "2020-06-01"
RANK_W, RANK_MP = 756, 252          # 近 3 年百分位(交易日)
COT_ZW, COT_ZMP = 156, 52           # 日圓持倉 z 分數:3 年(週)
TH = {"trim": 0.35, "trim_strong": 0.20, "buy": 0.80, "ext": 0.15, "dip": 0.15, "cool": 20}
NAN = float("nan")

def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)

def http(url, timeout=40, retries=3, as_json=True):
    last = None
    for k in range(retries):
        try:
            raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()
            return json.loads(raw) if as_json else raw.decode("utf-8", "replace")
        except Exception as e:
            last = e; time.sleep(2 + 3 * k)
    raise last

def isnan(x): return x is None or (isinstance(x, float) and math.isnan(x))

# ---------------- data ----------------
def yahoo(sym, start=START):
    p1 = int(datetime.datetime.fromisoformat(start).replace(tzinfo=datetime.timezone.utc).timestamp())
    u = ("https://query1.finance.yahoo.com/v8/finance/chart/%s?period1=%d&period2=%d&interval=1d&events=div%%2Csplit"
         % (urllib.parse.quote(sym), p1, int(time.time()) + 86400))
    r = http(u)["chart"]["result"][0]
    tz = ZoneInfo(r["meta"].get("exchangeTimezoneName") or "America/New_York")
    ts = r.get("timestamp") or []
    q = r["indicators"]["quote"][0]
    adj = ((r["indicators"].get("adjclose") or [{}])[0] or {}).get("adjclose")
    cl = adj if adj else q["close"]
    out = {}
    for t, c in zip(ts, cl):
        if c is None: continue
        d = datetime.datetime.fromtimestamp(t, tz).date().isoformat()
        out[d] = float(c)       # 同日重複取最後一筆(= pandas keep="last")
    return out

def align(cal, m, limit=5):
    """= pandas: x.reindex(cal ∪ own dates).sort_index().ffill(limit).reindex(cal)"""
    keys = sorted(set(cal) | set(m))
    out, last, gap = {}, NAN, 0
    for k in keys:
        v = m.get(k)
        if v is not None and not isnan(v): last, gap = v, 0
        else:
            gap += 1
            if gap > limit: last = NAN
        out[k] = last if (v is None or isnan(v)) else v
    return [out[d] for d in cal]

def cot_yen():
    url = ("https://publicreporting.cftc.gov/resource/gpe5-46if.json?" + urllib.parse.urlencode({
        "$where": "cftc_contract_market_code='097741'",
        "$select": "report_date_as_yyyy_mm_dd,open_interest_all,dealer_positions_long_all,dealer_positions_short_all",
        "$order": "report_date_as_yyyy_mm_dd", "$limit": 50000}))
    rows = http(url, timeout=90)
    agg = {}
    for r in rows:
        d = r["report_date_as_yyyy_mm_dd"][:10]
        a = agg.setdefault(d, [0.0, 0.0, 0.0])
        a[0] += float(r.get("open_interest_all") or 0); a[1] += float(r.get("dealer_positions_long_all") or 0); a[2] += float(r.get("dealer_positions_short_all") or 0)
    ds = sorted(agg)
    s = [(agg[d][1] - agg[d][2]) / agg[d][0] if agg[d][0] else NAN for d in ds]
    z = []
    for i in range(len(s)):
        w = [x for x in s[max(0, i - COT_ZW + 1):i + 1] if not isnan(x)]
        if len(w) < COT_ZMP or isnan(s[i]): z.append(NAN); continue
        m = sum(w) / len(w); sd = math.sqrt(sum((x - m) ** 2 for x in w) / (len(w) - 1))
        z.append((s[i] - m) / sd if sd > 0 else NAN)
    return ds, s, z, rows

def dix_gex():
    txt = http("https://squeezemetrics.com/monitor/static/DIX.csv", as_json=False)
    out = {}
    for ln in txt.strip().splitlines()[1:]:
        p = ln.split(",")
        if len(p) >= 4:
            try: out[p[0]] = (float(p[2]), float(p[3]))
            except ValueError: pass
    return out

# ---------------- math (pandas 同語意) ----------------
def roll_rank(x, w=RANK_W, mp=RANK_MP):
    out = []
    for t in range(len(x)):
        v = x[t]
        if isnan(v): out.append(NAN); continue
        win = [a for a in x[max(0, t - w + 1):t + 1] if not isnan(a)]
        if len(win) < mp: out.append(NAN); continue
        less = sum(1 for a in win if a < v); eq = sum(1 for a in win if a == v)
        out.append((less + (eq + 1) / 2) / len(win))
    return out

def roll_std(x, w, mp):
    out = []
    for t in range(len(x)):
        win = [a for a in x[max(0, t - w + 1):t + 1] if not isnan(a)]
        if len(win) < mp: out.append(NAN); continue
        m = sum(win) / len(win); out.append(math.sqrt(sum((a - m) ** 2 for a in win) / (len(win) - 1)))
    return out

def logdiff(c):
    return [NAN] + [math.log(c[i] / c[i - 1]) if not (isnan(c[i]) or isnan(c[i - 1]) or c[i] <= 0 or c[i - 1] <= 0) else NAN for i in range(1, len(c))]

def cta_pos(c, lbs=(21, 63, 126, 252), volwin=90, tgt=0.15, cap=2.0):
    """Kestner 式趨勢基金部位估計:各回看期(1/3/6/12 月)趨勢 t 值夾在 ±1 取平均 × 波動縮放(目標 15%)"""
    lr = logdiff(c); sd = roll_std(lr, volwin, 60); out = []
    for i in range(len(c)):
        if isnan(sd[i]) or sd[i] <= 0: out.append(NAN); continue
        sig = []
        for L in lbs:
            if i - L < 0 or isnan(c[i]) or isnan(c[i - L]) or c[i - L] <= 0: sig = None; break
            t = math.log(c[i] / c[i - L]) / (sd[i] * math.sqrt(L)); sig.append(max(-1.0, min(1.0, t)))
        if sig is None: out.append(NAN); continue
        scale = min(cap, tgt / (sd[i] * math.sqrt(252)))
        out.append(sum(sig) / len(sig) * scale)
    return out

def volctl(c, tgt=0.10, cap=1.5):
    lr = logdiff(c); s21 = roll_std(lr, 21, 15); s63 = roll_std(lr, 63, 40); out = []
    for a, b in zip(s21, s63):
        if isnan(a) or isnan(b) or a <= 0 or b <= 0: out.append(NAN); continue
        out.append((min(cap, tgt / (a * math.sqrt(252))) + min(cap, tgt / (b * math.sqrt(252)))) / 2)
    return out

def chg(x, k, mult=1.0, log_=False):
    out = []
    for i in range(len(x)):
        if i < k or isnan(x[i]) or isnan(x[i - k]): out.append(NAN); continue
        out.append(math.log(x[i] / x[i - k]) if log_ else (x[i] - x[i - k]) * mult)
    return out

def last_valid(x):
    for i in range(len(x) - 1, -1, -1):
        if not isnan(x[i]): return i
    return None

def r1(v, n=1):
    return None if isnan(v) else round(v, n)

# ---------------- 個股轉折 × 氣候(與前端 fcSeriesJS 逐位元同口徑) ----------------
def fc_events(dates, closes, clim_of, th=TH):
    n = len(closes); C = closes
    s20 = [NAN] * n; s50 = [NAN] * n; acc = 0.0
    pre = [0.0]
    for c in C: pre.append(pre[-1] + c)
    for i in range(n):
        if i >= 19: s20[i] = (pre[i + 1] - pre[i - 19]) / 20
        if i >= 49: s50[i] = (pre[i + 1] - pre[i - 49]) / 50
    rel = [C[i] / s50[i] - 1 if not isnan(s50[i]) else NAN for i in range(n)]
    ev, lt, lb = [], -999, -999
    st = {"ext": [NAN] * n, "dip": [NAN] * n, "s20": s20, "lt": -999, "lb": -999}
    for i in range(n):
        if i >= 68:
            w = rel[i - 19:i + 1]
            st["ext"][i] = max(w); st["dip"][i] = min(w)
        if i < 1 or isnan(s20[i]) or isnan(s20[i - 1]): continue
        dn = C[i] < s20[i] and C[i - 1] >= s20[i - 1]
        up = C[i] > s20[i] and C[i - 1] <= s20[i - 1]
        ex, dp = st["ext"][i], st["dip"][i]
        if dn and not isnan(ex) and ex >= th["ext"] and i - lt > th["cool"]:
            lt = i; cl = clim_of(dates[i])
            if cl is not None and cl <= th["trim"]:
                ev.append({"k": "trim", "i": i, "d": dates[i], "c": C[i], "clim": cl, "ext": ex, "s20": s20[i], "strong": cl <= th["trim_strong"]})
        if up and not isnan(dp) and dp <= -0.10 and i - lb > th["cool"]:
            lb = i; cl = clim_of(dates[i])
            if cl is not None and cl >= th["buy"] and dp <= -th["dip"]:
                ev.append({"k": "buy", "i": i, "d": dates[i], "c": C[i], "clim": cl, "dip": dp, "s20": s20[i]})
    st["lt"], st["lb"] = lt, lb     # 最後一次被接受的轉折(冷卻起點)
    return ev, st

STATS = {   # 2009-07~2026-09、259 檔美股(使用者追蹤清單中的個股)、隔日開盤進場;研究腳本見專案文件
    "trim": {"n": 1723, "down20": 54.2, "base_down20": 43.6, "down40": 54.5, "base_down40": 41.5,
             "mu20": -2.2, "base_mu20": 1.1, "mu40": -3.1, "base_mu40": 2.3, "dd40": 63.2, "base_dd40": 38.8,
             "p1": "2009-17:20日後較低 47%(平常41%)、40日內跌≥10% 48%(平常30%)",
             "p2": "2018-26:20日後較低 57%(平常46%)、40日內跌≥10% 69%(平常45%)",
             "ai": "AI/半導體子集:40日後較低 51%(平常40%)、40日內跌≥10% 59%(平常44%);20日方向優勢小"},
    "buy": {"n": 1251, "up20": 58.9, "base_up20": 56.2, "up40": 70.4, "base_up40": 58.4,
            "mu20": 3.6, "base_mu20": 1.1, "mu40": 9.6, "base_mu40": 2.3, "dd40": 51.4, "base_dd40": 38.8,
            "p1": "2009-17:40日後較高 65%(平常62%)、平均 +3.3%(平常 +2.7%)— 優勢小",
            "p2": "2018-26:40日後較高 73%(平常56%)、平均 +12.6%(平常 +1.9%)",
            "ai": "AI/半導體子集:40日後較高 72%(平常60%)、平均 +8.0%(平常 +3.8%)"},
    "raw": "同樣的轉折若不看氣候:減碼 20日後較低 46%(平常44%)、抄底 40日後較高 58%(平常58%)≈擲硬幣",
    "climate": {"le20": {"up20": 49.5, "mu20": -0.85, "dd20": 34.2}, "20_35": {"up20": 55.9, "mu20": 0.45, "dd20": 27.9},
                "35_65": {"up20": 57.8, "mu20": 1.29, "dd20": 24.2}, "65_80": {"up20": 55.5, "mu20": 1.41, "dd20": 25.7},
                "ge80": {"up20": 61.2, "mu20": 2.58, "dd20": 23.7}, "all": {"up20": 56.1, "mu20": 1.05, "dd20": 27.1}},
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/flow_climate.json")
    ap.add_argument("--config", default=None)
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--dump-series", default=None, help="(驗證用)輸出完整逐日序列 JSON")
    a = ap.parse_args()
    t0 = time.time(); dq = []
    spy = yahoo("SPY"); cal = sorted(d for d in spy if d >= START)
    log("calendar", cal[0], "→", cal[-1], len(cal))
    need = {"fvx": "^FVX", "dxy": "DX-Y.NYB", "spx": "^GSPC", "ndx": "^NDX", "vix": "^VIX", "vix3m": "^VIX3M", "vix9d": "^VIX9D",
            "tnx": "^TNX", "oil": "CL=F", "gold": "GC=F", "silver": "SI=F", "copper": "HG=F", "hyg": "HYG", "ief": "IEF", "jpy": "JPY=X"}
    raw = {}
    with cf.ThreadPoolExecutor(6) as ex:
        futs = {ex.submit(yahoo, s): k for k, s in need.items()}
        for f in cf.as_completed(futs):
            k = futs[f]
            try: raw[k] = f.result(); dq.append({"src": "yahoo " + need[k], "ok": True, "last": max(raw[k]) if raw[k] else None})
            except Exception as e: raw[k] = {}; dq.append({"src": "yahoo " + need[k], "ok": False, "err": str(e)[:80]})
    S = {k: align(cal, v) for k, v in raw.items()}
    S["oil"] = [x if (not isnan(x) and x > 1) else NAN for x in S["oil"]]
    # ① 日圓套利擁擠度(CFTC 交易商淨部位 z;週二部位 → 6 天後(下週一)起才使用,與回測同口徑)
    try:
        cds, cs, cz, crow = cot_yen()
        zmap = {}
        for d, z in zip(cds, cz):
            zmap[(datetime.date.fromisoformat(d) + datetime.timedelta(days=6)).isoformat()] = z
        cot_z = align(cal, zmap, limit=10)
        j = last_valid(cot_z)
        if j is not None and j < len(cal) - 1 and len(cal) - 1 - j <= 40:
            # CFTC 停更(例:2025-10 美國政府關門,COT 停發 6 週)→ 日圓分量沿用最後一份報告(最多 40 交易日),並在 dq 註記
            for k in range(j + 1, len(cal)): cot_z[k] = cot_z[j]
            dq.append({"src": "cftc yen TFF", "ok": False, "err": "COT 停更:沿用 %s 報告(%d 交易日)" % (cds[-1], len(cal) - 1 - j)})
        cot_last = {"report": cds[-1], "net_oi": r1(cs[-1] * 100, 1), "z": r1(cz[-1], 2)}
        dq.append({"src": "cftc yen TFF", "ok": True, "last": cds[-1]})
    except Exception as e:
        cot_z = [NAN] * len(cal); cot_last = None; dq.append({"src": "cftc yen TFF", "ok": False, "err": str(e)[:80]})
    fvx20 = chg(S["fvx"], 20, 100.0)
    cdx = cta_pos(S["dxy"])
    yen = [1 - v if not isnan(v) else NAN for v in roll_rank(cot_z)]
    rate = [1 - v if not isnan(v) else NAN for v in roll_rank(fvx20)]
    usd = [1 - v if not isnan(v) else NAN for v in roll_rank(cdx)]
    fin = [(r + u) / 2 if not (isnan(r) or isnan(u)) else NAN for r, u in zip(rate, usd)]
    A = [(y + f) / 2 if not (isnan(y) or isnan(f)) else NAN for y, f in zip(yen, fin)]
    clim = roll_rank(A)
    li = last_valid(clim)
    if li is None or cal[li] < cal[-1] and (datetime.date.fromisoformat(cal[-1]) - datetime.date.fromisoformat(cal[li])).days > 10:
        # 氣候算不出來(多半是 CFTC/Yahoo 暫時失敗)→ 不覆寫舊檔,讓前端沿用上一份(fail-safe)
        log("climate unavailable (last valid", cal[li] if li is not None else None, ") → keep previous file; dq:", dq)
        sys.exit(2)
    log("climate last", cal[li], round(clim[li] * 100, 1), "%.0fs" % (time.time() - t0))
    if a.dump_series:
        json.dump({"d": cal, "clim": clim, "yen": yen, "rate": rate, "usd": usd, "cot_z": cot_z, "fvx20": fvx20, "cta_dxy": cdx},
                  open(a.dump_series, "w"))
    # ---- 參考面板(只顯示,不計分) ----
    ctx = {}
    try:
        cspx = cta_pos(S["spx"]); cndx = cta_pos(S["ndx"]); vc = volctl(S["spx"])
        rs, rn, rv = roll_rank(cspx), roll_rank(cndx), roll_rank(vc)
        i = last_valid(cspx)
        ctx["cta"] = {"spx": r1(cspx[i], 2), "spx_pct": r1(rs[i] * 100, 0), "ndx": r1(cndx[i], 2), "ndx_pct": r1(rn[i] * 100, 0),
                      "flip_spx_1m": r1(S["spx"][i - 20], 0) if i >= 20 else None}
        j = last_valid(vc); ctx["volctl"] = {"exposure": r1(vc[j], 2), "pct": r1(rv[j] * 100, 0)}
    except Exception as e: dq.append({"src": "ctx cta/volctl", "ok": False, "err": str(e)[:80]})
    try:
        i = last_valid(S["vix"])
        ctx["vix"] = {"vix": r1(S["vix"][i], 2), "vix3m": r1(S["vix3m"][i], 2), "vix9d": r1(S["vix9d"][i], 2),
                      "ratio": r1(S["vix"][i] / S["vix3m"][i], 3) if not isnan(S["vix3m"][i]) else None,
                      "ratio9": r1(S["vix9d"][i] / S["vix"][i], 3) if not isnan(S["vix9d"][i]) else None}
    except Exception as e: dq.append({"src": "ctx vix", "ok": False, "err": str(e)[:80]})
    try:
        dg = dix_gex(); dd = sorted(dg)
        dixs = [dg[d][0] for d in dd]; gexs = [dg[d][1] for d in dd]
        dix5 = [sum(dixs[max(0, k - 4):k + 1]) / len(dixs[max(0, k - 4):k + 1]) for k in range(len(dixs))]
        ctx["gexdix"] = {"date": dd[-1], "dix": r1(dixs[-1] * 100, 1), "dix5_pct": r1(roll_rank(dix5, 504, 126)[-1] * 100, 0),
                         "gex_bn": r1(gexs[-1] / 1e9, 2), "gex_pct": r1(roll_rank(gexs, 504, 126)[-1] * 100, 0)}
        dq.append({"src": "squeezemetrics DIX/GEX", "ok": True, "last": dd[-1]})
    except Exception as e: dq.append({"src": "squeezemetrics DIX/GEX", "ok": False, "err": str(e)[:80]})
    def pc20(k):
        x = S.get(k); i = last_valid(x) if x else None
        if i is None or i < 20 or isnan(x[i - 20]): return None
        return r1((x[i] / x[i - 20] - 1) * 100, 1)
    i = last_valid(S["tnx"])
    ctx["macro"] = {"tnx": r1(S["tnx"][i], 2), "tnx_chg20_bp": r1((S["tnx"][i] - S["tnx"][i - 20]) * 100, 0),
                    "oil_20d": pc20("oil"), "gold_20d": pc20("gold"), "silver_20d": pc20("silver"), "copper_20d": pc20("copper"),
                    "jpy_20d": pc20("jpy"), "dxy_20d": pc20("dxy")}
    try:
        h = S["hyg"]; f_ = S["ief"]; i = last_valid(h)
        ctx["macro"]["hyg_ief_20d"] = r1((math.log(h[i] / f_[i]) - math.log(h[i - 20] / f_[i - 20])) * 100, 2)
    except Exception: pass
    # ---- 輸出 ----
    k0 = next(k for k, d in enumerate(cal) if d >= SERIES_FROM)
    pc = lambda v: None if isnan(v) else int(round(v * 100))
    ser = {"d": cal[k0:li + 1], "c": [pc(v) for v in clim[k0:li + 1]], "y": [pc(v) for v in yen[k0:li + 1]],
           "r": [pc(v) for v in rate[k0:li + 1]], "u": [pc(v) for v in usd[k0:li + 1]]}
    lab = lambda v: ("寬鬆" if v >= 80 else "偏寬" if v >= 65 else "中性" if v > 35 else "偏緊" if v > 20 else "緊縮")
    cnow = pc(clim[li])
    now = {"date": cal[li], "climate": cnow, "label": lab(cnow), "yen": pc(yen[li]), "rate": pc(rate[li]), "usd": pc(usd[li]),
           "raw": {"cot": cot_last, "fvx": r1(S["fvx"][li], 3), "fvx_chg20_bp": r1(fvx20[li], 1), "dxy": r1(S["dxy"][li], 2), "dxy_trend": r1(cdx[li], 2)},
           "ctx": ctx}
    out = {"updated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "version": "fc-2026-10-09", "th": TH, "series": ser, "now": now, "stats": STATS, "dq": dq}
    # ---- 全宇宙掃描(近 5 個交易日 ▲▼ + 待確認) ----
    if a.scan and a.config:
        try:
            out["scan"] = scan(a.config, ser, cal)
        except Exception as e:
            dq.append({"src": "scan", "ok": False, "err": str(e)[:100]})
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(out, open(a.out, "w"), ensure_ascii=False, separators=(",", ":"))
    log("wrote", a.out, os.path.getsize(a.out), "bytes", "%.0fs" % (time.time() - t0))

def scan(cfg_path, ser, cal):
    cfg = json.load(open(cfg_path)); mdu = cfg["market_data_url"]; base = mdu.rsplit("/", 1)[0] + "/"
    md = http(mdu + "?t=%d" % time.time(), timeout=60)
    uni = []
    for s in (list(md.get("kline_today") or {}) + list(md.get("ext_universe") or []) + [k.replace("US.", "") for k in (md.get("capital_flow") or {})]):
        s = str(s).strip().upper()
        if s and s not in uni: uni.append(s)
    cm = {d: c / 100 for d, c in zip(ser["d"], ser["c"]) if c is not None}
    lastc = [c for c in ser["c"] if c is not None][-1] / 100; lastd = ser["d"][-1]
    def clim_of(d): return cm.get(d, lastc if d > lastd else None)
    def one(s):
        try: bars = (http(base + "kline_%s.json" % s, timeout=30) or {}).get("bars") or []
        except Exception: return s, None
        bars = [b for b in bars if b and b[4]]
        if len(bars) < 70: return s, None
        D = [b[0] for b in bars]; C = [float(b[4]) for b in bars]
        ev, st = fc_events(D, C, clim_of)
        return s, (D, C, ev, st)
    res = {}
    with cf.ThreadPoolExecutor(8) as ex:
        for s, r in ex.map(one, uni): res[s] = r
    recent_from = cal[-5]
    buy, trim, wtrim, wbuy = [], [], [], []
    for s, r in res.items():
        if not r: continue
        D, C, ev, st = r; n = len(C) - 1
        for e in ev:
            if e["d"] >= recent_from:
                (buy if e["k"] == "buy" else trim).append({"s": s, "d": e["d"], "c": round(e["c"], 2), "clim": int(round(e["clim"] * 100))})
        cl = clim_of(D[n])
        if cl is None: continue
        s20 = st["s20"][n]; ex_, dp = st["ext"][n], st["dip"][n]
        if not isnan(s20):
            if cl <= TH["trim"] and not isnan(ex_) and ex_ >= TH["ext"] and C[n] >= s20 and (n + 1 - st["lt"]) > TH["cool"]:
                wtrim.append({"s": s, "px": round(C[n], 2), "s20": round(s20, 2), "gap": round((C[n] / s20 - 1) * 100, 1), "ext": round(ex_ * 100, 0)})
            if cl >= TH["buy"] and not isnan(dp) and dp <= -TH["dip"] and C[n] <= s20 and (n + 1 - st["lb"]) > TH["cool"]:
                wbuy.append({"s": s, "px": round(C[n], 2), "s20": round(s20, 2), "gap": round((C[n] / s20 - 1) * 100, 1), "dip": round(dp * 100, 0)})
    wtrim.sort(key=lambda x: x["gap"]); wbuy.sort(key=lambda x: -x["gap"])
    # 標記 ETF/槓桿 ETF(前端排在個股之後);只查名單內的少數代號
    tag = {}
    syms = sorted({e["s"] for e in buy + trim} | {w["s"] for w in wtrim[:40] + wbuy[:40]})
    def meta(sym):
        try:
            m = http("https://query1.finance.yahoo.com/v8/finance/chart/%s?range=5d&interval=1d" % urllib.parse.quote(sym), timeout=20, retries=2)["chart"]["result"][0]["meta"]
            return sym, m.get("instrumentType")
        except Exception: return sym, None
    with cf.ThreadPoolExecutor(8) as ex:
        for sym, t in ex.map(meta, syms): tag[sym] = t
    for lst in (buy, trim, wtrim, wbuy):
        for e in lst:
            if tag.get(e["s"]) == "ETF": e["etf"] = 1
    return {"universe": len(uni), "loaded": sum(1 for v in res.values() if v), "since": recent_from,
            "buy": sorted(buy, key=lambda x: x["d"], reverse=True), "trim": sorted(trim, key=lambda x: x["d"], reverse=True),
            "watch_trim": wtrim[:40], "watch_buy": wbuy[:40]}

if __name__ == "__main__":
    main()
