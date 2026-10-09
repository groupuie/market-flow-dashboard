import numpy as np, pandas as pd, pickle, warnings, itertools; warnings.filterwarnings("ignore")
exec(open("sellnext.py").read().split("W=touch&(uw>=0.25)")[0])
succ=pickle.load(open(DT+"/sell_succ.pkl","rb")); succ_close,succ_next=succ["succ_close"],succ["succ_next"]
offhi=1-C/H; offatr=(H-C)/atr.shift(1)
r20=C/C.shift(20)-1; d20atr=(C-mid)/atr
hot={"20日漲≥30%":r20>=0.30,"高於20日線≥3ATR":d20atr>=3,"拉離50日線≥25%":ext>=0.25}
hot["三者任一(漲多)"]=hot["20日漲≥30%"]|hot["高於20日線≥3ATR"]|hot["拉離50日線≥25%"]
hot["不限"]=C.notna()
rej={"離高≥4%":offhi>=0.04,"離高≥5%":offhi>=0.05,"離高≥7%":offhi>=0.07,"離高≥1.5ATR":offatr>=1.5,"離高≥2ATR":offatr>=2.0}
conf=(C.shift(-1)<L)    # 隔天收盤跌破訊號K最低價(在隔天收盤才知道)
PER={"A 07-16":("2007-01-01","2016-12-31"),"B 17-26":("2017-01-01","2026-12-31")}
ny={k:(C[(dates>=a)&(dates<=b)].notna().values.sum()/252) for k,(a,b) in PER.items()}
rows=[]
for (hn,hm),(rn,rm),cf in itertools.product(hot.items(),rej.items(),(False,True)):
    sig=touch&hm&rm&(conf if cf else True)
    r={"漲多條件":hn,"反轉幅度":rn,"隔天破低確認":"是" if cf else "否"}
    for p,(a,b) in PER.items():
        pm=(dates>=a)&(dates<=b); s=sig.loc[pm]; tgt=(succ_next if cf else succ_close).loc[pm]
        e=tgt.where(s).stack().dropna()
        r[p+" 每檔年"]=round(s.values.sum()/ny[p],2); r[p+" 賣在頂%"]=round(e.mean()*100,1)
    rows.append(r)
R=pd.DataFrame(rows); R["兩期最低"]=R[["A 07-16 賣在頂%","B 17-26 賣在頂%"]].min(axis=1)
pd.set_option("display.width",250); pd.set_option("display.max_rows",200)
print(R.sort_values("兩期最低",ascending=False).head(30).to_string(index=False))
print("…基準:任何一天 17%;碰上軌+上影≥1/4 約 18%")
