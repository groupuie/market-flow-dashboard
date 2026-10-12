#!/usr/bin/env python3
# 🧪 Astra 擴大範圍(2026-10-12;使用者 12:14「至少可以看 SPY500、QQQ100、每日成交金額前 100,主要鎖定 AI 軟硬體」,
#   13:xx 選「開始做」「底/回 加上強」「200 日線上限圖上也標出來」)
#
# 每天收盤後由 GitHub Actions(.github/workflows/astra-data.yml)跑,只寫 astra-data 分支(force-push 單一 commit):
#   k/<SYM>.json  每檔最近 1250 根還原日K(格式同 gist kline_*.json)→ 網站搜尋不在追蹤清單的股票也看得到K線與 Astra 記號
#   regime.json   大盤恐慌(第 6 輪 D18 通過的 3 個:造市商負 gamma、寬度差、信用轉弱)+ QQQ/SPY 200 日線
#   today.json    最近 10 個交易日出現 ▲底 △回 ▼頂 的股票(附強/一般、AI 族群)→ 網站「🧪 Astra 訊號」分頁
#   uni.json      名單(S&P 500、Nasdaq-100、成交金額前 100、AI 硬體/軟體)
#   meta.json     這次跑的紀錄
# 不動 main、不動 data 分支(public-collect)、不動 Mac / gist。只用標準函式庫(Actions 不必裝套件)。
#
# 規則(都和研究同式;研究檔在 research/):
#   ▲底 ▼頂 △回 = 網站 swSeriesJS(index.html)逐行照抄(算術順序也照抄 → 與瀏覽器算出來逐位元相同);
#     = research/swing_tune_2026-10-12/s4_lib.py swing + B2
#   日K = Yahoo 還原(股利+分割;開高低乘 還原收盤/收盤)= s4_lib.load
#   強(只給 底/回)= 下面 3 個至少 2 個成立(research/regime_factors_2026-10-12/p6_prereg.md §3 合併規則、r6_factors.py):
#     F15 前一天 GEX < 0(SqueezeMetrics DIX.csv;造市商負 gamma)
#     F9 不成立:全部個股站上 50 日線的比例 < 40%,而且沒有比 5 天前高(寬度差)
#     F6 HYG ÷ IEF(還原收盤)收在 60 日最低(信用轉弱)
#   200 日線 = QQQ、SPY 還原收盤 vs 200 日均線(第 6 輪 D20 S6;沒通過預先登記,網站只當「可以選」的提示)
#
# 用法:python3 scripts/astra_data.py --out DIR [--max N] [--cache DIR] [--asof YYYY-MM-DD]
import argparse, concurrent.futures as cf, datetime as dt, gzip, html.parser, json, math, os, re, sys, time
import urllib.error, urllib.parse, urllib.request
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
WIKI_UA = "market-flow-dashboard/1.0 (+https://github.com/groupuie/market-flow-dashboard)"
YH_H = {"User-Agent": "Mozilla/5.0"}   # Yahoo:完整瀏覽器 UA 會被 429(2026-10-12 實測),短 UA 正常(同 f0_fetch / nightly-engine)
NAS_H = {"User-Agent": UA, "Accept": "application/json, text/plain, */*", "Accept-Language": "en-US,en;q=0.9",
         "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"}
PUB = "https://raw.githubusercontent.com/groupuie/market-flow-dashboard/astra-data/"
KEEP = 1250          # 每檔發布的日K根數(= gist kline_*.json 的長度)
REG_KEEP = 1400      # regime.json 的天數(涵蓋 1250 根視窗)
LIST_DAYS = 10       # today.json 收最近幾個交易日的訊號
FETCH_DAYS = 2300    # 抓多少日曆天(≈ 6.3 年:1250 根 + 寬度要的 50 日線 + 260 根門檻)
COOL = 5             # 同邊冷卻(根)
MAG7 = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA"]
AI_HW = {   # research/regime_factors_2026-10-12/p6_prereg.md §4
    "半導體": "NVDA AMD AVGO QCOM MRVL ARM INTC TXN ADI MCHP NXPI ON MPWR TSM ASML AMAT LRCX KLAC TER ENTG AMKR GFS SWKS QRVO MTSI SNPS CDNS",
    "記憶體與儲存": "MU WDC STX SNDK PSTG NTAP",
    "網通與光通訊": "ANET CSCO CIEN COHR LITE AAOI GLW CRDO ALAB",
    "伺服器": "DELL SMCI HPE",
    "電力與基建": "VRT ETN GEV CEG VST NRG TLN OKLO PWR"}
