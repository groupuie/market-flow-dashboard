import numpy as np, pandas as pd, pickle, warnings, json; warnings.filterwarnings("ignore")
from lib import DT
exec(open("rules.py").read().split('print("=== 減碼確認')[0])
S=pickle.load(open(DT+"/prod_sigs.pkl","rb"))
dates=C.index
AIc=[c for c in C.columns if c in AI]
def st(sig,side,a="2009-01-01",b="2026-12-31",cols=None):
    per=(dates>=a)&(dates<=b); cols=cols or list(C.columns)
    r={"n":int(sig.loc[per,cols].values.sum())}
    for h in (10,20,40):
        f=F[h].loc[per,cols]; base=f.stack().dropna(); e=f.where(sig.loc[per,cols]).stack().dropna()
        r[f"p{h}"]=round(((e<0) if side=="top" else (e>0)).mean()*100,1); r[f"b{h}"]=round(((base<0) if side=="top" else (base>0)).mean()*100,1)
        r[f"m{h}"]=round(e.mean()*100,1); r[f"bm{h}"]=round(base.mean()*100,1)
    dd=DD[40].loc[per,cols]; r["dd40"]=round((dd.where(sig.loc[per,cols]).stack().dropna()<=np.log(0.9)).mean()*100,1); r["bdd40"]=round((dd.stack().dropna()<=np.log(0.9)).mean()*100,1)
    dd=DD[20].loc[per,cols]; r["dd20"]=round((dd.where(sig.loc[per,cols]).stack().dropna()<=np.log(0.9)).mean()*100,1); r["bdd20"]=round((dd.stack().dropna()<=np.log(0.9)).mean()*100,1)
    return r
out={}
T_all=S["T_strong"]|S["T_reg"]
for nm,sig,side in (("trim_strong",S["T_strong"],"top"),("trim_reg",S["T_reg"],"top"),("trim_all",T_all,"top"),("buy_strong",S["B_strong"],"bot"),("buy_reg",S["B_reg"],"bot"),
                    ("raw_trim",S["trimraw"],"top"),("raw_buy",S["buyraw"],"bot")):
    out[nm]={"all":st(sig,side),"p1":st(sig,side,"2009-01-01","2017-12-31"),"p2":st(sig,side,"2018-01-01","2026-12-31"),"ai":st(sig,side,cols=AIc)}
    print(nm,json.dumps(out[nm],ensure_ascii=False))
# climate buckets (stock-level, all days) 
cr=S["clim"]; clim_b=pd.DataFrame(np.repeat(cr.values[:,None],C.shape[1],axis=1),index=C.index,columns=C.columns)
per=(dates>="2009-07-01")
f20=F[20].loc[per]; dd20=DD[20].loc[per]; cb=clim_b.loc[per]
bk={}
for nm,(lo,hi) in {"<=20":(0,0.2),"20-35":(0.2,0.35),"35-65":(0.35,0.65),"65-80":(0.65,0.8),">=80":(0.8,1.01)}.items():
    m=(cb>lo if lo>0 else cb>=0)&(cb<=hi if hi<=1 else cb<hi)
    if nm==">=80": m=(cb>=0.8)
    if nm=="<=20": m=(cb<=0.2)
    e=f20.where(m).stack().dropna(); d2=dd20.where(m).stack().dropna()
    bk[nm]={"days":int(m.iloc[:,0].sum()),"up20":round((e>0).mean()*100,1),"mu20":round(e.mean()*100,2),"dd20":round((d2<=np.log(0.9)).mean()*100,1)}
base=f20.stack().dropna(); bk["all"]={"up20":round((base>0).mean()*100,1),"mu20":round(base.mean()*100,2),"dd20":round((dd20.stack().dropna()<=np.log(0.9)).mean()*100,1)}
print("climate buckets:",json.dumps(bk,ensure_ascii=False))
out["climate_buckets"]=bk
json.dump(out,open(DT+"/final_stats.json","w"),ensure_ascii=False,indent=1)
