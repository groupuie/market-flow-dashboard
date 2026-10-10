# t25 測試(Codex v0.1 修正 D):qm_risk_summary 的分母只用「期間已走完」的事件。
# 附錄 B 原文沒有留在這邊的工作檔,這是照同樣的檢查項目寫的等價測試(合成資料 + 真實面板)。
import numpy as np, pandas as pd, sys
sys.path.insert(0, ".")
from qlib import qm_risk_summary, evaluate, _stk, _pm, MAE, MAEC, VQ, cols, topk, chu
CUT = np.log(0.9)
ok_all = True
def check(name, cond):
    global ok_all
    ok_all &= bool(cond); print(("PASS " if cond else "FAIL ") + name)

# ---- 1. 合成:6 個事件,2 個未完成(NaN)、1 個 inf;舊算法把 NaN 當「沒跌」
ix = pd.MultiIndex.from_tuples([(d, "A") for d in range(8)])
dd = pd.Series([-0.20, -0.01, -0.15, np.nan, np.nan, -0.02, np.inf, -0.30], index=ix)
idx = ix[[0, 1, 2, 3, 4, 5, 6]]                           # 第 7 筆不是事件
old = (dd.reindex(idx) <= CUT).dropna().mean() * 100      # 舊:2/7 = 28.6%
r = qm_risk_summary(dd, idx)
check("舊算法把未完成當沒跌(2/7)", abs(old - 200 / 7) < 1e-9)
check("新算法 risk = 2/4 = 50%", abs(r["risk"] - 50.0) < 1e-9)
check("risk_n = 4(NaN、inf 都不算)", r["risk_n"] == 4)
check("risk_n + risk_missing_n = 事件數", r["risk_n"] + r["risk_missing_n"] == len(idx))

# ---- 2. 事件不在 dd 的索引裡 → 算未完成,不是沒跌
idx2 = pd.MultiIndex.from_tuples([(0, "A"), (99, "A")])
r2 = qm_risk_summary(dd, idx2)
check("索引外的事件算未完成", r2["risk_n"] == 1 and r2["risk_missing_n"] == 1 and r2["risk"] == 100.0)

# ---- 3. 沒有任何完整事件 → NaN(不是 0%)
r3 = qm_risk_summary(dd, pd.MultiIndex.from_tuples([(3, "A"), (4, "A")]))
check("全部未完成 → risk 是 NaN", np.isnan(r3["risk"]) and r3["risk_n"] == 0 and r3["risk_missing_n"] == 2)

# ---- 4. 同波動對照:對照組只用完整的日子;事件只取有波動分組且完整的
ix4 = pd.MultiIndex.from_tuples([(d, t) for d in range(6) for t in ("A", "B")])
dd4 = pd.Series([-0.2, -0.01, -0.2, -0.01, np.nan, -0.01, -0.2, np.nan, -0.01, -0.01, -0.2, -0.2], index=ix4)
vq4 = pd.Series([0.95, 0.95, 0.95, 0.95, 0.95, 0.15, 0.15, 0.15, 0.15, 0.15, np.nan, 0.95], index=ix4)
ev4 = ix4[[0, 4, 6, 7, 10]]          # (0,A) 完整高波動、(2,A) 未完成、(3,A) 低波動完整、(3,B) 未完成、(5,A) 無波動分組
r4 = qm_risk_summary(dd4, ev4, vq4)
hi = dd4[(vq4 >= 0.9)].dropna(); lo = dd4[(vq4 < 0.9) & vq4.notna()].dropna()
base_hi = (hi <= CUT).mean(); base_lo = (lo <= CUT).mean()
check("配對事件 = 2(排除未完成、無波動分組)", r4["risk_matched_n"] == 2)
check("配對風險 = 2/2 = 100%", abs(r4["risk_matched"] - 100.0) < 1e-9)
check("對照 = 兩個分組完整日子比例的平均", abs(r4["risk_base"] - (base_hi + base_lo) / 2 * 100) < 1e-9)
check("risk(不配對)用 3 個完整事件", r4["risk_n"] == 3 and r4["risk_missing_n"] == 2)

# ---- 5. 真實面板:資料尾端 40 天還沒走完的事件,舊算法算成「沒跌」;新算法排除
def old_eval_risk(sig, side, a, b, entry):
    pm = _pm(a, b); m = sig.loc[pm, cols].fillna(False).astype(bool); idx = m.stack(); idx = idx[idx].index
    dd = _stk((MAE if entry == "open" else MAEC)[40], pm, cols)
    return (dd.reindex(idx) <= CUT).dropna().mean() * 100, len(idx)
for nm, sig, side, entry in (("頂K", topk(), "top", "close"), ("出", chu(), "top", "open")):
    for per in (("2009-07-01", "2017-12-31"), ("2018-01-01", "2026-12-31")):
        r = evaluate(sig, side, per, 40, entry=entry)
        o, n = old_eval_risk(sig, side, *per, entry)
        print(f"  {nm} {per[0][:4]}–{per[1][:4]}:事件 {n}、完整 {r['risk_n']}、未完成 {r['risk_missing_n']} | 舊 {o:.2f}% → 新 {r['risk']:.2f}%")
        check(f"{nm} {per[0][:4]} n 加總", r["risk_n"] + r["risk_missing_n"] == n)
        if r["risk_missing_n"] == 0: check(f"{nm} {per[0][:4]} 沒有未完成 → 新舊一樣", abs(o - r["risk"]) < 1e-9)
        else: check(f"{nm} {per[0][:4]} 有未完成 → 新 ≥ 舊", r["risk"] >= o - 1e-9)
print("ALL PASS" if ok_all else "SOME FAILED")
