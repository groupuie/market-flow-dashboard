# t10/t11 的候選條件(自動抽出),供 t12 匯入
import sys; sys.path.insert(0,"."); from t10lib import *
X=chu(); XR=turn("top",0.15)
SELL_BASES={"出":(X,"open"),"出(不看資金)":(XR,"open"),"頂K":(TK,"close"),"減碼":(CF,"close")}
OILW=MR["原油20日"]<=1/3; YDROP=MR["10年債殖利率20日(bp)"]<=1/3; CREDW=MR["信用(高收益/公債)20日"]<=1/3
SELL_STOCK={
 "破線爆量(量≥1.5×)":vr>=1.5, "爆量(量≥2×)":vr>=2.0,
 "跳空跌≥2%":O<=C.shift(1)*0.98, "當天跌≥4%":ret1<=-0.04, "收在當日低檔(IBS≤.25)":ibs<=0.25,
 "跳空高開≥2%後收黑":(O>=C.shift(1)*1.02)&(C<O), "當天收跌":C<C.shift(1),
 "前20天有頂K":anyN(TK.shift(1),20), "漲更多(50日線上≥30%)":rel50.rolling(20).max()>=0.30,
 "已跌破50日線":C<S50, "高點降低(近5日高<前15日高2%)":H.rolling(5).max()<H.shift(5).rolling(15).max()*0.98,
 "相對QQQ弱(10日落後≥5%)":rsQ10<=-0.05, "相對QQQ強(10日領先≥5%)":rsQ10>=0.05,
 "在200日線上":C>S200, "AI/半導體股":AIc,
 "近20天財報反應差":EF["neg20"], "5天內要公布財報":EF["nxt"], "財報當天/隔天":EF["earn_win"],
 "內部人近3月賣超前10%":IF["heavy"],
}
SELL_MKT={
 "SPY在20日線下":SP.c<sp20, "QQQ在20日線下":Q.c<q20, "QQQ在50日線下":Q.c<q50, "QQQ 20日報酬<0":Q.c<Q.c.shift(20),
 "廣度:站上20日線<40%":br20<40, "廣度10天掉≥15點(50日)":(br50-br50.shift(10))<=-15,
 "VIX≥20":vix>=20, "VIX 10日升≥20%":vix>=vix.shift(10)*1.2, "VIX倒掛(≥VIX3M)":vix>=v3m,
 "QQQ出貨日≥5(25天)":dist25>=5,
 "油價20日走弱(最低1/3)":OILW, "10年債殖利率20日急降(1/3)":YDROP, "信用轉弱(1/3)":CREDW,
 "資金偏緊≤35%":cr<=0.35, "資金寬鬆≥65%":cr>=0.65,
}

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
BUY_BASES={"抄底":(chaodi(),"open"),"深跌站回(不看資金)":(chaodi(cut=-0.01),"open"),"★(資金≥65%)":(STAR&(CL>=0.65),"open"),"★(不看資金)":(STAR,"open"),"買(任一路徑)":(BUY,"open")}
L40=L.rolling(40).min(); L10=L.rolling(10).min()
vmax20=vix.rolling(20).max()
BUY_STOCK={
 "20天內爆量長黑(≥3×且跌≥5%)":anyN((vr>=3)&(ret1<=-0.05),20), "20天內爆量下跌(≥2×且跌≥3%)":anyN((vr>=2)&(ret1<=-0.03),20),
 "當天量≥1.5×":vr>=1.5, "當天跳空≥2%":O>=C.shift(1)*1.02, "當天漲≥4%":ret1>=0.04, "收在當日高檔(IBS≥.75)":ibs>=0.75,
 "打底≥10天(低點在10天前)":L10>L40, "二次探底守住(離低點≤8%)":(L10>L40)&(L10<=L40*1.08), "V型(低點在5天內)":L.rolling(5).min()<=L40,
 "在200日線上":C>S200, "跌更深(50日線下≥25%)":rel50.rolling(20).min()<=-0.25, "20天內RSI14<30":anyN(rsi14<30,20),
 "相對QQQ強(10日領先≥5%)":rsQ10>=0.05, "相對QQQ弱(10日落後≥5%)":rsQ10<=-0.05,
 "5天內要公布財報":EF["nxt"], "近20天財報反應好":EF["pos20"], "近20天財報反應差":EF["neg20"],
 "近3月內部人買":IF["buy63"], "AI/半導體股":AIc,
}
BUY_MKT={
 "SPY在20日線上":SP.c>sp20, "QQQ在20日線上":Q.c>q20, "QQQ在50日線上":Q.c>q50, "QQQ從一年高點回檔≥10%":Q.c<=Q.c.rolling(252,min_periods=60).max()*0.9,
 "20天內廣度洗盤(站上50日線≤20%)":anyN(br50<=20,20), "廣度衝刺(10天內≤30%→≥60%)":(br20>=60)&(br20.rolling(10).min()<=30), "廣度已回升(站上20日線≥50%)":br20>=50,
 "VIX 20天內≥30且已回落15%":(vmax20>=30)&(vix<=vmax20*0.85), "VIX 20天內≥25且已回落15%":(vmax20>=25)&(vix<=vmax20*0.85),
 "VIX倒掛已解除(20天內)":anyN(vix>=v3m,20)&(vix<v3m), "VIX<20":vix<20,
 "資金氣候20天升≥0.2":(cr-cr.shift(20))>=0.2, "資金≥90%":cr>=0.90, "資金≥65%":cr>=0.65,
 "信用改善(最高1/3)":MR["信用(高收益/公債)20日"]>=2/3, "油價20日走強(最高1/3)":MR["原油20日"]>=2/3, "殖利率20日急降(最低1/3)":MR["10年債殖利率20日(bp)"]<=1/3,
}
