import numpy as np, pandas as pd, time, warnings, sys; warnings.filterwarnings("ignore")
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from lib import DT
t0=time.time()
L=pd.read_pickle(DT+"/long.pkl"); M=pd.read_pickle(DT+"/market.pkl")
SF=["r1","r2","r3","r5","r10","r20","r60","r120","r250","z1","z5","z10","z20","d10","d20","d50","d200","p20","p50","p200","pctB","rsi2","rsi14","ibs","dd252","pos252","pos20","dd60","up60","volr","volr5","rvpos","sc","tds","tdb","ndown","nup","gap","beta","res5","res20","zres5","atrp","sd20","sd60"]
MF=["cta_spx","cta_ndx","cta_sox","cta_spx_chg5","cta_ndx_chg5","cta_ndx_pct","flip21_spx","flip63_spx","cta_tlt","cta_oil","cta_gold","cta_dxy","volctl","volctl_chg5","volctl_pct","rv21","rv63","sb_corr63",
"vix","vix_pct","vix_ratio","vix9_ratio","vix_chg5","vix_ma_ratio","vrp","vvix","skew","vix_ratio_max10","dix5","dix_pct","gex_pct","gex_neg",
"hy_chg5","hy_chg20","hy_dd60","hy_z20","ig_chg20","tnx","tnx_chg5","tnx_chg20","tnx_chg60","curve","curve_chg20","move","move_pct","move_chg20",
"dxy_chg5","dxy_chg20","jpy_chg10","jpy_z10","krw_chg20","oil_chg5","oil_chg20","oil_chg60","oil_pos252","gold_chg5","gold_chg20","gold_chg60","silver_chg20","agau_chg20","cuau_chg20","cuau_chg60","auspx_chg20","btc_chg20",
"spx_r5","spx_r20","spx_r60","spx_d50","spx_d200","spx_dd","ndx_r20","ndx_dd","sox_r5","sox_r20","sox_r60","sox_d50","sox_dd","rsp_spy20","hb_lv20","kospi_r5","kospi_r20","twii_r20",
"br20","br50","br200","br_low20","br_high20","br_adv5","br_mean_r5","br_disp20","tom",
"cot_eq_lev_z","cot_eq_am_z","cot_eq_dlr_z","cot_eq_am_chg4","cot_vx_lev_z","cot_zn_lev_z","cot_jy_lev_z","cot_cl_mm_z","cot_gc_mm_z","cot_si_mm_z"]
d=L.index.get_level_values(0)
X=L[SF].astype("float32").copy()
Mx=M[MF].astype("float32").reindex(d)
for c in MF: X[c]=Mx[c].values
# relative features: stock vs market
X["rel5"]=L["r5"].values-M["spx_r5"].reindex(d).values; X["rel20"]=L["r20"].values-M["spx_r20"].reindex(d).values
X["rel_sox20"]=L["r20"].values-M["sox_r20"].reindex(d).values
# cross-sectional ranks per date of a few key stock features
for c in ["r5","r20","r60","z5","d50","dd252","rvpos","volr5"]:
    X["cs_"+c]=L[c].groupby(level=0).rank(pct=True).astype("float32").values
y_up=(L["f20"]>0).astype(float).where(L["f20"].notna())
y_dd=(L["mae20"]<=np.log(0.85)).astype(float).where(L["mae20"].notna())
years=pd.Series(d.year,index=L.index)
print("X",X.shape,"%.0fs"%(time.time()-t0)); sys.stdout.flush()
preds={"pup":pd.Series(np.nan,index=L.index),"pdd":pd.Series(np.nan,index=L.index)}
dates=d.unique().sort_values()
for Y in range(2011,2027):
    test=(d.year==Y)
    tr_end=pd.Timestamp(f"{Y}-01-01")
    emb=dates[dates<tr_end][-25] if (dates<tr_end).sum()>25 else tr_end
    train=(d<emb)&(d>="2006-07-01")
    # subsample every 3rd date for training (overlapping targets)
    di=pd.Series(np.arange(len(dates)),index=dates)
    sub=train&((di.reindex(d).values%3)==0)
    for tgt,y in (("pup",y_up),("pdd",y_dd)):
        m=sub&y.notna().values
        clf=HistGradientBoostingClassifier(max_iter=250,learning_rate=0.05,max_depth=5,min_samples_leaf=800,l2_regularization=1.0,max_features=0.5,random_state=0)
        Xm=X[m]; cols=[c for c in X.columns if Xm[c].nunique()>1]
        clf.fit(Xm[cols],y[m])
        tm=test&y.notna().values
        if tm.sum()==0: continue
        preds[tgt][tm]=clf.predict_proba(X.loc[tm,cols])[:,1]
        if Y in (2018,2026): pd.to_pickle((clf,cols),DT+f"/ml_model_{tgt}_{Y}.pkl")
    m=test&y_up.notna().values
    a1=roc_auc_score(y_up[m],preds["pup"][m]) if m.sum()>100 else np.nan
    m2=test&y_dd.notna().values
    a2=roc_auc_score(y_dd[m2],preds["pdd"][m2]) if m2.sum()>100 and y_dd[m2].nunique()>1 else np.nan
    print(Y,"train rows",int(sub.sum()),"test",int(test.sum()),"AUC up %.3f  dd %.3f"%(a1,a2),"%.0fs"%(time.time()-t0)); sys.stdout.flush()
pd.DataFrame(preds).to_pickle(DT+"/ml_preds.pkl")
