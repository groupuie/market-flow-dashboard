#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全市場資金部位採集器(在【你的 Mac】執行;家用網路無雲端防火牆,能連 Futu + 所有公開源)
輸出兩個檔到同一個 gist:
  - market_data.json : 給即時 HTML 儀表板讀(大盤/個股/槓桿ETF/期權/FX/國債/加密/大宗/暗池proxy)
  - futu_snapshot.json: 給雲端排程讀(第三層⑦大單淨流,維持相容)
只讀行情、永不下單、永不 unlock_trade。
用法:python market_export.py --config config.json   [--no-futu] [--no-push] [--force-options]
"""
import json, sys, os, time, argparse, math, urllib.request, urllib.parse
from datetime import datetime, timezone

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
ERRORS = []
def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)
def err(tag, e): ERRORS.append(f"{tag}: {type(e).__name__} {str(e)[:80]}")

def http_get(url, timeout=15, retries=3, headers=None):
    req = urllib.request.Request(url, headers=headers or UA)
    last = None
    for a in range(retries):
        try:
            return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            last = e
            time.sleep((3.0 if e.code == 429 else 0.5)*(a+1))   # 429 拉長退避
        except Exception as e:
            last = e; time.sleep(0.5*(a+1))
    raise last
def http_json(url, timeout=15, retries=3): return json.loads(http_get(url, timeout, retries))

# ============ 觀察清單 ============
WL = {
  "market":    ["SPY","QQQ","DIA","IWM"],
  "stocks":    ["NVDA","MSFT","AAPL","AMZN","META","AVGO","GOOGL","TSLA","JPM","LLY",
                "MU","SNDK","WDC","MRVL","LITE","COHR","AAOI","SMH","SOXX",
                "AMD","PLTR","COIN","MSTR","NFLX","INTC","ORCL","TSM"],
  "leveraged": ["TQQQ","SQQQ","SOXL","SOXS","NVDL","NVDS","TSLL","TSLZ","FNGU","FNGD",
                "SPXL","SPXS","UPRO","SPXU","TNA","TZA","UDOW","SDOW","MUU","SNXX","MVLL"],
  "fx":        ["DX-Y.NYB","JPY=X","CNH=X","TWD=X","EURUSD=X"],
  "commodities":[("USO","原油"),("BNO","布蘭特原油"),("UNG","天然氣"),("GLD","黃金"),
                ("SLV","白銀"),("CPER","銅"),("DBC","綜合商品")],
  "crypto":    ["BTC-USD","ETH-USD","SOL-USD"],
}
# 期權聚合對象(CBOE;個股/大盤/槓桿ETF/波動率/大宗)
OPT_SYMS = ["_SPX","_VIX","SPY","QQQ","IWM","NVDA","TSLA","AAPL","MSFT","AVGO","META","AMZN",
            "MU","SMH","TQQQ","SQQQ","SOXL","SOXS","NVDL","TSLL","GLD","SLV","USO",
            "AMD","PLTR","COIN","MSTR"]
# Futu 大單淨流對象(⑦)= 正股 + 大盤 + 板塊 + 槓桿/反向 + 資金目的地(現金/債/金/crypto 現貨ETF)
CAP_SYMS = [
  # 大盤 ETF
  "US.SPY","US.QQQ","US.IWM","US.DIA",
  # 正股(megacap + 持倉 + 高成交額常駐)
  "US.NVDA","US.MSFT","US.AAPL","US.AMZN","US.META","US.GOOGL","US.AVGO","US.TSLA",
  "US.MU","US.SNDK","US.WDC","US.MRVL","US.LITE","US.COHR","US.AAOI",
  "US.AMD","US.PLTR","US.COIN","US.MSTR","US.NFLX","US.INTC","US.ORCL","US.TSM",
  # 板塊 ETF(半導體 + 大板塊輪動:科技/金融/能源/醫療)
  "US.SMH","US.SOXX","US.XLK","US.XLF","US.XLE","US.XLV",
  # 槓桿多方
  "US.TQQQ","US.SOXL","US.NVDL","US.TSLL","US.MUU","US.SNXX","US.MVLL","US.SPXL","US.TNA",
  # 反向(做空)
  "US.SQQQ","US.SOXS","US.SH","US.SPXU","US.TZA",
  # 信用債(風險偏好目的地:垃圾債/投等債)
  "US.HYG","US.LQD",
  # 目的地:現金 T-bill / 國債分天期 / 金・油・銀 / crypto 現貨 ETF
  "US.SGOV","US.BIL","US.SHY","US.IEF","US.TLT","US.GLD","US.USO","US.SLV","US.IBIT","US.ETHA"]
# 類別對照(前端分組/上色/目的地圖用)
CAP_CAT = {}
for _s in ["SPY","QQQ","IWM","DIA"]: CAP_CAT[_s]="大盤"
for _s in ["SMH","SOXX","XLK","XLF","XLE","XLV"]: CAP_CAT[_s]="板塊ETF"
for _s in ["TQQQ","SOXL","NVDL","TSLL","MUU","SNXX","MVLL","SPXL","TNA"]: CAP_CAT[_s]="槓桿"
for _s in ["SQQQ","SOXS","SH","SPXU","TZA"]: CAP_CAT[_s]="反向"
for _s in ["HYG","LQD"]: CAP_CAT[_s]="信用債"
for _s in ["SGOV","BIL"]: CAP_CAT[_s]="現金"
for _s in ["SHY","IEF","TLT"]: CAP_CAT[_s]="國債"
CAP_CAT["GLD"]="金"
CAP_CAT["USO"]="油"
CAP_CAT["SLV"]="銀"
for _s in ["IBIT","ETHA"]: CAP_CAT[_s]="Crypto"

FINRA_SYMS = {"NVDA","MU","SNDK","WDC","MRVL","TSLA","SMH","AVGO","SPY","QQQ","AMD"}
KL_HIST_DAYS = 1250     # 保留約 5 年日K

def _f(x):
    try:
        if x is None or x=="" or (isinstance(x,float) and x!=x): return None
        return float(x)
    except (ValueError,TypeError): return None

# ============ 美東交易時段判斷(時間戳誠實化)============
def market_session():
    """回傳 pre/rth/after/closed(週末;未含假日,由前端以 trade_date 為準)"""
    try:
        from zoneinfo import ZoneInfo
        et = datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return "unknown"
    if et.weekday() >= 5: return "closed"
    m = et.hour*60 + et.minute
    if 4*60 <= m < 9*60+30: return "pre"
    if 9*60+30 <= m < 16*60: return "rth"
    if 16*60 <= m < 20*60: return "after"
    return "closed"

# ============ Yahoo(價格歷史/漲跌/RS/sparkline)============
def yahoo_hist(sym, rng="3mo"):
    q = urllib.parse.quote(sym)
    d = http_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{q}?range={rng}&interval=1d", 12)
    r = d["chart"]["result"][0]; ind = r["indicators"]["quote"][0]; ts = r.get("timestamp",[]) or []
    closes, vols = [], []
    for i in range(len(ts)):
        c = (ind.get("close") or [None])[i] if i < len(ind.get("close",[])) else None
        if c is None: continue
        closes.append(c); vols.append((ind.get("volume") or [0]*len(ts))[i] or 0)
    return closes, vols, r.get("meta",{})

def pct(s,n): return round(100*(s[-1]/s[-1-n]-1),2) if len(s)>n and s[-1-n] else None
def sma(s,n): return sum(s[-n:])/n if len(s)>=n else None

def quote_block(sym, spy_closes=None):
    try:
        c,v,meta = yahoo_hist(sym)
        if not c: return None
        b = {"last": round(c[-1],4), "chg1d": pct(c,1), "chg5d": pct(c,5), "chg20d": pct(c,20)}
        if len(v)>=22:
            avg=sum(v[-21:-1])/20; b["vol_pace"]=round(v[-1]/avg,2) if avg else None
        b["spark"]=[round(x,4) for x in c[-20:]]
        # 當日% / 5日動能 現值
        b["mom5"]=b["chg5d"]; b["day"]=b["chg1d"]
        if spy_closes and len(c)>=26 and len(spy_closes)>=26:
            n=min(len(c),len(spy_closes)); r=[c[len(c)-n+i]/spy_closes[len(spy_closes)-n+i] for i in range(n)]
            m=sma(r,20); b["rs_vs_spy"]=round(100*(r[-1]/m-1),2) if m else None
            # 軌跡起點:5 個交易日前的 (RS, 5日動能, 當日%),供 3D 畫向量箭頭
            m5=sma(r[:-5],20) if n>=25 else None
            rs_prev=round(100*(r[-6]/m5-1),2) if m5 else None
            mom_prev=round(100*(c[-6]/c[-11]-1),2) if len(c)>11 else None
            day_prev=round(100*(c[-6]/c[-7]-1),2) if len(c)>7 else None
            b["prev"]=[rs_prev,mom_prev,day_prev]
        return b
    except Exception as e:
        err(f"yahoo {sym}", e); return None

# ============ CBOE 期權聚合 ============
def opt_parse(code):
    body=code[-15:]; return "20"+body[:2]+"-"+body[2:4]+"-"+body[4:6], body[6], int(body[7:])/1000.0
def cboe_options(sym):
    d=http_json(f"https://cdn.cboe.com/api/global/delayed_quotes/options/{sym}.json",30,2)
    data=d.get("data",{}); opts=data.get("options",[]); spot=data.get("current_price")
    if not spot or not opts: return None
    today=datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cv=pv=coi=poi=gex=zero=0.0; atm=[]; pk=[]; ck=[]; oi_str={}
    call_prem=put_prem=0.0   # 權利金成交額 = Σ 量×中價×100
    for o in opts:
        code=o.get("option","")
        if len(code)<15: continue
        exp,cp,K=opt_parse(code); oi=o.get("open_interest") or 0.0; vol=o.get("volume") or 0.0
        g=o.get("gamma") or 0.0; dl=o.get("delta") or 0.0; iv=o.get("iv") or 0.0
        bid=o.get("bid") or 0.0; ask=o.get("ask") or 0.0; ltp=o.get("last_trade_price") or 0.0
        mid=(bid+ask)/2 if (bid>0 and ask>0) else ltp
        prem=vol*mid*100
        if cp=="C": cv+=vol; coi+=oi; call_prem+=prem
        else: pv+=vol; poi+=oi; put_prem+=prem
        if exp==today: zero+=vol
        gex+=(1 if cp=="C" else -1)*g*oi*100*spot*spot*0.01
        if iv and abs(K-spot)/spot<=0.03: atm.append(iv)
        if iv and cp=="P" and -0.32<=dl<=-0.18: pk.append(iv)
        if iv and cp=="C" and 0.18<=dl<=0.32: ck.append(iv)
        if oi: oi_str[K]=oi_str.get(K,0.0)+oi
    mp=None
    if oi_str:
        cand=[K for K in oi_str if abs(K-spot)/spot<=0.15] or list(oi_str)
        def pain(P):
            t=0.0
            for o in opts:
                code=o.get("option","")
                if len(code)<15: continue
                _,cp,K=opt_parse(code); oi=o.get("open_interest") or 0.0
                if cp=="C" and P>K: t+=(P-K)*oi
                elif cp=="P" and P<K: t+=(K-P)*oi
            return t
        mp=min(cand,key=pain)
    return {"spot":round(spot,2),
            "pc_vol":round(pv/cv,3) if cv else None,"pc_oi":round(poi/coi,3) if coi else None,
            "call_vol":int(cv),"put_vol":int(pv),"call_oi":int(coi),"put_oi":int(poi),
            "gex_bn":round(gex/1e9,3),"atm_iv":round(sum(atm)/len(atm)*100,1) if atm else None,
            "skew_25d":round((sum(pk)/len(pk)-sum(ck)/len(ck))*100,1) if (pk and ck) else None,
            "zero_dte_share":round(zero/(cv+pv),3) if (cv+pv) else None,
            "max_pain":round(mp,2) if mp else None,
            "call_prem":round(call_prem,0),"put_prem":round(put_prem,0),
            "net_prem":round(call_prem-put_prem,0)}   # 正=看漲權利金成交額多、負=看跌多

# ============ 國債殖利率曲線 ============
def treasury():
    y=datetime.now(timezone.utc).year
    txt=http_get(f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{y}/all?type=daily_treasury_yield_curve&field_tdr_date_value={y}&page&_format=csv",20)
    lines=[l for l in txt.strip().splitlines() if l.strip()]; hdr=[h.strip().strip('"') for h in lines[0].split(",")]
    cols=["Date","3 Mo","2 Yr","5 Yr","10 Yr","20 Yr","30 Yr"]; idx={k:hdr.index(k) for k in cols if k in hdr}
    p=[x.strip().strip('"') for x in lines[1].split(",")]
    row={k:(p[i] if k=="Date" else float(p[i])) for k,i in idx.items()}
    row["2s10s"]=round(row["10 Yr"]-row["2 Yr"],2)
    return row

# ============ 盤中即時殖利率(CBOE 殖利率指數 via Yahoo;報價=殖利率×10)============
def live_yields():
    """^IRX 13週 / ^FVX 5年 / ^TNX 10年 / ^TYX 30年 → 盤中即時;官方曲線(EOD)另存 rates"""
    out={}
    for ysym,label in (("^IRX","3M"),("^FVX","5Y"),("^TNX","10Y"),("^TYX","30Y")):
        try:
            c,_,_=yahoo_hist(ysym,"1mo")
            if not c: continue
            k=10.0 if c[-1]>20 else 1.0   # 自動判斷刻度(CBOE 慣例=殖利率×10;Yahoo 有時已除回)
            y=round(c[-1]/k,3)
            prev=c[-2]/k if len(c)>1 else None
            out[label]={"y":y,"chg_bp":round((y-prev)*100,1) if prev is not None else None,
                        "spark":[round(x/k,3) for x in c[-20:]]}
        except Exception as e: err(f"yield {ysym}",e)
        time.sleep(0.1)
    return out

# ============ 多空槓桿資金(部位層;美股版期貨多空/融券)============
def cftc_cot():
    """CFTC TFF 期貨多空(週頻;週五發布週二資料):ES/NQ 槓桿基金與資產管理人部位(口)"""
    import urllib.parse as _p
    out={}
    for name,label in (("E-MINI S&P 500","ES"),("NASDAQ MINI","NQ"),("NASDAQ-100 STOCK INDEX (MINI)","NQ")):
        if label in out: continue
        try:
            q=_p.urlencode({"$where":f"contains(market_and_exchange_names,'{name}')",
                            "$order":"report_date_as_yyyy_mm_dd DESC","$limit":"1"})
            d=http_json(f"https://publicreporting.cftc.gov/resource/gpe5-46if.json?{q}",25,2)
            if not d: continue
            r=d[0]; g=lambda k: int(float(r.get(k) or 0))
            out[label]={"date":str(r.get("report_date_as_yyyy_mm_dd",""))[:10],
                "lev_long":g("lev_money_positions_long"),"lev_short":g("lev_money_positions_short"),
                "am_long":g("asset_mgr_positions_long"),"am_short":g("asset_mgr_positions_short"),
                "d_lev_long":g("change_in_lev_money_long"),"d_lev_short":g("change_in_lev_money_short")}
        except Exception as e: err(f"cftc {label}",e)
        time.sleep(0.4)
    return out

def yahoo_short_pos(syms):
    """個股/ETF 空方部位(半月頻,交易所申報;Yahoo defaultKeyStatistics)。
       需 cookie+crumb;住宅 IP(Mac)穩定,資料中心 IP 可能 429(Actions 備援允許失敗)"""
    import http.cookiejar, urllib.parse as _p
    cj=http.cookiejar.CookieJar()
    op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    try: op.open(urllib.request.Request("https://fc.yahoo.com",headers=UA),timeout=12)
    except Exception: pass
    crumb=op.open(urllib.request.Request("https://query1.finance.yahoo.com/v1/test/getcrumb",headers=UA),timeout=12).read().decode()
    out={}
    for s in syms:
        try:
            u=(f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{_p.quote(s)}"
               f"?modules=defaultKeyStatistics&crumb={_p.quote(crumb)}")
            ks=json.loads(op.open(urllib.request.Request(u,headers=UA),timeout=12).read())["quoteSummary"]["result"][0]["defaultKeyStatistics"]
            g=lambda k:(ks.get(k) or {}).get("raw")
            if g("sharesShort") is not None:
                out[s]={"sh":g("sharesShort"),"sh_prior":g("sharesShortPriorMonth"),
                        "ratio":g("shortRatio"),"pct_float":g("shortPercentOfFloat"),
                        "asof":(ks.get("dateShortInterest") or {}).get("fmt")}
        except Exception as e: err(f"shortpos {s}",e)
        time.sleep(0.5)
    return out

# ============ 現金池水位(層級觀測;「等機會的錢」)============
def nyfed_rrp(days=40):
    """Fed ON RRP 接納額(日頻;當日 13:15 ET 後有值)→ 貨幣基金停在 Fed 的過剩現金"""
    from datetime import timedelta
    end=datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start=(datetime.now(timezone.utc)-timedelta(days=days)).strftime("%Y-%m-%d")
    d=http_json(f"https://markets.newyorkfed.org/api/rp/reverserepo/propositions/search.json?startDate={start}&endDate={end}",20)
    out={}
    for o in (d.get("repo",{}) or {}).get("operations",[]) or []:
        dt=o.get("operationDate"); amt=_f(o.get("totalAmtAccepted"))
        if dt and amt is not None and "Reverse" in str(o.get("operationType","")):
            out[dt]=round(amt/1e9,3)   # 十億美元
    return out

def ici_mmf():
    """ICI 貨幣市場基金總資產(週頻;週四發布、資料截至週三)= 停泊現金主體
       句型:'Total money market fund assets decreased by $59.90 billion to $7.89 trillion
       for the week ended Wednesday, July 15'(週期日不含年;年取自發布日期行)"""
    import re as _re
    raw=http_get("https://www.ici.org/research/stats/mmf",25,2)
    t=_re.sub(r"<[^>]+>"," ",raw).replace("&nbsp;"," ")
    t=_re.sub(r"\s+"," ",t)
    def num(x): return float(x.replace(",",""))
    def to_bn(v,unit): return v*1000 if unit=="trillion" else (v if unit=="billion" else v/1000)
    r={}
    m=_re.search(r"Total money market fund assets\s*\d*\s*(increased|decreased)\s+by\s+\$([\d.,]+)\s*(billion|million)\s+to\s+\$([\d.,]+)\s*(trillion|billion)\s+for\s+the\s+week\s+ended\s+Wednesday,?\s*([A-Za-z]+\s+\d+)",t)
    if not m: return None
    sign=-1 if m.group(1)=="decreased" else 1
    r["chg_bn"]=round(sign*to_bn(num(m.group(2)),m.group(3)),2)
    r["total_bn"]=round(to_bn(num(m.group(4)),m.group(5)),1)
    wk=m.group(6)
    my=_re.search(r"([A-Za-z]+\s+\d+,\s*(\d{4}))\s*[—–-]",t)
    yr=my.group(2) if my else str(datetime.now(timezone.utc).year)
    r["asof"]=wk+", "+yr
    try:
        d=datetime.strptime(wk+" "+yr,"%B %d %Y")
        if (d-datetime.now()).days>7: d=d.replace(year=d.year-1)   # 跨年保護
        r["asof_iso"]=d.strftime("%Y-%m-%d")
    except Exception: pass
    m2=_re.search(r"retail money market funds\s+(?:increased|decreased)\s+by\s+\$[\d.,]+\s*(?:billion|million)\s+to\s+\$([\d.,]+)\s*(trillion|billion)",t)
    if m2: r["retail_bn"]=round(to_bn(num(m2.group(1)),m2.group(2)),1)
    m3=_re.search(r"institutional money market funds\s+(?:increased|decreased)\s+by\s+\$[\d.,]+\s*(?:billion|million)\s+to\s+\$([\d.,]+)\s*(trillion|billion)",t)
    if m3: r["inst_bn"]=round(to_bn(num(m3.group(1)),m3.group(2)),1)
    return r

