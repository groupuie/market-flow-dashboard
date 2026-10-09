import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from evalx import *
from lib import DT
L=load_long(); set_dateidx(L)
M=pd.read_pickle(DT+"/market.pkl"); d=L.index.get_level_values(0)
spx_up=(M.spx_d200.reindex(d).values>0); sox_up=(M.sox_d200.reindex(d).values>0)
up=(L.sc>=67); dn=(L.sc<=-67)
below50_first=(L.p50<0)&(L.groupby(level=1).p50.shift(1)>=0)&(L.groupby(level=1).p50.transform(lambda s:(s.shift(1)>0).rolling(20).sum())>=20)
C={
"uptrend & z5<=-1.5":up&(L.z5<=-1.5),
"uptrend & rsi2<10":up&(L.rsi2<10),
"uptrend & first close<SMA50 (after 20d above)":up&below50_first,
"uptrend & touch SMA20 (-1<=d20<=0)":up&(L.d20<=0)&(L.d20>=-1),
"strong (p50>=10%) & z5<=-1.5":(L.p50>=0.10)&(L.z5<=-1.5),
"above SMA200 & 3 down days":(L.p200>0)&(L.ndown>=3),
"downtrend & z5<=-2 (knife)":dn&(L.z5<=-2),
"uptrend & z5<=-1.5 & SPX>200d":up&(L.z5<=-1.5)&spx_up,
"uptrend & z5<=-1.5 & SPX<200d":up&(L.z5<=-1.5)&~spx_up,
"uptrend & rsi2<10 & SPX>200d":up&(L.rsi2<10)&spx_up,
"first<SMA50 & SPX>200d":up&below50_first&spx_up,
}
for nm,sig in C.items():
    for per in ("IS","OOS"):
        r=stats(L,sig,per,"bot",ep=True)
        print(f"{nm:46s} {per:3s} n={r['n']:5d} hit10={r['hit10']:.1f}/{r['base10']:.1f} hit20={r['hit20']:.1f}/{r['base20']:.1f} mu20={r['mu20']:+.2f}/{r['bmu20']:+.2f} exs20={r['exs20']:+.2f} xSPY={r['x20']:+.2f} mae={r['mae20']:.1f}")
