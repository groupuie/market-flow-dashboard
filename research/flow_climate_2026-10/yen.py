import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from lib import DT
M=pd.read_pickle(DT+"/market.pkl"); I=pd.read_pickle(DT+"/idx_targets.pkl"); L=pd.read_pickle(DT+"/long.pkl")
ew=L.f20.groupby(level=0).mean().reindex(M.index)
cot=pd.read_pickle(DT+"/cot.pkl")["JY"]
oi=cot.open_interest_all
lev=(cot.lev_money_positions_long-cot.lev_money_positions_short)/oi
am=(cot.asset_mgr_positions_long-cot.asset_mgr_positions_short)/oi
dl=(cot.dealer_positions_long_all-cot.dealer_positions_short_all)/oi
nr=(cot.nonrept_positions_long_all-cot.nonrept_positions_short_all)/oi
print("weekly corr lev/am/dl/nr:\n",pd.concat([lev,am,dl,nr],axis=1,keys=["lev","am","dl","nr"]).corr().round(2))
# yearly snapshot of yen spec net (lev+am) and dealers
spec=lev+am
y=pd.DataFrame({"spec":spec,"dl":dl}).resample("YE").mean()
print(y.round(3).T.to_string())
# correlation of yen positioning with stress features
for c in ["cot_jy_dlr","cot_jy_am","cot_jy_lev","cot_jy_dlr_z"]:
    print(c, "corr with vix %.2f cta_ndx %.2f spx_dd %.2f jpy_chg20 %.2f dxy_chg20 %.2f"%tuple(M[c].corr(M[x]) for x in ["vix","cta_ndx","spx_dd","jpy_chg20","dxy_chg20"]))
# block-bootstrap IC (6-month blocks) of cot_jy_dlr vs EW f20 and SPY f20
def bic(x,yv,B=2000,blk=126,seed=0):
    d=pd.concat([x,yv],axis=1).dropna(); d=d.iloc[::5]
    n=len(d); nb=n//(blk//5); rng=np.random.default_rng(seed); out=[]
    xs=d.iloc[:,0].values; ys=d.iloc[:,1].values; bl=blk//5
    for _ in range(B):
        st=rng.integers(0,n-bl,nb); idx=np.concatenate([np.arange(s,s+bl) for s in st])
        out.append(pd.Series(xs[idx]).rank().corr(pd.Series(ys[idx]).rank()))
    full=pd.Series(xs).rank().corr(pd.Series(ys).rank())
    return round(full,3), np.percentile(out,[5,95]).round(3)
for c in ["cot_jy_dlr","cot_jy_dlr_z","cot_jy_am","cot_jy_lev"]:
    print(c,"EW f20 IC & 90%CI",bic(M[c],ew)," SPY f20",bic(M[c],I.SPY_f20)," SMH f20",bic(M[c],I.SMH_f20))
# quintiles by sub-period for dealers' net (contrarian): Q1 = dealers most short yen (specs long) ...
P=[("2007-07-01","2011-12-31"),("2012-01-01","2016-12-31"),("2017-01-01","2021-12-31"),("2022-01-01","2026-12-31")]
x=M.cot_jy_dlr_z
for a,b in P:
    dd=pd.concat([x,ew,I.SPY_f20,I.SMH_f20],axis=1,keys=["x","ew","spy","smh"])[a:b].dropna()
    dd["q"]=pd.qcut(dd.x,5,labels=False)
    t=dd.groupby("q")[["ew","spy","smh"]].mean()*100
    print(a[:4],"-",b[:4]," EW:",t.ew.round(2).tolist()," SPY:",t.spy.round(2).tolist()," SMH:",t.smh.round(2).tolist())
