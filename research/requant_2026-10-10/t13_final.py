# t13:收斂成幾個「高準確」定義,做最後檢查(兩段、四段、頻率、40 日、跌≥10% 風險),並列出最近 10 個交易日的實際訊號
import sys; sys.path.insert(0,"."); from t1x_cands import *; from t10lib import _sel
YRS={"p1":8.5,"p2":8.75}
def line(lab,d,mk,side):
    s=f"  {lab:40s}"
    for per in ("p1","p2"):
        r=hit(d,mk,side,20,per,boot=400); r4=hit(d,mk,side,40,per,boot=0)
        if r["n"]<8: s+=f" | {per} n={r['n']:4d} —"; continue
        c=f"[{r['ci'][0]:+.0f},{r['ci'][1]:+.0f}]" if not np.isnan(r['ci'][0]) else ""
        rk="40日內跌≥10%" if side=="top" else "中途再跌≥10%"
        s+=(f" | {per} n={r['n']:4d}({r['n']/YRS[per]:3.0f}/年) 20日 {r['hit']:4.1f}%(基準{r['base']:4.1f} 差{r['hit']-r['base']:+5.1f}{c})"
            f" 40日 {r4['hit']:4.1f}%(基準{r4['base']:4.1f}) 均{r['mean']:+5.1f}% {rk} {r['dd10']:3.0f}%")
    s4=[]
    for a,b in SUB4:
        r=hit(d,mk,side,20,(a,b),boot=0); s4.append("  —" if r["n"]<10 else f"{r['hit']-r['base']:+4.0f}")
    print(s+" | 四段 "+" ".join(s4),flush=True)
M=samp
qdd=Q.c/Q.c.rolling(252,min_periods=60).max()-1
COR=qdd<=-0.10; VIXH=vix>=20; TIGHT=cr<=0.35; BIGDN=ret1<=-0.04; PRETK=anyN(TK.shift(1),20); QB20=Q.c<q20; SPB20=SP.c<sp20
NXT=EF["nxt"]; DEEP25=rel50.rolling(20).min()<=-0.25

print("################ 賣出 ################")
d=ev(XR,"open"); t,o,y,b,p,ai=[M(x,d) for x in (TIGHT,OILW,YDROP,BIGDN,PRETK,AIc)]
mac=o|y; px=b|p
line("出(現行)",d,t,"top")
line("出 + 總經(油弱或殖利率急降)",d,t&mac,"top")
line("出 + 價格(跌≥4%或前20天頂K)",d,t&px,"top")
line("出 + 總經 + 價格",d,t&mac&px,"top")
line("出 + 總經或價格(=出(強))",d,t&(mac|px),"top")
line("出 + 總經或價格,非AI",d,t&(mac|px)&~ai,"top")
line("出 + 都沒有(=出(弱))",d,t&~(mac|px),"top")
line("不看資金:跌≥4% + 前20天頂K",d,b&p,"top")
line("不看資金:跌≥4% + 前20天頂K + 總經",d,b&p&mac,"top")
d=ev(TK,"close"); qb,sb,y,ai=[M(x,d) for x in (QB20,SPB20,YDROP,AIc)]
line("頂K(現行)",d,np.ones(len(d),bool),"top")
line("頂K + QQQ在20日線下",d,qb,"top"); line("頂K + SPY在20日線下",d,sb,"top")
line("頂K + (QQQ線下或殖利率急降)",d,qb|y,"top"); line("頂K + (QQQ線下或殖利率急降) 非AI",d,(qb|y)&~ai,"top")
line("頂K 非AI 且 QQQ在線上、殖利率沒急降",d,~(qb|y)&~ai,"top")
d=ev(CF,"close"); qb,y,ai=[M(x,d) for x in (QB20,YDROP,AIc)]
line("減碼(現行)",d,np.ones(len(d),bool),"top")
line("減碼 + (QQQ線下或殖利率急降)",d,qb|y,"top"); line("減碼 + (QQQ線下或殖利率急降) 非AI",d,(qb|y)&~ai,"top")
line("減碼 + 都沒有",d,~(qb|y),"top")

