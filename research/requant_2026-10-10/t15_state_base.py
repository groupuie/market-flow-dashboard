# t15:同一個大盤狀態下,「所有股票日」本身的命中率 —— 拆開「大盤狀態的功勞」與「個股訊號的功勞」
import sys; sys.path.insert(0,"."); from t1x_cands import *; from t10lib import _sel, _pm
qmax=Q.c.rolling(252,min_periods=60).max(); COR=Q.c<=qmax*0.9
def state_hit(state,side,per,entry="open",h=20):
    FRx=FR if entry=="open" else FRC
    a,b=PERIODS[per]; pm=_pm(a,b)
    sm=np.asarray(state.reindex(dates).fillna(False).values,dtype=bool)
    v=FRx[h].values[pm&sm]; v=v[~np.isnan(v)]
    return len(v),((v<0) if side=="top" else (v>0)).mean()*100
def show(lab,state,side,sigs,entry="open"):
    print(f"\n[{lab}]")
    for per in ("p1","p2"):
        n,hb=state_hit(state,side,per,entry); s=f"  {per}: 所有股票日 {hb:4.1f}%(股票日 n={n})"
        for nm,(sig,ent) in sigs.items():
            d=ev(sig,ent); mk=samp(state,d); r=hit(d,mk,side,20,per,boot=0)
            n2,hb2=state_hit(state,side,per,ent)
            s+=f" | {nm} {r['hit']:4.1f}%(n{r['n']}) 比同狀態{r['hit']-hb2:+5.1f}"
        print(s,flush=True)
show("大盤回檔≥10% 且 資金≥35%",COR&(cr>=0.35),"bot",{"深跌站回":(BUY_BASES["深跌站回(不看資金)"][0],"open")})
show("大盤回檔≥10% 且 資金≥65%",COR&(cr>=0.65),"bot",{"買":(BUY,"open"),"★":(STAR,"open"),"深跌站回":(BUY_BASES["深跌站回(不看資金)"][0],"open")})
show("大盤沒回檔 且 VIX<20",(~COR)&(vix<20),"bot",{"深跌站回":(BUY_BASES["深跌站回(不看資金)"][0],"open"),"買":(BUY,"open"),"★":(STAR,"open")})
show("資金偏緊 且 (油弱或殖利率急降)",(cr<=0.35)&(OILW|YDROP),"top",{"出的價格部分":(XR,"open")})
show("資金偏緊",(cr<=0.35),"top",{"出的價格部分":(XR,"open")})
show("QQQ在20日線下",(Q.c<q20),"top",{"頂K":(TK,"close"),"減碼":(CF,"close")})
show("全部日子",pd.Series(True,index=dates),"top",{"跌≥4%+前20天頂K":(XR&(ret1<=-0.04)&anyN(TK.shift(1),20),"open")})
