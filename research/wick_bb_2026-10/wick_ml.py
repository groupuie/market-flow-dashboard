# 3) 讓機器在「碰上軌的日子」裡自己找條件組合:有/無上影線特徵,樣本外 AUC 有沒有差?
import numpy as np, pandas as pd, pickle, warnings; warnings.filterwarnings("ignore")
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.metrics import roc_auc_score
exec(open("wick_cond.py").read().split("COMBO={")[0])
O1=O.shift(-1); f10=np.log(C.shift(-10)/O1); dd20=np.log(L[::-1].rolling(20,min_periods=20).min()[::-1].shift(-1)/O1)
feat={"uw":uw,"wick_atr":wick_atr,"ibs":ibs,"black":(C<O).astype(float),"ext":ext,"volr":volr,
 "keyrev":((H>H.shift(1))&(C<C.shift(1))).astype(float),"up20":((H>hh20)&(C<hh20)).astype(float),"up252":((H>hh252)&(C<hh252)).astype(float),
 "gapfade":((O>=C.shift(1)*1.02)&(C<O)).astype(float),"r20":C/C.shift(20)-1,"r5":C/C.shift(5)-1,"rsi":rsi,"tds":tds,"clim":clim,"spyweak":spyweak.astype(float),"mtop":mtop.astype(float),
 "gap":O/C.shift(1)-1,"dayret":C/C.shift(1)-1}
mask=touch&C.notna()
idx=mask.stack(); idx=idx[idx].index
X=pd.DataFrame({k:v.stack().reindex(idx) for k,v in feat.items()})
y_top=near_top.stack().reindex(idx).astype(float)
y_bad=((f10.stack().reindex(idx)<-0.03)).astype(float).where(f10.stack().reindex(idx).notna())
d=X.index.get_level_values(0)
A=(d>="2007-01-01")&(d<="2016-12-31"); B=(d>="2017-01-01")&(d<="2026-09-30")
WICK=["uw","wick_atr","ibs","black"]
for tn,y in (("落在真高點±2天",y_top),("10日後跌>3%",y_bad)):
    ok=y.notna().values
    for nm,cols in (("全部特徵(含上影)",list(X.columns)),("拿掉上影/K棒形狀",[c for c in X.columns if c not in WICK]),("只有上影/K棒形狀",WICK)):
        clf=HistGradientBoostingClassifier(max_iter=200,learning_rate=0.05,max_depth=4,min_samples_leaf=400,l2_regularization=1.0,random_state=0)
        clf.fit(X.loc[A&ok,cols],y[A&ok]); p=clf.predict_proba(X.loc[B&ok,cols])[:,1]
        yb=y[B&ok].values; auc=roc_auc_score(yb,p)
        q=np.quantile(p,0.9); top10=yb[p>=q].mean()*100
        print(f"[{tn}] {nm:14s} 樣本外 AUC {auc:.3f} | 最高分10%的命中 {top10:.1f}%(平常 {yb.mean()*100:.1f}%)")
# 可讀規則:深度3決策樹(訓練A)→ 在B驗證每片葉子
ok=y_top.notna().values
t=DecisionTreeClassifier(max_depth=3,min_samples_leaf=800,random_state=0).fit(X.loc[A&ok],y_top[A&ok])
print(export_text(t,feature_names=list(X.columns),decimals=2))
lfA=t.apply(X.loc[A&ok]); lfB=t.apply(X.loc[B&ok])
ya=y_top[A&ok].values; yb=y_top[B&ok].values
print("葉子 | A期 n/命中 | B期 n/命中")
for lf in sorted(set(lfA)):
    print(lf, f"{(lfA==lf).sum()}/{ya[lfA==lf].mean()*100:.1f}%", f"{(lfB==lf).sum()}/{(yb[lfB==lf].mean()*100 if (lfB==lf).sum() else float('nan')):.1f}%")
