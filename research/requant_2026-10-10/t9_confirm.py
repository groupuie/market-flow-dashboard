# 最有希望的幾個「修正」再做一次嚴格確認:區塊自助法信賴區間 + 四段期間
import sys; sys.path.insert(0,"."); from qlib import *
EF=pickle.load(open(DT+"/earn_frames.pkl","rb")); MR=pd.read_pickle(DT+"/macro_ranks.pkl")
bc=lambda s: pd.DataFrame(np.repeat(s.reindex(dates).values[:,None],len(cols),axis=1),index=dates,columns=cols)
TK=topk(); X=chu(); Y=chaodi()
F=FE; scf=F["sc"].astype("float64"); rv=F["rvpos"].astype("float64"); tdb=F["tdb"].astype("float64"); volr=F["volr"].astype("float64")
BOT=((tdb>=9).astype(int)+(rv>=80).astype(int)+((volr>=1.75)&(C<C.shift(5))).astype(int)+(scf<66).astype(int)).where(scf.notna())
star1=cool(BOT>=3,20)
m20=C.rolling(20).mean(); sd=C.rolling(20).std(ddof=0); lo=m20-2*sd; up=m20+2*sd; pb=(C-lo)/(up-lo); bw=(up-lo)/m20; sqz=bw<=bw.rolling(60,min_periods=1).min()
s50=C.rolling(50).mean(); trend=(C>s50)&(s50>s50.shift(10))
runc=lambda cond: cond.astype(int).apply(lambda c: c.groupby((c==0).cumsum()).cumsum())
tdbc=runc(C<C.shift(4)); anyN=lambda Xx,n: Xx.astype(int).rolling(n,min_periods=1).max().astype(bool)
first=lambda Xx: Xx&~Xx.shift(1).fillna(False).astype(bool)
buy=first(trend&anyN(tdbc>=6,10)&anyN((pb<=0.35)|sqz,10))|first((~trend)&((pb<=0.2)|sqz)&anyN(tdbc>=9,5))|first(anyN(tdbc>=9,10)&anyN(C<lo,10)&(C>lo))
oil_lo=bc(MR["原油20日"]<1/3); y60_lo=bc(MR["10年債殖利率60日(bp)"]<1/3); y20_lo=bc(MR["10年債殖利率20日(bp)"]<1/3)
cases=[
 ("A 頂K(全部)",TK,"top","close",20),("A 頂K 非財報日",TK&~EF["earn_win"],"top","close",20),("A 頂K 財報當天/隔天",TK&EF["earn_win"],"top","close",20),
 ("A 頂K 財報前5天內",TK&EF["nxt"],"top","close",20),
 ("B 買(價格部分)全部",buy,"bot","open",20),("B 買 × 氣候≥65%",buy&(CL>=0.65),"bot","open",20),("B 買 × 氣候≥35%",buy&(CL>0.35),"bot","open",20),("B 買 × 氣候≤35%",buy&(CL<=0.35),"bot","open",20),
 ("C ★ 全部",star1,"bot","open",40),("C ★ × 氣候≥65%",star1&(CL>=0.65),"bot","open",40),("C ★ × 氣候≥65% × 殖利率60日下降",star1&(CL>=0.65)&y60_lo,"bot","open",40),
 ("D 出(現行)",X,"top","open",20),("D 出 × 油價20日走弱",X&oil_lo,"top","open",20),("D 出 × 其他油價",X&~oil_lo,"top","open",20),("D 出 × 殖利率20日急降",X&y20_lo,"top","open",20),
 ("E 抄底(現行)",Y,"bot","open",40),("E 抄底 × 5天內要公布財報",Y&EF["nxt"],"bot","open",40),("E 抄底 × 氣候≥90%",chaodi(cut=0.90),"bot","open",40),
]
for nm,s,side,ent,h in cases:
    report(nm,s,side,h,boot=600,entry=ent); print("   四段期間命中差:",sub4(s,side,h,entry=ent),flush=True)
