# 量化重新回測共用函式庫(2026-10-10)
# 資料:259 檔個股 Yahoo 調整後日K(2004–2026),全球資金氣候序列(climA_rank)。進場=訊號隔天開盤(避免偷看)。
import numpy as np, pandas as pd, pickle, warnings; warnings.filterwarnings("ignore")
DT="/tmp/claude-0/-home-claude/d0a676e0-fcd7-5eae-bc26-2609f6d7a033/scratchpad/dt"
S=pickle.load(open(DT+"/stock.pkl","rb")); P=S["P"]; FE=S["F"]
O,H,L,C,V=[P[k].astype("float64") for k in "OHLCV"]
dates=C.index; cols=list(C.columns); dix=pd.Series(np.arange(len(dates)),index=dates)
cr=pd.read_pickle(DT+"/climA_rank.pkl").reindex(dates)
CL=pd.DataFrame(np.repeat(cr.values[:,None],C.shape[1],axis=1),index=dates,columns=cols)
AI=set("NVDA AMD AVGO MU SNDK WDC STX MRVL LITE COHR AAOI TSM ASML AMAT LRCX KLAC SMCI ANET ARM MPWR QCOM INTC TXN ADI ON MCHP NXPI CRDO ALAB CIEN GLW VRT DELL TER ENTG AMKR WOLF POET AEHR MXL GFS SWKS QRVO MTSI".split())
O1=O.shift(-1)
HZ=(5,10,20,40,60)
FR={h:np.log(C.shift(-h)/O1) for h in HZ}                                     # 隔天開盤進場 → 第 h 天收盤
MAE={h:np.log(L[::-1].rolling(h,min_periods=h).min()[::-1].shift(-1)/O1) for h in (20,40)}   # 期間最低
MFE={h:np.log(H[::-1].rolling(h,min_periods=h).max()[::-1].shift(-1)/O1) for h in (20,40)}
XM={h:FR[h].sub(FR[h].mean(axis=1),axis=0) for h in HZ}                        # 扣掉同一天全體平均(市場中性)
FRC={h:np.log(C.shift(-h)/C) for h in HZ}                                     # 當天收盤進場(頂K 當晚賣用)
XMC={h:FRC[h].sub(FRC[h].mean(axis=1),axis=0) for h in HZ}
MAEC={h:np.log(L[::-1].rolling(h,min_periods=h).min()[::-1].shift(-1)/C) for h in (20,40)}
vol20=np.log(C).diff().rolling(20,min_periods=15).std()
VQ=vol20.rank(axis=1,pct=True)                                                 # 當天波動在全體的百分位(配對基準用)
PERIODS={"all":("2009-07-01","2026-12-31"),"p1":("2009-07-01","2017-12-31"),"p2":("2018-01-01","2026-12-31")}
SUB4=[("2009-07-01","2013-12-31"),("2014-01-01","2018-12-31"),("2019-01-01","2022-12-31"),("2023-01-01","2026-12-31")]
def cool(raw,k=20):
    arr=raw.fillna(False).values.astype(bool); out=np.zeros_like(arr)
    for j in range(arr.shape[1]):
        last=-10**9
        for i in np.flatnonzero(arr[:,j]):
            if i-last>k: out[i,j]=True; last=i
    return pd.DataFrame(out,index=raw.index,columns=raw.columns)
def _pm(a,b): return (dates>=a)&(dates<=b)
def _stk(X,pm,cs): return X.loc[pm,cs].stack()
def evaluate(sig,side,per="all",h=20,cs=None,boot=0,vmatch=True,entry="open"):
    """sig: bool frame。side: 'top'(賣出訊號,看之後跌)或 'bot'(買進訊號,看之後漲)。回傳 dict。"""
    cs=cs or cols; a,b=PERIODS[per] if isinstance(per,str) else per; pm=_pm(a,b)
    m=sig.loc[pm,cs].fillna(False).astype(bool)
    idx=m.stack(); idx=idx[idx].index
    FRx,XMx,MAEx=(FR,XM,MAE) if entry=="open" else (FRC,XMC,MAEC)
    f=_stk(FRx[h],pm,cs); x=_stk(XMx[h],pm,cs)
    e=f.reindex(idx).dropna(); ex=x.reindex(idx).dropna()
    good=(e<0) if side=="top" else (e>0)
    base=f.dropna(); bgood=(base<0) if side=="top" else (base>0)
    r={"n":int(len(e)),"rate":len(idx)/max(1,(m.shape[0]/252)*m.shape[1]) ,"hit":good.mean()*100,"base":bgood.mean()*100,
       "mean":e.mean()*100,"bmean":base.mean()*100,"xmean":ex.mean()*100}
    hh=40 if h>=40 else 20
    dd=_stk(MAEx[hh],pm,cs)
    if side=="top":
        ev=(dd.reindex(idx)<=np.log(0.9)).dropna(); r["risk"]=ev.mean()*100
        if vmatch:   # 同波動百分位的平常日子:跌 ≥10% 的機率
            vq=_stk(VQ,pm,cs).dropna(); bins=(vq*10).clip(0,9.999).astype(int); ddn=dd.dropna(); bd=(ddn<=np.log(0.9)); tab=bd.groupby(bins.reindex(bd.index)).mean()
            eb=bins.reindex(idx).dropna().astype(int); r["risk_base"]=tab.reindex(eb.values).mean()*100
    else:
        ev=(dd.reindex(idx)<=np.log(0.9)).dropna(); r["risk"]=ev.mean()*100   # 買進後中途再跌 ≥10%
    if boot and len(e)>20:
        blk=dix.reindex(e.index.get_level_values(0)).values//20
        g=pd.DataFrame({"b":blk,"g":good.values.astype(float),"v":e.values}).groupby("b").agg(gs=("g","sum"),vs=("v","sum"),n=("g","count"))
        rng=np.random.default_rng(0); k=len(g); hb=[]; mb=[]
        for _ in range(boot):
            ii=rng.integers(0,k,k); nn=g["n"].values[ii].sum()
            hb.append(g["gs"].values[ii].sum()/nn*100-r["base"]); mb.append(g["vs"].values[ii].sum()/nn*100-r["bmean"])
        r["hit_ci"]=tuple(np.round(np.percentile(hb,[5,95]),1)); r["mean_ci"]=tuple(np.round(np.percentile(mb,[5,95]),2))
    return r
