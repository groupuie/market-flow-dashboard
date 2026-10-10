# t11:買進訊號(抄底 / 深跌站回不看資金 / ★ / 買)—— 哪些「加分條件」能讓抄底更準?
# 比法同 t10:同一訊號裡「有條件」vs「沒條件」的 20 日後上漲比例差;前半/後半、CI、四段、40 日差、扣大盤差、大盤本身效果。
import sys; sys.path.insert(0,"."); from t10lib import *; from t10lib import _sel
import pickle
F=FE; scf=F["sc"].astype("float64"); rv=F["rvpos"].astype("float64"); tdbF=F["tdb"].astype("float64"); volrF=F["volr"].astype("float64"); rsi14=F["rsi14"].astype("float64")
BOT=((tdbF>=9).astype(int)+(rv>=80).astype(int)+((volrF>=1.75)&(C<C.shift(5))).astype(int)+(scf<66).astype(int)).where(scf.notna())
STAR=cool(BOT>=3,20)
# 買(技判手冊三路徑,價格部分;同 t4)
m20=C.rolling(20).mean(); sd=C.rolling(20).std(ddof=0); up=m20+2*sd; lo=m20-2*sd; pb=(C-lo)/(up-lo); bw=(up-lo)/m20
sqz=bw<=bw.rolling(60,min_periods=1).min(); trend=(C>S50)&(S50>S50.shift(10))
def runcount(cond): return cond.astype(int).apply(lambda c: c.groupby((c==0).cumsum()).cumsum())
tdb=runcount(C<C.shift(4))
pT=trend&anyN(tdb>=6,10)&anyN((pb<=0.35)|sqz,10); pC=(~trend)&((pb<=0.2)|sqz)&anyN(tdb>=9,5); pD=anyN(tdb>=9,10)&anyN(C<lo,10)&(C>lo)
first=lambda X: X&~X.shift(1).fillna(False).astype(bool)
BUY=first(pT)|first(pC)|first(pD)
BASES={"抄底":(chaodi(),"open"),"深跌站回(不看資金)":(chaodi(cut=-0.01),"open"),"★(資金≥65%)":(STAR&(CL>=0.65),"open"),"★(不看資金)":(STAR,"open"),"買(任一路徑)":(BUY,"open")}
L40=L.rolling(40).min(); L10=L.rolling(10).min()
vmax20=vix.rolling(20).max()
STOCK={
 "20天內爆量長黑(≥3×且跌≥5%)":anyN((vr>=3)&(ret1<=-0.05),20), "20天內爆量下跌(≥2×且跌≥3%)":anyN((vr>=2)&(ret1<=-0.03),20),
 "當天量≥1.5×":vr>=1.5, "當天跳空≥2%":O>=C.shift(1)*1.02, "當天漲≥4%":ret1>=0.04, "收在當日高檔(IBS≥.75)":ibs>=0.75,
 "打底≥10天(低點在10天前)":L10>L40, "二次探底守住(離低點≤8%)":(L10>L40)&(L10<=L40*1.08), "V型(低點在5天內)":L.rolling(5).min()<=L40,
 "在200日線上":C>S200, "跌更深(50日線下≥25%)":rel50.rolling(20).min()<=-0.25, "20天內RSI14<30":anyN(rsi14<30,20),
 "相對QQQ強(10日領先≥5%)":rsQ10>=0.05, "相對QQQ弱(10日落後≥5%)":rsQ10<=-0.05,
 "5天內要公布財報":EF["nxt"], "近20天財報反應好":EF["pos20"], "近20天財報反應差":EF["neg20"],
 "近3月內部人買":IF["buy63"], "AI/半導體股":AIc,
}
MKT={
 "SPY在20日線上":SP.c>sp20, "QQQ在20日線上":Q.c>q20, "QQQ在50日線上":Q.c>q50, "QQQ從一年高點回檔≥10%":Q.c<=Q.c.rolling(252,min_periods=60).max()*0.9,
 "20天內廣度洗盤(站上50日線≤20%)":anyN(br50<=20,20), "廣度衝刺(10天內≤30%→≥60%)":(br20>=60)&(br20.rolling(10).min()<=30), "廣度已回升(站上20日線≥50%)":br20>=50,
 "VIX 20天內≥30且已回落15%":(vmax20>=30)&(vix<=vmax20*0.85), "VIX 20天內≥25且已回落15%":(vmax20>=25)&(vix<=vmax20*0.85),
 "VIX倒掛已解除(20天內)":anyN(vix>=v3m,20)&(vix<v3m), "VIX<20":vix<20,
 "資金氣候20天升≥0.2":(cr-cr.shift(20))>=0.2, "資金≥90%":cr>=0.90, "資金≥65%":cr>=0.65,
 "信用改善(最高1/3)":MR["信用(高收益/公債)20日"]>=2/3, "油價20日走強(最高1/3)":MR["原油20日"]>=2/3, "殖利率20日急降(最低1/3)":MR["10年債殖利率20日(bp)"]<=1/3,
}
ALLRES={}
for bn,(sig,ent) in BASES.items():
    d=ev(sig,ent)
    print(f"\n######## {bn}  事件 前半 {int(_sel(d,20,'p1').sum())} / 後半 {int(_sel(d,20,'p2').sum())}",flush=True)
    for per in ("p1","p2"):
        r=hit(d,np.ones(len(d),bool),"bot",20,per); r4=hit(d,np.ones(len(d),bool),"bot",40,per,boot=0)
        print(f"  整體 {per}: 20日後較高 {r['hit']:.1f}%(基準 {r['base']:.1f}%,差 {r['hit']-r['base']:+.1f} [{r['ci'][0]:+.1f},{r['ci'][1]:+.1f}]) 平均 {r['mean']:+.2f}% 扣大盤 {r['xm']:+.2f}% 中途再跌≥10% {r['dd10']:.0f}% | 40日 {r4['hit']:.1f}%(基準 {r4['base']:.1f}%)",flush=True)
    res={}
    print("  -- 個股條件",flush=True)
    for nm,m in STOCK.items(): res[nm]=row(nm,d,m,"bot")
    print("  -- 大盤/總經條件",flush=True)
    for nm,m in MKT.items():
        if bn in ("抄底",) and nm in ("資金≥65%",): continue
        if bn.startswith("★(資金") and nm in ("資金≥65%",): continue
        res[nm]=row(nm,d,m,"bot")
    ALLRES[bn]=res
pickle.dump(ALLRES,open(DT+"/t11_buy.pkl","wb"))