AI_SW = {
    "雲端巨頭": "MSFT GOOGL AMZN META ORCL",
    "AI 軟體、資料、資安": "PLTR NOW CRM SNOW DDOG MDB CRWD PANW ZS NET APP ADBE INTU WDAY TEAM AI SOUN PATH U IOT GTLB ESTC OKTA S TWLO HUBS",
    "新雲與算力": "CRWV NBIS IREN CIFR APLD CORZ WULF"}
# Wikipedia 改版抓不到 Nasdaq-100 表時用(2026-10-12 版,101 檔)
NDX_FALLBACK = ("AAPL ABNB ADBE ADI ADP ADSK AEP ALAB ALNY AMAT AMD AMGN AMZN APP ARM ASML AVGO AXON BKNG BKR CCEP CDNS CEG CMCSA COST CPRT "
                "CRWD CRWV CSCO CSX CTAS DASH DDOG DXCM EXC FANG FAST FER FTNT GEHC GILD GOOG GOOGL HON HONA IDXX INTC INTU ISRG KDP KLAC LIN LITE "
                "LRCX MAR MCHP MDLZ MELI META MNST MPWR MRNA MRVL MSFT MSTR MU NBIS NFLX NVDA NXPI ODFL ORLY PANW PAYX PCAR PDD PEP PLTR PYPL QCOM "
                "REGN RKLB ROP ROST SBUX SHOP SNDK SNPS SPCX STX TER TMUS TRI TSLA TTWO TXN VRTX WDAY WDC WMT XEL").split()
INDEX = ["SPY", "QQQ"]
MACRO = ["HYG", "IEF"]          # 信用(只內部用,不發布)
SYM_RE = re.compile(r"[A-Z][A-Z0-9\-]{0,6}")
T0 = time.time()
LOG = {"warn": []}


def log(*a):
    print(f"[{time.time() - T0:5.0f}s]", *a, flush=True)


def http_get(url, timeout=30, retries=3, hdr=None, no_retry=(400, 401, 403, 404)):
    last = None
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers=dict(hdr or {"User-Agent": UA}, **{"Accept-Encoding": "gzip"}))
            with urllib.request.urlopen(req, timeout=timeout) as r:
                b = r.read()
                return gzip.decompress(b) if r.headers.get("Content-Encoding") == "gzip" else b
        except urllib.error.HTTPError as e:
            last = e
            if e.code in no_retry: break
        except Exception as e:
            last = e
        time.sleep(1.5 * (a + 1) ** 2)
    raise last


# ---------------------------------------------------------------- 名單
class _Table(html.parser.HTMLParser):   # 抓 <table id=...> 第一層的列(不靠 pandas)
    def __init__(self, tid):
        super().__init__(); self.tid = tid; self.depth = 0; self.rows = []; self.cur = None; self.cell = None; self.on = False

    def handle_starttag(self, tag, a):
        if tag == "table":
            if self.on: self.depth += 1
            elif dict(a).get("id") == self.tid: self.on = True; self.depth = 1
        if not self.on or self.depth != 1: return
        if tag == "tr": self.cur = []
        elif tag in ("td", "th") and self.cur is not None: self.cell = []
        elif tag == "br" and self.cell is not None: self.cell.append(" ")

    def handle_endtag(self, tag):
        if not self.on: return
        if tag == "table":
            self.depth -= 1
            if self.depth == 0: self.on = False
            return
        if self.depth != 1: return
        if tag in ("td", "th") and self.cell is not None:
            self.cur.append(re.sub(r"\s+", " ", "".join(self.cell)).strip()); self.cell = None
        elif tag == "tr" and self.cur is not None:
            if self.cur: self.rows.append(self.cur)
            self.cur = None

    def handle_data(self, d):
        if self.cell is not None: self.cell.append(d)


def wiki_rows(page):
    last = None
    for ua in (WIKI_UA, UA):
        try:
            t = _Table("constituents"); t.feed(http_get("https://en.wikipedia.org/wiki/" + page, 60, 3, {"User-Agent": ua}).decode("utf-8", "ignore"))
            if len(t.rows) > 50: return t.rows
            last = RuntimeError("table too small " + page)
        except Exception as e:
            last = e
    raise last


