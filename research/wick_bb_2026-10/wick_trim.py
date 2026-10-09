# 5) 上影線當「先行警示」:▼減碼/技判出 之前 10 日內有沒有出現過「碰上軌+長上影」,結果有差嗎?
import numpy as np, pandas as pd, pickle, warnings; warnings.filterwarnings("ignore")
from lib import DT
exec(open("rules.py").read().split('print("=== 減碼確認')[0])
S2=pickle.load(open(DT+"/prod_sigs.pkl","rb")); W=pickle.load(open(DT+"/wick.pkl","rb"))
P=pickle.load(open(DT+"/stock.pkl","rb"))["P"]; Hh=P["H"].astype("float64")
wk=(W["touch"]&(W["uw"]>=0.25)).reindex(index=C.index,columns=C.columns).fillna(False)
wk10=wk.astype(int).rolling(10,min_periods=1).max().astype(bool)     # 近10日內出現過(含當天)
cr=S2["clim"]; clim=pd.DataFrame(np.repeat(cr.values[:,None],C.shape[1],axis=1),index=C.index,columns=C.columns)
dates=C.index
def st(sig,side="top"):
    out=[]
    for a,b in (("2009-01-01","2017-12-31"),("2018-01-01","2026-12-31")):
        per=(dates>=a)&(dates<=b); r=[]
        for h in (20,40):
            f=F[h].loc[per]; base=f.stack().dropna(); e=f.where(sig.loc[per]).stack().dropna()
            r.append(f"{h}日後較低 {(e<0).mean()*100:.0f}%(平常{(base<0).mean()*100:.0f}) 均{e.mean()*100:+.1f}%")
        dd=DD[40].loc[per]; ed=dd.where(sig.loc[per]).stack().dropna()
        out.append(f"{a[2:4]}-{b[2:4]} n={len(ed):4d} "+" ".join(r)+f" 40日內跌≥10% {(ed<=np.log(0.9)).mean()*100:.0f}%")
    return " | ".join(out)
tr=S2["trimraw"]; T=tr&(clim<=0.35)
print("技判出(不看氣候)                ",st(tr))
print("  ├ 之前10日有長上影碰上軌         ",st(tr&wk10))
print("  └ 之前10日沒有                  ",st(tr&~wk10))
print("▼減碼(出+氣候≤35%)              ",st(T))
print("  ├ 之前10日有長上影碰上軌         ",st(T&wk10))
print("  └ 之前10日沒有                  ",st(T&~wk10))
print("有長上影的比例:出 %.0f%%  ▼ %.0f%%"%(wk10.where(tr).stack().dropna().mean()*100, wk10.where(T).stack().dropna().mean()*100))
