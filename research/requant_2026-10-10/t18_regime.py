# t18:使用者:「最近是油價漲、通膨疑慮升、美債殖利率升、可能升息,所以美股跌」→ 在「通膨/升息恐慌」(油價漲、殖利率急升)時,
#      「出」準不準?現行強/弱分級(油弱、殖利率急降、跌≥4%、前20根頂K)在這種時候會不會把準的「出」標成灰?
import sys; sys.path.insert(0,"."); from t1x_cands import *; from t10lib import _sel, _pm
M=samp
OILU=MR["原油20日"]>=2/3; YUP=MR["10年債殖利率20日(bp)"]>=2/3
BIGDN=ret1<=-0.04; PRETK=anyN(TK.shift(1),20)
YRS={"p1":8.5,"p2":8.75}
def line(lab,d,mk,side="top"):
    s=f"  {lab:40s}"
    for per in ("p1","p2"):
        r=hit(d,mk,side,20,per,boot=400); r4=hit(d,mk,side,40,per,boot=0)
        if r["n"]<8: s+=f" | {per} n={r['n']:4d} —"; continue
        c=f"[{r['ci'][0]:+.0f},{r['ci'][1]:+.0f}]" if not np.isnan(r['ci'][0]) else ""
        s+=f" | {per} n={r['n']:4d} 20日後較低 {r['hit']:4.1f}%(平常{r['base']:4.1f},差{r['hit']-r['base']:+5.1f}{c}) 40日 {r4['hit']:4.1f}% 均{r['mean']:+5.1f}%"
    s4=[]
    for a,b in SUB4:
        r=hit(d,mk,side,20,(a,b),boot=0); s4.append("  —" if r["n"]<10 else f"{r['hit']-r['base']:+4.0f}")
    print(s+" | 四段 "+" ".join(s4),flush=True)
d=ev(X,"open")
ow,ou,yd,yu,px=[M(x,d) for x in (OILW,OILU,YDROP,YUP,BIGDN|PRETK)]
strong=ow|yd|px; gray=~strong
print("### 「出」(資金偏緊)× 油價/殖利率 情境")
line("全部「出」",d,np.ones(len(d),bool))
line("殖利率 20 日急升(最高 1/3)",d,yu); line("殖利率 20 日持平(中間 1/3)",d,~yu&~yd); line("殖利率 20 日急降(最低 1/3)",d,yd)
line("油價 20 日大漲(最高 1/3)",d,ou); line("油價 20 日持平(中間)",d,~ou&~ow); line("油價 20 日走弱(最低 1/3)",d,ow)
line("通膨恐慌:油價大漲 且 殖利率急升",d,ou&yu)
line("通膨恐慌 + 價格條件(跌≥4%或前有頂K)",d,ou&yu&px); line("通膨恐慌 但沒價格條件",d,ou&yu&~px)
print("### 現行分級在「殖利率急升」時")
line("殖利率急升 & 現行=強",d,yu&strong); line("殖利率急升 & 現行=灰",d,yu&gray)
line("殖利率不急升 & 現行=灰",d,~yu&gray)
line("現行=灰(全部)",d,gray)
print("### 2022(升息+通膨的典型年)")
y22=(d.date>="2022-01-01").values&(d.date<="2022-12-31").values
for lab,mk in (("2022 全部出",y22),("2022 現行=強",y22&strong),("2022 現行=灰",y22&gray)):
    sel=_sel(d,20,("2022-01-01","2022-12-31"))&mk; f=d.f20.values[sel]
    print(f"  {lab:14s} n={len(f):4d} 20日後較低 {np.mean(f<0)*100:4.1f}%(2022 所有股票日 {base('top','open',20,('2022-01-01','2022-12-31')):.1f}%)")
print("### 同狀態所有股票日(大盤本身):資金偏緊 且 殖利率急升 / 通膨恐慌")
for lab,st in (("資金偏緊&殖利率急升",(cr<=0.35)&YUP),("資金偏緊&通膨恐慌",(cr<=0.35)&YUP&OILU),("資金偏緊&殖利率持平",(cr<=0.35)&~YUP&~YDROP)):
    for per in ("p1","p2"):
        a,b=PERIODS[per]; pm=_pm(a,b); sm=np.asarray(st.reindex(dates).fillna(False).values,dtype=bool)
        v=FR[20].values[pm&sm]; v=v[~np.isnan(v)]
        print(f"  {lab:16s} {per}: 佔交易日 {sm[pm].mean()*100:4.1f}% 所有股票 20日後較低 {np.mean(v<0)*100:4.1f}%")
