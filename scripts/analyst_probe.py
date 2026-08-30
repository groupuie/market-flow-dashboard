#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析師層試驗引擎(2026-08-08;純 stdlib、只讀公開資料、fail-open)
產出 data/analyst.json:評級分布/目標價區間/逐月評級史/EPS 預估vs實際+驚喜%/
財報揭露日(EDGAR 8-K item 2.02,含盤前盤後判定)/財報後3日反應(gist 日K計算)/預估上修下修。

資料源(本次試驗新增,採用前需使用者同意入 SPEC):
  api.nasdaq.com  — analyst/{s}/targetprice、analyst/{s}/ratings、quote/{s}/eps、
                    analyst/{s}/estimate-momentum(免金鑰;需 Origin/Referer 頭;日頻)
  data.sec.gov    — submissions(8-K item 2.02 = 財報揭露事件,acceptanceDateTime 精確到秒)
  gist 日K        — 3日反應計算(前復權收盤)
備援:Yahoo quoteSummary(crumb)寫成 try 層但本場 429,預設關(--try-yahoo 開)。

⚠ 誠實邊界:分析師評級/目標價=賣方觀點統計,系統性偏多、常滯後價格;
   驚喜%=對共識的偏離,不是「好壞」;3日反應=歷史描述非預測。均不構成投資建議。

