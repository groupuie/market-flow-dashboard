# s3:成本調節口徑 —— 頂賣一部分 → 下一個底買回(買得比較便宜嗎?);底買 → 下一個頂賣(賣得比較貴嗎?)
#   價格 = 訊號隔天開盤;下一個反向記號要在 40 根內出現,否則記「沒等到」。只描述。
import numpy as np, pandas as pd, json, os, warnings; warnings.filterwarnings("ignore")
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "s1_candidates.py"), encoding="utf-8").read().split("CAND = {")[0]
exec(src)
BOT = cool(lastk(osold10 | belowLB | td9b) & revUp & ~np.isnan(Cv), 5)
TOP = cool(lastk(obought90 | aboveUB | td9s) & revDn & ~np.isnan(Cv), 5)
nxtO = np.roll(Ov, -1, axis=0); nxtO[-1] = np.nan
def rt(A, Bm, side):
    rows = []
    for j in range(m):
        ia = np.flatnonzero(A[:, j] & per); ib = np.flatnonzero(Bm[:, j])
        for i in ia:
            k = ib[np.searchsorted(ib, i, side="right")] if np.searchsorted(ib, i, side="right") < len(ib) else None
            if k is None or k - i > 40 or np.isnan(nxtO[i, j]) or np.isnan(nxtO[k, j]): rows.append((j, i, None, None)); continue
            r = nxtO[k, j] / nxtO[i, j] - 1
            rows.append((j, i, k - i, r))
    return rows
def summ(rows, gm, side):
    gs = set(np.flatnonzero(gm)); R = [r for r in rows if r[0] in gs]
    got = [r for r in R if r[3] is not None]
    if not got: return None
    rr = np.array([r[3] for r in got]); dd = np.array([r[2] for r in got])
    good = (rr < 0) if side == "頂→底" else (rr > 0)
    h2 = np.array([dates[r[1]] >= pd.Timestamp(MID) for r in got])
    return {"n": len(R), "等到": len(got), "成功%": round(good.mean() * 100, 1), "前段%": round(good[~h2].mean() * 100, 1) if (~h2).any() else None,
            "後段%": round(good[h2].mean() * 100, 1) if h2.any() else None, "平均差%": round(rr.mean() * 100, 2), "中位天數": int(np.median(dd))}
out = {}
for side, A, Bm in (("頂→底", TOP, BOT), ("底→頂", BOT, TOP)):
    rows = rt(A, Bm, side); out[side] = {}
    for g, gm in groups.items():
        s = summ(rows, np.array(gm), side); out[side][g] = s
        print(side, g, s)
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "s3_roundtrip.json"), "w"), ensure_ascii=False, indent=1)
# 基準:任何一天買(或賣)→ 下一個反向記號;和記號比
ANY = (~np.isnan(Cv)) & per[:, None]
print("--- 基準:任何一天進場 ---")
for side, A, Bm in (("任一天→底(頂賣的對照)", ANY, BOT), ("任一天→頂(底買的對照)", ANY, TOP)):
    rows = rt(A, Bm, "頂→底" if "→底" in side else "底→頂"); out["base_" + side] = {}
    for g, gm in groups.items():
        s = summ(rows, np.array(gm), "頂→底" if "→底" in side else "底→頂"); out["base_" + side][g] = s
        print(side, g, s)
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "s3_roundtrip.json"), "w"), ensure_ascii=False, indent=1)