print("\n################ 買進 ################")
DIPRAW=BUY_BASES["深跌站回(不看資金)"][0]
d=ev(DIPRAW,"open"); c,v,nx,dp=[M(x,d) for x in (COR,VIXH,NXT,DEEP25)]
for lo in (-0.01,0.35,0.50,0.65,0.80):
    cl=M(cr>=lo,d); line(f"深跌站回 + 大盤回檔≥10% + 資金≥{max(lo,0):.0%}",d,c&cl,"bot")
line("深跌站回 + 大盤回檔≥10% + VIX≥20",d,c&v,"bot")
line("深跌站回 + 大盤回檔≥10% 不太深(<25%)",d,c&~dp,"bot")
line("深跌站回 + 大盤回檔≥10% 或 5天內財報",d,c|nx,"bot")
line("深跌站回 + 大盤沒回檔、VIX<20(個股自己跌)",d,~c&~v,"bot")
d=ev(BUY_BASES["抄底"][0],"open"); c,v=[M(x,d) for x in (COR,VIXH)]
line("抄底(現行) ",d,np.ones(len(d),bool),"bot"); line("抄底 + 大盤回檔≥10%",d,c,"bot"); line("抄底 + 大盤沒回檔、VIX<20",d,~c&~v,"bot")
d=ev(STAR,"open"); l6,sb,c,v=[M(x,d) for x in (cr>=0.65,SPB20,COR,VIXH)]
line("★ + 資金≥65%",d,l6,"bot"); line("★ + 資金≥65% + SPY在20日線下",d,l6&sb,"bot")
line("★ + 資金≥65% + 大盤回檔≥10%",d,l6&c,"bot"); line("★ + 大盤回檔≥10%(不看資金)",d,c,"bot")
line("★ + 資金≥65% + SPY線下 + VIX≥20",d,l6&sb&v,"bot")
d=ev(BUY,"open"); l6,sb,c=[M(x,d) for x in (cr>=0.65,SPB20,COR)]
line("買 + 資金≥65% + SPY在20日線下",d,l6&sb,"bot"); line("買 + 資金≥65% + 大盤回檔≥10%",d,l6&c,"bot")

print("\n################ 最近 10 個交易日的訊號(資料到 %s)################"%dates[-1].date())
last=dates[-10:]
st=lambda X: X.reindex(index=dates,columns=cols).fillna(False).astype(bool)
cur={"大盤QQQ離一年高點":f"{qdd.iloc[-1]*100:+.1f}%","QQQ在20日線":"上" if not QB20.iloc[-1] else "下","VIX":round(vix.iloc[-1],1),
     "資金氣候":round(cr.iloc[-1],2),"油價20日百分位":round(MR['原油20日'].iloc[-1],2),"10年債殖利率20日百分位":round(MR['10年債殖利率20日(bp)'].iloc[-1],2)}
print("  大盤狀態:",cur)
for nm,S in (("出",st(chu())),("出的價格部分",st(XR)),("頂K",st(TK)),("減碼",st(CF)),("抄底",st(BUY_BASES['抄底'][0])),("深跌站回",st(DIPRAW)),("★",st(STAR))):
    rows=[]
    for dt in last:
        for tk in np.array(cols)[S.loc[dt].values]:
            tags=[]
            if nm.startswith("出"):
                if bool(OILW.reindex(dates).fillna(False).loc[dt]) or bool(YDROP.reindex(dates).fillna(False).loc[dt]): tags.append("總經")
                if bool(BIGDN.loc[dt,tk]): tags.append("跌≥4%")
                if bool(PRETK.loc[dt,tk]): tags.append("前有頂K")
            if nm in ("頂K","減碼"):
                if bool(QB20.loc[dt]): tags.append("QQQ線下")
                if bool(YDROP.reindex(dates).fillna(False).loc[dt]): tags.append("殖利率急降")
            if tk in AI: tags.append("AI")
            rows.append(f"{dt.strftime('%m-%d')} {tk}({'/'.join(tags) if tags else '-'})")
    print(f"  {nm}: {len(rows)} 筆 " + ("; ".join(rows[-40:]) if rows else ""),flush=True)