def fmt(r,side):
    s=f"n={r['n']:5d} ({r['rate']:.2f}/檔年) 命中 {r['hit']:.1f}% vs {r['base']:.1f}%"
    if "hit_ci" in r: s+=f" [{r['hit_ci'][0]:+.1f},{r['hit_ci'][1]:+.1f}]"
    s+=f" | 平均 {r['mean']:+.2f}% vs {r['bmean']:+.2f}%"
    if "mean_ci" in r: s+=f" [{r['mean_ci'][0]:+.2f},{r['mean_ci'][1]:+.2f}]"
    s+=f" | 扣大盤 {r['xmean']:+.2f}%"
    if side=="top" and "risk_base" in r: s+=f" | 跌≥10% {r['risk']:.0f}% vs 同波動 {r['risk_base']:.0f}%"
    elif "risk" in r: s+=f" | 中途再跌≥10% {r['risk']:.0f}%"
    return s
def report(name,sig,side,h=20,boot=400,cs=None,entry="open"):
    out=[]
    for per in ("p1","p2","all"):
        r=evaluate(sig,side,per,h,cs=cs,boot=boot if per!="all" else 0,entry=entry); out.append((per,r))
        print(f"{name:34s} {per:3s} {h:2d}日 "+fmt(r,side),flush=True)
    return out
def sub4(sig,side,h=20,cs=None,entry="open"):   # 四段期間:命中率-基準 的正負號
    res=[]
    for a,b in SUB4:
        r=evaluate(sig,side,(a,b),h,cs=cs,vmatch=False,entry=entry); res.append(round(r["hit"]-r["base"],1) if r["n"]>=20 else None)
    return res
# ---------- 訊號 ----------
S20=C.rolling(20).mean(); S50=C.rolling(50).mean()
def turn(kind,thr,win=20,ma_ext=50,ma_x=20,cd=20):
    sx=C.rolling(ma_ext).mean(); sc=C.rolling(ma_x).mean(); rel=C/sx-1
    if kind=="top": cond=rel.rolling(win).max()>=thr; x=(C<sc)&(C.shift(1)>=sc.shift(1))
    else: cond=rel.rolling(win).min()<=-thr; x=(C>sc)&(C.shift(1)<=sc.shift(1))
    return cool(cond&x,cd)
def chu(thr=0.15,cut=0.35,**k): return turn("top",thr,**k)&(CL<=cut)
def chaodi(thr=0.10,deep=0.15,cut=0.80,**k):
    raw=turn("bot",thr,**k); rel=C/C.rolling(k.get("ma_ext",50)).mean()-1
    return raw&(rel.rolling(k.get("win",20)).min()<=-deep)&(CL>=cut)
def topk(r20=0.30,atrm=3.0,ext=0.25,off=0.05,bbk=2.0):
    mid=C.rolling(20).mean(); sd=C.rolling(20).std(ddof=0); up=mid+bbk*sd
    tr=np.maximum(H-L,np.maximum((H-C.shift()).abs(),(L-C.shift()).abs())); atr=tr.rolling(14,min_periods=10).mean()
    hot=(C/C.shift(20)-1>=r20)|((C-mid)/atr>=atrm)|(C/C.rolling(50).mean()-1>=ext)
    return hot&(H>=up)&(1-C/H>=off)
def confirm(tk): return tk.shift(1).fillna(False).astype(bool)&(C<L.shift(1))
