import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from lib import DT
M=pd.read_pickle(DT+"/market.pkl"); I=pd.read_pickle(DT+"/idx_targets.pkl")
def rk(x,n=756,mp=252): return x.rolling(n,min_periods=mp).rank(pct=True)
comp={ # oriented so HIGH = bullish (contrarian / supportive)
 "cta_ndx": 1-rk(M.cta_ndx), "cta_spx": 1-rk(M.cta_spx),
 "gex": 1-rk(M.gex,504,126), "dix": rk(M.dix5,504,126),
 "vix": rk(M.vix), "vixr": rk(M.vix_ratio),
 "am": 1-rk(M.cot_eq_am_z), "dlr": rk(M.cot_eq_dlr_z),
 "dd": 1-rk(M.spx_dd), "volctl": 1-rk(M.volctl), "tnx": 1-rk(M.tnx_chg20),
}
Cp=pd.DataFrame(comp)
Cp.to_pickle(DT+"/climate_comp.pkl")
IS=(Cp.index>="2007-07-01")&(Cp.index<"2018-01-01"); OOS=Cp.index>="2018-01-01"
pd.set_option("display.width",250)
def dec_table(x,y,mask,nb=5):
    d=pd.concat([x,y],axis=1)[mask].dropna(); d.columns=["x","y"]
    d["b"]=pd.qcut(d.x,nb,labels=False,duplicates="drop")
    return d.groupby("b").y.agg(["mean","count",lambda s:(s>0).mean()]).rename(columns={"<lambda_0>":"hit"})
# component correlation
print(Cp[IS|OOS].corr().round(2).to_string())
for name,cols in (("ALL",list(Cp.columns)),("POS (cta,gex,dix,am,dlr)",["cta_ndx","cta_spx","gex","dix","am","dlr"]),("STRESS (vix,vixr,dd,volctl)",["vix","vixr","dd","volctl"])):
    sc=Cp[cols].mean(axis=1,skipna=True)
    for tgt in ("SPY_f10","SPY_f20","QQQ_f20","SMH_f20"):
        for per,m in (("IS",IS),("OOS",OOS)):
            t=dec_table(sc,I[tgt],m)
            print(f"{name:28s} {tgt} {per}: "+"  ".join(f"Q{int(b)+1}:{r['mean']*100:+.2f}%/{r['hit']*100:.0f}%" for b,r in t.iterrows()))