def col(hdr, *names):
    for n in names:
        for i, h in enumerate(hdr):
            if re.sub(r"\[.*?\]", "", h).strip().lower() == n.lower(): return i
    return None


def ysym(s):
    return str(s).strip().upper().replace(".", "-").replace("/", "-").replace("^", "-")


def get_sp500():
    R = wiki_rows("List_of_S%26P_500_companies"); h = R[0]
    i, n, se, su = col(h, "Symbol"), col(h, "Security"), col(h, "GICS Sector"), col(h, "GICS Sub-Industry")
    out = {}
    for r in R[1:]:
        if len(r) <= max(i, n, se, su): continue
        s = ysym(r[i])
        if SYM_RE.fullmatch(s): out[s] = {"n": r[n], "sec": r[se], "sub": r[su]}
    if len(out) < 480: raise RuntimeError(f"S&P 500 只有 {len(out)} 檔")
    return out


def get_ndx():
    R = wiki_rows("List_of_NASDAQ-100_companies"); h = R[0]
    i, n, se = col(h, "Ticker", "Symbol"), col(h, "Company", "Security"), col(h, "ICB Industry", "GICS Sector")
    out = {}
    for r in R[1:]:
        if i is None or len(r) <= i: continue
        s = ysym(r[i])
        if SYM_RE.fullmatch(s): out[s] = {"n": r[n] if n is not None and len(r) > n else "", "sec": r[se] if se is not None and len(r) > se else ""}
    if len(out) < 95: raise RuntimeError(f"Nasdaq-100 只有 {len(out)} 檔")
    return out


def get_top(k=100):
    j = json.loads(http_get("https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&download=true", 60, 3, NAS_H))
    def num(x):
        try: return float(str(x).replace("$", "").replace(",", ""))
        except Exception: return float("nan")
    rows = []
    for r in j["data"]["rows"]:
        s = ysym(r.get("symbol", ""))
        if not SYM_RE.fullmatch(s): continue
        dv = num(r.get("lastsale")) * num(r.get("volume"))
        if dv == dv: rows.append((dv, s, r.get("name", ""), r.get("sector", "")))
    rows.sort(reverse=True)
    if len(rows) < 1000: raise RuntimeError(f"Nasdaq 篩選器只有 {len(rows)} 檔")
    return [(s, {"n": nm, "sec": se, "dv": round(dv / 1e6, 1)}) for dv, s, nm, se in rows[:k]]


def prev_uni():
    try: return json.loads(http_get(PUB + "uni.json", 30, 2))
    except Exception: return None


# ---------------------------------------------------------------- 日K
def last_done(now=None):   # 最近已收盤的美東交易日(16:15 後當天才算;假日 Yahoo 本來就沒有那根)
    now = now or dt.datetime.now(ET); d = now.date()
    if (now.hour, now.minute) < (16, 15): d -= dt.timedelta(days=1)
    while d.weekday() >= 5: d -= dt.timedelta(days=1)
    return d.isoformat()


def yahoo(sym, p1, p2, cache=None):
    raw = None; cf_ = os.path.join(cache, sym + ".json") if cache else None
    if cf_ and os.path.exists(cf_) and time.time() - os.path.getmtime(cf_) < 12 * 3600:
        raw = open(cf_, "rb").read()
    if raw is None:
        q = f"?period1={p1}&period2={p2}&interval=1d&events=div%2Csplit&includeAdjustedClose=true"
        err = None
        for host in ("query1", "query2"):
            try:
                raw = http_get(f"https://{host}.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}{q}", 30, 3, YH_H); break
            except Exception as e:
                err = e
        if raw is None: raise err
        if cf_: open(cf_, "wb").write(raw)
    r = json.loads(raw)["chart"]["result"][0]
    ts = r.get("timestamp") or []
    if not ts: return []
    qd = r["indicators"]["quote"][0]; adj = ((r["indicators"].get("adjclose") or [{}])[0]).get("adjclose")
    tz = ZoneInfo(r["meta"].get("exchangeTimezoneName") or "America/New_York")
    rows = {}
    for i, t in enumerate(ts):
        c = qd["close"][i]
        if c is None or not (c > 0): continue
        ac = adj[i] if (adj and i < len(adj) and adj[i] is not None) else c
        f = ac / c
        def fx(v):
            return v * f if (v is not None and v > 0) else None
        o, h, l = fx(qd["open"][i]), fx(qd["high"][i]), fx(qd["low"][i])
        o = ac if o is None else o; h = ac if h is None else h; l = ac if l is None else l
        rows[dt.datetime.fromtimestamp(t, tz).strftime("%Y-%m-%d")] = (o, max(h, o, ac), min(l, o, ac), ac, int(qd["volume"][i] or 0))
    return sorted((d,) + v for d, v in rows.items())


