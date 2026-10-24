# 獨立重算:某幾個月的 IC_3m(G) 與 H2 差,和 em1_monthly{_synthetic}.csv 比(第 2 個參數 syn / real)
import sys, zipfile, numpy as np, pandas as pd
from scipy.stats import spearmanr
S, mode = sys.argv[1], sys.argv[2]
z = zipfile.ZipFile(S + "/sr/raw/49_Industry_Portfolios_CSV.zip"); lines = z.read(z.namelist()[0]).decode("latin-1").splitlines()
i = next(k for k, l in enumerate(lines) if l.strip().startswith("Average Value Weighted Returns -- Monthly"))
hdr = [c.strip() for c in lines[i + 1].split(",")[1:]]; rows = []
for l in lines[i + 2:]:
    p = [x.strip() for x in l.split(",")]
    if not (p[0].isdigit() and len(p[0]) == 6): break
    rows.append(p)
R = pd.DataFrame([[float(x) for x in r[1:]] for r in rows], index=pd.PeriodIndex([f"{r[0][:4]}-{r[0][4:]}" for r in rows], freq="M"), columns=hdr)
R = R.mask(R <= -99.99) / 100; R = R[R.index <= pd.Period("2026-06", "M")]
if mode == "syn":
    rng = np.random.default_rng(7 + 49); R = pd.DataFrame(rng.normal(0.009, 0.055, R.shape), index=R.index, columns=R.columns).where(R.notna())
sig = pd.read_csv(S + "/ern/out/em1_signals.csv"); mon = pd.read_csv(S + f"/ern/out/em1_monthly{'_synthetic' if mode == 'syn' else ''}.csv")
for t in ("2011-02", "2016-08", "2023-11"):
    tp = pd.Period(t, "M"); g = sig[(sig.t == t)].set_index("ff")["G"].dropna()
    f3 = (1 + R.loc[tp + 1:tp + 3]).prod() - 1; s0 = (1 + R.loc[tp - 11:tp - 1]).prod() - 1
    ks = [k for k in g.index if not np.isnan(f3[k]) and not np.isnan(s0[k])]
    ic = spearmanr(g[ks], f3[ks]).correlation
    fused = pd.Series(s0[ks]).rank().values + pd.Series(g[ks]).rank().values
    h2 = spearmanr(fused, f3[ks]).correlation - spearmanr(s0[ks], f3[ks]).correlation
    r = mon[mon.t == t].iloc[0]
    print(t, "n", len(ks), "IC3 重算 %.6f 程式 %.6f | H2 重算 %.6f 程式 %.6f" % (ic, r.IC3_G, h2, r.H2_diff))
