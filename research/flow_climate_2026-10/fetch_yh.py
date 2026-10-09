# Download Yahoo daily full history (split/div adjusted via adjclose) → pickled pandas frames
import json, urllib.request, urllib.parse, time, os, sys, concurrent.futures as cf
import pandas as pd, numpy as np
DT="/tmp/claude-0/-home-claude/d0a676e0-fcd7-5eae-bc26-2609f6d7a033/scratchpad/dt"
OUT=os.path.join(DT,"yh"); os.makedirs(OUT,exist_ok=True)
UA={"User-Agent":"Mozilla/5.0"}
MACRO=["^GSPC","^NDX","^SOX","^RUT","^VIX","^VIX3M","^VIX9D","^VVIX","^SKEW","^MOVE","^TNX","^IRX","^FVX","^TYX",
 "CL=F","BZ=F","GC=F","SI=F","HG=F","NG=F","DX-Y.NYB","JPY=X","EURUSD=X","CNY=X","KRW=X","TWD=X","BTC-USD","ETH-USD",
 "HYG","JNK","LQD","TLT","IEF","SHY","TIP","RSP","IWM","QQQ","SPY","SMH","SOXX","XLK","XLF","XLE","XLV","XLP","XLU","XLI","XLY","XLB","XLC","XLRE",
 "GLD","SLV","USO","UUP","EEM","EWT","EWY","EWJ","FXI","^KS11","^TWII","^N225","^HSI","^STOXX50E","MTUM","USMV","IWF","IWD","SPHB","SPLV","ARKK","KRE","XBI","DBC","CPER","URA","COPX"]
uni=json.load(open(os.path.join(DT,"universe.json")))
syms=list(dict.fromkeys(MACRO+uni))
now=int(time.time())
def fetch(s):
    fn=os.path.join(OUT,s.replace("^","_").replace("=","_")+".pkl")
    if os.path.exists(fn): return s,"cached"
    for a in range(3):
        try:
            u=f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(s)}?period1=0&period2={now}&interval=1d&events=div%2Csplit"
            d=json.loads(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=60).read())
            r=d["chart"]["result"][0]
            ts=r.get("timestamp") or []
            if not ts: return s,"empty"
            q=r["indicators"]["quote"][0]
            adj=(r["indicators"].get("adjclose") or [{}])[0].get("adjclose")
            tz=r["meta"].get("exchangeTimezoneName","America/New_York")
            idx=pd.to_datetime(ts,unit="s",utc=True).tz_convert(tz).tz_localize(None).normalize()
            df=pd.DataFrame({"o":q["open"],"h":q["high"],"l":q["low"],"c":q["close"],"v":q["volume"]},index=idx,dtype="float64")
            df["ac"]=np.array(adj,dtype="float64") if adj else df["c"]
            df=df[~df.index.duplicated(keep="last")].dropna(subset=["c"])
            df.to_pickle(fn); return s,len(df)
        except Exception as e:
            err=str(e)[:80]; time.sleep(2+3*a)
    return s,"ERR "+err
t0=time.time(); res=[]
with cf.ThreadPoolExecutor(6) as ex:
    for s,r in ex.map(fetch,syms): res.append((s,r))
bad=[(s,r) for s,r in res if not isinstance(r,int) and r!="cached"]
print("done",len(res),"in %.0fs"%(time.time()-t0),"bad:",bad)
