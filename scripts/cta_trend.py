#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CTA 趨勢跟蹤近似模型 — 原型/回測/事實產出(純 stdlib)
六子訊號:3 條 SMA 交叉(50/100/200,含今日解的翻轉價=前 N−1 日收盤均值)
        +3 個時序動能回看(63/126/252,翻轉價=K 日前收盤)
分數 = 六訊號 ±1 平均 ×100 ∈ [−100,+100]
另算 20 日年化實現波動(RV20)及其對自身近兩年的百分位(vol-scaling 縮部位壓力 proxy)。
語意:SPY/QQQ/IWM/DIA=「CTA 觸發」(指數期貨有真實機械流);其餘=「趨勢位階」(間接機制)。
用法:
  python3 cta_trend.py --symbols SPY,QQQ --kline-dir fresh [--fill-missing] [--since 2026-06-01]
  --json out.json  # 機器可讀(給 stock_signals.py / 前端對拍)
"""
import json, os, math, argparse, urllib.request, urllib.parse, time
from datetime import datetime, timezone

MA_N=(50,100,200); MOM_K=(63,126,252)
MA_LABEL={50:"短期",100:"中期",200:"長期"}
MOM_LABEL={63:"3月動能",126:"6月動能",252:"12月動能"}
CTA_SYMS={"SPY","QQQ","IWM","DIA"}
UA={"User-Agent":"Mozilla/5.0"}

def yahoo_fill(sym, have_dates, upto=None):
    """補缺的近日日K(僅回測用;正式資料由 Mac 富途覆蓋)"""
    try:
        q=urllib.parse.quote(sym)
        d=json.loads(urllib.request.urlopen(urllib.request.Request(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{q}?range=1mo&interval=1d",headers=UA),timeout=15).read())
        r=d["chart"]["result"][0]; ind=r["indicators"]["quote"][0]; ts=r.get("timestamp") or []
        off=r.get("meta",{}).get("gmtoffset",-14400)
        out=[]
        for i,t in enumerate(ts):
            o=(ind.get("open") or [None]*len(ts))[i]; h=(ind.get("high") or [None]*len(ts))[i]
            l=(ind.get("low") or [None]*len(ts))[i]; c=(ind.get("close") or [None]*len(ts))[i]
            v=(ind.get("volume") or [None]*len(ts))[i]
            if None in (o,h,l,c): continue
            dt=datetime.fromtimestamp(t+off,timezone.utc).strftime("%Y-%m-%d")
            if dt in have_dates: continue
            if upto and dt>upto: continue
            out.append([dt,round(o,3),round(h,3),round(l,3),round(c,3),int(v or 0),None])
        return out
    except Exception:
        return []

def load_bars(sym, kdir, fill=False, today_bar=None):
    p=os.path.join(kdir,f"kline_{sym}.json")
    raw=json.load(open(p))
    bars={b[0]:b for b in raw["bars"]}
    if fill:
        # 補到「今天之前」的缺日(例:gist 日更差一天)
        upto=today_bar[0] if today_bar else None
        for b in yahoo_fill(sym,set(bars),upto=None):
            if upto and b[0]>=upto: continue
            bars[b[0]]=b+["yfill"]
    if today_bar and today_bar[0] not in bars:
        bars[today_bar[0]]=list(today_bar)+["intraday"]
    elif today_bar:
        bars[today_bar[0]]=list(today_bar)+["intraday"]
    out=[bars[k] for k in sorted(bars)]
    return out, raw.get("src")

def sma(vals,i,n):
    if i+1<n: return None
    return sum(vals[i-n+1:i+1])/n

def compute(sym, bars):
    """回傳逐日 rows 與今日觸發線"""
    D=[b[0] for b in bars]; C=[float(b[4]) for b in bars]
    n=len(bars)
    rows=[]
    rv=[None]*n
    for i in range(n):
        if i>=20:
            rets=[math.log(C[j]/C[j-1]) for j in range(i-19,i+1) if C[j-1]>0]
            m=sum(rets)/len(rets)
            var=sum((x-m)**2 for x in rets)/(len(rets)-1)
            rv[i]=math.sqrt(var)*math.sqrt(252)*100
    for i in range(n):
        sigs={}; trig={}
        ok=True
        for N in MA_N:
            s=sma(C,i,N)
            if s is None: ok=False; break
            sigs["ma%d"%N]=1 if C[i]>s else -1
            trig["ma%d"%N]=sum(C[i-N+1:i])/ (N-1)   # 前 N−1 日均值=今日翻轉價
        if not ok: continue
        for K in MOM_K:
            if i-K<0: ok=False; break
            sigs["mom%d"%K]=1 if C[i]>C[i-K] else -1
            trig["mom%d"%K]=C[i-K]
        if not ok: continue
        score=round(100*sum(sigs.values())/len(sigs))
        # RV 百分位(對自身近 504 個 RV 觀測)
        rvp=None
        if rv[i] is not None:
            hist=[x for x in rv[max(0,i-504):i+1] if x is not None]
            if len(hist)>=60:
                rvp=round(100*sum(1 for x in hist if x<=rv[i])/len(hist))
        rows.append({"d":D[i],"c":C[i],"score":score,"sigs":sigs,"trig":{k:round(v,2) for k,v in trig.items()},
                     "rv20":None if rv[i] is None else round(rv[i],1),"rv_pct":rvp,
                     "prov":(bars[i][7] if len(bars[i])>7 else None)})
    # 翻轉事件
    events=[]
    for j in range(1,len(rows)):
        a,b=rows[j-1],rows[j]
        if (a["score"]>=0)!=(b["score"]>=0) or (a["score"]>0)!=(b["score"]>0):
            if a["score"]>0 and b["score"]<=0: events.append({"d":b["d"],"ev":"分數翻負","score":b["score"]})
            elif a["score"]<0 and b["score"]>=0: events.append({"d":b["d"],"ev":"分數翻正","score":b["score"]})
        for k,lab in [("ma50","跌破短期(50D)"),("ma100","跌破中期(100D)"),("ma200","跌破長期(200D)"),
                      ("mom63","3月動能轉負"),("mom126","6月動能轉負"),("mom252","12月動能轉負")]:
            if a["sigs"][k]==1 and b["sigs"][k]==-1: events.append({"d":b["d"],"ev":lab})
            if a["sigs"][k]==-1 and b["sigs"][k]==1: events.append({"d":b["d"],"ev":lab.replace("跌破","收復").replace("轉負","轉正")})
    return rows,events

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--symbols",default="SPY,QQQ,IWM,SMH,SOXX,MU,SNDK,WDC")
    ap.add_argument("--kline-dir",default="fresh")
    ap.add_argument("--market-data",default=None,help="market_data.json 路徑(取 kline_today 當日盤中bar)")
    ap.add_argument("--fill-missing",action="store_true")
    ap.add_argument("--since",default="2026-06-01")
    ap.add_argument("--json",default=None)
    a=ap.parse_args()
    kt={}
    if a.market_data and os.path.exists(a.market_data):
        try: kt=json.load(open(a.market_data)).get("kline_today",{}) or {}
        except Exception: pass
    OUT={}
    for sym in [s.strip().upper() for s in a.symbols.split(",") if s.strip()]:
        try:
            bars,src=load_bars(sym,a.kline_dir,fill=a.fill_missing,today_bar=kt.get(sym))
        except Exception as e:
            print(f"{sym}: 載入失敗 {e}"); continue
        rows,events=compute(sym,bars)
        if not rows:
            print(f"{sym}: 樣本不足(需≥253根)"); continue
        cur=rows[-1]
        tag="CTA觸發" if sym in CTA_SYMS else "趨勢位階"
        OUT[sym]={"tag":tag,"src":src,"rows":[r for r in rows if r["d"]>=a.since],"events":[e for e in events if e["d"]>=a.since],
                  "current":{"d":cur["d"],"close":cur["c"],"score":cur["score"],"rv20":cur["rv20"],"rv_pct":cur["rv_pct"],
                             "triggers":{k:{"px":cur["trig"][k],
                                            "dist_pct":round(100*(cur["trig"][k]/cur["c"]-1),2)} for k in cur["trig"]}}}
        print(f"\n==== {sym}({tag},src={src}) 現值 {cur['d']} close={cur['c']} score={cur['score']:+d} RV20={cur['rv20']}%(第{cur['rv_pct']}百分位)")
        for k in ["ma50","ma100","ma200","mom63","mom126","mom252"]:
            t=cur["trig"][k]; d=100*(t/cur["c"]-1)
            lab={"ma50":"短期觸發(50D)","ma100":"中期觸發(100D)","ma200":"長期觸發(200D)",
                 "mom63":"3月動能位","mom126":"6月動能位","mom252":"12月動能位"}[k]
            side="↑上方" if d>0 else "↓下方"
            print(f"   {lab:12s} {t:>10.2f}  距現價 {d:+.1f}% {side}  訊號={'+1' if cur['sigs'][k]==1 else '−1'}")
        print(f"   -- {a.since} 以來事件 --")
        for e in OUT[sym]["events"]:
            print(f"   {e['d']}  {e['ev']}" + (f"(score={e['score']:+d})" if 'score' in e else ""))
    if a.json:
        json.dump(OUT,open(a.json,"w"),ensure_ascii=False)
        print("\njson ->",a.json)

if __name__=="__main__":
    main()