用法:python3 analyst_probe.py --symbols NVDA,MU,... --out data/analyst.json [--kline-dir data] [--config config.json]
SEC 聯絡信箱:config.json 的 sec_contact 或環境變數 SEC_CONTACT(2026-08-31 起自原始碼移除)。
"""
import json, os, sys, time, argparse, urllib.request, urllib.parse, bisect
from datetime import datetime, timezone

NAS_H = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
         "Accept": "application/json, text/plain, */*", "Accept-Language": "en-US,en;q=0.9",
         "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"}
SEC_UA = {"User-Agent": "market-flow-research " + (os.environ.get("SEC_CONTACT") or "research@users.noreply.github.com")}
UA = {"User-Agent": NAS_H["User-Agent"]}
GIST = "https://gist.githubusercontent.com/groupuie/147672e7493b26aec57f42f5e12cb524/raw/"
ETFS = {"SPY","QQQ","DIA","IWM","SMH","SOXX","GLD","SLV","USO","TLT","IEF","SHY","UUP","VGK","EWJ","EWY","EWT","DBC",
        "TQQQ","SQQQ","SOXL","SOXS","NVDL","MUU","SNXX","MVLL","SPCX"}
MON = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,"Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
DQ = []
def dq(src, ok, note=""): DQ.append({"source": src, "ok": bool(ok), "note": str(note)[:160]})
def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)
def utcs(): return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def http_get(url, timeout=20, retries=3, hdr=None, backoff=1.2):
    last=None
    for a in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdr or UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:
            last=e; time.sleep(backoff*(a+1))
    raise last
def http_json(url, timeout=20, retries=3, hdr=None):
    return json.loads(http_get(url, timeout, retries, hdr).decode("utf-8","replace"))

# ---------- Nasdaq ----------
def nasdaq(path):
    j=http_json("https://api.nasdaq.com/api/"+path, 15, 3, NAS_H)
    return (j or {}).get("data")
def nas_analyst(sym):
    """targetprice + ratings + eps + estimate-momentum;個別失敗個別缺欄(fail-open)"""
    out={}
    try:
        tp=nasdaq(f"analyst/{sym}/targetprice") or {}
        co=tp.get("consensusOverview") or {}
        if co.get("priceTarget") is not None:
            out["pt"]={"low":co.get("lowPriceTarget"),"mean":co.get("priceTarget"),
                       "high":co.get("highPriceTarget"),
                       "buy":co.get("buy"),"hold":co.get("hold"),"sell":co.get("sell")}
        hist=[]
        for h in (tp.get("historicalConsensus") or []):
            z=h.get("z") or {}
            if z.get("date"):
                mm,dd,yy=z["date"].split("/")
                hist.append({"m":f"{yy}-{mm}","buy":z.get("buy"),"hold":z.get("hold"),
                             "sell":z.get("sell"),"px":h.get("y")})
        if hist: out["rating_hist"]=hist[-13:]
        dq(f"nasdaq tp {sym}", bool(out.get("pt")))
    except Exception as e: dq(f"nasdaq tp {sym}", False, e)
    time.sleep(0.5)
    try:
        rt=nasdaq(f"analyst/{sym}/ratings") or {}
        if rt.get("meanRatingType"):
            out["mean_rating"]=rt["meanRatingType"]
            s=rt.get("ratingsSummary") or ""
            n=[w for w in s.split() if w.isdigit()]
            out["n_analysts"]=int(n[0]) if n else None
        dq(f"nasdaq rt {sym}", bool(rt))
    except Exception as e: dq(f"nasdaq rt {sym}", False, e)
    time.sleep(0.5)
    try:
        ep=nasdaq(f"quote/{sym}/eps") or {}
        prev=[]; fwd=[]
        for e in (ep.get("earningsPerShare") or []):
            per=e.get("period"); est=e.get("consensus"); act=e.get("earnings")
            if e.get("type")=="PreviousQuarter" and per:
                spr=None
                if est not in (None,0) and act is not None:
                    spr=round(100*(act-est)/abs(est),1)
                prev.append({"per":per,"est":est,"act":act,"spr_pct":spr})
            elif e.get("type")=="UpcomingQuarter" and per:
                fwd.append({"per":per,"est":est})
        if prev: out["eps"]=prev
        if fwd: out["eps_fwd"]=fwd[:3]
        dq(f"nasdaq eps {sym}", bool(prev))
    except Exception as e: dq(f"nasdaq eps {sym}", False, e)
    time.sleep(0.5)
    try:
        em=nasdaq(f"analyst/{sym}/estimate-momentum") or {}
        ec=em.get("estimatesChanged") or {}
        def _v(k): return ((ec.get(k) or {}).get("changeValue"))
        if ec: out["est_momo"]={"q_up":_v("quarterDataUp"),"q_dn":_v("quarterDataDown"),
                                "y_up":_v("yearDataUp"),"y_dn":_v("yearDataDown")}
        dq(f"nasdaq momo {sym}", bool(ec))
    except Exception as e: dq(f"nasdaq momo {sym}", False, e)
    return out

# ---------- EDGAR 8-K 2.02 ----------
_CIK=None
def cik_map():
    global _CIK
    if _CIK is None:
        d=http_json("https://www.sec.gov/files/company_tickers.json",25,2,SEC_UA)
        _CIK={v["ticker"].upper():int(v["cik_str"]) for v in d.values()}
    return _CIK
def edgar_releases(sym):
    """[(filingDate, acceptanceDateTime)] 由新到舊;item 含 2.02"""
    cik=cik_map().get(sym)
    if not cik: return []
    sub=http_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json",30,2,SEC_UA)
    r=sub.get("filings",{}).get("recent",{})
    out=[]
    for i in range(len(r.get("form",[]))):
        if r["form"][i]=="8-K" and "2.02" in (r["items"][i] or ""):
            out.append((r["filingDate"][i], r["acceptanceDateTime"][i]))
    return out

# ---------- 3 日反應 ----------
def et_after_close(acc_utc):
    """acceptanceDateTime UTC → 是否美東 16:00 後(3-11月 EDT=UTC-4,其餘 EST=UTC-5;近似足矣)"""
    try:
        dt=datetime.strptime(acc_utc[:19],"%Y-%m-%dT%H:%M:%S")
        off=4 if 3<=dt.month<=10 else 5   # 邊界週誤差可忽略:財報極少落在切換日
        h=dt.hour-off
        return h>=16 or h<4               # 深夜檔也視為盤後
    except Exception:
        return True
def load_bars(sym, kdir):
    p=os.path.join(kdir or ".", f"kline_{sym}.json")
    if kdir and os.path.exists(p):
        try: return json.load(open(p)).get("bars")
        except Exception: pass
    try:
        return json.loads(http_get(GIST+f"kline_{sym}.json",20,2).decode()).get("bars")
    except Exception:
        return None
def chg3d(bars_dates, closes, fil_d, acc):
    i=bisect.bisect_left(bars_dates, fil_d)
    if et_after_close(acc):
        if not (i<len(bars_dates) and bars_dates[i]==fil_d): i-=1
    else:
        i-=1
    if i<0 or i+3>=len(bars_dates): return None,None
    b=closes[i]; e=closes[i+3]
    return (round(100*(e/b-1),2), bars_dates[i]) if b else (None,None)

def per_to_end(per):
    """'Apr 2026' → '2026-04-31'字典序上界(僅供比對,不需真日曆)"""
    try:
        m,y=per.split(); return f"{y}-{MON[m]:02d}-31"
    except Exception: return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--symbols",default="MU,SNDK,WDC,MRVL,LITE,COHR,AAOI,NVDA,AVGO,SMH,SOXX,SPY,QQQ")
    ap.add_argument("--out",default="data/analyst.json")
    ap.add_argument("--kline-dir",default=None)
    ap.add_argument("--config",default="config.json")
    a=ap.parse_args()
    try:
        _cfg=json.load(open(a.config)) if os.path.exists(a.config) else {}
        if _cfg.get("sec_contact"): SEC_UA["User-Agent"]="market-flow-research "+str(_cfg["sec_contact"])
    except Exception: pass
    syms=[s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    out={"updated_utc":utcs(),"src":"nasdaq(analyst/eps)+edgar(8-K 2.02)+gist kline(3d)",
         "note":"評級/目標價=賣方共識統計(系統性偏多、常滯後);驚喜%=(實際-共識)/|共識|;3日反應=揭露前收盤→第3個交易日收盤,歷史描述非預測;不構成投資建議。",
         "symbols":{}}
    for s in syms:
        node={}
        if s in ETFS:
            node["na"]="ETF 無分析師覆蓋"
            out["symbols"][s]=node
            dq(f"analyst {s}",True,"ETF skip"); continue
        node.update(nas_analyst(s))
        # EDGAR 財報日 + 3日反應
        try:
            rel=edgar_releases(s); time.sleep(0.3)
            bars=load_bars(s,a.kline_dir)
            if bars and rel and node.get("eps"):
                ds=[b[0] for b in bars]; cs=[b[4] for b in bars]
                rel_sorted=sorted(rel)   # 舊→新
                for q in node["eps"]:
                    ub=per_to_end(q["per"])
                    if not ub: continue
                    cand=[r for r in rel_sorted if r[0]>ub][:1]
                    # 上一行取「期末之後第一筆 8-K 2.02」;要求 80 天內,避免錯配
                    if cand:
                        fd,acc=cand[0]
                        y1,m1=int(ub[:4]),int(ub[5:7]); y2,m2=int(fd[:4]),int(fd[5:7])
                        if (y2-y1)*12+(m2-m1)<=3:
                            q["report_d"]=fd
                            c3,bd=chg3d(ds,cs,fd,acc)
                            if c3 is not None: q["chg3d_pct"]=c3
            if rel: node["last_report"]=rel[0][0]
            dq(f"edgar {s}",bool(rel))
        except Exception as e: dq(f"edgar {s}",False,e)
        out["symbols"][s]=node
        log(s, "pt=",(node.get("pt") or {}).get("mean"), "eps_q=",len(node.get("eps") or []),
            "3d=",[q.get("chg3d_pct") for q in (node.get("eps") or [])])
        time.sleep(0.6)
    out["data_quality"]=DQ
    os.makedirs(os.path.dirname(a.out) or ".",exist_ok=True)
    json.dump(out,open(a.out,"w"),ensure_ascii=False,indent=1)
    ok=sum(1 for s in syms if out["symbols"].get(s,{}).get("pt") or out["symbols"].get(s,{}).get("na"))
    log(f"analyst -> {a.out} 覆蓋 {ok}/{len(syms)}")

if __name__=="__main__":
    main()