# ============ FINRA 賣空(暗池 proxy)============
def finra_short():
    from datetime import timedelta
    for back in range(5):
        ds=(datetime.now(timezone.utc)-timedelta(days=back)).strftime("%Y%m%d")
        try:
            txt=http_get(f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{ds}.txt",12,2)
            out={"_date":ds}
            for line in txt.splitlines()[1:]:
                q=line.split("|")
                if len(q)>=5 and q[1] in FINRA_SYMS:
                    sv,tv=_f(q[2]),_f(q[4])
                    if sv is not None and tv: out[q[1]]={"short_ratio":round(sv/tv,3)}
            if len(out)>1: return out
        except Exception: continue
    return {}

def finra_short_hist(days=30):
    """FINRA 每日賣空比回填(近 days 個有檔交易日)→ 暗池趨勢圖首日即可用"""
    from datetime import timedelta
    out={}; back=0
    while len(out)<days and back<55:
        dt=datetime.now(timezone.utc)-timedelta(days=back); back+=1
        if dt.weekday()>=5: continue
        ds=dt.strftime("%Y%m%d")
        try: txt=http_get(f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{ds}.txt",12,1)
        except Exception: continue
        day={}
        for line in txt.splitlines()[1:]:
            q=line.split("|")
            if len(q)>=5 and q[1] in FINRA_SYMS:
                sv,tv=_f(q[2]),_f(q[4])
                if sv is not None and tv: day[q[1]]=round(sv/tv,3)
        if day: out[ds]=day
        time.sleep(0.25)
    return out

# 機構持股(13F,季頻;僅美股正股/基金)監控清單
INST_SYMS = ["US.NVDA","US.MU","US.SNDK","US.WDC","US.MRVL","US.AVGO","US.TSLA","US.SMH","US.SOXX",
             "US.AAPL","US.MSFT","US.AMZN","US.META","US.GOOGL"]

# ============ 個股K線層(stock.html 用;另一 session 開發,已合併)============
def kline_symbols(custom):
    base = WL["market"] + WL["stocks"] + WL["leveraged"]
    out = []
    for s in list(base) + [c for c in (custom or [])]:
        s = str(s).replace("US.", "")
        if s and s not in out: out.append(s)
    return out

def yahoo_ohlc(sym, rng="5y"):
    q = urllib.parse.quote(sym)
    d = http_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{q}?range={rng}&interval=1d", 15)
    r = d["chart"]["result"][0]; ind = r["indicators"]["quote"][0]; ts = r.get("timestamp") or []
    off = r.get("meta", {}).get("gmtoffset", -14400)
    bars = []
    for i, t in enumerate(ts):
        o = (ind.get("open") or [None]*len(ts))[i]; h = (ind.get("high") or [None]*len(ts))[i]
        l = (ind.get("low") or [None]*len(ts))[i]; c = (ind.get("close") or [None]*len(ts))[i]
        v = (ind.get("volume") or [None]*len(ts))[i]
        if None in (o, h, l, c): continue
        dt = datetime.fromtimestamp(t + off, timezone.utc).strftime("%Y-%m-%d")
        bars.append([dt, round(o, 3), round(h, 3), round(l, 3), round(c, 3), int(v or 0), None])
    return bars

def futu_hist_bars(q, sym, start, end):
    """富途歷史日K(前復權,含真實週轉率);自動翻頁"""
    from futu import RET_OK, KLType, AuType
    code = sym if sym.startswith("US.") else "US." + sym
    bars = []; page = None
    while True:
        ret, d, page = q.request_history_kline(code, start=start, end=end, ktype=KLType.K_DAY,
                                               autype=AuType.QFQ, max_count=1000, page_req_key=page)
        if ret != RET_OK: raise RuntimeError(str(d)[:80])
        for _, r in d.iterrows():
            dt = str(r.get("time_key", ""))[:10]
            o, h, l, c = _f(r.get("open")), _f(r.get("high")), _f(r.get("low")), _f(r.get("close"))
            v = _f(r.get("volume")); tr = _f(r.get("turnover_rate"))
            if dt and None not in (o, h, l, c):
                bars.append([dt, round(o, 3), round(h, 3), round(l, 3), round(c, 3), int(v or 0),
                             None if tr is None else round(tr, 3)])
        if not page: break
        time.sleep(0.4)
    return bars

def merge_bars(old, new):
    """按日期 upsert;新 bar 無週轉率而舊有 → 保留舊值(避免 Yahoo 增量洗掉 Futu 週轉率)"""
    m = {b[0]: list(b) for b in (old or [])}
    for b in (new or []):
        b = list(b); ob = m.get(b[0])
        if ob and b[6] is None and len(ob) > 6 and ob[6] is not None: b[6] = ob[6]
        m[b[0]] = b
    return [m[k] for k in sorted(m)]

def snapshot_today(kl_syms):
    """當日K(每5分):開高低收/量/週轉率 → market_data.json 的 kline_today"""
    from futu import OpenQuoteContext, RET_OK
    q = OpenQuoteContext(host="127.0.0.1", port=11111)
    out = {}
    try:
        fs = ["US." + s for s in kl_syms]
        for i in range(0, len(fs), 200):
            ret, d = q.get_market_snapshot(fs[i:i+200])
            if ret == RET_OK:
                for _, r in d.iterrows():
                    sym = str(r.get("code", "")).replace("US.", "")
                    dt = str(r.get("update_time") or "")[:10]
                    o, h, l, c = _f(r.get("open_price")), _f(r.get("high_price")), _f(r.get("low_price")), _f(r.get("last_price"))
                    v = _f(r.get("volume")); tr = _f(r.get("turnover_rate"))
                    if dt and None not in (o, h, l, c):
                        out[sym] = [dt, o, h, l, c, int(v or 0), tr]
            time.sleep(0.3)
    finally:
        q.close()
    return out

def refresh_klines(cfg, args, kl_syms):
    """日K歷史維護:首次全量(Futu 前復權,失敗退 Yahoo);之後盤後每日增量(含復權偵測,漂移>2%全量重抓);
       新自訂標的每輪最多補抓 3 檔(≈10 分內上線)。變動檔分塊推 gist(kline_SYM.json)。"""
    kdir = args.config + ".klines"
    os.makedirs(kdir, exist_ok=True)
    mark = args.config + ".klmark"
    try: age = time.time() - os.path.getmtime(mark)
    except OSError: age = 1e9
    sess = market_session()
    daily_due = age > 20*3600 and sess in ("after", "closed")
    missing = [s for s in kl_syms if not os.path.exists(os.path.join(kdir, s + ".json"))][:3]
    todo = list(kl_syms) if daily_due else missing
    if not todo: return
    from datetime import timedelta
    end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start5 = (datetime.now(timezone.utc) - timedelta(days=int(KL_HIST_DAYS*1.55))).strftime("%Y-%m-%d")
    q = None
    if not args.no_futu:
        try:
            from futu import OpenQuoteContext
            q = OpenQuoteContext(host="127.0.0.1", port=11111)
        except Exception as e: err("kline-ctx", e)
    changed = {}
    try:
        for s in todo:
            path = os.path.join(kdir, s + ".json")
            try: cache = json.load(open(path))
            except Exception: cache = None
            bars = None; src = None
            try:
                if q:
                    if cache and cache.get("bars"):
                        st = (datetime.now(timezone.utc) - timedelta(days=40)).strftime("%Y-%m-%d")
                        newb = futu_hist_bars(q, s, st, end); src = "futu-qfq"
                        om = {b[0]: b[4] for b in cache["bars"]}
                        drift = [b for b in newb if b[0] in om and om[b[0]] and abs(b[4]/om[b[0]]-1) > 0.02]
                        bars = futu_hist_bars(q, s, start5, end) if drift else merge_bars(cache["bars"], newb)
                        if drift: src = "futu-qfq(復權重抓)"
                    else:
                        bars = futu_hist_bars(q, s, start5, end); src = "futu-qfq"
                else:
                    raise RuntimeError("no futu ctx")
            except Exception as e:
                if not isinstance(e, RuntimeError) or "no futu ctx" not in str(e): err(f"kline {s}", e)
                try:
                    if cache and cache.get("bars"):
                        newb = yahoo_ohlc(s, "3mo")
                        om = {b[0]: b[4] for b in cache["bars"]}
                        drift = [b for b in newb if b[0] in om and om[b[0]] and abs(b[4]/om[b[0]]-1) > 0.02]
                        bars = merge_bars(cache["bars"], yahoo_ohlc(s, "5y")) if drift else merge_bars(cache["bars"], newb)
                    else:
                        bars = yahoo_ohlc(s, "5y")
                    src = "yahoo備援" if q else "yahoo"
                except Exception as e2:
                    err(f"kline-yh {s}", e2); bars = None
            if bars:
                payload = {"sym": s, "src": src, "updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                           "bars": bars[-KL_HIST_DAYS:]}
                try: json.dump(payload, open(path, "w"), ensure_ascii=False, separators=(",", ":"))
                except Exception: pass
                changed["kline_" + s + ".json"] = payload
            time.sleep(0.6 if q else 0.35)
    finally:
        if q:
            try: q.close()
            except Exception: pass
    if daily_due:
        try: open(mark, "w").write(str(time.time()))
        except Exception: pass
    if changed and not args.no_push and cfg.get("gist_id") and cfg.get("gist_token"):
        names = sorted(changed)
        for i in range(0, len(names), 8):
            try: push_gist(cfg, {n: changed[n] for n in names[i:i+8]})
            except Exception as e: err("kline-push", e); break
    log(f"klines updated: {len(changed)}/{len(todo)}")

# ============ 自訂追蹤清單(存於同一 gist 的 custom_symbols.json,由網頁寫入)============
def fetch_custom_syms(cfg):
    try:
        if not cfg.get("gist_id") or not cfg.get("gist_token"): return []
        req=urllib.request.Request(f"https://api.github.com/gists/{cfg['gist_id']}",
            headers={"Authorization":f"token {cfg['gist_token']}","User-Agent":"market-export",
                     "Accept":"application/vnd.github+json"})
        d=json.load(urllib.request.urlopen(req,timeout=15))
        c=d.get("files",{}).get("custom_symbols.json",{}).get("content","")
        arr=json.loads(c) if c else []
        out=[]
        for s in arr:
            s=str(s).strip().upper()
            if not s or len(s)>12: continue
            if not s.startswith("US."): s="US."+s
            if s not in out: out.append(s)
        return out[:30]
    except Exception as e:
        err("custom_syms",e); return []

# ============ Futu ============
def pull_top_turnover(q, topn=20):
    """美股成交額 TOP N(排行闖入者來源)"""
    from futu import Market, AccumulateFilter, StockField, SortDir, RET_OK
    af=AccumulateFilter(); af.stock_field=StockField.TURNOVER
    af.is_no_filter=False; af.filter_min=1; af.days=1; af.sort=SortDir.DESCEND
    ret,data=q.get_stock_filter(Market.US, [af], begin=0, num=topn)
    if ret!=RET_OK: raise RuntimeError(str(data)[:80])
    _,_,stock_list=data
    out=[]
    for item in stock_list:
        code=getattr(item,"stock_code",None) or getattr(item,"code","") or ""
        if code: out.append(code)
    return out

def pull_daily_hist(q, syms, days=45):
    """歷史日頻資金流回填(get_capital_flow period_type=DAY):讓 1/3/5/10 日視窗立即可用"""
    from futu import RET_OK, PeriodType
    from datetime import timedelta
    end=datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start=(datetime.now(timezone.utc)-timedelta(days=days)).strftime("%Y-%m-%d")
    out={}
    for s in syms:
        try:
            ret,d=q.get_capital_flow(s, period_type=PeriodType.DAY, start=start, end=end)
            if ret==RET_OK and len(d):
                sym=s.replace("US.","")
                for _,r in d.iterrows():
                    dt=str(r.get("capital_flow_item_time",""))[:10]
                    if not dt or dt<"2000": continue
                    si,bi=_f(r.get("super_in_flow")),_f(r.get("big_in_flow"))
                    mi,sm=_f(r.get("mid_in_flow")),_f(r.get("sml_in_flow"))
                    m=(si+bi) if None not in (si,bi) else _f(r.get("main_in_flow"))
                    rr=(mi+sm) if None not in (mi,sm) else None
                    if m is None: continue
                    out.setdefault(dt,{})[sym]={"m":round(m/1e6,1),
                        "r":round(rr/1e6,1) if rr is not None else None,
                        "c":CAP_CAT.get(sym,"正股")}
            elif ret!=RET_OK:
                err(f"histflow {s}", RuntimeError(str(d)[:40]))   # 之前靜默吞掉→清單尾端被限流看不見
        except Exception as e: err(f"histflow {s}",e)
        time.sleep(1.1)   # Futu 歷史資金流配額約 30 次/30 秒;0.5s 會超限→尾端(目的地ETF)全失敗
    return out

def pull_futu(want_inst=False, want_hist=False, extra_syms=None):
    from futu import OpenQuoteContext, RET_OK
    q=OpenQuoteContext(host="127.0.0.1",port=11111)
    cap={}; snaps={}; inst={}; hist={}
    extra=set(extra_syms or [])
    syms=CAP_SYMS+[s for s in extra if s not in CAP_SYMS]
    try:
        # 大單淨流(⑦):固定清單 + 自訂
        for s in syms:
            try:
                ret,d=q.get_capital_distribution(s)
                if ret==RET_OK and len(d):
                    r=d.iloc[0]
                    si,bi=_f(r.get("capital_in_super")),_f(r.get("capital_in_big"))
                    so,bo=_f(r.get("capital_out_super")),_f(r.get("capital_out_big"))
                    mi,sm=_f(r.get("capital_in_mid")),_f(r.get("capital_in_small"))
                    mo,so2=_f(r.get("capital_out_mid")),_f(r.get("capital_out_small"))
                    mn=round((si+bi)-(so+bo),0) if None not in (si,bi,so,bo) else None
                    rn=round((mi+sm)-(mo+so2),0) if None not in (mi,sm,mo,so2) else None
                    sym=s.replace("US.","")
                    _cat="自訂" if s in extra else CAP_CAT.get(sym,"正股")
                    cap[s]={"main_net":mn,"retail_net":rn,"super_in":si,"big_in":bi,"super_out":so,"big_out":bo,
                            "cat":_cat,"update_time":str(r.get("update_time") or "")}
            except Exception as e: err(f"capdist {s}", e)
            time.sleep(0.5)
        # 機構持股變動(13F,季頻;節流:每次執行只在 want_inst 時抓)
        if want_inst:
            for s in INST_SYMS:
                try:
                    ret,d=q.get_shareholders_institutional(s, num=1)
                    if ret==RET_OK and len(d):
                        r=d.iloc[0]
                        inst[s.replace("US.","")]={
                            "pct":_f(r.get("holder_pct")), "pct_chg":_f(r.get("holder_pct_change")),
                            "inst_chg":_f(r.get("institution_quantity_change")),
                            "qty_chg":_f(r.get("holder_quantity_change")),
                            "period":str(r.get("period_text") or "")}
                except Exception as e: err(f"inst {s}", e)
                time.sleep(0.4)
        # 排行闖入者:美股成交額 TOP20,清單外的自動補抓 ⑦
        try:
            ranked=pull_top_turnover(q, topn=20)
            known=set(syms)
            intruders=[c for c in ranked if c.startswith("US.") and c not in known][:20]
            for rank_i,s in enumerate(intruders):
                try:
                    ret,d=q.get_capital_distribution(s)
                    if ret==RET_OK and len(d):
                        r=d.iloc[0]
                        si,bi=_f(r.get("capital_in_super")),_f(r.get("capital_in_big"))
                        so,bo=_f(r.get("capital_out_super")),_f(r.get("capital_out_big"))
                        mi,sm=_f(r.get("capital_in_mid")),_f(r.get("capital_in_small"))
                        mo,so2=_f(r.get("capital_out_mid")),_f(r.get("capital_out_small"))
                        mn=round((si+bi)-(so+bo),0) if None not in (si,bi,so,bo) else None
                        rn=round((mi+sm)-(mo+so2),0) if None not in (mi,sm,mo,so2) else None
                        if mn is not None:
                            cap[s]={"main_net":mn,"retail_net":rn,"cat":"闖入","turnover_rank":rank_i+1,
                                    "update_time":str(r.get("update_time") or "")}
                except Exception as e: err(f"intruder {s}",e)
                time.sleep(0.5)
        except Exception as e: err("rank",e)
        # 歷史日頻回填(重;每日一次;固定清單+自訂,闖入者不回填)
        if want_hist:
            hist=pull_daily_hist(q, syms)
    finally:
        q.close()
    return cap, snaps, inst, hist

# ============ 主流程 ============
def options_due(state_path, force):
    """期權更新節奏(即時性優先、兼顧 CBOE 速率):
       盤中 rth=每次採集都重算(即時到 CBOE ~15 分源延遲上限);盤前/盤後=15 分;休市=60 分"""
    if force: return True
    sess=market_session()
    if sess=="rth": return True
    interval=900 if sess in ("pre","after") else 3600
    mk=state_path+".optmark"
    now=time.time()
    try:
        if now-os.path.getmtime(mk) < interval: return False
    except OSError: pass
    open(mk,"w").write(str(now)); return True

def run_once(cfg, args):
    now=datetime.now(timezone.utc)
    data={"ts_utc":now.strftime("%Y-%m-%d %H:%M:%S"),"source":"mac-market-export",
          "market":{},"stocks":{},"leveraged":{},"options":{},"fx":{},"rates":{},
          "crypto":{},"commodities":{},"darkpool":{},"capital_flow":{},"errors":[]}
    # SPY 基準(RS 用)
    try: spy_c,_,_=yahoo_hist("SPY")
    except Exception as e: err("spy",e); spy_c=None
    # 大盤/個股/槓桿
    for grp in ("market","stocks","leveraged"):
        for s in WL[grp]:
            b=quote_block(s, spy_c if grp!="market" else None)
            if b: data[grp][s]=b
            time.sleep(0.1)
    # FX
    for s in WL["fx"]:
        b=quote_block(s);
        if b: data["fx"][s]=b
        time.sleep(0.1)
    # 大宗
    for s,name in WL["commodities"]:
        b=quote_block(s)
        if b: b["name"]=name; data["commodities"][s]=b
        time.sleep(0.1)
    # crypto
    for s in WL["crypto"]:
        b=quote_block(s)
        if b: data["crypto"][s]=b
        time.sleep(0.1)
    # 國債(官方 EOD 曲線 + 盤中即時殖利率)
    try: data["rates"]=treasury()
    except Exception as e: err("treasury",e)
    try: data["rates_live"]=live_yields()
    except Exception as e: err("live_yields",e)
    # 期權(節流每 15 分;跳過時沿用上次快取,避免推空把 gist 期權洗掉)
    optcache=args.config+".optcache.json"
    if options_due(args.config, args.force_options):
        for s in OPT_SYMS:
            try:
                r=cboe_options(s)
                if r: data["options"][s]=r
                time.sleep(1.0)   # CBOE 有速率限制;放慢避免 429(期權每 15 分才更新,慢無妨)
            except Exception as e: err(f"cboe {s}",e)
        data["_options_ts"]=now.strftime("%Y-%m-%d %H:%M:%S")
        try: json.dump({"ts":data["_options_ts"],"options":data["options"]}, open(optcache,"w"), ensure_ascii=False)
        except Exception: pass
    else:
        try:
            c=json.load(open(optcache)); data["options"]=c.get("options",{}); data["_options_ts"]=c.get("ts"); data["_options_cached"]=True
        except Exception:
            data["_options_skipped"]=True
    # 期權日檔歸檔(30 交易日;盤中=今日至此刻、收盤後=全日終值)→ 盤後可選日期區間看趨勢
    optdaily=args.config+".optdaily.json"
    try: optd=json.load(open(optdaily))
    except Exception: optd={}
    if data.get("options") and market_session() in ("rth","after"):
        try:
            from zoneinfo import ZoneInfo
            et_date=datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
        except Exception: et_date=None
        if et_date:
            optd[et_date]={s:{k:o.get(k) for k in
                ("spot","gex_bn","pc_vol","pc_oi","atm_iv","skew_25d","max_pain","zero_dte_share",
                 "call_prem","put_prem","call_oi","put_oi","call_vol","put_vol")}
                for s,o in data["options"].items()}
            for d_ in sorted(optd)[:-30]: optd.pop(d_,None)
            try: json.dump(optd, open(optdaily,"w"), ensure_ascii=False)
            except Exception: pass
    data["opt_daily"]=optd
    # 暗池 proxy(最新日)
    try: data["darkpool"]=finra_short()
    except Exception as e: err("finra",e)
    # 暗池日檔(30 交易日;首次自動回填 FINRA 歷史檔,之後逐日 upsert)
    dppath=args.config+".dpdaily.json"
    try: dpd=json.load(open(dppath))
    except Exception: dpd={}
    if len(dpd)<10:
        try: dpd.update(finra_short_hist(30))
        except Exception as e: err("finra_hist",e)
    dp=data.get("darkpool") or {}
    if dp.get("_date"):
        dpd[dp["_date"]]={k:v["short_ratio"] for k,v in dp.items()
                          if isinstance(v,dict) and v.get("short_ratio") is not None}
    dpd={k:dpd[k] for k in sorted(dpd)[-30:]}
    try: json.dump(dpd, open(dppath,"w"))
    except Exception: pass
    data["dp_daily"]=dpd
    # 現金池水位(層級,非盤中流量):ON RRP 日頻每次刷新;ICI MMF 週頻(6 小時節流+滾動半年史)
    cashpath=args.config+".cashpool.json"
    try: cash=json.load(open(cashpath))
    except Exception: cash={}
    try: cash["onrrp"]=nyfed_rrp()
    except Exception as e: err("nyfed_rrp",e)
    if time.time()-cash.get("_mmf_ts",0)>6*3600:
        try:
            r=ici_mmf()
            if r:
                cash["mmf"]=r; cash["_mmf_ts"]=time.time()
                h=cash.setdefault("mmf_hist",{})
                key=r.get("asof_iso") or r.get("asof")
                if key: h[key]=r["total_bn"]
                for k in sorted(h)[:-26]: h.pop(k,None)   # 保留半年(26 週)
        except Exception as e: err("ici_mmf",e)
    try: json.dump(cash, open(cashpath,"w"), ensure_ascii=False)
    except Exception: pass
    data["cash_pool"]=cash
    # 多空槓桿資金層(部位;長頻快取:COT 20h、空方部位 20h 檢查一次)
    levpath=args.config+".levpos.json"
    try: lev=json.load(open(levpath))
    except Exception: lev={}
    if time.time()-lev.get("_cot_ts",0)>20*3600:
        try:
            c=cftc_cot()
            if c: lev["cot"]=c; lev["_cot_ts"]=time.time()
        except Exception as e: err("cftc",e)
    if time.time()-lev.get("_short_ts",0)>20*3600:
        try:
            sp=yahoo_short_pos(WL["market"]+[x for x in WL["stocks"] if x not in ("SMH","SOXX")][:26]+["SMH","SOXX"])
            if sp: lev["short_pos"]=sp; lev["_short_ts"]=time.time()
        except Exception as e: err("shortpos",e)
    try: json.dump(lev,open(levpath,"w"),ensure_ascii=False)
    except Exception: pass
    data["lev_pos"]=lev
    # Futu 大單淨流 + 機構持股(機構持股跟期權同節流,15 分抓一次;季頻資料低頻足夠)
    fsnap={"ts_utc":data["ts_utc"],"source":"futu-opend","snapshots":{},"capital":{},"errors":[]}
    # 機構持股 15 分一次(季頻資料,低頻足夠;與期權節流解耦——盤中期權已改每次重算)
    instmark=args.config+".instmark"
    try: _instage=time.time()-os.path.getmtime(instmark)
    except OSError: _instage=1e9
    want_inst = _instage>900
    # 歷史回填:日檔不足 10 天,或距上次回填 >20 小時
    histmark=args.config+".histmark"
    dailypath0=args.config+".dailyflows.json"
    try: _nd=len(json.load(open(dailypath0)))
    except Exception: _nd=0
    try: _age=time.time()-os.path.getmtime(histmark)
    except OSError: _age=1e9
    # 清單新增標的(如 USO/SLV)時,近 5 個歷史日缺其資料 → 補回填(每小時限速,避免 Futu 無該檔日頻資料時反覆重拉)
    _missing=[]
    try:
        _d0=json.load(open(dailypath0))
        _core={x.replace("US.","") for x in CAP_SYMS}
        for _dt in sorted(_d0)[-6:-1] or sorted(_d0):
            _missing+= list(_core-set(_d0[_dt].keys()))
        _missing=sorted(set(_missing))
    except Exception: _missing=[]
    want_hist = (not args.no_futu) and (_nd<10 or _age>20*3600 or (bool(_missing) and _age>3600))
    data["_hist_state"]={"want":bool(want_hist),"missing":_missing[:8],"mark_age_h":round(_age/3600,1)}
    histfill={}
    custom=fetch_custom_syms(cfg) if not args.no_futu else []
    data["custom_symbols"]=[s.replace("US.","") for s in custom]
    if not args.no_futu:
        try:
            cap,_,inst,histfill=pull_futu(want_inst=want_inst, want_hist=want_hist, extra_syms=custom)
            data["capital_flow"]=cap
            if inst:
                data["institutions"]=inst
                try: open(instmark,"w").write(str(time.time()))
                except Exception: pass
            if histfill:
                try: open(histmark,"w").write(str(time.time()))
                except Exception: pass
            fsnap["capital"]=cap; fsnap["n_cap"]=len(cap); fsnap["n_snap"]=0
        except Exception as e:
            err("futu",e); fsnap["errors"].append(str(e)[:100])
    # 機構持股跳過那次:沿用快取,避免面板閃爍
    instcache=args.config+".instcache.json"
    if data.get("institutions"):
        try: json.dump(data["institutions"], open(instcache,"w"), ensure_ascii=False)
        except Exception: pass
    else:
        try: data["institutions"]=json.load(open(instcache))
        except Exception: pass
    # 時段誠實化:fetch 時間 vs 資料所屬交易日分開
    data["session"]=market_session()
    uts=[v.get("update_time","") for v in data["capital_flow"].values() if v.get("update_time")]
    data["trade_date"]=max(uts)[:10] if uts else None   # ⑦ 資料實際所屬日(源自富途 update_time)
    # 持續性:滾動歷史 —— 只在盤中(rth)累積,且內容有變才記;載入時自癒去除連續重複(修週末污染)
    histpath=args.config+".flowhist.json"
    try: hist=json.load(open(histpath))
    except Exception: hist=[]
    dedup=[]
    for h in hist:
        if dedup and dedup[-1].get("f")==h.get("f"): continue
        dedup.append(h)
    hist=dedup
    if data["capital_flow"] and data["session"]=="rth":
        hist=[h for h in hist if h.get("d")==data["trade_date"]]   # 換日清除他日/盤前殘留欄(修週一首欄顯示上週五終值)
        snap={"ts":data["ts_utc"][11:16],"d":data["trade_date"],
              "f":{k.replace("US.",""):round(v["main_net"]/1e6,1) for k,v in data["capital_flow"].items() if v.get("main_net") is not None},
              "fr":{k.replace("US.",""):round(v["retail_net"]/1e6,1) for k,v in data["capital_flow"].items() if v.get("retail_net") is not None}}
        if not hist or hist[-1].get("f")!=snap["f"]:
            hist.append(snap); hist=hist[-48:]
    try: json.dump(hist, open(histpath,"w"))
    except Exception: pass
    data["flow_history"]=hist
    # 日檔歸檔:⑦ 為當日盤中累計 → 以 trade_date upsert(當日最後值=全日淨額),留 30 個交易日
    # 前端「過去 N 個交易日」視窗由此加總
    dailypath=args.config+".dailyflows.json"
    try: daily=json.load(open(dailypath))
    except Exception: daily={}
    # 先併入歷史回填(不覆蓋既有日期;今日之後由 live upsert 蓋最新值)
    for dt,day in histfill.items():
        if dt not in daily: daily[dt]=day
        else:
            for s_,e_ in day.items():
                if s_ not in daily[dt]: daily[dt][s_]=e_   # 新標的補進既有日期,不覆蓋原值
    if data["capital_flow"] and data["trade_date"] and data["session"] in ("rth","after"):
        # 只在盤中/盤後歸檔:避免盤前把前日累計寫進新日期(原已知bug,現根治)
        daily[data["trade_date"]]={k.replace("US.",""):{
            "m":round((v.get("main_net") or 0)/1e6,1),
            "r":round((v.get("retail_net") or 0)/1e6,1) if v.get("retail_net") is not None else None,
            "c":v.get("cat","正股")} for k,v in data["capital_flow"].items() if v.get("main_net") is not None}
        for d_ in sorted(daily)[:-30]: daily.pop(d_,None)
        try: json.dump(daily, open(dailypath,"w"), ensure_ascii=False)
        except Exception: pass
    data["daily_flows"]=daily
    # 個股K線層(stock.html):當日K快照+日K歷史維護 —— Mac 專屬,public-out(Actions 備援)跳過
    if getattr(args,"public_out",None):
        kl_syms=[]
    else:
        kl_syms=kline_symbols(data.get("custom_symbols") or [])
    if not args.no_futu:
        try: data["kline_today"]=snapshot_today(kl_syms)
        except Exception as e: err("kline_today",e)
    if kl_syms:
        try: refresh_klines(cfg,args,kl_syms)
        except Exception as e: err("klines",e)
    data["errors"]=ERRORS
    data["meta"]={"futu_ok":len(data["capital_flow"])>0,"n_opt":len(data["options"]),
                  "n_inst":len(data.get("institutions",{})),
                  "n_kl_today":len(data.get("kline_today",{})),
                  "n_stocks":len(data["stocks"])+len(data["leveraged"])+len(data["market"])}
    return data, fsnap

def push_gist(cfg, files):
    gid=cfg["gist_id"]; tok=cfg["gist_token"]
    body=json.dumps({"files":{k:{"content":json.dumps(v,ensure_ascii=False)} for k,v in files.items()}}).encode()
    req=urllib.request.Request(f"https://api.github.com/gists/{gid}",data=body,method="PATCH",
        headers={"Authorization":f"token {tok}","Accept":"application/vnd.github+json","User-Agent":"market-export"})
    urllib.request.urlopen(req,timeout=25).read(); return "ok"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--config",default=os.path.join(os.path.dirname(os.path.abspath(__file__)),"config.json"))
    ap.add_argument("--no-futu",action="store_true")
    ap.add_argument("--no-push",action="store_true")
    ap.add_argument("--force-options",action="store_true")
    ap.add_argument("--public-out",default=None,help="公開源-only 模式:跳過 Futu/K線/gist 推送,結果寫入指定 JSON(GitHub Actions 備援採集用)")
    a=ap.parse_args()
    # 看門狗:Futu SDK 斷線(網絡中斷)時可能無限期掛住,會卡死 launchd 排程 →
    # 單輪超過 7 分鐘就自我了斷,交給 launchd 下一輪全新重啟(2026-07-20 事故對策)
    try:
        import signal as _sig
        def _wd(s,f):
            log("WATCHDOG: 本輪超時,自我重啟交給下一輪"); os._exit(3)
        _sig.signal(_sig.SIGALRM,_wd); _sig.alarm(420)
    except Exception: pass
    if a.public_out:
        a.no_futu=True; a.no_push=True   # 備援模式:純公開源
    cfg=json.load(open(a.config)) if os.path.exists(a.config) else {}
    data,fsnap=run_once(cfg,a)
    if a.public_out:
        data["source"]="gh-actions-public"
        json.dump(data, open(a.public_out,"w"), ensure_ascii=False, separators=(",",":"))
        log(f"public-out 寫入 {a.public_out}: options={len(data.get('options',{}))} rates_live={bool(data.get('rates_live'))}")
        return
    log(f"collected: stocks={data['meta']['n_stocks']} opt={data['meta']['n_opt']} "
        f"cap={len(data['capital_flow'])} errs={len(data['errors'])}")
    if a.no_push:
        print(json.dumps(data,ensure_ascii=False,indent=1)[:3000]); return
    try:
        push_gist(cfg,{"market_data.json":data,"futu_snapshot.json":fsnap})
        log("pushed market_data.json + futu_snapshot.json")
    except Exception as e:
        log("PUSH ERROR:",type(e).__name__,e)

if __name__=="__main__":
    main()

