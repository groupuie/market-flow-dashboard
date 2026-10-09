import numpy as np, pandas as pd, pickle, warnings; warnings.filterwarnings("ignore")
exec(open("sellnext3.py").read().split("R5=touch&hot&(offhi>=0.05)")[0])
R5=touch&hot&(offhi>=0.05); sig=R5&conf
maxc10=C.rolling(10).max()      # 訊號日之前(含)10日最高收盤
dclose=np.log(maxc10/sell)      # 賣價比近10日最高收盤低多少
# 技判出(對照):賣價離近10日最高收盤
S2=pickle.load(open(DT+"/prod_sigs.pkl","rb")); trm=S2["trimraw"].reindex(index=dates,columns=C.columns).fillna(False)
d_out=np.log(C.rolling(20).max()/C)
pm=(dates>="2017-01-01")
print("頂K→隔天賣:賣價比近10日最高收盤低 中位 %.1f%%"%(np.median(dclose.loc[pm].where(sig.loc[pm]).stack().dropna())*100))
print("技判出:賣價比近20日最高收盤低 中位 %.1f%%"%(np.median(d_out.loc[pm].where(trm.loc[pm]).stack().dropna())*100))
AIc=[c for c in C.columns if c in AI]
for nm,mk in (("AI × 氣候≤35%",sig&(clim<=0.35)),("AI × 氣候>35%",sig&(clim>0.35))):
    sc=succ_next.loc[pm,AIc].where(mk.loc[pm,AIc]).stack().dropna(); e40=fr[40].loc[pm,AIc].where(mk.loc[pm,AIc]).stack().dropna()
    print(f"{nm}: n={len(sc)} 賣在頂 {sc.mean()*100:.0f}% 40日後較低 {(e40<0).mean()*100:.0f}% 均 {e40.mean()*100:+.1f}%")
# 近兩年實例
ev=sig.loc["2025-01-01":].stack(); ev=ev[ev]
rows=[]
for (d,s) in ev.index:
    i=dates.get_loc(d)
    rows.append((s,d.date(),round(H.iloc[i][s],2),round(C.iloc[i+1][s],2) if i+1<len(dates) else None,
                 round((fr[20].iloc[i][s])*100,1) if not np.isnan(fr[20].iloc[i][s]) else None, round(clim.iloc[i][s]*100) if not np.isnan(clim.iloc[i][s]) else None,
                 int(succ_next.iloc[i][s]) if not np.isnan(succ_next.iloc[i][s]) else None))
E=pd.DataFrame(rows,columns=["sym","頂K日","當天最高","隔天賣價","賣後20日%","氣候","賣在頂"])
focus=set("MU SNDK WDC STX MRVL NVDA AVGO LITE COHR AAOI AMD TSM SMCI ARM ANET CRDO ALAB VRT DELL INTC ORCL PLTR TSLA META".split())
print(E[E.sym.isin(focus)].sort_values("頂K日").to_string(index=False))
print("2025–2026 全部:",len(E),"次;賣在頂",round(E["賣在頂"].mean()*100),"%(有結果者)")
