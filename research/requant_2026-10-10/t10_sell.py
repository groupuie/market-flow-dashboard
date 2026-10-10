# t10:賣出訊號(出 / 出不看資金 / 頂K / 減碼)—— 哪些「加分條件」能讓賣出更準?
# 比法:同一個訊號裡,「有條件」vs「沒條件」的 20 日後下跌比例差(百分點),前半 2009-17 / 後半 2018-26,
#       20 日區塊自助法 90% CI;四段期間正負;40 日差;扣大盤後平均報酬差;大盤層級條件另列「大盤本身」效果。
import sys; sys.path.insert(0,"."); from t10lib import *; from t10lib import _sel
import pickle
X=chu(); XR=turn("top",0.15)              # 出(資金≤35%)/ 出的價格部分(不看資金)
BASES={"出":(X,"open"),"出(不看資金)":(XR,"open"),"頂K":(TK,"close"),"減碼":(CF,"close")}
OILW=MR["原油20日"]<=1/3; YDROP=MR["10年債殖利率20日(bp)"]<=1/3; CREDW=MR["信用(高收益/公債)20日"]<=1/3
STOCK={
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
MKT={
 "SPY在20日線下":SP.c<sp20, "QQQ在20日線下":Q.c<q20, "QQQ在50日線下":Q.c<q50, "QQQ 20日報酬<0":Q.c<Q.c.shift(20),
 "廣度:站上20日線<40%":br20<40, "廣度10天掉≥15點(50日)":(br50-br50.shift(10))<=-15,
 "VIX≥20":vix>=20, "VIX 10日升≥20%":vix>=vix.shift(10)*1.2, "VIX倒掛(≥VIX3M)":vix>=v3m,
 "QQQ出貨日≥5(25天)":dist25>=5,
 "油價20日走弱(最低1/3)":OILW, "10年債殖利率20日急降(1/3)":YDROP, "信用轉弱(1/3)":CREDW,
 "資金偏緊≤35%":cr<=0.35, "資金寬鬆≥65%":cr>=0.65,
}
ALLRES={}
for bn,(sig,ent) in BASES.items():
    d=ev(sig,ent)
    print(f"\n######## {bn}(進場:{'隔天開盤' if ent=='open' else '當晚收盤'})  事件 前半 {int(_sel(d,20,'p1').sum())} / 後半 {int(_sel(d,20,'p2').sum())}",flush=True)
    for per in ("p1","p2"):
        r=hit(d,np.ones(len(d),bool),"top",20,per); r4=hit(d,np.ones(len(d),bool),"top",40,per,boot=0)
        print(f"  整體 {per}: 20日後較低 {r['hit']:.1f}%(基準 {r['base']:.1f}%,差 {r['hit']-r['base']:+.1f} [{r['ci'][0]:+.1f},{r['ci'][1]:+.1f}]) 平均 {r['mean']:+.2f}% 扣大盤 {r['xm']:+.2f}% | 40日 {r4['hit']:.1f}%(基準 {r4['base']:.1f}%)",flush=True)
    res={}
    print("  -- 個股條件",flush=True)
    for nm,m in STOCK.items():
        if bn in ("頂K","減碼") and nm in ("前20天有頂K",): continue
        res[nm]=row(nm,d,m,"top")
    print("  -- 大盤/總經條件",flush=True)
    for nm,m in MKT.items():
        if bn=="出" and nm in ("資金偏緊≤35%","資金寬鬆≥65%"): continue
        res[nm]=row(nm,d,m,"top")
    ALLRES[bn]=res
pickle.dump(ALLRES,open(DT+"/t10_sell.pkl","wb"))
