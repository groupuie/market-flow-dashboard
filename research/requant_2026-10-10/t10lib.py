# t10/t11/t12 共用:事件表 + 「有加分條件 vs 沒有」比較(20 日區塊自助法 CI)+ 候選條件
import sys; sys.path.insert(0,"."); sys.path.insert(1,"/tmp/claude-0/-home-claude/d0a676e0-fcd7-5eae-bc26-2609f6d7a033/scratchpad/res")
from qlib import *
from qlib import _pm, _stk
from lib import series, load

# ---------- 事件表 ----------
def ev(sig, entry="open", start="2009-07-01"):
    A=sig.reindex(index=dates,columns=cols).fillna(False).values.astype(bool).copy()
    A[np.asarray(dates<pd.Timestamp(start))]=False
    i,j=np.nonzero(A)
    FRx,XMx,MAEx=(FR,XM,MAE) if entry=="open" else (FRC,XMC,MAEC)
    d=pd.DataFrame({"i":i,"j":j}); d["date"]=dates[i]; d["tk"]=np.array(cols)[j]; d.attrs["entry"]=entry
    for h in (10,20,40,60):
        d[f"f{h}"]=FRx[h].values[i,j]; d[f"x{h}"]=XMx[h].values[i,j]
    d["mae40"]=MAEx[40].values[i,j]
    return d

def samp(mod, d):
    """mod:日期層級 Series(大盤)或 個股 DataFrame;回傳事件上的 bool 陣列(缺值=False)"""
    if isinstance(mod,pd.Series):
        return np.asarray(mod.reindex(dates).fillna(False).values,dtype=bool)[d.i.values]
    return np.asarray(mod.reindex(index=dates,columns=cols).fillna(False).values,dtype=bool)[d.i.values,d.j.values]

_BASE={}
def base(side,entry,h,per):
    key=(side,entry,h,str(per))
    if key not in _BASE:
        FRx=FR if entry=="open" else FRC
        a,b=PERIODS[per] if isinstance(per,str) else per
        v=FRx[h].values[_pm(a,b)]; v=v[~np.isnan(v)]
        _BASE[key]=((v<0) if side=="top" else (v>0)).mean()*100
    return _BASE[key]

def _sel(d,h,per):
    a,b=PERIODS[per] if isinstance(per,str) else per
    return ((d.date>=a)&(d.date<=b)&d[f"f{h}"].notna()).values

def cmp(d, mk, side, h=20, per="p1", boot=500, seed=0):
    """有條件(mk=True)vs 沒有 的命中率差;CI 用 20 日區塊自助法(同一次抽樣同時算兩組)"""
    sel=_sel(d,h,per); f=d[f"f{h}"].values[sel]; g=(f<0) if side=="top" else (f>0); m=mk[sel]
    nw,nwo=int(m.sum()),int((~m).sum())
    r=dict(nw=nw,nwo=nwo,hw=np.nan,hwo=np.nan,diff=np.nan,ci=(np.nan,np.nan),mw=np.nan,mwo=np.nan,xw=np.nan,xwo=np.nan)
    if nw<5 or nwo<5: return r
    x=d[f"x{h}"].values[sel]
    r.update(hw=g[m].mean()*100,hwo=g[~m].mean()*100,mw=f[m].mean()*100,mwo=f[~m].mean()*100,xw=np.nanmean(x[m])*100,xwo=np.nanmean(x[~m])*100)
    r["diff"]=r["hw"]-r["hwo"]
    if boot:
        blk=d.i.values[sel]//20
        A=pd.DataFrame({"b":blk,"gw":(g&m),"nw":m,"gwo":(g&~m),"nwo":~m}).astype({"gw":float,"nw":float,"gwo":float,"nwo":float}).groupby("b").sum().values
        k=len(A); rng=np.random.default_rng(seed); out=[]
        for _ in range(boot):
            s=A[rng.integers(0,k,k)].sum(0)
            if s[1]>0 and s[3]>0: out.append(s[0]/s[1]*100-s[2]/s[3]*100)
        r["ci"]=tuple(np.percentile(out,[5,95]))
    return r

def hit(d, mk, side, h=20, per="p1", boot=500, seed=0):
    """事件子集的命中率、與基準(所有股票日)差、CI"""
    sel=_sel(d,h,per)&mk; f=d[f"f{h}"].values[sel]; g=(f<0) if side=="top" else (f>0)
    b=base(side,d.attrs["entry"],h,per)
    r=dict(n=int(sel.sum()),hit=g.mean()*100 if len(g) else np.nan,base=b,mean=np.nanmean(f)*100 if len(f) else np.nan,
           xm=np.nanmean(d[f"x{h}"].values[sel])*100 if len(f) else np.nan, ci=(np.nan,np.nan))
    mae=d["mae40"].values[sel]; r["dd10"]=np.nanmean(mae<=np.log(0.9))*100 if len(f) else np.nan
    if boot and len(f)>20:
        blk=d.i.values[sel]//20
        A=pd.DataFrame({"b":blk,"g":g.astype(float),"n":1.0}).groupby("b").sum().values; k=len(A); rng=np.random.default_rng(seed); out=[]
        for _ in range(boot):
            s=A[rng.integers(0,k,k)].sum(0); out.append(s[0]/s[1]*100-b)
        r["ci"]=tuple(np.percentile(out,[5,95]))
    return r

