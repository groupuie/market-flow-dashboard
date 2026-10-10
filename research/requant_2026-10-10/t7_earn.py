# 財報(含財測)回測:EDGAR 8-K 2.02 公布日 → 公布前一天收盤 到 公布後一天收盤 的兩天反應(含盤後/盤前公布)
import sys; sys.path.insert(0,"."); from qlib import *
E=pd.read_pickle(DT+"/earn_dates.pkl"); E=E[E.tk.isin(cols)]
E["i"]=np.searchsorted(dates.values,E.fd.values.astype("datetime64[ns]"),side="left")
E=E[(E.i>=21)&(E.i<len(dates)-2)]
vol=np.log(C).diff().rolling(20,min_periods=15).std()
cpos={c:k for k,c in enumerate(cols)}; Cv=C.values; Vv=vol.values
E["j"]=E.tk.map(cpos)
E["r2"]=np.log(Cv[E.i+1,E.j]/Cv[E.i-1,E.j]); E["z"]=E.r2/(Vv[E.i-1,E.j]*np.sqrt(2))
E=E.dropna(subset=["r2","z"])
print("財報事件",len(E),"檔數",E.tk.nunique(),"兩天反應 |中位數|",round(E.r2.abs().median()*100,1),"%",flush=True)
def at(rows,k=1):   # 事件訊號放在「公布後那天(i+1)」→ 隔天開盤進場
    S=pd.DataFrame(False,index=dates,columns=cols)
    for i,j in zip(rows.i.values+k,rows.j.values): S.iat[i,j]=True
    return S
print("=== 財報反應後續漂移(買進方向=之後上漲)",flush=True)
for nm,q in (("大好 z≥2",E.z>=2),("偏好 1≤z<2",(E.z>=1)&(E.z<2)),("平 −1<z<1",(E.z>-1)&(E.z<1)),("偏差 −2<z≤−1",(E.z>-2)&(E.z<=-1)),("大壞 z≤−2",E.z<=-2)):
    s=at(E[q])
    for h in (20,60): report("財報 "+nm,s,"bot",h,boot=300 if h==20 else 0)
    print("   四段期間 20日命中差:",sub4(s,"bot",20),flush=True)
# 財報窗口標記
earn_win=pd.DataFrame(False,index=dates,columns=cols)
for i,j in zip(E.i.values,E.j.values):
    earn_win.iat[i,j]=True; earn_win.iat[i+1,j]=True
neg=at(E[E.z<=-1]); pos=at(E[E.z>=1])
neg20=neg.astype(int).rolling(20,min_periods=1).max().astype(bool); pos20=pos.astype(int).rolling(20,min_periods=1).max().astype(bool)
# 下一次財報在 5 個交易日內
nxt=pd.DataFrame(False,index=dates,columns=cols)
for i,j in zip(E.i.values,E.j.values):
    nxt.iloc[max(0,i-5):i,j]=True
X=chu(); Y=chaodi(); TK=topk(); CF=confirm(TK)
print("=== 量化訊號 × 財報情境",flush=True)
for nm,s,side in (("出 & 近20天財報反應差",X&neg20,"top"),("出 & 近20天財報反應好",X&pos20,"top"),("出 & 其他",X&~neg20&~pos20,"top"),
                  ("頂K 發生在財報當天/隔天",TK&earn_win,"top"),("頂K 非財報日",TK&~earn_win,"top"),
                  ("頂K & 5天內要公布財報",TK&nxt,"top"),
                  ("抄底 & 近20天財報反應好",Y&pos20,"bot"),("抄底 & 近20天財報反應差",Y&neg20,"bot"),("抄底 & 其他",Y&~pos20&~neg20,"bot"),
                  ("抄底 & 5天內要公布財報",Y&nxt,"bot"),("出 & 5天內要公布財報",X&nxt,"top")):
    ent="close" if nm.startswith("頂K") else "open"
    report(nm,s,side,20,boot=0,entry=ent); report(nm,s,side,40,boot=0,entry=ent)
pickle.dump({"E":E,"earn_win":earn_win,"neg20":neg20,"pos20":pos20,"nxt":nxt},open(DT+"/earn_frames.pkl","wb"))
