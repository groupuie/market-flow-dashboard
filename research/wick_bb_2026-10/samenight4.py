# 為什麼「賣對的機率 > 一半」但平均卻≈打平?看 40 日後的分布(中位數 vs 平均、兩邊尾巴)
import numpy as np, pandas as pd, pickle, warnings; warnings.filterwarnings("ignore")
exec(open("samenight.py").read().split("PER={")[0])
sigA = touch & hot & (offhi >= 0.05)
C1 = C.shift(-1)
ALL = list(C.columns); AIc = [c for c in ALL if c in AI]
for lab, cols in (("全部", ALL), ("AI股", AIc)):
    for a, b in (("2009-01-01", "2016-12-31"), ("2017-01-01", "2026-12-31")):
        pm = (dates >= a) & (dates <= b)
        ix = sigA.loc[pm, cols].stack(); ix = ix[ix == True].index
        st = lambda X: X.loc[pm, cols].stack().reindex(ix)
        cf = st(conf).fillna(False).astype(bool)
        e = st(C.shift(-40))
        for nm, P, m in (("A 當晚收盤賣", st(C), pd.Series(True, index=ix)), ("B 等確認(只算有賣的)", st(C1), cf)):
            r = (e / P - 1)[m].dropna()          # 賣掉之後 40 日股價變化(正 = 賣早了)
            print(f"{lab} {a[:4]}–{b[:4]} {nm:14s} n={len(r):4d} | 40日後比賣價低 {(r<0).mean()*100:3.0f}% | "
                  f"中位 {-r.median()*100:+5.1f}% 平均 {-r.mean()*100:+5.1f}%(正=賣得好) | 之後再漲≥20% {(r>=0.2).mean()*100:3.0f}% · ≥40% {(r>=0.4).mean()*100:3.0f}% | 再跌≥20% {(r<=-0.2).mean()*100:3.0f}%")
