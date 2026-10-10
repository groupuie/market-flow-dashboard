# t12:把「兩段都成立」的加分條件組成強度分級,檢查命中率是否隨分數單調上升;
#      再做機械式「只用前半挑條件 → 後半驗證」(及反向),看這種挑法本身會不會過度擬合;
#      最後把市場層級條件(大盤回檔、VIX)按「回檔事件」分組,避免少數幾次大跌撐起整體數字。
import sys; sys.path.insert(0,"."); from t1x_cands import *; from t10lib import _sel
import pickle
YRS={"p1":8.5,"p2":8.75}
def yr_n(d,mk,per): return int((_sel(d,20,per)&mk).sum())
def line(lab,d,mk,side,ci=True):
    s=f"  {lab:34s}"
    for per in ("p1","p2"):
        r=hit(d,mk,side,20,per,boot=400 if ci else 0); r4=hit(d,mk,side,40,per,boot=0)
        if r["n"]<8: s+=f" | {per} n={r['n']:4d}  —"; continue
        c=f"[{r['ci'][0]:+.0f},{r['ci'][1]:+.0f}]" if ci and not np.isnan(r['ci'][0]) else ""
        s+=(f" | {per} n={r['n']:4d}({r['n']/YRS[per]:3.0f}/年) {r['hit']:4.1f}% 差{r['hit']-r['base']:+5.1f}{c}"
            f" 均{r['mean']:+5.1f}% 扣盤{r['xm']:+5.1f}% 40日{r4['hit']:4.1f}%")
    s4=[]
    for a,b in SUB4:
        r=hit(d,mk,side,20,(a,b),boot=0); s4.append("  —" if r["n"]<10 else f"{r['hit']-r['base']:+4.0f}")
    print(s+" | 四段 "+" ".join(s4),flush=True)
def M(mod,d): return samp(mod,d)

qdd=Q.c/Q.c.rolling(252,min_periods=60).max()-1
COR=qdd<=-0.10; VIXH=vix>=20; TIGHT=cr<=0.35; L65=cr>=0.65; L80=cr>=0.80; L90=cr>=0.90
BIGDN=ret1<=-0.04; PRETK=anyN(TK.shift(1),20); OVERS=br20<40; NXT=EF["nxt"]; DEEP25=rel50.rolling(20).min()<=-0.25
QB20=Q.c<q20; WASH=anyN(br50<=20,20); SPYA20=SP.c>sp20

print("################ A. 賣出 ################")
d=ev(XR,"open"); print(f"\n[出的價格部分:漲多後跌破20日線]  基準(所有股票日 20 日後較低)前半 {base('top','open',20,'p1'):.1f}% / 後半 {base('top','open',20,'p2'):.1f}%")
t,o,y,b,p,ov=[M(x,d) for x in (TIGHT,OILW,YDROP,BIGDN,PRETK,OVERS)]
line("全部(不看資金)",d,np.ones(len(d),bool),"top")
line("現行「出」= 資金偏緊",d,t,"top")
line("出 + (油弱或殖利率急降)",d,t&(o|y),"top")
line("出 + 當天跌≥4%",d,t&b,"top")
line("出 + 前20天有頂K",d,t&p,"top")
line("出 + 以上任一",d,t&(o|y|b|p),"top")
line("出 + 以上都沒有",d,t&~(o|y|b|p),"top")
line("出 + 但大盤已超賣(廣度<40%)",d,t&ov,"top")
sc=t.astype(int)+(o|y).astype(int)+b.astype(int)+p.astype(int)-ov.astype(int)
print("  -- 分數 = 資金偏緊 + (油弱或殖利率急降) + 當天跌≥4% + 前20天有頂K − 大盤已超賣")
for k,lab in ((-1,"≤0"),(1,"1"),(2,"2"),(3,"≥3")):
    mk=(sc<=0) if k==-1 else ((sc>=3) if k==3 else (sc==k)); line(f"分數 {lab}",d,mk,"top")
line("不看資金、只看 當天跌≥4% + 前20天有頂K",d,b&p,"top")

