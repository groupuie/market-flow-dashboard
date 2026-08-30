#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
個股 AI 訊號引擎（雲端執行；純 stdlib、只讀公開資料、不下單）
產出 data/signals.json 供 stock.html 渲染：技術掃描 + 期權 GEX 剖面（翻轉位/牆/擠壓分數）
+ 內部人(SEC Form 4) + 財報日(Yahoo crumb, best-effort) + ⑦大單持續性 + 大盤水位。

事實計算全自動；「stance/plan/敘事理由/買賣點標註」由排程場次的 Claude 依本引擎 computed
事實補寫（引擎僅自動產生保守的 watch 標註候選）。merge 規則：舊 marks 保留(累積歷史)、
Claude 欄位不被覆蓋，除非 --refresh-claude。

省 token 分流（2026-07-23）：引擎為每檔產 review={due,why}——機械觸發器判定「這檔是否
需要 Claude 重寫判讀」。排程場次僅對 due=true 的標的做判讀，其餘保留原判讀不讀不寫。

CTA 趨勢跟蹤層（2026-07-30）：自 cta_trend.py 匯入六訊號模型，把趨勢分數/三條觸發線
(50/100/200 翻轉價)/RV20 百分位寫進 computed_tech.cta；SPY/QQQ/IWM 摘要進 market.cta。

自動趨勢線層（2026-08-01）：自 auto_trendline.py 匯入 TrendSpider 式自動畫線（pivot
兩兩成線+觸及驗證+突破偵測），寫進 computed_tech.trendlines（與前端駕駛艙同演算法）。

財報營收階梯（2026-08-01 P3A）：full mode 抓 SEC companyfacts 近 16 季營收+YoY，寫
computed_fund.rev_q（週節流、財報日後重抓；10-K 年度−前三季=Q4 推導；fail-open）。

型態辨識層（2026-08-01 P4）：自 patterns.py 匯入 ZigZag+古典型態（頭肩/雙頂底/三角/楔形/
旗形/杯柄，逐條規則存 why[]）+蠟燭型態，寫進 computed_tech.patterns（與前端駕駛艙同演算法）。

用法：
  python3 stock_signals.py --symbols MU,SNDK,... --out data/signals.json \
      [--kline-dir data] [--config config.json] [--mode full|intraday] [--prev data/signals.json]