def rp(x):   # 發布用的價格位數(同 gist:3 位;< 1 元留 5 位)
    return round(x, 3) if abs(x) >= 1 else round(x, 5)


# ---------------------------------------------------------------- Astra 底/頂/回(= index.html swSeriesJS,逐行照抄)
def js_round(x):
    return math.floor(x + 0.5)


def sw_series(B):
    n = len(B); D = [b[0] for b in B]; O = [b[1] for b in B]; H = [b[2] for b in B]; L = [b[3] for b in B]; C = [b[4] for b in B]
    r2 = [None] * n
    if n >= 4:
        ag = 0.0; al = 0.0
        for i in (1, 2):
            d = C[i] - C[i - 1]; ag += max(d, 0); al += max(-d, 0)
        ag /= 2; al /= 2
        r2[2] = 100 if al == 0 else 100 - 100 / (1 + ag / al)
        for i in range(3, n):
            d = C[i] - C[i - 1]; ag = (ag + max(d, 0)) / 2; al = (al + max(-d, 0)) / 2
            r2[i] = 100 if al == 0 else 100 - 100 / (1 + ag / al)
    lo = [None] * n; up = [None] * n
    for i in range(19, n):
        m = 0.0
        for k in range(i - 19, i + 1): m += C[k]
        m /= 20
        v = 0.0
        for k in range(i - 19, i + 1): v += (C[k] - m) * (C[k] - m)
        sd = math.sqrt(v / 20); lo[i] = m - 2 * sd; up[i] = m + 2 * sd
    tb = [0] * n; ts = [0] * n
    for i in range(4, n):
        tb[i] = tb[i - 1] + 1 if C[i] < C[i - 4] else 0
        ts[i] = ts[i - 1] + 1 if C[i] > C[i - 4] else 0

    def os_(i):
        w = []
        if r2[i] is not None and r2[i] <= 10: w.append("RSI2 " + str(js_round(r2[i])))
        if lo[i] is not None and C[i] <= lo[i]: w.append("碰布林下緣")
        if tb[i] == 9: w.append("九轉買9")
        return w

    def ob_(i):
        w = []
        if r2[i] is not None and r2[i] >= 90: w.append("RSI2 " + str(js_round(r2[i])))
        if up[i] is not None and C[i] >= up[i]: w.append("碰布林上緣")
        if ts[i] == 9: w.append("九轉賣9")
        return w

    def uniq(a):
        out = []
        for x in a:
            if x not in out: out.append(x)
        return out
    bot, top, why = [], [], {}; lb = lt = -10 ** 9
    for i in range(2, n):
        wb = uniq(os_(i) + os_(i - 1) + os_(i - 2)); wt = uniq(ob_(i) + ob_(i - 1) + ob_(i - 2))
        if wb and C[i] > H[i - 1] and i - lb > COOL: lb = i; bot.append(i); why[i] = "、".join(wb)
        if wt and C[i] < L[i - 1] and i - lt > COOL: lt = i; top.append(i); why[i] = "、".join(wt)
    b2, m200 = [], {}; l2 = -10 ** 9
    for i in range(199, n):
        s = 0.0
        for k in range(i - 199, i + 1): s += C[k]
        m = s / 200; mn = math.inf
        for k in range(i - 6, i + 1):
            if C[k] < mn: mn = C[k]
        if C[i] > m and C[i] <= mn and i - l2 > COOL: l2 = i; b2.append(i); m200[i] = m
    buys = sorted(bot + b2); rep = {}
    for t in buys:
        best = 0
        for s_ in buys:
            if s_ < t - 20 or s_ >= t: continue
            if C[t] < L[s_] and rep[s_] > best: best = rep[s_]
        rep[t] = best + 1
    return {"n": n, "D": D, "C": C, "H": H, "L": L, "bot": bot, "top": top, "b2": b2, "m200": m200, "why": why, "rep": rep}


