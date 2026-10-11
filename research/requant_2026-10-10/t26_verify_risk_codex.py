# Codex v0.2 附錄 A 的原版 verify_risk.py(v0.1 原檔內容)。
# 唯一改動:第 3 行原本是 `from qm_risk import qm_risk_summary`(Codex 的測試介面),
# 照 Codex 建議改成從正式函式匯入 `from qlib import qm_risk_summary`;其餘逐字保留。
import numpy as np
import pandas as pd
from qlib import qm_risk_summary

raw = pd.Series([np.nan, np.log(.8), np.log(.95)])
r = qm_risk_summary(raw, raw.index)
assert (raw <= np.log(.9)).dropna().mean() == 1/3
assert r['risk'] == 50 and r['risk_n'] == 2 and r['risk_missing_n'] == 1
empty = pd.Series([np.nan, np.inf])
r = qm_risk_summary(empty, empty.index)
assert np.isnan(r['risk']) and r['risk_n'] == 0
low = pd.Series([100.,91.,82.,73.,64.,55.])
future_min = low[::-1].rolling(3,min_periods=3).min()[::-1].shift(-1)
assert future_min.iloc[:3].tolist() == [73.,64.,55.]
assert future_min.iloc[-3:].isna().all()
low.iloc[2] = np.nan
incomplete=low[::-1].rolling(3,min_periods=3).min()[::-1].shift(-1)
assert incomplete.iloc[:2].isna().all()
# 同波動配對：缺 MAE 及缺波動分類都不能混入配對樣本。
dd=pd.Series([np.log(.8),np.log(.95),np.nan,np.log(.7)],index=['a','b','c','d'])
vq=pd.Series([.15,.15,.95,np.nan],index=dd.index)
r=qm_risk_summary(dd,dd.index,vq)
assert r['risk_n']==3 and r['risk_matched_n']==2
assert r['risk_matched']==50 and r['risk_base']==50
r=qm_risk_summary(dd,pd.Index(['z']),vq)
assert r['risk_n']==0 and r['risk_matched_n']==0 and np.isnan(r['risk_base'])
print('PASS: missing outcomes, empty samples, forward window, matched sample alignment')
