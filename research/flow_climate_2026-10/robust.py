import numpy as np, pandas as pd, warnings, itertools; warnings.filterwarnings("ignore")
from lib import DT, series
from market import cta_pos
M=pd.read_pickle(DT+"/market.pkl"); L=pd.read_pickle(DT+"/long.pkl"); cal=M.index
cot=pd.read_pickle(DT+"/cot.pkl")["JY"]; oi=cot.open_interest_all
dl=(cot.dealer_positions_long_all-cot.dealer_positions_short_all)/oi
spec=((cot.lev_money_positions_long-cot.lev_money_positions_short)+(cot.asset_mgr_positions_long-cot.asset_mgr_positions_short))/oi
def align(s):
    s=s.copy(); s.index=s.index+pd.Timedelta(days=6)
    return s.reindex(cal.union(s.index)).sort_index().ffill(limit=10).reindex(cal)
def rk(x,n,mp=252): return x.rolling(n,min_periods=mp).rank(pct=True)
fvx=series("^FVX",cal); tnx=series("^TNX",cal); dxy=series("DX-Y.NYB",cal)
d=L.index.get_level_values(0); f20=L.f20.values
P=[("2007-07-01","2011-12-31"),("2012-01-01","2016-12-31"),("2017-01-01","2021-12-31"),("2022-01-01","2026-12-31")]
def evals(score):
    r=score.rolling(756,min_periods=252).rank(pct=True).reindex(d).values; out=[]
    for a,b in P:
        m=(d>=a)&(d<=b)&~np.isnan(r)&~np.isnan(f20)
        f=f20[m]; rr=r[m]; base=(f>0).mean()
        out.append(((f[rr>0.9]>0).mean()-base)*100); out.append(((f[rr<=0.1]>0).mean()-base)*100)
    return out
rows=[]
for yen_src,zw,yld,yw,dxm,rw in itertools.product(["dealer","spec"],[104,156,260],["fvx","tnx"],[10,20,40],["cta","chg60"],[504,756]):
    s=dl if yen_src=="dealer" else -spec
    z=(s-s.rolling(zw,min_periods=52).mean())/s.rolling(zw,min_periods=52).std()
    yen=1-rk(align(z),rw)
    y=fvx if yld=="fvx" else tnx
    rate=1-rk(y-y.shift(yw),rw)
    dol=1-rk(cta_pos(dxy)[1] if dxm=="cta" else np.log(dxy/dxy.shift(60)),rw)
    A=(yen+(rate+dol)/2)/2
    rows.append([yen_src,zw,yld,yw,dxm,rw]+evals(A))
R=pd.DataFrame(rows,columns=["yen","zw","yld","yw","dx","rw"]+[f"{p}{k}" for p in ("07","12","17","22") for k in ("top","bot")])
pd.set_option("display.width",220)
print(R.describe().loc[["mean","min","25%","50%","75%","max"]].round(1).to_string())
print("share of 144 variants with top>0 in all 4 periods:",(R[[c for c in R if c.endswith("top")]]>0).all(axis=1).mean().round(2),
      " bot<0 in all 4:",(R[[c for c in R if c.endswith("bot")]]<0).all(axis=1).mean().round(2))
print(R[(R.yen=="dealer")&(R.zw==156)&(R.yld=="fvx")&(R.yw==20)&(R.dx=="cta")].round(1).to_string(index=False))