d=ev(TK,"close"); print(f"\n[頂K(當晚收盤賣)]  基準 前半 {base('top','close',20,'p1'):.1f}% / 後半 {base('top','close',20,'p2'):.1f}%")
qb,y,nx,ai,t=[M(x,d) for x in (QB20,YDROP,NXT,AIc,TIGHT)]
line("全部頂K",d,np.ones(len(d),bool),"top")
line("頂K + QQQ已在20日線下",d,qb,"top"); line("頂K + QQQ在20日線上",d,~qb,"top")
line("頂K + 殖利率急降",d,y,"top"); line("頂K + 5天內財報",d,nx,"top")
line("頂K 非AI股",d,~ai,"top"); line("頂K AI股",d,ai,"top")
line("頂K + (QQQ線下或殖利率急降) 非AI",d,(qb|y)&~ai,"top")
d=ev(CF,"close"); print(f"\n[減碼(頂K 隔天收破低點,當晚收盤賣)]")
qb,y,ai=[M(x,d) for x in (QB20,YDROP,AIc)]
line("全部減碼",d,np.ones(len(d),bool),"top")
line("減碼 + QQQ已在20日線下",d,qb,"top"); line("減碼 + QQQ在20日線上",d,~qb,"top")
line("減碼 非AI股",d,~ai,"top"); line("減碼 + QQQ線下 非AI",d,qb&~ai,"top")

print("\n################ B. 買進 ################")
d=ev(BUY_BASES["深跌站回(不看資金)"][0],"open"); print(f"\n[深跌後站回20日線(抄底的價格部分)]  基準(所有股票日 20 日後較高)前半 {base('bot','open',20,'p1'):.1f}% / 後半 {base('bot','open',20,'p2'):.1f}%")
c,v,l8,l9,nx,dp=[M(x,d) for x in (COR,VIXH,L80,L90,NXT,DEEP25)]
line("全部(不看資金)",d,np.ones(len(d),bool),"top" if False else "bot")
line("現行「抄底」= 資金≥80%(含深跌≥15%)",d,M(BUY_BASES["抄底"][0],d),"bot")
line("大盤回檔≥10%(QQQ)",d,c,"bot"); line("VIX≥20",d,v,"bot"); line("大盤回檔或VIX≥20(=全面性下跌)",d,c|v,"bot")
line("都沒有(=個股自己跌)",d,~(c|v),"bot")
line("全面性下跌 + 資金≥80%",d,(c|v)&l8,"bot"); line("全面性下跌 + 資金<80%",d,(c|v)&~l8,"bot")
line("個股自己跌 + 資金≥80%",d,~(c|v)&l8,"bot")
line("資金≥90%",d,l9,"bot"); line("5天內財報",d,nx,"bot"); line("跌太深(≥25%)",d,dp,"bot")
sc=(c|v).astype(int)+c.astype(int)*0+l8.astype(int)+nx.astype(int)-dp.astype(int)
print("  -- 分數 = 全面性下跌(大盤回檔≥10% 或 VIX≥20) + 資金≥80% + 5天內財報 − 跌太深(≥25%)")
for k,lab in ((-1,"≤0"),(1,"1"),(2,"2"),(3,"≥3")):
    mk=(sc<=0) if k==-1 else ((sc>=3) if k==3 else (sc==k)); line(f"分數 {lab}",d,mk,"bot")

d=ev(STAR,"open"); print(f"\n[★(TD買9/RV/殺量/CTA弱 ≥3 項)]")
c,v,l6,w,sa=[M(x,d) for x in (COR,VIXH,L65,WASH,SPYA20)]
line("全部★",d,np.ones(len(d),bool),"bot"); line("★ + 資金≥65%(現行建議)",d,l6,"bot")
line("★ + 全面性下跌",d,c|v,"bot"); line("★ + 資金≥65% + 全面性下跌",d,l6&(c|v),"bot")
line("★ + 資金≥65% + SPY在20日線下",d,l6&~sa,"bot"); line("★ + 資金≥65% + SPY在20日線上",d,l6&sa,"bot")
line("★ + 資金<65% + 個股自己跌",d,~l6&~(c|v),"bot")

