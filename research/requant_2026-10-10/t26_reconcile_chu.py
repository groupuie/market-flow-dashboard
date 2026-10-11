# t26(Codex v0.2 第 4.1 節):網站 STATS 的「出」1,723 次 vs 新研究 1,674 次 —— 逐筆事件對帳(event key = 股票 + 訊號日 + 類型)
#   A = flow_climate 研究 prod_eval.py → prod_sigs.pkl 的 T_strong|T_reg(stats_final.py 用它算網站 STATS)
#   B = requant qlib.chu()(t25_fixD 用它算新的風險表)
import pickle, hashlib, numpy as np, pandas as pd
from qlib import DT, C, cols, dates, chu, CL
S = pickle.load(open(DT + "/prod_sigs.pkl", "rb"))
A = (S["T_strong"] | S["T_reg"]).reindex(index=dates, columns=cols).fillna(False).astype(bool)
Bq = chu().reindex(index=dates, columns=cols).fillna(False).astype(bool)
def keys(X, a, b):
    m = X.loc[(dates >= a) & (dates <= b)]; s = m.stack(); s = s[s]
    return {(str(d.date()), t, "出") for d, t in s.index}
def h(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
print("資料:stock.pkl sha256", h(DT + "/stock.pkl"), "| prod_sigs.pkl", h(DT + "/prod_sigs.pkl"), "| climA_rank.pkl", h(DT + "/climA_rank.pkl"))
print("股票:A", A.shape[1], "檔、B", Bq.shape[1], "檔(同一份 259 檔名單:", list(A.columns) == list(Bq.columns), ");日期", dates[0].date(), "~", dates[-1].date())
cr_prod = S["clim"].reindex(dates); cr_q = CL.iloc[:, 0]
both = cr_prod.notna() & cr_q.notna()
print("資金氣候序列:prod 與 qlib 同一天的值相同的天數", int((np.isclose(cr_prod[both], cr_q[both])).sum()), "/", int(both.sum()),
      "| 只有一邊有值:", int((cr_prod.notna() ^ cr_q.notna()).sum()))
for lab, a, b in (("網站 STATS 口徑 2009-01-01~2026-12-31", "2009-01-01", "2026-12-31"), ("新研究口徑 2009-07-01~2026-12-31", "2009-07-01", "2026-12-31"),
                  ("2009-01-01~2009-06-30", "2009-01-01", "2009-06-30"), ("2018-01-01~2026-12-31", "2018-01-01", "2026-12-31")):
    ka, kb = keys(A, a, b), keys(Bq, a, b)
    print(f"\n[{lab}] A {len(ka)} 次、B {len(kb)} 次、交集 {len(ka & kb)}、只在 A {len(ka - kb)}、只在 B {len(kb - ka)}")
    for k in sorted(ka - kb)[:10]: print("   只在 A:", k)
    for k in sorted(kb - ka)[:10]: print("   只在 B:", k)
# 同一分母下比較比例:用 qlib 的 qm_risk_summary(只算 40 天已完整的事件)重算兩種起點
from qlib import qm_risk_summary, MAE, _stk, _pm
print("\n### 同一份事件、同一種算法(隔天開盤進場,40 天內最低價比進場價低 ≥10%;未完成不算)")
for lab, a in (("2009-01-01 起(網站 STATS 口徑)", "2009-01-01"), ("2009-07-01 起(新研究口徑)", "2009-07-01")):
    pm = _pm(a, "2026-12-31"); m = A.loc[pm]; idx = m.stack(); idx = idx[idx].index
    dd = _stk(MAE[40], pm, cols); r = qm_risk_summary(dd, idx)
    base = dd.replace([np.inf, -np.inf], np.nan).dropna(); b = (base <= np.log(0.9)).mean() * 100
    print(f"  {lab}:事件 {len(idx)}、有效 {r['risk_n']}、未完成 {r['risk_missing_n']} → {r['risk']:.1f}%(所有股票日 {b:.1f}%,n={len(base)})")
