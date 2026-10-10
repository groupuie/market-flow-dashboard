# EDGAR 8-K Item 2.02(財報公布)日期 → 每檔財報日清單
import json, glob, os, numpy as np, pandas as pd
DL="/tmp/claude-0/-home-claude/d0a676e0-fcd7-5eae-bc26-2609f6d7a033/scratchpad/dl/edgar"
rows=[]
for fn in glob.glob(DL+"/*.json"):
    tk=os.path.basename(fn)[:-5]
    if tk=="ticker_cik": continue
    d=json.load(open(fn)); blocks=[d["recent"]]+d.get("files",[])
    for b in blocks:
        for f,it,fd in zip(b.get("form",[]),b.get("items",[]),b.get("filingDate",[])):
            if f in ("8-K",) and "2.02" in str(it): rows.append((tk,fd))
E=pd.DataFrame(rows,columns=["tk","fd"]).drop_duplicates()
E["fd"]=pd.to_datetime(E.fd); E=E.sort_values(["tk","fd"])
# 同一檔 5 天內多筆(更正/補件)只留第一筆
E["gap"]=E.groupby("tk").fd.diff().dt.days
E=E[(E.gap.isna())|(E.gap>5)].drop(columns="gap")
E.to_pickle("/tmp/claude-0/-home-claude/d0a676e0-fcd7-5eae-bc26-2609f6d7a033/scratchpad/dt/earn_dates.pkl")
print("rows",len(E),"tickers",E.tk.nunique(),"range",E.fd.min().date(),E.fd.max().date())
print(E.groupby(E.fd.dt.year).size().to_dict())
