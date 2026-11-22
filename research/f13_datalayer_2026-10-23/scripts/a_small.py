#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""13F 資料層 DL1 步驟 a:從 54 個 SEC Form 13F Data Sets 抽出 SUBMISSION / COVERPAGE / SUMMARYPAGE / OTHERMANAGER2,合併成 parquet。
用法:python3 -I a_small.py SCRATCH(zip 在 SCRATCH/f13/zips/,先跑 dl_zips.sh)"""
import os, sys, glob, zipfile, duckdb
S = sys.argv[1]; Z = os.path.join(S, "f13", "zips"); O = os.path.join(S, "f13", "small")
tabs = ("SUBMISSION", "COVERPAGE", "SUMMARYPAGE", "OTHERMANAGER2")
for zp in sorted(glob.glob(os.path.join(Z, "*.zip"))):
    tag = os.path.basename(zp).replace("_form13f.zip", "")
    z = zipfile.ZipFile(zp)
    for t in tabs:
        out = os.path.join(O, f"{t}__{tag}.tsv")
        if not os.path.exists(out):
            mem = [n for n in z.namelist() if os.path.basename(n) == f"{t}.tsv"]; assert len(mem) == 1, (zp, t)
            open(out, "wb").write(z.read(mem[0]))
con = duckdb.connect()
for t in tabs:
    con.execute(f"""CREATE TABLE {t} AS SELECT *, regexp_extract(filename, '__(.*)\\.tsv$', 1) AS dataset
        FROM read_csv('{O}/{t}__*.tsv', delim='\t', header=true, all_varchar=true, quote='', escape='', filename=true, ignore_errors=false)""")
    print(t, con.execute(f"SELECT count(*) FROM {t}").fetchone()[0])
con.execute(f"COPY SUBMISSION TO '{O}/SUBMISSION_all.parquet' (FORMAT parquet)")
con.execute(f"COPY COVERPAGE TO '{O}/COVERPAGE_all.parquet' (FORMAT parquet)")
con.execute(f"COPY SUMMARYPAGE TO '{O}/SUMMARYPAGE_all.parquet' (FORMAT parquet)")
con.execute(f"COPY OTHERMANAGER2 TO '{O}/OTHERMANAGER2_all.parquet' (FORMAT parquet)")
print(con.execute("""SELECT dataset, min(strptime(FILING_DATE,'%d-%b-%Y'))::DATE mn, max(strptime(FILING_DATE,'%d-%b-%Y'))::DATE mx, count(*) n
    FROM SUBMISSION GROUP BY dataset ORDER BY mn""").fetchall())
print(con.execute("SELECT SUBMISSIONTYPE, count(*) FROM SUBMISSION GROUP BY 1 ORDER BY 2 DESC").fetchall())
