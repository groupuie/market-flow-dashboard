import sys; sys.path.insert(0,"."); from t1x_cands import *
qmax=Q.c.rolling(252,min_periods=60).max(); COR=Q.c<=qmax*0.9; VIXH=vix>=20
d=ev(BUY_BASES["抄底"][0],"open"); c=samp(COR,d); v=samp(VIXH,d)
r=d[(d.date>="2024-10-01")]; rc=c[(d.date>="2024-10-01").values]; rv=v[(d.date>="2024-10-01").values]
for lab,m in (("弱(個股自己跌)",~rc&~rv),("強(大盤回檔)",rc)):
    x=r[m].copy(); x["m"]=x.date.dt.strftime("%Y-%m"); x["up"]=x.f20>0
    g=x.groupby("m").agg(n=("up","size"),up=("up","mean"),mean=("f20","mean"))
    print(lab); print((g.assign(up=lambda t:(t.up*100).round(0),mean=lambda t:(t["mean"]*100).round(1))).to_string())
d=ev(TK,"close"); qb=samp(Q.c<q20,d); ai=samp(AIc,d); r=d[d.date>="2024-10-01"]; m=(~qb&ai)[(d.date>="2024-10-01").values]
x=r[m].copy(); x["m"]=x.date.dt.strftime("%Y-%m"); x["dn"]=x.f20<0
print("AI 頂K(大盤在線上)近兩年 by month"); print(x.groupby("m").agg(n=("dn","size"),dn=("dn","mean")).assign(dn=lambda t:(t.dn*100).round(0)).to_string())
