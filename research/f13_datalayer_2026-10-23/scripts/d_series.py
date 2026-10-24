#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""13F 資料層 DL1 步驟 d:相鄰兩季(D46 快照)的三條序列(DL1_SPEC.md §5),先只到 CUSIP 層級;拆股 / 合併判定;品質報告。
不碰任何報酬或預測。用法:python3 -I d_series.py SCRATCH → SCRATCH/f13/series/flow__{P}.parquet、SCRATCH/f13/out/dl1_series_quality.json"""
import os, sys, json, glob
import duckdb

S = sys.argv[1]; F = os.path.join(S, "f13"); SN, SE, OUT = (os.path.join(F, x) for x in ("snap", "series", "out"))
os.makedirs(SE, exist_ok=True)
con = duckdb.connect(); con.execute("SET memory_limit='5GB'; SET threads=2; SET preserve_insertion_order=false")
CAND = [2, 3, 4, 5, 6, 8, 10, 15, 20, 25, 30, 40, 50, 100, 1.5]
CAND = sorted(set(CAND + [1 / c for c in CAND]))
con.execute("CREATE TABLE cand AS SELECT unnest(?) AS k", [CAND])
snaps = sorted(glob.glob(os.path.join(SN, "snap_D46__*.parquet")))
periods = [os.path.basename(p)[len("snap_D46__"):-len(".parquet")] for p in snaps]
CLEAN = "typ = 'SH' AND putcall = '' AND shares > 0 AND value_fixed > 0 AND NOT coalesce(price_outlier, false)"
Q = {}
for a, b in zip(periods[:-1], periods[1:]):
    con.execute(f"CREATE OR REPLACE TEMP TABLE s0 AS SELECT cik, cusip, sum(shares) sh, sum(value_fixed) v, min(name) name FROM '{SN}/snap_D46__{a}.parquet' WHERE {CLEAN} GROUP BY 1, 2")
    con.execute(f"CREATE OR REPLACE TEMP TABLE s1 AS SELECT cik, cusip, sum(shares) sh, sum(value_fixed) v, min(name) name FROM '{SN}/snap_D46__{b}.parquet' WHERE {CLEAN} GROUP BY 1, 2")
    con.execute(f"CREATE OR REPLACE TEMP TABLE c0 AS SELECT DISTINCT cik FROM '{SN}/snap_D46__{a}.parquet'")
    con.execute(f"CREATE OR REPLACE TEMP TABLE c1 AS SELECT DISTINCT cik FROM '{SN}/snap_D46__{b}.parquet'")
    con.execute("CREATE OR REPLACE TEMP TABLE both_ciks AS SELECT cik FROM c0 INTERSECT SELECT cik FROM c1")
    # 參考價(同季同 CUSIP 申報人隱含價格中位數,≥ 3 家)
    con.execute("CREATE OR REPLACE TEMP TABLE r0 AS SELECT cusip, median(v / sh) p, count(*) n FROM s0 GROUP BY 1 HAVING count(*) >= 3")
    con.execute("CREATE OR REPLACE TEMP TABLE r1 AS SELECT cusip, median(v / sh) p, count(*) n FROM s1 GROUP BY 1 HAVING count(*) >= 3")
    # 拆股 / 合併:價格比與「兩季都持有」的股數比都接近同一個常見比例
    # v4(歷程:v1 要求價格比也接近 k → NVDA / AAPL / GOOGL 判不出;v2 股數比中位數 ±2% → AAPL 2020 中位數 3.91 判不出;
    #        v3 股數比剛好 = k(±0.2%)的家數 ≥ 10% → 大型股大家都有小幅進出,NVDA 只有 7.5% 剛好 10 倍,又判不出)
    # 現在:兩季都持有的申報人中,股數比落在 k ±5% 的家數 nb、落在 1 ±5% 的家數 n1;nb ≥ 5、nb ≥ 20% × 兩季都持有家數、nb > 3 × n1(k = 1.5 或 2/3 要 > 5 × n1),
    #        而且拆股調整後價格變化在 −60% ~ +150% → 判定拆股 / 合併
    con.execute("CREATE OR REPLACE TEMP TABLE cand1 AS SELECT k FROM cand UNION ALL SELECT 1.0")
    con.execute("""CREATE OR REPLACE TEMP TABLE rat AS SELECT s0.cusip, s1.sh / s0.sh r FROM s0 JOIN s1 USING (cik, cusip) WHERE s0.cik IN (SELECT cik FROM both_ciks)""")
    con.execute("""CREATE OR REPLACE TEMP TABLE cont AS SELECT cusip, median(r) mr, count(*) ncont FROM rat GROUP BY 1""")
    con.execute("""CREATE OR REPLACE TEMP TABLE kc AS SELECT rat.cusip, cand1.k, count(*) n FROM rat JOIN cand1 ON abs(rat.r / cand1.k - 1) <= 0.05 GROUP BY 1, 2""")
    con.execute("""CREATE OR REPLACE TEMP TABLE kbest AS SELECT cusip, arg_max(k, n) kb, max(n) nb FROM kc WHERE k <> 1.0 GROUP BY 1""")
    con.execute("""CREATE OR REPLACE TEMP TABLE px AS SELECT r0.cusip, r0.p p0, r1.p p1, r0.p / r1.p kp, cont.mr, cont.ncont, kbest.kb, kbest.nb, coalesce(k1.n, 0) n1
                   FROM r0 JOIN r1 USING (cusip) LEFT JOIN cont USING (cusip) LEFT JOIN kbest USING (cusip) LEFT JOIN (SELECT cusip, n FROM kc WHERE k = 1.0) k1 USING (cusip)""")
    con.execute("""CREATE OR REPLACE TEMP TABLE sp AS SELECT px.*,
            CASE WHEN kb IS NOT NULL AND nb >= 5 AND nb >= 0.2 * ncont AND nb > (CASE WHEN abs(kb - 1.5) < 1e-9 OR abs(kb - 1 / 1.5) < 1e-9 THEN 5 ELSE 3 END) * n1
                      AND kp / kb BETWEEN 0.4 AND 2.5 THEN kb END ksplit FROM px""")
    con.execute("""CREATE OR REPLACE TEMP TABLE sp2 AS SELECT *, coalesce(ksplit, 1.0) k,
            (ksplit IS NULL AND ncont >= 5 AND abs(mr - 1) > 0.2) unresolved,
            (ksplit IS NULL AND coalesce(ncont, 0) < 5 AND (kp > 1.8 OR kp < 0.55)) thin_jump FROM sp""")
    # (a)(b):兩季都有快照的申報人;拆股調整;新建倉 / 出清
    con.execute("""CREATE OR REPLACE TEMP TABLE pos AS
        SELECT coalesce(s1.cik, s0.cik) cik, coalesce(s1.cusip, s0.cusip) cusip, coalesce(s0.sh, 0) sh0, coalesce(s1.sh, 0) sh1, coalesce(s0.v, 0) v0, coalesce(s1.v, 0) v1,
               coalesce(s1.name, s0.name) name
        FROM s0 FULL OUTER JOIN s1 USING (cik, cusip)
        WHERE coalesce(s1.cik, s0.cik) IN (SELECT cik FROM both_ciks)""")
    con.execute("""CREATE OR REPLACE TEMP TABLE pos2 AS SELECT pos.*, coalesce(sp2.k, 1.0) k, sp2.p0, sp2.p1, coalesce(sp2.unresolved, false) unresolved, coalesce(sp2.thin_jump, false) thin_jump,
            pos.sh1 - pos.sh0 * coalesce(sp2.k, 1.0) dsh,
            (pos.sh1 - pos.sh0 * coalesce(sp2.k, 1.0)) * (sp2.p0 / coalesce(sp2.k, 1.0)) flow_fixed
        FROM pos LEFT JOIN sp2 USING (cusip)""")
    # (c) 配置:每個申報人可見長倉的占比;扣掉價格漂移
    con.execute("""CREATE OR REPLACE TEMP TABLE tot AS SELECT cik, sum(v0) t0, sum(v1) t1 FROM pos2 GROUP BY 1""")
    con.execute("""CREATE OR REPLACE TEMP TABLE al AS SELECT pos2.*, CASE WHEN t0 > 0 THEN v0 / t0 ELSE 0 END w0, CASE WHEN t1 > 0 THEN v1 / t1 ELSE 0 END w1,
            CASE WHEN p0 IS NOT NULL AND p1 IS NOT NULL THEN p1 / (p0 / k) ELSE 1.0 END gr FROM pos2 JOIN tot USING (cik)""")
    con.execute("""CREATE OR REPLACE TEMP TABLE al2 AS SELECT al.*, w1 - (w0 * gr) / nullif(sum(w0 * gr) OVER (PARTITION BY cik), 0) dalloc FROM al""")
    con.execute(f"""COPY (SELECT cusip, mode(name) name, any_value(p0) p0, any_value(p1) p1, any_value(k) split_k, bool_or(unresolved) unresolved, bool_or(thin_jump) thin_jump,
            sum(CASE WHEN sh0 > 0 THEN 1 ELSE 0 END) n_prev, sum(CASE WHEN sh1 > 0 THEN 1 ELSE 0 END) n_now,
            sum(CASE WHEN sh0 > 0 AND sh1 > 0 THEN 1 ELSE 0 END) n_cont, sum(CASE WHEN sh0 = 0 AND sh1 > 0 THEN 1 ELSE 0 END) n_new, sum(CASE WHEN sh0 > 0 AND sh1 = 0 THEN 1 ELSE 0 END) n_exit,
            sum(sh0 * k) sh_prev_adj, sum(sh1) sh_now, sum(dsh) dshares, sum(flow_fixed) flow_fixed_usd, sum(v1) value_now, sum(v0) value_prev,
            (sum(CASE WHEN dsh > 0 THEN 1 ELSE 0 END) - sum(CASE WHEN dsh < 0 THEN 1 ELSE 0 END)) / nullif(count(*), 0) breadth,
            avg(dalloc) mean_dalloc, sum(dalloc * t1) dalloc_usd
        FROM al2 JOIN tot USING (cik) GROUP BY 1) TO '{SE}/flow__{b}.parquet' (FORMAT parquet, COMPRESSION zstd)""")
    st = con.execute(f"""SELECT count(*), sum(CASE WHEN split_k <> 1 THEN 1 ELSE 0 END), sum(CASE WHEN unresolved THEN 1 ELSE 0 END),
            sum(CASE WHEN unresolved THEN value_now ELSE 0 END) / sum(value_now), sum(CASE WHEN p0 IS NULL OR p1 IS NULL THEN value_now ELSE 0 END) / sum(value_now),
            sum(CASE WHEN thin_jump THEN 1 ELSE 0 END),
            sum(flow_fixed_usd) / 1e9, sum(value_now) / 1e9 FROM '{SE}/flow__{b}.parquet'""").fetchone()
    nb = con.execute("SELECT (SELECT count(*) FROM both_ciks), (SELECT count(*) FROM c0), (SELECT count(*) FROM c1)").fetchone()
    Q[f"{a} → {b}"] = {"兩季都有的申報人": nb[0], "前一季申報人": nb[1], "這一季申報人": nb[2], "CUSIP 數": st[0], "判定拆股 / 合併": st[1],
                       "股數比偏離 1 超過 20% 但判斷不了": st[2], "判斷不了的市值占比%": round(100 * (st[3] or 0), 3), "沒有參考價的市值占比%": round(100 * (st[4] or 0), 2),
                       "持有家數少、價格大跳(< 5 家)": st[5], "固定價格持有量變化合計(十億美元)": round(st[6] or 0, 1), "這一季市值(十億美元,兩季都有的申報人、乾淨持股)": round(st[7] or 0, 1)}
    print(a, "→", b, Q[f"{a} → {b}"], flush=True)
json.dump(Q, open(os.path.join(OUT, "dl1_series_quality.json"), "w"), ensure_ascii=False, indent=1)