d=ev(BUY,"open"); print(f"\n[買(技判三路徑,價格部分)]")
c,v,l6,sa=[M(x,d) for x in (COR,VIXH,L65,SPYA20)]
line("全部買",d,np.ones(len(d),bool),"bot"); line("買 + 資金≥65%",d,l6,"bot")
line("買 + 資金≥65% + SPY在20日線下",d,l6&~sa,"bot"); line("買 + 資金≥65% + 全面性下跌",d,l6&(c|v),"bot")
line("買 + 資金<65% + SPY在20日線上",d,~l6&sa,"bot")

print("\n################ C. 機械式樣本外:只用一段挑條件(差≥+4 且 CI 不含 0 → +1;差≤−4 且 CI 不含 0 → −1),另一段驗證 ################")
R10=pickle.load(open(DT+"/t10_sell.pkl","rb")); R11=pickle.load(open(DT+"/t11_buy.pkl","rb"))
def mech(bn,sig,ent,side,RES,CANDS):
    d=ev(sig,ent)
    for fit,test in (("p1","p2"),("p2","p1")):
        plus=[k for k,v in RES[bn].items() if v[fit]["nw"]>=30 and v[fit]["diff"]>=4 and v[fit]["ci"][0]>0]
        minus=[k for k,v in RES[bn].items() if v[fit]["nw"]>=30 and v[fit]["diff"]<=-4 and v[fit]["ci"][1]<0]
        sc=np.zeros(len(d),int)
        for k in plus: sc+=M(CANDS[k],d).astype(int)
        for k in minus: sc-=M(CANDS[k],d).astype(int)
        print(f"\n  {bn}:用{fit}挑 → 加分 {plus} / 扣分 {minus};在{test}驗證:",flush=True)
        for lab,mk in (("分數≤−1",sc<=-1),("分數 0",sc==0),("分數 1",sc==1),("分數≥2",sc>=2)):
            r=hit(d,mk,side,20,test,boot=400)
            if r["n"]<8: print(f"    {lab:8s} n={r['n']}"); continue
            print(f"    {lab:8s} n={r['n']:5d} 命中 {r['hit']:4.1f}%(基準 {r['base']:.1f},差 {r['hit']-r['base']:+5.1f} [{r['ci'][0]:+.0f},{r['ci'][1]:+.0f}]) 平均 {r['mean']:+5.2f}% 扣大盤 {r['xm']:+5.2f}%",flush=True)
SC={**SELL_STOCK,**SELL_MKT}; BC={**BUY_STOCK,**BUY_MKT}
for bn in ("出","出(不看資金)","頂K"): mech(bn,*SELL_BASES[bn],"top",R10,SC)
for bn in ("抄底","深跌站回(不看資金)","★(不看資金)","買(任一路徑)"): mech(bn,*BUY_BASES[bn],"bot",R11,BC)

print("\n################ D. 大盤層級條件按「回檔事件」分組(QQQ 從一年高點回檔≥10% 的區間,間隔<40天合併)################")
cor=COR.reindex(dates).fillna(False).values
epi=np.zeros(len(dates),int); k=0; last=-999
for i in np.flatnonzero(cor):
    if i-last>40: k+=1
    epi[i]=k; last=i
for nm,sig in (("深跌站回(不看資金)",BUY_BASES["深跌站回(不看資金)"][0]),("抄底",BUY_BASES["抄底"][0]),("★",STAR)):
    d=ev(sig,"open"); d["ep"]=epi[d.i.values]; dd=d[(d.ep>0)&d.f20.notna()]
    g=dd.groupby("ep").agg(start=("date","min"),end=("date","max"),n=("f20","size"),hit=("f20",lambda x:(x>0).mean()*100),mean=("f20",lambda x:x.mean()*100),
                           hit40=("f40",lambda x:(x>0).mean()*100))
    print(f"\n  {nm}:每次大盤回檔期間的事件(20日後較高比例 / 平均報酬)")
    for _,r in g.iterrows(): print(f"    {r.start.date()}~{r.end.date()} n={r.n:4d} 20日 {r.hit:5.1f}% 均 {r['mean']:+6.2f}% | 40日 {r.hit40:5.1f}%")
    print(f"    → 回檔事件中 20日命中 >50% 的次數:{(g.hit>50).sum()}/{len(g)};事件平均命中 {g.hit.mean():.1f}%(每次回檔等權)")
