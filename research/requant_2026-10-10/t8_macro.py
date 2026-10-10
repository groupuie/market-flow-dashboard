# 大環境:能源(原油)、美債(殖利率)、貴金屬(金/銀)、銅金比、美元、信用 —— 對量化每個訊號是加分、扣分還是沒差
import sys; sys.path.insert(0,"."); sys.path.insert(1,"/tmp/claude-0/-home-claude/d0a676e0-fcd7-5eae-bc26-2609f6d7a033/scratchpad/res")
from qlib import *
from lib import series
cal=dates
oil=np.log(series("CL=F",cal)); gold=np.log(series("GC=F",cal)); silv=np.log(series("SI=F",cal)); cu=np.log(series("HG=F",cal))
y10=series("^TNX",cal); y3m=series("^IRX",cal); dxy=np.log(series("DX-Y.NYB",cal)); cred=np.log(series("HYG",cal)/series("IEF",cal))
M=pd.DataFrame({
 "原油20日":oil.diff(20),"原油60日":oil.diff(60),
 "10年債殖利率20日(bp)":y10.diff(20)*100,"10年債殖利率60日(bp)":y10.diff(60)*100,
 "殖利率曲線10Y-3M":(y10-y3m),"10年債殖利率水準":y10,
 "黃金20日":gold.diff(20),"黃金60日":gold.diff(60),"白銀20日":silv.diff(20),"白銀60日":silv.diff(60),
 "金銀比60日":(gold-silv).diff(60),"銅金比60日":(cu-gold).diff(60),"美元20日":dxy.diff(20),"信用(高收益/公債)20日":cred.diff(20)})
R=M.rolling(756,min_periods=252).rank(pct=True)          # 近 3 年百分位(不偷看未來)
def B(col,lo,hi): b=(R[col]>=lo)&(R[col]<hi); return pd.DataFrame(np.repeat(b.values[:,None],len(cols),axis=1),index=dates,columns=cols)
SIG={"出":(chu(),"top","open"),"抄底":(chaodi(),"bot","open"),"頂K":(topk(),"top","close"),"減碼":(confirm(topk()),"top","close")}
F=FE; scf=F["sc"].astype("float64"); rv=F["rvpos"].astype("float64"); tdb=F["tdb"].astype("float64"); volr=F["volr"].astype("float64")
BOT=((tdb>=9).astype(int)+(rv>=80).astype(int)+((volr>=1.75)&(C<C.shift(5))).astype(int)+(scf<66).astype(int)).where(scf.notna())
SIG["★(氣候≥65%)"]=(cool(BOT>=3,20)&(CL>=0.65),"bot","open")
SIG["所有股票日(大盤效應)"]=(C.notna()&(C.index.to_series().dt.dayofweek==0).values[:,None],"bot","open")   # 每週一抽樣,看整體
print("格式:各訊號在「該總經量 低/中/高 三分之一」時的 20日命中差(前半 2009-17 / 後半 2018-26);n 為事件數",flush=True)
for col in M.columns:
    print(f"\n### {col}",flush=True)
    for nm,(s,side,ent) in SIG.items():
        line=f"  {nm:16s}"
        for lo,hi,tag in ((0,1/3,"低"),(1/3,2/3,"中"),(2/3,1.01,"高")):
            a=evaluate(s&B(col,lo,hi),side,"p1",20,vmatch=False,entry=ent); b=evaluate(s&B(col,lo,hi),side,"p2",20,vmatch=False,entry=ent)
            fa=f"{a['hit']-a['base']:+5.1f}" if a['n']>=30 else "  —  "; fb=f"{b['hit']-b['base']:+5.1f}" if b['n']>=30 else "  —  "
            line+=f" | {tag} {fa}/{fb} (n{a['n']}/{b['n']})"
        print(line,flush=True)
M.to_pickle(DT+"/macro_feats.pkl"); R.to_pickle(DT+"/macro_ranks.pkl")
