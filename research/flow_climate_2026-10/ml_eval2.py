import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from lib import DT
df=pd.read_pickle(DT+"/ml_df.pkl")
AI=set("NVDA AMD AVGO MU SNDK WDC STX MRVL LITE COHR AAOI TSM ASML AMAT LRCX KLAC SMCI ANET ARM MPWR QCOM INTC TXN ADI ON MCHP NXPI CRDO ALAB CIEN GLW VRT DELL TER ENTG AMKR WOLF POET AEHR MXL GFS SWKS QRVO MTSI ORCL CRWV NBIS APLD".split())
df["ai"]=df.sym.isin(AI)
for per,(a,b) in (("2011-17",(2011,2017)),("2018-26",(2018,2026))):
    s=df[(df.yr>=a)&(df.yr<=b)].copy()
    s["dec"]=s.groupby("yr").pup.transform(lambda x: pd.qcut(x,20,labels=False,duplicates="drop"))
    for nm,m in (("top5pct",s.dec==19),("top10pct",s.dec>=18),("bot10pct",s.dec<=1),("bot5pct",s.dec==0)):
        e=s[m]
        nd=e.date.nunique(); conc=e.groupby("date").size().sort_values(ascending=False)
        top_share=conc.head(int(max(1,nd*0.1))).sum()/len(e)
        print(f"{per} {nm:9s} n={len(e):6d} dates={nd:4d} top10%dates share={top_share*100:.0f}% | hit={(e.f20>0).mean()*100:.1f} (base {(s.f20>0).mean()*100:.1f}) mu={e.f20.mean()*100:+.2f} (base {s.f20.mean()*100:+.2f}) | AI: hit={(e[e.ai].f20>0).mean()*100:.1f} (base {(s[s.ai].f20>0).mean()*100:.1f}) mu={e[e.ai].f20.mean()*100:+.2f} | mae={e.mae20.mean()*100:.1f}")
# cross-sectional only: within-date decile of pup
s=df[df.yr>=2011].copy()
s["csd"]=s.groupby("date").pup.transform(lambda x: pd.qcut(x.rank(method="first"),10,labels=False))
s["exd"]=s.f20-s.groupby("date").f20.transform("mean")
t=s.groupby("csd").exd.agg(["mean","count"]); print("cross-sectional deciles excess f20 (%):", (t["mean"]*100).round(2).tolist())
# date-level timing: mean pup across stocks → quintiles of EW f20
g=s.groupby("date").agg(p=("pup","mean"),f=("f20","mean"),yr=("yr","first"))
g["q"]=g.groupby("yr").p.transform(lambda x: pd.qcut(x,5,labels=False,duplicates="drop"))
print("timing quintiles EW f20 (%):", (g.groupby("q").f.mean()*100).round(2).tolist(), " hit:", (g.groupby("q").f.apply(lambda x:(x>0).mean())*100).round(1).tolist())
