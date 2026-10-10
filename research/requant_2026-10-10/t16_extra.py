# t16:補充 —— 同狀態基準的平均報酬/中途回撤;最強賣出層的 AI 與非 AI;大盤狀態出現的時間比例
import sys; sys.path.insert(0,"."); from t1x_cands import *; from t10lib import _sel, _pm
qmax=Q.c.rolling(252,min_periods=60).max(); COR=Q.c<=qmax*0.9
def state_stats(state,per,h=20):
    a,b=PERIODS[per]; pm=_pm(a,b); sm=np.asarray(state.reindex(dates).fillna(False).values,dtype=bool)
    v=FR[h].values[pm&sm]; mae=MAE[40].values[pm&sm]; ok=~np.isnan(v); okm=~np.isnan(mae)   # 2026-10-11 修正D:沒資料/40日未完成不算「沒跌」
    return dict(share=sm[pm].mean()*100,hit=(v[ok]>0).mean()*100,mean=v[ok].mean()*100,dd10=(mae[okm]<=np.log(0.9)).mean()*100)
for lab,st in (("回檔≥10% 且 資金≥35%",COR&(cr>=0.35)),("回檔≥10% 且 資金<35%",COR&(cr<0.35)),("沒回檔 且 VIX<20",(~COR)&(vix<20))):
    for per in ("p1","p2"):
        s=state_stats(st,per); print(f"{lab:16s} {per}: 佔交易日 {s['share']:4.1f}% | 所有股票 20日上漲 {s['hit']:4.1f}% 平均 {s['mean']:+5.2f}% 40日內曾跌≥10% {s['dd10']:3.0f}%",flush=True)
d=ev(BUY_BASES["深跌站回(不看資金)"][0],"open"); mk=samp(COR&(cr>=0.35),d)
for per in ("p1","p2"):
    r=hit(d,mk,"bot",20,per,boot=0); print(f"深跌站回 + 回檔 + 資金≥35% {per}: 20日上漲 {r['hit']:.1f}% 平均 {r['mean']:+.2f}% 中途再跌≥10% {r['dd10']:.0f}%")
d=ev(XR,"open"); t=samp(cr<=0.35,d); mac=samp(OILW|YDROP,d); px=samp((ret1<=-0.04)|anyN(TK.shift(1),20),d); ai=samp(AIc,d)
for lab,mk in (("出+總經+價格 AI",t&mac&px&ai),("出+總經+價格 非AI",t&mac&px&~ai),("出+總經 AI",t&mac&ai),("出+總經 非AI",t&mac&~ai)):
    for per in ("p1","p2"):
        r=hit(d,mk,"top",20,per,boot=0); print(f"{lab:16s} {per}: n={r['n']:4d} 20日後較低 {r['hit']:.1f}% 平均 {r['mean']:+.2f}%")
# 資金偏緊+總經 狀態佔比
for per in ("p1","p2"):
    a,b=PERIODS[per]; pm=_pm(a,b)
    for lab,st in (("資金偏緊",cr<=0.35),("資金偏緊且總經",(cr<=0.35)&(OILW|YDROP)),("QQQ<20日線",Q.c<q20)):
        sm=np.asarray(st.reindex(dates).fillna(False).values,dtype=bool); print(f"{per} {lab} 佔交易日 {sm[pm].mean()*100:.0f}%")