def sub(d,mk,side,h=20,minn=15):
    res=[]
    for a,b in SUB4:
        r=cmp(d,mk,side,h,(a,b),boot=0)
        res.append(None if (r["nw"]<minn or r["nwo"]<minn) else float(round(r["diff"],1)))
    return res

def mkt_effect(s, side, h=20, per="p1", entry="open"):
    """大盤層級條件對「所有股票日」本身的命中差(看是不是只是大盤擇時)"""
    FRx=FR if entry=="open" else FRC
    a,b=PERIODS[per]; pm=_pm(a,b)
    v=FRx[h].values[pm]; ok=~np.isnan(v); good=np.where(ok,(v<0) if side=="top" else (v>0),False).astype(float)
    gs=good.sum(1); ns=ok.sum(1)
    sm=np.asarray(s.reindex(dates).fillna(False).values,dtype=bool)[pm]
    if ns[sm].sum()==0 or ns[~sm].sum()==0: return np.nan
    return gs[sm].sum()/ns[sm].sum()*100-gs[~sm].sum()/ns[~sm].sum()*100

def f1(x,w=5,p=1,sign=True):
    if x is None or (isinstance(x,float) and np.isnan(x)): return " "*(w-1)+"—"
    return f"{x:+{w}.{p}f}" if sign else f"{x:{w}.{p}f}"

def row(name, d, mod, side, show_mkt=True):
    mk=samp(mod,d); share=mk.mean()*100
    a=cmp(d,mk,side,20,"p1"); b=cmp(d,mk,side,20,"p2"); a4=cmp(d,mk,side,40,"p1",boot=0); b4=cmp(d,mk,side,40,"p2",boot=0)
    s4=sub(d,mk,side,20)
    pos=sum(1 for x in s4 if x is not None and x>0); tot=sum(1 for x in s4 if x is not None)
    line=(f"{name:26s} 佔{share:4.0f}% | 前半 有{a['hw']:5.1f}%(n{a['nw']:4d}) 無{a['hwo']:5.1f}% 差{f1(a['diff'])} [{f1(a['ci'][0])},{f1(a['ci'][1])}]"
          f" | 後半 有{b['hw']:5.1f}%(n{b['nw']:4d}) 無{b['hwo']:5.1f}% 差{f1(b['diff'])} [{f1(b['ci'][0])},{f1(b['ci'][1])}]"
          f" | 40日差 {f1(a4['diff'])}/{f1(b4['diff'])} | 扣大盤差 {f1(a['xw']-a['xwo'],5,2)}/{f1(b['xw']-b['xwo'],5,2)}% | 四段 {pos}/{tot} {s4}")
    if show_mkt and isinstance(mod,pd.Series):
        line+=f" | 大盤本身 {f1(mkt_effect(mod,side,20,'p1',d.attrs['entry']))}/{f1(mkt_effect(mod,side,20,'p2',d.attrs['entry']))}"
    print(line,flush=True)
    return dict(name=name,share=share,p1=a,p2=b,p1_40=a4,p2_40=b4,s4=s4)

# ---------- 共用特徵 ----------
anyN=lambda X,n: X.fillna(False).astype(int).rolling(n,min_periods=1).max().astype(bool)
V60=V.rolling(60,min_periods=40).mean().shift(1); vr=V/V60
ret1=C/C.shift(1)-1
ibs=(C-L)/(H-L).replace(0,np.nan)
S200=C.rolling(200).mean(); rel50=C/S50-1
TK=topk(); CF=confirm(TK)
AIc=pd.DataFrame(np.repeat(np.array([c in AI for c in cols])[None,:],len(dates),axis=0),index=dates,columns=cols)
def _mk(sym):
    x=load(sym); return x.reindex(dates)
Q=_mk("QQQ"); SP=_mk("SPY"); SM=_mk("SMH")
q20=Q.c.rolling(20).mean(); q50=Q.c.rolling(50).mean(); sp20=SP.c.rolling(20).mean(); sp50=SP.c.rolling(50).mean()
qret=Q.c.pct_change(); dist25=((qret<=-0.002)&(Q.v>Q.v.shift(1))).astype(int).rolling(25).sum()
def breadth(ma):
    ok=C.notna()&ma.notna(); return ((C>ma)&ok).sum(1)/ok.sum(1).replace(0,np.nan)*100
br20=breadth(S20); br50=breadth(S50)
vix=series("^VIX",dates); v3m=series("^VIX3M",dates)
MR=pd.read_pickle(DT+"/macro_ranks.pkl").reindex(dates)
EF=pd.read_pickle(DT+"/earn_frames.pkl"); IF=pd.read_pickle(DT+"/insider_frames.pkl")
rsQ10=(C/C.shift(10)).sub(Q.c/Q.c.shift(10),axis=0)          # 個股 10 日報酬 − QQQ 10 日報酬
crs=cr.copy()                                                 # 全球資金氣候(日期層級)
