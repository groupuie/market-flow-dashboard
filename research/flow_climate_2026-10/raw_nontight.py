# 技判「出」同型轉折(ext15 → 跌破20日線)在全球資金「不緊」(>35%)時的表現 → 決定圖上要不要標「減碼」
import numpy as np, pandas as pd, pickle, warnings, json; warnings.filterwarnings("ignore")
exec(open("stats_final.py").read().split("out={}")[0])
cr=S["clim"]; clim_b=pd.DataFrame(np.repeat(cr.values[:,None],C.shape[1],axis=1),index=C.index,columns=C.columns)
raw=S["trimraw"].astype(bool)
for nm,sig in (("raw 全部",raw),("raw 氣候≤35% (=▼)",raw&(clim_b<=0.35)),("raw 氣候>35%",raw&(clim_b>0.35)),("raw 氣候35–65%",raw&(clim_b>0.35)&(clim_b<0.65)),("raw 氣候≥65%",raw&(clim_b>=0.65))):
    for per,(a,b) in (("all",("2009-07-01","2026-12-31")),("p1",("2009-07-01","2017-12-31")),("p2",("2018-01-01","2026-12-31"))):
        r=st(sig,"top",a,b); print(f"{nm:18s} {per}: n={r['n']:5d} 20日後較低 {r['p20']}% (平常 {r['b20']}) | 40日後較低 {r['p40']}% ({r['b40']}) | 40日內跌≥10% {r['dd40']}% ({r['bdd40']}) | 40日平均 {r['m40']}% ({r['bm40']})")