# ---------------------------------------------------------------- 大盤背景值(= r6_factors.py F15 / F9 / F6;D20 的 200 日線)
def ffill_on(cal, ser, limit=5):   # = pandas ser.reindex(ser.index ∪ cal).ffill(limit).reindex(cal)
    keys = sorted(set(ser) | set(cal)); last = None; gap = 0; out = {}
    for k in keys:
        v = ser.get(k)
        if v is not None and v == v: last = v; gap = 0; out[k] = v
        else:
            gap += 1; out[k] = last if (last is not None and gap <= limit) else None
    return [out[d] for d in cal]


def sma(C, w):   # 全部有值才算(= pandas rolling(w).mean())
    n = len(C); out = [None] * n
    for i in range(w - 1, n):
        s = 0.0; ok = True
        for k in range(i - w + 1, i + 1):
            if C[k] is None: ok = False; break
            s += C[k]
        if ok: out[i] = s / w
    return out


def regime(cal, closes, stk, dix, hyg, ief):
    N = len(cal)
    # F15:前一天 GEX < 0
    gx = ffill_on(cal, dix, 5) if dix else [None] * N
    g = [None] + [None if gx[i - 1] is None else int(gx[i - 1] < 0) for i in range(1, N)]
    gprev = [None] + gx[:-1]
    # F9:寬度(站上 50 日線的比例 ≥ 40% 或比 5 天前高)→ 有利 = 不成立
    above = [0] * N; cnt = [0] * N
    for s in stk:
        c = closes[s]; run = 0.0; nn = 0
        for i in range(N):
            x = c[i]
            if x is None: nn += 1
            else: run += x
            if i >= 50:
                y = c[i - 50]
                if y is None: nn -= 1
                else: run -= y
            if i >= 49 and nn == 0:
                cnt[i] += 1; above[i] += int(x > run / 50)
    br = [above[i] / cnt[i] if cnt[i] > 50 else None for i in range(N)]
    f9 = [None if br[i] is None else int(br[i] >= 0.40 or (i >= 5 and br[i - 5] is not None and br[i] > br[i - 5])) for i in range(N)]
    b = [None if v is None else 1 - v for v in f9]
    # F6:HYG ÷ IEF 收在 60 日最低
    h_, i_ = ffill_on(cal, hyg, 5), ffill_on(cal, ief, 5)
    hi = [None if (h_[i] is None or i_[i] is None) else h_[i] / i_[i] for i in range(N)]
    c6 = [None] * N; mn60 = [None] * N
    for i in range(N):
        if hi[i] is None: continue
        if i >= 59 and all(hi[k] is not None for k in range(i - 59, i + 1)):
            mn60[i] = min(hi[i - 59:i + 1])
        c6[i] = int(mn60[i] is not None and hi[i] <= mn60[i] + 1e-12)
    sc = [int(g[i] == 1) + int(b[i] == 1) + int(c6[i] == 1) for i in range(N)]
    return {"g": g, "gx": gprev, "br": br, "b": b, "c": c6, "hi": hi, "mn60": mn60, "sc": sc}


