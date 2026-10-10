# t25(Codex v0.1 修正 D):「40 天內曾跌 ≥10%」舊算法 vs 新算法,上線的 6 種記號 × 4 個期間。
#   舊:(dd.reindex(事件) <= log 0.9).dropna() → 40 天還沒走完的事件被當成「沒跌」(低估)。
#   新:qlib.qm_risk_summary → 只用 40 天已走完的事件;列出有效 n 與未完成 n。
#   進場價:頂K/減碼/熱 = 當天收盤;出/抄底/加 = 隔天開盤(與上線說明一致)。資料到 2026-10-09。
from t23_dip import *                 # HOT(熱)、UTS、qdip、R14、lo、above_n、first、X(出)
from t10lib import _pm
from qlib import qm_risk_summary, _stk, MAE, MAEC, VQ, topk, confirm, chaodi
CUT = np.log(0.9)
TKs = topk(); CFs = confirm(TKs); CHD = chaodi()
rsi40 = (R14 <= 40) & (R14.shift(1) > 40); lob = (L <= lo) & above_n(L, lo, 10)
recentCHU = X.fillna(False).astype(bool).astype(int).rolling(11, min_periods=1).max().astype(bool)   # 修正 B 之後
ADD = first((rsi40 | lob) & UTS & qdip & ~recentCHU, 10)
SIGS = [("頂K", TKs, "top", "close"), ("減碼", CFs, "top", "close"), ("熱", HOT, "top", "close"),
        ("出", X, "top", "open"), ("抄底", CHD, "bot", "open"), ("加", ADD, "bot", "open")]
PER = [("2009–17", ("2009-07-01", "2017-12-31")), ("2018–26", ("2018-01-01", "2026-12-31")),
       ("近兩年", ("2024-10-01", "2026-12-31")), ("全期", ("2009-07-01", "2026-12-31"))]
print("### 40 天內曾跌 ≥10%:舊 → 新(有效 n / 未完成 n);賣出側另列同波動平常日子(新)")
print("| 記號 | 期間 | 進場 | 事件 | 有效 n | 未完成 n | 舊 | 新 | 差 | 同波動平常(舊→新) |")
print("|---|---|---|---|---|---|---|---|---|---|")
for nm, sig, side, entry in SIGS:
    for per, (a, b) in PER:
        pm = _pm(a, b); m = sig.reindex(index=dates, columns=cols).loc[pm].fillna(False).astype(bool)
        idx = m.stack(); idx = idx[idx].index
        dd = _stk((MAE if entry == "open" else MAEC)[40], pm, cols)
        old = (dd.reindex(idx) <= CUT).dropna().mean() * 100
        vq = _stk(VQ, pm, cols) if side == "top" else None
        r = qm_risk_summary(dd, idx, vq)
        base = ""
        if vq is not None:
            vqo = vq.dropna(); bins = (vqo * 10).clip(0, 9.999).astype(int); ddn = dd.dropna()
            tab = (ddn <= CUT).groupby(bins.reindex(ddn.index)).mean(); eb = bins.reindex(idx).dropna().astype(int)
            base = f"{tab.reindex(eb.values).mean()*100:.1f}% → {r['risk_base']:.1f}%"
        print(f"| {nm} | {per} | {'收盤' if entry=='close' else '隔天開盤'} | {len(idx)} | {r['risk_n']} | {r['risk_missing_n']} | "
              f"{old:.1f}% | {r['risk']:.1f}% | {r['risk']-old:+.1f} | {base or '—'} |", flush=True)
# 全面板:40 天報酬已完整、但 40 天最低價還不完整的股票日(檢查 wick_trim2 這類「先用報酬篩、再算最低價」的寫法會不會受影響)
fr40 = FR[40].values; mae40 = MAE[40].values
print(f"\n隔天開盤 40 天報酬完整、但 40 天最低價不完整的股票日:{int((~np.isnan(fr40) & np.isnan(mae40)).sum())}")
