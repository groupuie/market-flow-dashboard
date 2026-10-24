#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""13F 資料層 DL1 步驟 b:每個資料集的 INFOTABLE 依(申報、CUSIP、PUT/CALL、股 / 債)加總,存 parquet;另存每份申報的列數與金額合計(和 SUMMARYPAGE 對)。
金額維持申報單位(之後依申報日換算)。用法:python3 -I b_infotable.py SCRATCH"""
import os, sys, glob, zipfile, time, duckdb
S = sys.argv[1]; Z = os.path.join(S, "f13", "zips"); H = os.path.join(S, "f13", "hold"); T = os.path.join(S, "f13", "tmp")
con = duckdb.connect(); con.execute("SET memory_limit='4GB'; SET threads=2")
for zp in sorted(glob.glob(os.path.join(Z, "*.zip"))):
    tag = os.path.basename(zp).replace("_form13f.zip", ""); out = os.path.join(H, f"hold__{tag}.parquet"); out2 = os.path.join(H, f"acc__{tag}.parquet")
    if os.path.exists(out) and os.path.exists(out2):
        continue
    t0 = time.time(); z = zipfile.ZipFile(zp); mem = [n for n in z.namelist() if os.path.basename(n) == "INFOTABLE.tsv"][0]
    tsv = os.path.join(T, "INFOTABLE.tsv")
    with z.open(mem) as src, open(tsv, "wb") as dst:
        while True:
            b = src.read(1 << 24)
            if not b:
                break
            dst.write(b)
    src_sql = f"read_csv('{tsv}', delim='\t', header=true, all_varchar=true, quote='', escape='', null_padding=true, ignore_errors=false)"
    con.execute(f"""COPY (SELECT ACCESSION_NUMBER AS acc, upper(trim(CUSIP)) AS cusip, coalesce(upper(trim(PUTCALL)), '') AS putcall, upper(trim(SSHPRNAMTTYPE)) AS typ,
          sum(TRY_CAST(VALUE AS DOUBLE)) AS value_raw, sum(TRY_CAST(SSHPRNAMT AS DOUBLE)) AS shares, count(*) AS nrows,
          sum(CASE WHEN TRY_CAST(VALUE AS DOUBLE) IS NULL THEN 1 ELSE 0 END) AS bad_value, sum(CASE WHEN TRY_CAST(SSHPRNAMT AS DOUBLE) IS NULL THEN 1 ELSE 0 END) AS bad_shares,
          min(NAMEOFISSUER) AS name, min(TITLEOFCLASS) AS cls
        FROM {src_sql} GROUP BY 1, 2, 3, 4) TO '{out}' (FORMAT parquet, COMPRESSION zstd)""")
    con.execute(f"""COPY (SELECT ACCESSION_NUMBER AS acc, count(*) AS nrows, sum(TRY_CAST(VALUE AS DOUBLE)) AS value_raw FROM {src_sql} GROUP BY 1) TO '{out2}' (FORMAT parquet)""")
    os.remove(tsv)
    n = con.execute(f"SELECT count(*), sum(nrows) FROM '{out}'").fetchone()
    print(f"ok {tag} 彙總列 {n[0]} 原始列 {n[1]} {time.time() - t0:.0f}s", flush=True)
print("done", flush=True)