# ---------------------------------------------------------------- 主程式
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True); ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--cache", default=""); ap.add_argument("--asof", default="")
    A = ap.parse_args()
    os.makedirs(os.path.join(A.out, "k"), exist_ok=True)
    if A.cache: os.makedirs(A.cache, exist_ok=True)
    asof = A.asof or last_done()
    gen = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    log("asof", asof)

    # 1. 名單(抓不到 → 用上一次發布的 uni.json;再不行 → 停,不發布)
    PU = None; src = {}
    try: SP = get_sp500(); src["sp500"] = "wikipedia"
    except Exception as e:
        PU = PU or prev_uni(); LOG["warn"].append("S&P 500 名單抓不到:" + str(e)[:120])
        if not PU: raise
        SP = {s: {"n": PU.get("names", {}).get(s, ""), "sec": PU.get("sec", {}).get(s, ""), "sub": ""} for s in PU["sp500"]}; src["sp500"] = "上一次"
    try: NQ = get_ndx(); src["ndx"] = "wikipedia"
    except Exception as e:
        PU = PU or prev_uni(); LOG["warn"].append("Nasdaq-100 名單抓不到:" + str(e)[:120])
        lst = (PU or {}).get("ndx") or NDX_FALLBACK; NQ = {s: {"n": "", "sec": ""} for s in lst}; src["ndx"] = "上一次" if PU else "內建"
    try: TOP = get_top(100); src["top100"] = "nasdaq"
    except Exception as e:
        PU = PU or prev_uni(); LOG["warn"].append("成交金額前 100 抓不到:" + str(e)[:120])
        TOP = [(s, {"n": "", "sec": "", "dv": None}) for s in ((PU or {}).get("top100") or [])]; src["top100"] = "上一次" if PU else "沒有"
    AIH = {k: v.split() for k, v in AI_HW.items()}; AIS = {k: v.split() for k, v in AI_SW.items()}
    names, sec = {}, {}
    for s, m in list(TOP) + list(NQ.items()) + list(SP.items()):   # 後面的蓋前面:S&P > NDX > 篩選器
        if m.get("n"): names[s] = m["n"]
        if m.get("sec"): sec[s] = m["sec"]
    ai = {}
    for g_, D_ in (("hw", AIH), ("sw", AIS)):
        for sub, L_ in D_.items():
            for s in L_: ai.setdefault(s, [g_, sub])
    U = sorted(set(SP) | set(NQ) | {s for s, _ in TOP} | set(ai) | set(INDEX))
    if A.max: U = sorted(set(INDEX) | set(MAG7) | set(U[:A.max]))
    log("名單", {"sp500": len(SP), "ndx": len(NQ), "top100": len(TOP), "ai": len(ai), "union": len(U)}, src)

    # 2. 日K(Yahoo 還原)
    now = int(time.time()); p1 = now - FETCH_DAYS * 86400
    BARS, FAIL = {}, {}
    def job(s):
        try: return s, yahoo(s, p1, now + 86400, A.cache or None), None
        except Exception as e: return s, None, str(e)[:100]
    with cf.ThreadPoolExecutor(8) as ex:
        for s, b, err in ex.map(job, U + MACRO):
            if err is not None or not b: FAIL[s] = err or "沒有資料"; continue
            b = [x for x in b if x[0] <= asof]
            if b: BARS[s] = b
            else: FAIL[s] = "沒有已收盤的K"
    log("日K", len(BARS), "檔;失敗", len(FAIL), list(FAIL.items())[:8])
    for s in INDEX + MACRO:
        if s not in BARS: raise SystemExit(f"{s} 抓不到 → 不發布(保留上一次)")
    if len([s for s in U if s in FAIL]) > 0.15 * len(U): raise SystemExit(f"失敗太多({len(FAIL)})→ 不發布")
    cal = [b[0] for b in BARS["SPY"]]
    if cal[-1] != asof: LOG["warn"].append(f"SPY 最後一根是 {cal[-1]},不是 {asof}")
    asof = cal[-1]; N = len(cal); CI = {d: i for i, d in enumerate(cal)}

    # 3. 大盤背景值
    dix = {}
    try:
        txt = http_get("https://squeezemetrics.com/monitor/static/DIX.csv", 60, 3).decode("utf-8", "ignore").splitlines()
        hd = [x.strip().lower() for x in txt[0].split(",")]; jd, jg = hd.index("date"), hd.index("gex")
        for line in txt[1:]:
            p = line.split(",")
            try: dix[p[jd].strip()[:10]] = float(p[jg]) if p[jg].strip() else None
            except Exception: pass
        src["gex"] = "squeezemetrics " + max(dix)
    except Exception as e:
        LOG["warn"].append("GEX 抓不到(這次『造市商負 gamma』都算不成立):" + str(e)[:100]); src["gex"] = "沒有"
    closes = {s: [None] * N for s in BARS}
    for s, b in BARS.items():
        c = closes[s]
        for x in b:
            i = CI.get(x[0])
            if i is not None: c[i] = x[4]
    stk = [s for s in U if s in BARS and s not in ("SPY", "QQQ", "GOOG") and len(BARS[s]) >= 260]
    RG = regime(cal, closes, stk, dix, {x[0]: x[4] for x in BARS["HYG"]}, {x[0]: x[4] for x in BARS["IEF"]})
    m2 = {k: sma(closes[k], 200) for k in INDEX}
    up2 = {k: [None if m2[k][i] is None or closes[k][i] is None else int(not closes[k][i] < m2[k][i]) for i in range(N)] for k in INDEX}   # = 1 − D20 的 off
    log("背景值", {"寬度檔數": len(stk), "最後": {"GEX前一天": RG["gx"][-1], "寬度": RG["br"][-1], "信用60日最低": RG["c"][-1], "分數": RG["sc"][-1]}})

    # 4. 每檔:發布日K + Astra 訊號(用發布的那 1250 根,和網站拿到的完全一樣)
    rows = []; kset = []; days = cal[-LIST_DAYS:]; dset = set(days)
    for s in U:
        b = BARS.get(s)
        if not b: continue
        pb = [[x[0], rp(x[1]), rp(x[2]), rp(x[3]), rp(x[4]), x[5]] for x in b[-KEEP:]]
        with open(os.path.join(A.out, "k", s + ".json"), "w") as fh: json.dump({"sym": s, "src": "yahoo-astra", "updated_utc": gen, "bars": pb}, fh, separators=(",", ":"))
        kset.append(s)
        if len(pb) < 30: continue
        W = sw_series(pb)
        for kind, arr in (("底", W["bot"]), ("回", W["b2"]), ("頂", W["top"])):
            for j in arr:
                d = W["D"][j]
                if d not in dset: continue
                ri = CI.get(d); sc = RG["sc"][ri] if ri is not None else None
                rows.append({"s": s, "d": d, "k": kind, "c": W["C"][j], "chg": round(100 * (W["C"][j] / W["C"][j - 1] - 1), 2) if j else None,
                             "dv": round(W["C"][j] * pb[j][5] / 1e6, 1), "rep": W["rep"].get(j, 1) if kind != "頂" else None,
                             "st": (None if sc is None else int(sc >= 2)) if kind != "頂" else None, "why": W["why"].get(j, "") if kind != "回" else "",
                             "m200": round(W["m200"][j], 3) if kind == "回" else None})
    rows.sort(key=lambda r: (r["d"], r["dv"] or 0), reverse=True)

    # 5. 寫檔
    def J(o, f):
        with open(os.path.join(A.out, f), "w", encoding="utf-8") as fh: json.dump(o, fh, ensure_ascii=False, separators=(",", ":"))
    a0 = max(0, N - REG_KEEP); R1 = lambda v, k: None if v is None else round(v, k)
    J({"asof": asof, "gen": gen, "d": cal[a0:], "sc": RG["sc"][a0:], "g": RG["g"][a0:], "b": RG["b"][a0:], "c": RG["c"][a0:],
       "gx": [R1(v / 1e9 if v is not None else None, 2) for v in RG["gx"][a0:]], "br": [R1(v, 3) for v in RG["br"][a0:]],
       "hi": [R1(v, 5) for v in RG["hi"][a0:]], "hm": [R1(v, 5) for v in RG["mn60"][a0:]],
       "q": up2["QQQ"][a0:], "s": up2["SPY"][a0:], "qc": [R1(v, 2) for v in closes["QQQ"][a0:]], "qm": [R1(v, 2) for v in m2["QQQ"][a0:]],
       "sc_": [R1(v, 2) for v in closes["SPY"][a0:]], "sm": [R1(v, 2) for v in m2["SPY"][a0:]], "nb": len(stk),
       "rule": "強 = 3 個至少 2 個:前一天 GEX<0、站上 50 日線 <40% 且沒比 5 天前多、HYG/IEF 60 日最低(第 6 輪 D18)"}, "regime.json")
    J({"asof": asof, "gen": gen, "days": days[::-1], "n": len(kset), "rows": rows}, "today.json")
    J({"asof": asof, "gen": gen, "sp500": sorted(SP), "ndx": sorted(NQ), "top100": [s for s, _ in TOP],
       "top100_dv": {s: m.get("dv") for s, m in TOP}, "ai": ai, "ai_hw": AIH, "ai_sw": AIS, "mag7": MAG7, "names": names, "sec": sec,
       "k": kset, "src": src}, "uni.json")
    J({"gen": gen, "asof": asof, "n_union": len(U), "n_k": len(kset), "n_rows": len(rows), "fail": FAIL, "warn": LOG["warn"], "src": src,
       "sec": round(time.time() - T0)}, "meta.json")
    log("完成", {"k": len(kset), "訊號列": len(rows), "失敗": len(FAIL), "警告": LOG["warn"]})


if __name__ == "__main__":
    main()
