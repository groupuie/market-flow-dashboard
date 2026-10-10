# 內部人買賣(SEC Form 4,公開市場 P/S)回測:單獨的效果 + 搭配量化訊號
import sys; sys.path.insert(0,"."); from qlib import *
D=pd.read_pickle(DT+"/insider_ps.pkl")
D=D[D.tk.isin(cols)&(D.is_off|D.is_dir)&D.val.notna()&(D.val>0)]           # 只看高階主管/董事(不含純大股東基金)
D["i"]=np.searchsorted(dates.values,D.fd.values.astype("datetime64[ns]"),side="left")   # 申報日(公開日)→ 當天或下一個交易日;隔天開盤進場
D=D[D.i<len(dates)]
def daily(sub,how):
    g=sub.groupby(["i","tk"])
    s=g.owner.nunique() if how=="n" else g.val.sum()
    out=pd.DataFrame(0.0,index=range(len(dates)),columns=cols)
    for (i,tk),v in s.items(): out.at[i,tk]=v
    out.index=dates; return out
Pb=D[D.code=="P"]; Ps=D[D.code=="S"]
nb=daily(Pb,"n"); vb=daily(Pb,"v"); ns=daily(Ps,"n"); vs=daily(Ps,"v")
ceo_b=daily(Pb[Pb.ceo_cfo],"v")
adv=(C*V).rolling(60,min_periods=40).mean()
# 21 個交易日內不同人數(近似:日人數加總;同一人連續申報會重複算 → 另用 owner 去重版本)
def distinct_window(sub,w=21):
    out=pd.DataFrame(0.0,index=range(len(dates)),columns=cols)
    for tk,g in sub.groupby("tk"):
        arr=g[["i","owner"]].values; idx=np.array(sorted(set(g.i)))
        for i in idx:
            lo=i-w+1; m=(arr[:,0]>=lo)&(arr[:,0]<=i); out.at[i,tk]=len(set(arr[m,1]))
    out.index=dates; return out
cb=distinct_window(Pb); cs=distinct_window(Ps)
print("data through",D.fd.max().date(),"| buys",len(Pb),"sells",len(Ps),flush=True)
sig={}
sig["買:任一主管/董事買進≥$25K"]=cool((vb>=25e3),20)
sig["買:21天內≥2位內部人買(群聚)"]=cool((cb>=2),20)
sig["買:單日買進≥$1M"]=cool((vb>=1e6),20)
sig["買:CEO/CFO/總裁買≥$100K"]=cool((ceo_b>=1e5),20)
sig["賣:21天內≥3位內部人賣(群聚)"]=cool((cs>=3),20)
sig["賣:單日賣出≥平常日成交額25%"]=cool((vs>=0.25*adv),20)
sig["賣:單日賣出≥$10M"]=cool((vs>=1e7),20)
s63=vs.rolling(63,min_periods=1).sum()/adv
heavy=s63.rank(axis=1,pct=True)>=0.9
sig["賣:近3個月賣出額前10%(相對成交額)"]=cool(heavy&(vs>0),20)
# 2023-04 起有「10b5-1 預定計畫」勾選 → 非計畫(自主)賣出
Pn=Ps[(~Ps.plan)&(Ps.fd>="2023-04-01")]; vsn=daily(Pn,"v")
sig["賣:非預定計畫賣出≥$1M(2023-04起)"]=cool((vsn>=1e6),20)
for k,v in sig.items():
    side="bot" if k.startswith("買") else "top"
    for h in (20,60):
        report(k,v,side,h,boot=300 if h==20 else 0)
    print("   四段期間 20日命中差:",sub4(v,side,20),flush=True)
# 與量化訊號搭配
buy63=(nb.rolling(63,min_periods=1).sum()>0)
print("=== 搭配:出 × 近3個月內部人賣超多 / 抄底 × 近3個月有內部人買",flush=True)
X=chu(); Y=chaodi(); TK=topk()
for nm,s,side in (("出 & 內部人賣超前10%",X&heavy,"top"),("出 & 其餘",X&~heavy,"top"),
                  ("頂K & 內部人賣超前10%",TK&heavy,"top"),("頂K & 其餘",TK&~heavy,"top"),
                  ("抄底 & 近3月有內部人買",Y&buy63,"bot"),("抄底 & 其餘",Y&~buy63,"bot"),
                  ("跌深站回(不看氣候)& 內部人買",turn("bot",0.10)&buy63,"bot"),("跌深站回(不看氣候)& 其餘",turn("bot",0.10)&~buy63,"bot")):
    report(nm,s,side,20,boot=0); report(nm,s,side,40,boot=0)
pickle.dump({"nb":nb,"vb":vb,"ns":ns,"vs":vs,"cb":cb,"cs":cs,"heavy":heavy,"buy63":buy63,"vsn":vsn},open(DT+"/insider_frames.pkl","wb"))
