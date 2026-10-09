# 「當晚就賣」的幾種做法,同一把尺比較(都與「不賣、續抱到第 h 日」相比;正 = 賣得比較好)
#   A 收盤賣   :漲多 + 碰上軌 + 收盤離當日高點 ≥5% → 當天收盤賣
#   I 盤中賣   :昨收已漲多 + 今天碰上軌 + 盤中從今日高點回落 5% → 在「今日高點×0.95」賣
#               (日K看不到先高後低還是先低後高,一律當作先高後低 → 次數是上限)
#   B 等確認   :A 的那根K,隔天收盤跌破它的最低價才在隔天收盤賣;沒跌破就不賣(=續抱)
#   M 一半一半 :A 賣一半、剩下一半照 B
import numpy as np, pandas as pd, pickle, warnings; warnings.filterwarnings("ignore")
exec(open("samenight.py").read().split("PER={")[0])
dix = pd.Series(np.arange(len(dates)), index=dates)
hot_prev = hot.shift(1).fillna(False).astype(bool)
sigA = touch & hot & (offhi >= 0.05)
sigI = touch & hot_prev & (L <= H * 0.95)
sigR = sigI & (C > H * 0.95)                      # 盤中跌 5% 但收盤又拉回(A 不會賣、I 會賣)
pxI = H * 0.95
succA = ((futH <= H * 1.02) & (futL <= C * 0.92))
succI = ((futH <= H * 1.02) & (futL <= pxI * 0.92))
succB = succ_next.astype(bool)
C1 = C.shift(-1)

def boot(vals, d, reps=800):
    blk = dix.reindex(d).values // 20
    g = pd.DataFrame({"b": blk, "v": vals}).dropna().groupby("b").v.agg(["sum", "count"])
    r = np.random.default_rng(0); bs = []
    for _ in range(reps):
        ii = r.integers(0, len(g), len(g)); bs.append(g["sum"].values[ii].sum() / g["count"].values[ii].sum())
    return np.percentile(bs, [5, 95]) * 100

def run(label, cols, a, b, extra=None):
    pm = (dates >= a) & (dates <= b)
    sd = C.loc[pm, cols].notna().values.sum() / 252          # 檔·年
    out = [f"\n== {label} {a[:4]}–{b[:4]} =="]
    for nm, sig, px, succ in (("A 收盤賣", sigA, C, succA), ("I 盤中賣", sigI, pxI, succI), ("I' 其中收盤拉回的日子", sigR, pxI, succI)):
        s = sig if extra is None else (sig & extra)
        ix = s.loc[pm, cols].stack(); ix = ix[ix == True].index
        st = lambda X: X.loc[pm, cols].stack().reindex(ix)
        P = st(px); n = len(ix)
        top = st(succ.astype(float).where(futH.notna())).mean() * 100
        gap10 = np.median(np.log(st(maxc10) / P).dropna()) * 100
        line = f"{nm:16s} n={n:5d} 每檔每年{n/sd:4.2f}次 | 賣在頂 {top:4.1f}% | 賣價比近10日最高收盤低 {gap10:4.1f}%"
        for h in (20, 40):
            e = st(C.shift(-h)); ben = np.log(P / e); ok = ben.notna()
            lo, hi = boot(ben[ok].values, ix[ok.values].get_level_values(0))
            line += f" | {h}日 賣得好{(ben[ok] >= np.log(1/0.9)).mean()*100:3.0f}% 賣早{(ben[ok] <= np.log(1/1.1)).mean()*100:3.0f}% 平均{ben[ok].mean()*100:+5.1f}% [{lo:+.1f},{hi:+.1f}]"
        if nm.startswith("A"):
            cf = st(conf).fillna(False).astype(bool)
            impr = np.log((H * 0.95) / C); im = st(impr).mean() * 100
            line += f"\n{'':16s} 隔天確認 {cf.mean()*100:.0f}% | 同一批K若在「高點×0.95」盤中賣,賣價平均比收盤高 {im:.1f}%"
            # B 與 M
            topB = st(succB.astype(float)).where(cf).mean() * 100
            gapB = np.median(np.log(st(maxc10) / st(C1))[cf].dropna()) * 100
            lineB = f"{'B 等隔天確認':14s} n={int(cf.sum()):5d} 每檔每年{cf.sum()/sd:4.2f}次 | 賣在頂 {topB:4.1f}%(只算有確認的) | 賣價比近10日最高收盤低 {gapB:4.1f}%"
            lineM = f"{'M 一半一半':15s}"
            for h in (20, 40):
                e = st(C.shift(-h)); bA = np.log(st(C) / e); bB = np.log(st(C1) / e).where(cf, 0.0)
                ok = bA.notna() & bB.notna()
                lo, hi = boot(bB[ok].values, ix[ok.values].get_level_values(0))
                lineB += f" | {h}日 平均(含沒確認=0){bB[ok].mean()*100:+5.1f}% [{lo:+.1f},{hi:+.1f}]"
                bM = 0.5 * bA + 0.5 * bB
                lo, hi = boot(bM[ok].values, ix[ok.values].get_level_values(0))
                lineM += f" | {h}日 平均{bM[ok].mean()*100:+5.1f}% [{lo:+.1f},{hi:+.1f}]"
            line += "\n" + lineB + "\n" + lineM
        out.append(line)
    print("\n".join(out), flush=True)

ALL = list(C.columns); AIc = [c for c in ALL if c in AI]
for a, b in (("2009-01-01", "2016-12-31"), ("2017-01-01", "2026-12-31")):
    run("全部", ALL, a, b)
    run("氣候≤35%", ALL, a, b, clim <= 0.35)
    run("氣候>35%", ALL, a, b, clim > 0.35)
    run("AI股", AIc, a, b)