mode=intraday：只更新 gamma/⑦/大盤/現價觸發，不重算內部人與財報日（快）。
SEC 聯絡信箱（SEC fair-access 規範要求 UA 附聯絡方式）：config.json 的 sec_contact 或環境變數
SEC_CONTACT；皆無時用通用位址（2026-08-31 起自原始碼移除,以便腳本可放公開 repo）。
"""
import json, os, sys, time, argparse, urllib.request, urllib.parse, re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
SEC_UA = {"User-Agent": "market-flow-research " + (os.environ.get("SEC_CONTACT") or "research@users.noreply.github.com")}
DQ = []
def dq(src, ok, note=""): DQ.append({"source": src, "ok": bool(ok), "note": str(note)[:160]})
def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)
def now_utc(): return datetime.now(timezone.utc)
def utcs(): return now_utc().strftime("%Y-%m-%d %H:%M:%S")

def http_get(url, timeout=20, retries=3, hdr=None):
    req = urllib.request.Request(url, headers=hdr or UA)
    last = None
    for a in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            last = e; time.sleep(0.6*(a+1))
    raise last
def http_json(url, timeout=20, retries=3, hdr=None):
    return json.loads(http_get(url, timeout, retries, hdr).decode("utf-8", "replace"))

ETFS = {"SPY","QQQ","DIA","IWM","SMH","SOXX","TQQQ","SQQQ","SOXL","SOXS","NVDL","NVDS","TSLL","TSLZ",
        "FNGU","FNGD","SPXL","SPXS","UPRO","SPXU","TNA","TZA","UDOW","SDOW","MUU","SNXX","MVLL","GLD","SLV","USO"}
try:
    from cta_trend import compute as cta_compute
except ImportError:
    cta_compute=None
try:
    from auto_trendline import trendlines_for
except ImportError:
    trendlines_for=None
try:
    from patterns import patterns_for
except ImportError:
    patterns_for=None
try:
    from backtest import backtest_for, DISCLAIMER as BT_DISCLAIMER, MIN_N as BT_MIN_N
except ImportError:
    backtest_for=None; BT_DISCLAIMER=""; BT_MIN_N=20

# ---------------- 技術指標 ----------------
def ema(vals, n):
    out=[None]*len(vals); k=2/(n+1); e=None
    for i,v in enumerate(vals):
        if v is None: out[i]=e; continue
        e=v if e is None else v*k+e*(1-k); out[i]=e
    return out
def sma(vals, n, i=None):
    if i is None: i=len(vals)-1
    s=vals[max(0,i-n+1):i+1]
    s=[x for x in s if x is not None]
    return sum(s)/len(s) if len(s)>=n else None
def wilder_rsi(closes, p):
    out=[None]*len(closes); au=ad=0.0
    for i in range(1,len(closes)):
        ch=closes[i]-closes[i-1]; u=max(ch,0); d=max(-ch,0)
        if i<=p: au+=u/p; ad+=d/p
        if i>p: au=(au*(p-1)+u)/p; ad=(ad*(p-1)+d)/p
        if i>=p: out[i]=100.0 if ad==0 else 100-100/(1+au/ad)
    return out
def obv_series(closes, vols):
    out=[0]*len(closes)
    for i in range(1,len(closes)):
        out[i]=out[i-1]+(vols[i] if closes[i]>closes[i-1] else -vols[i] if closes[i]<closes[i-1] else 0)
    return out
def boll(closes, n=20, k=2.0):
    mid=[sma(closes,n,i) for i in range(len(closes))]
    up=[None]*len(closes); lo=[None]*len(closes); bw=[None]*len(closes)
    for i in range(len(closes)):
        if mid[i] is None: continue
        seg=closes[i-n+1:i+1]
        m=mid[i]; sd=(sum((x-m)**2 for x in seg)/n)**0.5
        up[i]=m+k*sd; lo[i]=m-k*sd; bw[i]=(up[i]-lo[i])/m*100 if m else None
    return mid,up,lo,bw
def td_states(bars):
    """回傳 su(±1..9), cb, cs 與最近完成事件"""
    n=len(bars); su=[0]*n; cb=[0]*n; cs=[0]*n
    b=s=0
    for i in range(4,n):
        c=bars[i]["c"]; c4=bars[i-4]["c"]
        if c<c4: b=(1 if b>=9 else b+1); s=0; su[i]=-b
        elif c>c4: s=(1 if s>=9 else s+1); b=0; su[i]=s
        else: b=s=0
    ba=sa=False; bc=sc=0
    for i in range(n):
        if su[i]==-9: ba=True; bc=0; sa=False
        if su[i]==9: sa=True; sc=0; ba=False
        if ba and i>=2 and bars[i]["c"]<=bars[i-2]["l"]:
            bc+=1; cb[i]=bc
            if bc>=13: ba=False
        if sa and i>=2 and bars[i]["c"]>=bars[i-2]["h"]:
            sc+=1; cs[i]=sc
            if sc>=13: sa=False
    return su,cb,cs

def analyze_technicals(bars):
    """bars: [{d,o,h,l,c,v,tor}] 日K"""
    if len(bars)<30: return None
    C=[b["c"] for b in bars]; V=[b["v"] for b in bars]
    e5,e10,e20,e50=ema(C,5),ema(C,10),ema(C,20),ema(C,50)
    e120,e200=ema(C,120),ema(C,200)
    r6,r12=wilder_rsi(C,6),wilder_rsi(C,12)
    ob=obv_series(C,V); obm=[sma(ob,30,i) for i in range(len(ob))]
    mid,up,lo,bw=boll(C)
    su,cbn,csn=td_states([{"c":b["c"],"l":b["l"],"h":b["h"]} for b in bars])
    i=len(bars)-1; c=C[i]
    v20=sma(V[:-1] if len(V)>21 else V,20)
    volpace=round(V[i]/v20,2) if v20 else None
    # 近30根 RSI/OBV 背離（價新低 vs 指標未新低）
    look=min(30,i)
    seg=range(i-look+1,i+1)
    pmin_i=min(seg,key=lambda j:C[j]); div_rsi=div_obv=False
    if C[i-look+1:i+1] and pmin_i>i-look:
        prev_min_i=min(range(i-look+1,pmin_i),key=lambda j:C[j]) if pmin_i>i-look+2 else None
        if prev_min_i is not None and C[pmin_i]<C[prev_min_i]:
            if r6[pmin_i] is not None and r6[prev_min_i] is not None and r6[pmin_i]>r6[prev_min_i]: div_rsi=True
            if ob[pmin_i]>ob[prev_min_i]: div_obv=True
    # BOLL 擠壓：當前帶寬位於近120日帶寬第幾百分位
    bws=[x for x in bw[-120:] if x is not None]; sq_pct=None
    if bw[i] is not None and len(bws)>=30:
        sq_pct=round(100*sum(1 for x in bws if x<=bw[i])/len(bws),0)
    # swing 高低（近60根）
    lookb=min(60,i)
    swing_hi=max(bars[j]["h"] for j in range(i-lookb+1,i+1))
    swing_lo=min(bars[j]["l"] for j in range(i-lookb+1,i+1))
    # 最近 TD 事件（60 根內）
    events=[]
    for j in range(max(0,i-60),i+1):
        if su[j]==-9: events.append({"d":bars[j]["d"],"t":"TD9買入結構完成(下跌Setup 9)"})
        if su[j]==9: events.append({"d":bars[j]["d"],"t":"TD9賣出結構完成(上漲Setup 9)"})
        if cbn[j]==13: events.append({"d":bars[j]["d"],"t":"TD13買方倒數完成"})
        if csn[j]==13: events.append({"d":bars[j]["d"],"t":"TD13賣方倒數完成"})
    tor=bars[i].get("tor")
    return {
      "close":round(c,3),"d":bars[i]["d"],
      "ema5":rnd(e5[i]),"ema10":rnd(e10[i]),"ema20":rnd(e20[i]),"ema50":rnd(e50[i]),
      "ema120":rnd(e120[i]),"ema200":rnd(e200[i]),
      "vs_ema20_pct":rnd(100*(c/e20[i]-1),2) if e20[i] else None,
      "vs_ema50_pct":rnd(100*(c/e50[i]-1),2) if e50[i] else None,
      "rsi6":rnd(r6[i],1),"rsi12":rnd(r12[i],1),
      "boll_mid":rnd(mid[i]),"boll_up":rnd(up[i]),"boll_lo":rnd(lo[i]),
      "boll_bw_pctile":sq_pct,
      "obv_above_ma":bool(ob[i]>obm[i]) if obm[i] is not None else None,
      "vol_pace":volpace,"turnover_rate":tor,
      "chg1d":rnd(100*(C[i]/C[i-1]-1),2) if i>=1 else None,
      "chg5d":rnd(100*(C[i]/C[i-5]-1),2) if i>=5 else None,
      "chg20d":rnd(100*(C[i]/C[i-20]-1),2) if i>=20 else None,
      "off_60d_high_pct":rnd(100*(c/swing_hi-1),1),"swing_hi":rnd(swing_hi),"swing_lo":rnd(swing_lo),
      "td_setup_now":su[i],"td_buy_cd":cbn[i],"td_sell_cd":csn[i],
      "td_events_60d":events[-6:],
      "rsi_bull_div":div_rsi,"obv_bull_div":div_obv,
    }
def rnd(x,d=3):
    return None if x is None else round(float(x),d)

# ---------------- CBOE GEX 剖面 ----------------
def opt_parse(code):
    body=code[-15:]; return "20"+body[:2]+"-"+body[2:4]+"-"+body[4:6], body[6], int(body[7:])/1000.0
def gex_profile(sym):
    d=http_json(f"https://cdn.cboe.com/api/global/delayed_quotes/options/{sym}.json",30,2)
    data=d.get("data",{}); opts=data.get("options",[]); spot=data.get("current_price")
    if not spot or not opts: return None
    today=now_utc().strftime("%Y-%m-%d")
    by_strike={}; cv=pv=coi=poi=0.0; gex=0.0; zero=0.0; atm=[]
    calloi_by={}; putoi_by={}; oi_str={}
    for o in opts:
        code=o.get("option","")
        if len(code)<15: continue
        exp,cp,K=opt_parse(code)
        oi=o.get("open_interest") or 0.0; vol=o.get("volume") or 0.0
        g=o.get("gamma") or 0.0; iv=o.get("iv") or 0.0
        sign=1 if cp=="C" else -1
        gx=sign*g*oi*100*spot*spot*0.01
        gex+=gx; by_strike[K]=by_strike.get(K,0.0)+gx
        if cp=="C": cv+=vol; coi+=oi; calloi_by[K]=calloi_by.get(K,0.0)+oi
        else: pv+=vol; poi+=oi; putoi_by[K]=putoi_by.get(K,0.0)+oi
        if exp==today: zero+=vol
        if iv and abs(K-spot)/spot<=0.03: atm.append(iv)
        if oi: oi_str[K]=oi_str.get(K,0.0)+oi
    # gamma 翻轉位：strike 累計淨 gamma 的零交叉(雙向偵測,取最接近現價者;近似法,同 gex-tracker 慣例)
    ks=sorted(by_strike); cum=0.0; crossings=[]
    prevK=None; prevC=None
    for K in ks:
        cum+=by_strike[K]
        if prevC is not None and (prevC<0<=cum or prevC>0>=cum):
            crossings.append(K if abs(cum)<abs(prevC) else prevK)
        prevK=K; prevC=cum
    crossings=[k for k in crossings if k and abs(k-spot)/spot<0.35]
    flip=min(crossings,key=lambda k:abs(k-spot)) if crossings else None
    # 牆：現價上方 call OI 最大 / 下方 put OI 最大（±15% 內較有操作意義）
    cw=[K for K in calloi_by if spot<=K<=spot*1.15]
    call_wall=max(cw,key=lambda K:calloi_by[K]) if cw else None
    pw=[K for K in putoi_by if spot*0.85<=K<=spot]
    put_wall=max(pw,key=lambda K:putoi_by[K]) if pw else None
    # max pain
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
    callshare=cv/(cv+pv) if (cv+pv) else None
    # 擠壓分數（0-100;規則透明,詳 note）
    score=0; why=[]
    if gex<0: score+=30; why.append("dealer 空gamma(+30)")
    if flip and spot<flip: score+=15; why.append("價在翻轉位下(波動放大區,+15)")
    if callshare and callshare>0.58: score+=20; why.append(f"call量佔比{callshare:.0%}(+20)")
    if call_wall and 0<(call_wall/spot-1)<=0.06: score+=15; why.append("距call牆<6%(+15)")
    if (cv+pv) and zero/(cv+pv)>0.3: score+=10; why.append("0DTE佔比高(+10)")
    if atm and (sum(atm)/len(atm))>1.0: score+=10; why.append("IV>100%(+10)")
    return {"spot":round(spot,2),"gex_bn":round(gex/1e9,3),"flip":rnd(flip,2),
            "call_wall":rnd(call_wall,2),"put_wall":rnd(put_wall,2),"max_pain":rnd(mp,2),
            "atm_iv":round(sum(atm)/len(atm)*100,1) if atm else None,
            "pc_vol":round(pv/cv,3) if cv else None,"call_share":rnd(callshare,3),
            "zero_dte_share":round(zero/(cv+pv),3) if (cv+pv) else None,
            "squeeze_score":min(100,score),"squeeze_why":why,"asof":utcs()}

# ---------------- SEC Form 4 內部人 ----------------
_CIK=None
def cik_map():
    global _CIK
    if _CIK is not None: return _CIK
    cache="._cik_cache.json"
    try:
        if os.path.exists(cache) and time.time()-os.path.getmtime(cache)<7*86400:
            _CIK=json.load(open(cache)); return _CIK
    except Exception: pass
    d=http_json("https://www.sec.gov/files/company_tickers.json",25,2,SEC_UA)
    _CIK={v["ticker"].upper():int(v["cik_str"]) for v in d.values()}
    try: json.dump(_CIK,open(cache,"w"))
    except Exception: pass
    return _CIK
def insider_90d(sym):
    if sym in ETFS: return None
    cik=cik_map().get(sym)
    if not cik: return None
    sub=http_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json",25,2,SEC_UA)
    rec=sub.get("filings",{}).get("recent",{})
    forms=rec.get("form",[]); accs=rec.get("accessionNumber",[]); dates=rec.get("filingDate",[])
    docs=rec.get("primaryDocument",[])
    cutoff=(now_utc()-timedelta(days=90)).strftime("%Y-%m-%d")
    idx=[i for i,f in enumerate(forms) if f=="4" and dates[i]>=cutoff][:10]
    p_cnt=s_cnt=0; p_val=s_val=0.0; last=[]
    for i in idx:
        acc=accs[i].replace("-",""); doc=docs[i].split("/")[-1]   # 去掉 xslF345X0x/ 前綴=原始XML
        try:
            xml=http_get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}",20,2,SEC_UA)
            root=ET.fromstring(xml)
            owner=(root.findtext(".//rptOwnerName") or "").title()
            officer=root.findtext(".//officerTitle") or ""
            for tr in root.iter("nonDerivativeTransaction"):
                code=tr.findtext(".//transactionCode") or ""
                sh=tr.findtext(".//transactionShares/value"); px=tr.findtext(".//transactionPricePerShare/value")
                ad=tr.findtext(".//transactionAcquiredDisposedCode/value") or ""
                dt=tr.findtext(".//transactionDate/value") or dates[i]
                try: val=float(sh or 0)*float(px or 0)
                except ValueError: val=0
                if code=="P" or (code=="A" and ad=="A" and val>0):
                    p_cnt+=1; p_val+=val
                    last.append({"d":dt,"who":owner or officer,"act":"買","val":round(val)})
                elif code=="S":
                    s_cnt+=1; s_val+=val
                    last.append({"d":dt,"who":owner or officer,"act":"賣","val":round(val)})
        except Exception:
            continue
        time.sleep(0.15)
    last=sorted(last,key=lambda x:x["d"],reverse=True)[:5]
    return {"p_cnt":p_cnt,"s_cnt":s_cnt,"p_val":round(p_val),"s_val":round(s_val),
            "last":last,"asof":utcs(),"src":"SEC Form 4 (90天,前10筆申報)"}

# ---------------- SEC companyfacts 季營收(P3A;2026-08-01) ----------------
REV_TAGS=("RevenueFromContractWithCustomerExcludingAssessedTax","Revenues","SalesRevenueNet")
def revenue_quarters(sym, prev_fund=None, next_earnings=None):
    """近 16 季營收+YoY% → computed_fund.rev_q。10-Q 季值直取;10-K 年度值−同年度前三季=Q4。
    節流:prev asof <7 天且未剛過財報日 → 沿用 prev(其餘場次零成本);ETF/無 CIK/無資料回 None。"""
    if sym in ETFS: return None
    try:
        if prev_fund and prev_fund.get("rev_q") and prev_fund.get("asof"):
            age=(now_utc()-datetime.strptime(prev_fund["asof"][:10],"%Y-%m-%d").replace(tzinfo=timezone.utc)).days
            just_reported=False
            if next_earnings:
                de=(now_utc().date()-datetime.strptime(next_earnings,"%Y-%m-%d").date()).days
                just_reported=(0<=de<=2)
            if age<7 and not just_reported: return prev_fund
    except Exception: pass
    cik=cik_map().get(sym)
    if not cik: return None
    d=http_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json",40,2,SEC_UA)
    gaap=(d.get("facts") or {}).get("us-gaap") or {}
    from datetime import date as _date
    def _days(a,b):
        ya,ma,da=map(int,a.split("-")); yb,mb,db=map(int,b.split("-"))
        return (_date(yb,mb,db)-_date(ya,ma,da)).days
    # 三個 tag 中取「季頻資料最新」者(公司會換 tag,舊 tag 停更;NVDA 實例:RevenueFromContract… 停在 2020)
    units=None; tag_used=None; best_end=""
    for tag in REV_TAGS:
        u=((gaap.get(tag) or {}).get("units") or {}).get("USD")
        if not u: continue
        qe=[it["end"] for it in u if it.get("start") and it.get("end") and it.get("val") is not None
            and 80<=_days(it["start"],it["end"])<=100]
        if qe and max(qe)>best_end:
            best_end=max(qe); units=u; tag_used=tag
    if not units: return None
    q={}; annual=[]
    for it in units:
        st,en,v=it.get("start"),it.get("end"),it.get("val")
        if not st or not en or v is None: continue
        dd=_days(st,en)
        if 80<=dd<=100:
            q[en]={"end_d":en,"rev":float(v),"q":en[:7]}   # 標籤=期末年月(SEC fy/fp 是申報年,勿用)
        elif 350<=dd<=380:
            annual.append({"start":st,"end":en,"rev":float(v)})
    for a in annual:   # Q4 推導:年度 − 年度區間內三季
        if a["end"] in q: continue
        inner=[x for x in q.values() if a["start"]<=x["end_d"]<a["end"]]
        if len(inner)==3:
            v4=a["rev"]-sum(x["rev"] for x in inner)
            if v4>0:
                q[a["end"]]={"end_d":a["end"],"rev":v4,"q":a["end"][:7]}
    rows=sorted(q.values(), key=lambda x:x["end_d"])[-20:]
    out=[]
    for i,r in enumerate(rows):
        yoy=None
        if i>=4:
            base=rows[i-4]["rev"]; dd2=_days(rows[i-4]["end_d"],r["end_d"])
            if base>0 and 330<=dd2<=400: yoy=round(100*(r["rev"]/base-1),1)
        out.append({"q":r["q"],"end_d":r["end_d"],"rev":round(r["rev"]),"yoy":yoy})
    out=out[-16:]
    if not out: return None
    return {"rev_q":out,"asof":utcs(),"src":"SEC companyfacts","tag":tag_used}

# ---------------- Yahoo 財報日(crumb, best-effort) ----------------
def yahoo_earnings(sym):
    try:
        import http.cookiejar
        cj=http.cookiejar.CookieJar()
        op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.addheaders=[("User-Agent",UA["User-Agent"])]
        try: op.open("https://fc.yahoo.com",timeout=10).read()
        except Exception: pass
        crumb=op.open("https://query1.finance.yahoo.com/v1/test/getcrumb",timeout=10).read().decode().strip()
        if not crumb or "<" in crumb: return None
        d=json.load(op.open(f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{urllib.parse.quote(sym)}?modules=calendarEvents&crumb={urllib.parse.quote(crumb)}",timeout=12))
        ev=d["quoteSummary"]["result"][0]["calendarEvents"]["earnings"]
        arr=ev.get("earningsDate") or []
        if not arr: return None
        ts=arr[0].get("raw")
        dt=datetime.fromtimestamp(ts,timezone.utc).strftime("%Y-%m-%d") if ts else None
        est=len(arr)>1  # 區間=未確認
        return {"date":dt,"est":est}
    except Exception:
        return None

# ---------------- 主流程 ----------------
def load_kline(sym,kdir,gist_base):
    if kdir:
        p=os.path.join(kdir,f"kline_{sym}.json")
        if os.path.exists(p):
            try: return json.load(open(p))
            except Exception: pass
    if gist_base:
        try: return json.loads(http_get(gist_base+f"kline_{sym}.json",20,2).decode())
        except Exception: return None
    return None
def bars_of(raw):
    return [{"d":b[0],"o":b[1],"h":b[2],"l":b[3],"c":b[4],"v":b[5],"tor":b[6]} for b in (raw or {}).get("bars",[])]

def market_regime(kd, mkt):
    spy=analyze_technicals(bars_of(kd.get("SPY"))) if kd.get("SPY") else None
    smh=analyze_technicals(bars_of(kd.get("SMH"))) if kd.get("SMH") else None
    vix=None
    try: vix=(mkt.get("options",{}).get("_VIX") or {}).get("spot")
    except Exception: pass
    light="🟢"; notes=[]
    if spy:
        if spy["vs_ema20_pct"] is not None and spy["vs_ema20_pct"]<0: light="🟡"; notes.append(f"SPY 低於 20DMA {spy['vs_ema20_pct']}%")
        else: notes.append(f"SPY 高於 20DMA {spy['vs_ema20_pct']}%")
        if spy["vs_ema50_pct"] is not None and spy["vs_ema50_pct"]<0 and (vix or 0)>28: light="🔴"
    if vix:
        notes.append(f"VIX {vix}")
        if vix>24 and light=="🟢": light="🟡"
    if smh and smh["chg20d"] is not None and spy and spy["chg20d"] is not None:
        rs=smh["chg20d"]-spy["chg20d"]
        notes.append(f"SMH-SPY 20日相對 {rs:+.1f}%")
    return {"regime_light":light,"vix":vix,
            "spy_vs_20dma":spy["vs_ema20_pct"] if spy else None,
            "spy_vs_50dma":spy["vs_ema50_pct"] if spy else None,
            "notes":notes,"asof":utcs()}

def auto_marks(tech):
    """保守自動標註候選：只標 TD 事件(watch);買賣點升級由 Claude 判讀"""
    out=[]
    for ev in (tech or {}).get("td_events_60d",[]):
        kind="watch"
        out.append({"d":ev["d"],"kind":kind,"title":ev["t"],"auto":True,
                    "reasons":{"tech":[ev["t"]+"（TD Sequential 自動偵測）"]},"conf":1})
    return out

def compute_review(node, prev_gamma, prev_cta=None):
    """省 token 分流：機械觸發器判定本檔是否需要 Claude 重寫判讀。
    觸發任一即 due=true；全未觸發 due=false（排程場次直接跳過該檔判讀）。fail-open。"""
    try:
        why=[]
        t=node.get("computed_tech") or {}; g=node.get("gamma") or {}; f7=node.get("futu7") or {}
        c=t.get("close")
        if not node.get("stance"): why.append("無既有判讀")
        plan=node.get("plan") or {}
        for e in (plan.get("entry") or []):
            lo,hi=e.get("px_lo"),e.get("px_hi")
            if c and lo and hi and lo*0.99<=c<=hi*1.01: why.append("價入entry區"); break
        st=(plan.get("stop") or {}).get("px")
        if c and st and c<=st*1.01: why.append("價觸停損")
        tg=plan.get("targets") or []
        if c and tg and isinstance(tg[0],dict) and tg[0].get("px") and c>=tg[0]["px"]*0.99: why.append("價達目標1")
        if abs(t.get("td_setup_now") or 0)==9 or t.get("td_buy_cd")==13 or t.get("td_sell_cd")==13:
            why.append("TD9/13完成")
        d1,d5=f7.get("d1"),f7.get("d5")
        if d1 is not None and d5 is not None and abs(d1)>5e6 and (d1>0)!=(d5>0): why.append("⑦與5日反向")
        sp,fl=g.get("spot"),g.get("flip"); psp,pfl=prev_gamma.get("spot"),prev_gamma.get("flip")
        if sp and fl and psp and pfl and ((sp>fl)!=(psp>pfl)): why.append("gamma翻轉位易手")
        ne=node.get("next_earnings")
        if ne:
            dd=(datetime.strptime(ne,"%Y-%m-%d").date()-now_utc().date()).days
            if 0<=dd<=3: why.append("財報%d天內"%dd)
        if (g.get("squeeze_score") or 0)>=70 and (prev_gamma.get("squeeze_score") or 0)<70: why.append("擠壓≥70首見")
        # CTA 觸發線易手 / 分數翻轉(2026-07-30)
        cta=(t.get("cta") or {}); pc=prev_cta or {}
        if cta and pc:
            if (cta.get("score") or 0)*(pc.get("score") or 0)<0: why.append("CTA分數翻轉")
            for k,lab in (("ma50","短期"),("ma100","中期"),("ma200","長期")):
                a_=((cta.get("triggers") or {}).get(k) or {}).get("dist_pct")
                b_=((pc.get("triggers") or {}).get(k) or {}).get("dist_pct")
                if a_ is not None and b_ is not None and (a_>0)!=(b_>0): why.append("CTA"+lab+"線易手")
        return {"due":bool(why),"why":why[:6],"asof":utcs()}
    except Exception as e:
        return {"due":True,"why":["review計算例外(保守列入):"+str(e)[:60]],"asof":utcs()}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--symbols",default="MU,SNDK,WDC,MRVL,LITE,COHR,AAOI,NVDA,AVGO,SMH,SOXX,SPY,QQQ")
    ap.add_argument("--out",default="data/signals.json")
    ap.add_argument("--prev",default=None)
    ap.add_argument("--kline-dir",default=None)
    ap.add_argument("--config",default="config.json")
    ap.add_argument("--mode",default="full",choices=["full","intraday"])
    ap.add_argument("--refresh-claude",action="store_true")
    a=ap.parse_args()
    syms=[s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    cfg={}
    if os.path.exists(a.config):
        try: cfg=json.load(open(a.config))
        except Exception: pass
    if cfg.get("sec_contact"): SEC_UA["User-Agent"]="market-flow-research "+str(cfg["sec_contact"])
    gist_base=None
    mdu=cfg.get("market_data_url")
    if mdu: gist_base=mdu.rsplit("/",1)[0]+"/"
    mkt={}
    if mdu:
        try: mkt=http_json(mdu,25,2); dq("market_data",True,f"ts={mkt.get('ts_utc')}")
        except Exception as e: dq("market_data",False,e)
    prev={}
    pv=a.prev or a.out
    if pv and os.path.exists(pv):
        try: prev=json.load(open(pv))
        except Exception: pass
    kd={}
    for s in set(syms)|{"SPY","SMH","QQQ","IWM"}:
        kd[s]=load_kline(s,a.kline_dir,gist_base)
    dq("kline",sum(1 for v in kd.values() if v),f"{sum(1 for v in kd.values() if v)}/{len(kd)}")
    out={"updated_utc":utcs(),"mode":a.mode,
         "market":market_regime(kd,mkt),
         "symbols":prev.get("symbols",{}) if isinstance(prev.get("symbols"),dict) else {}}
    if cta_compute:
        cta_mkt={}
        for s_ in ("SPY","QQQ","IWM"):
            try:
                rows,_=cta_compute(s_,(kd.get(s_) or {}).get("bars") or [])
                if rows:
                    cur=rows[-1]
                    cta_mkt[s_]={"score":cur["score"],
                                 "mid_px":round(cur["trig"]["ma100"],2),
                                 "mid_dist_pct":round(100*(cur["trig"]["ma100"]/cur["c"]-1),2),
                                 "rv_pct":cur["rv_pct"]}
            except Exception: pass
        if cta_mkt: out["market"]["cta"]=cta_mkt
    for s in syms:
        node=out["symbols"].get(s,{})
        prev_gamma=dict(node.get("gamma") or {})
        prev_cta=dict((node.get("computed_tech") or {}).get("cta") or {})
        tech=analyze_technicals(bars_of(kd.get(s))) if kd.get(s) else None
        if tech: node["computed_tech"]=tech
        # CTA 趨勢跟蹤層(六訊號分數+觸發線+RV百分位;cta_trend.py)
        if cta_compute and kd.get(s):
            try:
                rows,evs=cta_compute(s,(kd[s] or {}).get("bars") or [])
                if rows:
                    cur=rows[-1]
                    cutoff30=(now_utc()-timedelta(days=30)).strftime("%Y-%m-%d")
                    node.setdefault("computed_tech",{})["cta"]={
                        "tag":"CTA觸發" if s in {"SPY","QQQ","IWM","DIA"} else "趨勢位階",
                        "score":cur["score"],"rv20":cur["rv20"],"rv_pct":cur["rv_pct"],
                        "triggers":{k:{"px":round(cur["trig"][k],2),
                                       "dist_pct":round(100*(cur["trig"][k]/cur["c"]-1),2)} for k in cur["trig"]},
                        "events_30d":[e for e in evs if e.get("d","")>=cutoff30][-6:],
                        "asof":cur["d"]}
                dq(f"cta {s}",bool(rows))
            except Exception as e: dq(f"cta {s}",False,e)
        # 型態辨識層(ZigZag+古典型態+蠟燭;patterns.py;2026-08-01 P4;與前端同演算法;fail-open)
        if patterns_for and kd.get(s):
            try:
                pt=patterns_for((kd[s] or {}).get("bars") or [])
                if pt is not None:
                    node.setdefault("computed_tech",{})["patterns"]=pt
                dq(f"patterns {s}",pt is not None,"" if pt is not None else "K線歷史不足")
            except Exception as e: dq(f"patterns {s}",False,e)
        # 規則回測層(backtest.py;2026-08-01 P7;預設規則組;與前端 backtest() 逐筆一致;fail-open)
        # ⚠ 歷史模擬:含前視偏誤、未計滑價與交易成本;樣本 <20 標 few=True。任何引用處必須一併呈現 disclaimer。
        if backtest_for and kd.get(s):
            try:
                bt=backtest_for((kd[s] or {}).get("bars") or [])
                if bt is not None and not bt.get("err"):
                    st=bt.get("stat") or {}
                    node.setdefault("computed_tech",{})["backtest"]={
                        "rule_in": bt.get("inK"), "rule_out": bt.get("outK"),
                        "n": st.get("n"), "win": st.get("win"), "avg": st.get("avg"),
                        "hold": st.get("hold"), "mdd": st.get("mdd"), "pf": st.get("pf"),
                        "eq": st.get("eq"), "bh": st.get("bh"),
                        "first": st.get("first"), "last": st.get("last"),
                        "few": st.get("few"), "min_n": BT_MIN_N,
                        "open": st.get("open"),
                        "trades_10": (bt.get("trades") or [])[-10:],
                        "disclaimer": BT_DISCLAIMER}
                dq(f"backtest {s}", bt is not None, "" if bt is not None else "K線歷史不足")
            except Exception as e: dq(f"backtest {s}",False,e)
        # 自動趨勢線層(pivot 兩兩成線+觸及驗證+突破偵測;auto_trendline.py;2026-08-01)
        # 與前端駕駛艙同參數同演算法;歷史不足回 None → 只缺 trendlines 欄,不影響其餘(fail-open)
        if trendlines_for and kd.get(s):
            try:
                tl=trendlines_for((kd[s] or {}).get("bars") or [])
                if tl is not None:
                    node.setdefault("computed_tech",{})["trendlines"]=tl
                dq(f"trendline {s}",tl is not None,"" if tl is not None else "K線歷史不足")
            except Exception as e: dq(f"trendline {s}",False,e)
        try:
            g=gex_profile(s); time.sleep(1.0)
            if g: node["gamma"]=g
            dq(f"gex {s}",bool(g))
        except Exception as e: dq(f"gex {s}",False,e)
        if a.mode=="full":
            try:
                ins=insider_90d(s)
                if ins is not None: node["insider_90d"]=ins
                dq(f"insider {s}",ins is not None,"" if ins else "ETF或無CIK")
            except Exception as e: dq(f"insider {s}",False,e)
            try:
                ey=yahoo_earnings(s)
                today=now_utc().strftime("%Y-%m-%d")
                if ey and ey.get("date") and ey["date"]>=today:
                    node["next_earnings"]=ey["date"]
                    node["earnings_src"]="yahoo"+("(est)" if ey.get("est") else "")
                elif ey and ey.get("date"):
                    node.pop("next_earnings",None)
                    node["earnings_note_auto"]="下季日期公司尚未公告(最近一次 "+ey["date"]+")"
                dq(f"earnings {s}",bool(ey and ey.get("date")))
            except Exception as e: dq(f"earnings {s}",False,e)
            # 財報營收階梯(P3A):SEC companyfacts 近16季+YoY → computed_fund.rev_q(週節流/財報後重抓;fail-open)
            try:
                rq=revenue_quarters(s, node.get("computed_fund"), node.get("next_earnings"))
                if rq is not None: node["computed_fund"]=rq
                dq(f"rev_q {s}",rq is not None,"" if rq is not None else "ETF或無資料")
            except Exception as e: dq(f"rev_q {s}",False,e)
            time.sleep(0.3)
        # ⑦ 持續性
        try:
            cap=(mkt.get("capital_flow") or {}).get("US."+s)
            d1=cap.get("main_net") if cap else None
            d5=None
            df=mkt.get("daily_flows") or {}
            for d_ in sorted(df)[-5:]:
                e=df[d_].get(s)
                if e and e.get("m") is not None: d5=(d5 or 0)+e["m"]
            node["futu7"]={"d1":d1,"d5":rnd(d5,1),"asof":mkt.get("ts_utc")}
        except Exception: pass
        # 自動 watch 標註（不覆蓋既有同日同題標註）
        marks=node.get("marks",[])
        seen={(m.get("d"),m.get("title")) for m in marks}
        for m in auto_marks(tech):
            if (m["d"],m["title"]) not in seen: marks.append(m)
        node["marks"]=sorted(marks,key=lambda m:m.get("d",""))[-60:]
        node["review"]=compute_review(node,prev_gamma,prev_cta)
        node["engine_updated_utc"]=utcs()
        out["symbols"][s]=node
    out["data_quality"]=DQ
    os.makedirs(os.path.dirname(a.out) or ".",exist_ok=True)
    json.dump(out,open(a.out,"w"),ensure_ascii=False,indent=1)
    log(f"signals -> {a.out} symbols={len(syms)}")
    due=[s for s in syms if out["symbols"][s].get("review",{}).get("due")]
    log(f"review due={len(due)}/{len(syms)}: {','.join(due) or '(無)'}")
    # 簡報
    for s in syms:
        n=out["symbols"][s]; t=n.get("computed_tech") or {}; g=n.get("gamma") or {}
        log(f"{s:5s} c={t.get('close')} rsi6={t.get('rsi6')} td={t.get('td_setup_now')}/cd{t.get('td_buy_cd')} "
            f"gex={g.get('gex_bn')} flip={g.get('flip')} cw={g.get('call_wall')} pw={g.get('put_wall')} sq={g.get('squeeze_score')} "
            f"ins={'' if not n.get('insider_90d') else str(n['insider_90d']['p_cnt'])+'買/'+str(n['insider_90d']['s_cnt'])+'賣'} "
            f"earn={n.get('next_earnings')} "
            f"cta={((n.get('computed_tech') or {}).get('cta') or {}).get('score')} "
            f"due={'Y' if n.get('review',{}).get('due') else 'n'}")

if __name__=="__main__":
    main()
