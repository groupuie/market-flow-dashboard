# 使用者假設:K棒碰到布林上軌,且上影線佔整根K棒 ≥ 1/4(1/3、1/2…)→ 之後幾天下跌機率較高?
import numpy as np, pandas as pd, pickle, warnings; warnings.filterwarnings("ignore")
from lib import DT, series
S=pickle.load(open(DT+"/stock.pkl","rb")); P=S["P"]
O,H,L,C,V=[P[k].astype("float64") for k in "OHLCV"]
mid=C.rolling(20).mean(); sd=C.rolling(20).std(ddof=0); up=mid+2*sd
rng=(H-L).where(H>L)
uw=(H-np.maximum(O,C))/rng            # 上影線佔比
body=(C-O).abs()/rng
touch=H>=up
volr=V/V.rolling(60,min_periods=40).mean()
cr=pd.read_pickle(DT+"/climA_rank.pkl").reindex(C.index)
clim=pd.DataFrame(np.repeat(cr.values[:,None],C.shape[1],axis=1),index=C.index,columns=C.columns)
# 前瞻:收盤進場(訊號收盤即知)與隔日開盤進場
FC={k:np.log(C.shift(-k)/C) for k in (1,2,3,5,10)}
FO={k:np.log(C.shift(-k)/O.shift(-1)) for k in (1,3,5,10)}
AI=set("NVDA AMD AVGO MU SNDK WDC STX MRVL LITE COHR AAOI TSM ASML AMAT LRCX KLAC SMCI ANET ARM MPWR QCOM INTC TXN ADI ON MCHP NXPI CRDO ALAB CIEN GLW VRT DELL TER ENTG AMKR WOLF POET AEHR MXL GFS SWKS QRVO MTSI".split())
dates=C.index
PER={"07-17":("2007-01-01","2017-12-31"),"18-26":("2018-01-01","2026-12-31")}
dix=pd.Series(np.arange(len(dates)),index=dates)
def ev(sig,cols=None,per="all",F=FC,hs=(1,3,5,10),boot_h=None):
    cols=cols or list(C.columns)
    m=np.ones(len(dates),bool) if per=="all" else (dates>=PER[per][0])&(dates<=PER[per][1])
    out={}
    s=sig.loc[m,cols]
    out["n"]=int(s.values.sum())
    for h in hs:
        f=F[h].loc[m,cols]; base=f.stack().dropna(); e=f.where(s).stack().dropna()
        out[f"dn{h}"]=(e<0).mean()*100; out[f"bdn{h}"]=(base<0).mean()*100
        out[f"mu{h}"]=e.mean()*100; out[f"bmu{h}"]=base.mean()*100
        if boot_h==h and len(e)>30:
            blk=(dix.reindex(e.index.get_level_values(0)).values//20)
            g=pd.DataFrame({"b":blk,"w":(e<0).values}).groupby("b").w.agg(["sum","count"])
            rng_=np.random.default_rng(0); k=len(g); bs=[]
            for _ in range(400):
                ii=rng_.integers(0,k,k); bs.append(g["sum"].values[ii].sum()/g["count"].values[ii].sum()*100-out[f"bdn{h}"])
            out["ci"]=np.percentile(bs,[5,95]).round(1)
    return out
def line(nm,r,hs=(1,3,5,10)):
    return f"{nm:46s} n={r['n']:6d} | "+" | ".join(f"{h}日跌 {r[f'dn{h}']:.1f}%(平常{r[f'bdn{h}']:.1f}) 均{r[f'mu{h}']:+.2f}%" for h in hs)+(f" | CI(5日跌-平常) {r['ci']}" if 'ci' in r else "")
sigs={
 "碰上軌(任何)":touch,
 "碰上軌 & 上影≥1/4":touch&(uw>=0.25),
 "碰上軌 & 上影≥1/3":touch&(uw>=1/3),
 "碰上軌 & 上影≥1/2":touch&(uw>=0.5),
 "碰上軌 & 上影≥2/3(流星/墓碑)":touch&(uw>=2/3),
 "碰上軌 & 上影≥1/3 & 收回軌內":touch&(uw>=1/3)&(C<up),
 "碰上軌 & 上影≥1/3 & 黑K(收<開)":touch&(uw>=1/3)&(C<O),
 "碰上軌 & 上影≥1/3 & 爆量≥1.5倍":touch&(uw>=1/3)&(volr>=1.5),
 "碰上軌 & 上影<0.1(收在最高附近)":touch&(uw<0.1),
}
for per in ("07-17","18-26"):
    print(f"===== 全部個股 {per}(收盤進場)")
    for nm,sg in sigs.items():
        print(line(nm,ev(sg,per=per,boot_h=5)))
print("===== AI/半導體子集 2018-26")
for nm in ("碰上軌(任何)","碰上軌 & 上影≥1/4","碰上軌 & 上影≥1/3","碰上軌 & 上影≥1/2","碰上軌 & 上影<0.1(收在最高附近)"):
    print(line(nm,ev(sigs[nm],cols=[c for c in C.columns if c in AI],per="18-26",boot_h=5)))
print("===== 隔日開盤進場(全部 18-26)")
for nm in ("碰上軌 & 上影≥1/4","碰上軌 & 上影≥1/3","碰上軌 & 上影≥1/2"):
    print(line(nm,ev(sigs[nm],per="18-26",F=FO,hs=(1,3,5,10))))
print("===== 搭配資金氣候(全部 2009-26)")
for nm in ("碰上軌 & 上影≥1/3",):
    for cn,cm in (("氣候≤35%",clim<=0.35),("氣候35-65%",(clim>0.35)&(clim<0.65)),("氣候≥65%",clim>=0.65)):
        r=ev(sigs[nm]&cm,per="all"); print(line(nm+" × "+cn,r))
pickle.dump({"uw":uw,"touch":touch,"up":up},open(DT+"/wick.pkl","wb"))
