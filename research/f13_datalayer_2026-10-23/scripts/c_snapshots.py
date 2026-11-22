#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""13F 資料層 DL1 步驟 c:申報分類、版本解析、每季 D46 / D180 快照(持股換成美元)、品質報告。規則見 DL1_SPEC.md §2–§4、§6。
用法:python3 -I c_snapshots.py SCRATCH  → SCRATCH/f13/snap/snap_D46__{季}.parquet、SCRATCH/f13/out/dl1_quality.json"""
import os, sys, json, glob, datetime as dt
import duckdb, pandas as pd

S = sys.argv[1]; F = os.path.join(S, "f13"); SM, HO, SN, OUT = (os.path.join(F, x) for x in ("small", "hold", "snap", "out"))
os.makedirs(SN, exist_ok=True); os.makedirs(OUT, exist_ok=True)
DATA_END = dt.date(2026, 8, 31)


def fed_holidays(y):
    """美國聯邦假日(含週末遞補):只用來把 45 天期限順延到下一個營業日"""
    def nth(month, wd, n):
        d = dt.date(y, month, 1); k = 0
        while True:
            if d.weekday() == wd:
                k += 1
                if k == n:
                    return d
            d += dt.timedelta(days=1)
    def last(month, wd):
        d = dt.date(y, month + 1, 1) - dt.timedelta(days=1) if month < 12 else dt.date(y, 12, 31)
        while d.weekday() != wd:
            d -= dt.timedelta(days=1)
        return d
    def obs(d):
        return d - dt.timedelta(days=1) if d.weekday() == 5 else d + dt.timedelta(days=1) if d.weekday() == 6 else d
    h = {obs(dt.date(y, 1, 1)), nth(1, 0, 3), nth(2, 0, 3), last(5, 0), obs(dt.date(y, 7, 4)), nth(9, 0, 1), nth(10, 0, 2), obs(dt.date(y, 11, 11)), nth(11, 3, 4), obs(dt.date(y, 12, 25))}
    if y >= 2021:
        h.add(obs(dt.date(y, 6, 19)))
    return h


def deadline(P):
    d = P + dt.timedelta(days=45)
    while d.weekday() >= 5 or d in fed_holidays(d.year):
        d += dt.timedelta(days=1)
    return d
con = duckdb.connect(); con.execute("SET memory_limit='5GB'; SET threads=2; SET preserve_insertion_order=false")
con.execute(f"""CREATE TABLE filings AS
 SELECT s.ACCESSION_NUMBER acc, strptime(s.FILING_DATE, '%d-%b-%Y')::DATE fd, s.SUBMISSIONTYPE stype, s.CIK cik,
        strptime(s.PERIODOFREPORT, '%d-%b-%Y')::DATE period, c.ISAMENDMENT isam, c.AMENDMENTTYPE atype, c.REPORTTYPE rtype, c.FILINGMANAGER_NAME mgr,
        TRY_CAST(m.OTHERINCLUDEDMANAGERSCOUNT AS INT) n_other, TRY_CAST(m.TABLEENTRYTOTAL AS BIGINT) n_entries, TRY_CAST(m.TABLEVALUETOTAL AS DOUBLE) value_total,
        m.ISCONFIDENTIALOMITTED conf, s.dataset,
        CASE WHEN s.SUBMISSIONTYPE IN ('13F-HR', '13F-HR/A') AND c.AMENDMENTTYPE = 'NEW HOLDINGS' THEN 'add'
             WHEN s.SUBMISSIONTYPE = '13F-HR' THEN 'base'
             WHEN s.SUBMISSIONTYPE = '13F-HR/A' AND c.AMENDMENTTYPE = 'RESTATEMENT' THEN 'base'
             WHEN s.SUBMISSIONTYPE = '13F-HR/A' THEN 'unknown'
             ELSE 'notice' END cls,
        CASE WHEN strptime(s.FILING_DATE, '%d-%b-%Y')::DATE < DATE '2023-01-03' THEN 1000.0 ELSE 1.0 END unit
 FROM '{SM}/SUBMISSION_all.parquet' s JOIN '{SM}/COVERPAGE_all.parquet' c USING (ACCESSION_NUMBER)
 LEFT JOIN '{SM}/SUMMARYPAGE_all.parquet' m USING (ACCESSION_NUMBER)""")
con.execute(f"CREATE VIEW hold AS SELECT * FROM read_parquet('{HO}/hold__*.parquet')")
con.execute(f"CREATE TABLE acct AS SELECT acc, sum(nrows) nrows, sum(value_raw) value_raw FROM read_parquet('{HO}/acc__*.parquet') GROUP BY 1")
Q = {}
# 每份持股申報和 SUMMARYPAGE 對
chk = con.execute("""SELECT count(*) n, sum(CASE WHEN a.nrows = f.n_entries THEN 1 ELSE 0 END) rows_ok,
        sum(CASE WHEN abs(a.value_raw - f.value_total) <= greatest(1, 1e-6 * abs(f.value_total)) THEN 1 ELSE 0 END) value_ok,
        sum(CASE WHEN a.acc IS NULL THEN 1 ELSE 0 END) no_table
    FROM filings f LEFT JOIN acct a USING (acc) WHERE f.cls IN ('base', 'add', 'unknown')""").fetchone()
Q["持股申報和封面合計"] = {"持股申報數": chk[0], "列數相同": chk[1], "金額合計相同": chk[2], "沒有資訊表": chk[3]}
Q["申報類別"] = dict(con.execute("SELECT cls, count(*) FROM filings GROUP BY 1").fetchall())
periods = [r[0] for r in con.execute("SELECT DISTINCT period FROM filings WHERE period BETWEEN DATE '2013-06-30' AND DATE '2026-06-30' AND extract(day FROM period + INTERVAL 1 DAY) = 1 AND extract(month FROM period) IN (3, 6, 9, 12) ORDER BY 1").fetchall()]
per = {}
for P in periods:
    d46 = deadline(P) + dt.timedelta(days=1); d180 = min(P + dt.timedelta(days=180), DATA_END + dt.timedelta(days=1))
    row = {"法定期限": str(deadline(P)), "D46": str(d46), "D180": str(d180), "D180 完整": P + dt.timedelta(days=180) <= DATA_END + dt.timedelta(days=1)}
    for lab, D in (("D46", d46), ("D180", d180)):
        con.execute(f"""CREATE OR REPLACE TEMP TABLE f AS SELECT * FROM filings WHERE period = DATE '{P}' AND fd < DATE '{D}'""")
        con.execute("""CREATE OR REPLACE TEMP TABLE b AS SELECT cik, arg_max(acc, fd::VARCHAR || acc) bacc, max(fd::VARCHAR || acc) bkey, count(*) nbase,
                       count(*) FILTER (WHERE stype = '13F-HR') norig FROM f WHERE cls = 'base' GROUP BY 1""")
        con.execute("""CREATE OR REPLACE TEMP TABLE use AS
            SELECT b.cik, b.bacc acc, 'base' role FROM b
            UNION ALL SELECT f.cik, f.acc, 'add' FROM f JOIN b USING (cik) WHERE f.cls = 'add' AND f.fd::VARCHAR || f.acc > b.bkey""")
        st = con.execute("""SELECT (SELECT count(*) FROM b), (SELECT sum(CASE WHEN norig > 1 THEN 1 ELSE 0 END) FROM b),
              (SELECT count(*) FROM use WHERE role = 'add'),
              (SELECT count(*) FROM f WHERE cls = 'add' AND cik NOT IN (SELECT cik FROM b)),
              (SELECT count(*) FROM f WHERE cls = 'unknown'), (SELECT count(*) FROM f WHERE cls = 'notice'),
              (SELECT count(*) FROM f JOIN b ON f.acc = b.bacc WHERE f.rtype = '13F COMBINATION REPORT'),
              (SELECT count(*) FROM f JOIN b ON f.acc = b.bacc WHERE f.conf = 'Y'),
              (SELECT count(*) FROM f JOIN b ON f.acc = b.bacc WHERE f.atype = 'RESTATEMENT')""").fetchone()
        tags = [r[0] for r in con.execute("SELECT DISTINCT f2.dataset FROM use JOIN filings f2 USING (acc)").fetchall()]
        files = "[" + ", ".join(f"'{HO}/hold__{t}.parquet'" for t in tags) + "]"
        con.execute(f"""CREATE OR REPLACE TEMP TABLE snap AS
            SELECT u.cik, h.cusip, h.putcall, h.typ, sum(h.shares) shares, sum(h.value_raw * f2.unit) value_usd, sum(h.bad_value + h.bad_shares) bad, min(h.name) name
            FROM use u JOIN read_parquet({files}) h ON h.acc = u.acc JOIN filings f2 ON f2.acc = u.acc
            GROUP BY 1, 2, 3, 4""")
        v = con.execute("""SELECT count(*), 0, 0, 0, count(DISTINCT cusip), sum(bad) FROM snap""").fetchone()
        row[lab] = {"申報人": st[0], "重複原始(同一季兩份以上 13F-HR)": st[1], "套用新增修正": st[2], "沒有基準的新增修正": st[3], "類型不明修正": st[4], "通知": st[5],
                    "合併報告": st[6], "保密省略": st[7], "基準是重述版": st[8], "持股列": v[0], "CUSIP 數": v[4], "數字無法解析": v[5]}
        # 單位:先用未更正的隱含價格求參考價,再看每個申報人的中位數比值(≥ 3 檔可比):> 100 → 申報的是美元(應為千美元)→ ÷ 1000;< 0.01 → × 1000
        con.execute("""CREATE OR REPLACE TEMP TABLE ip0 AS SELECT cik, cusip, value_usd / shares p FROM snap WHERE typ = 'SH' AND putcall = '' AND shares > 0 AND value_usd > 0""")
        con.execute("CREATE OR REPLACE TEMP TABLE ref0 AS SELECT cusip, median(p) refp, count(*) nh FROM ip0 GROUP BY 1")
        con.execute("""CREATE OR REPLACE TEMP TABLE fix AS SELECT cik, median(ip0.p / ref0.refp) r, count(*) n,
                CASE WHEN count(*) >= 3 AND median(ip0.p / ref0.refp) > 100 THEN 0.001 WHEN count(*) >= 3 AND median(ip0.p / ref0.refp) < 0.01 THEN 1000.0 ELSE 1.0 END f
              FROM ip0 JOIN ref0 USING (cusip) WHERE ref0.nh >= 3 GROUP BY 1""")
        raw_total = con.execute("SELECT sum(value_usd) FROM snap").fetchone()[0] or 0
        con.execute("""CREATE OR REPLACE TEMP TABLE snap2 AS SELECT snap.*, coalesce(fix.f, 1.0) unit_fix, snap.value_usd * coalesce(fix.f, 1.0) value_fixed,
                (fix.cik IS NULL OR fix.n < 3) unit_undetermined FROM snap LEFT JOIN fix USING (cik)""")
        fx = con.execute("""SELECT sum(CASE WHEN f = 0.001 THEN 1 ELSE 0 END), sum(CASE WHEN f = 1000 THEN 1 ELSE 0 END), count(*) FROM fix""").fetchone()
        und = con.execute("SELECT count(DISTINCT cik), sum(value_fixed) FROM snap2 WHERE unit_undetermined").fetchone()
        con.execute("""CREATE OR REPLACE TEMP TABLE ref AS SELECT cusip, median(value_fixed / shares) refp, count(*) nh FROM snap2
                       WHERE typ = 'SH' AND putcall = '' AND shares > 0 AND value_fixed > 0 GROUP BY 1""")
        v2 = con.execute("""SELECT sum(value_fixed), sum(CASE WHEN putcall <> '' THEN value_fixed ELSE 0 END), sum(CASE WHEN typ = 'PRN' THEN value_fixed ELSE 0 END) FROM snap2""").fetchone()
        res = con.execute("""SELECT sum(CASE WHEN s.value_fixed / s.shares > 300 * r.refp OR s.value_fixed / s.shares < r.refp / 300 THEN s.value_fixed ELSE 0 END), sum(s.value_fixed)
                 FROM snap2 s JOIN ref r USING (cusip) WHERE s.typ = 'SH' AND s.putcall = '' AND s.shares > 0 AND s.value_fixed > 0 AND r.nh >= 3""").fetchone()
        row[lab].update({"更正前總市值(十億美元)": round(raw_total / 1e9, 1), "總市值(十億美元)": round((v2[0] or 0) / 1e9, 1),
                         "選擇權占比%": round(100 * (v2[1] or 0) / (v2[0] or 1), 2), "債券占比%": round(100 * (v2[2] or 0) / (v2[0] or 1), 2),
                         "單位更正": {"÷1000 的申報人": fx[0], "×1000 的申報人": fx[1], "可判斷的申報人": fx[2], "判斷不了的申報人": und[0],
                                     "判斷不了的市值占比%": round(100 * (und[1] or 0) / (v2[0] or 1), 3),
                                     "更正後仍偏離 300 倍的持股市值占比%": round(100 * (res[0] or 0) / (res[1] or 1), 3)}})
        if lab == "D46":
            con.execute(f"""COPY (SELECT s.*, r.refp, r.nh,
                    (s.typ = 'SH' AND s.putcall = '' AND s.shares > 0 AND s.value_fixed > 0 AND r.nh >= 3 AND (s.value_fixed / s.shares > 300 * r.refp OR s.value_fixed / s.shares < r.refp / 300)) price_outlier
                FROM snap2 s LEFT JOIN ref r USING (cusip)) TO '{SN}/snap_D46__{P}.parquet' (FORMAT parquet, COMPRESSION zstd)""")
    late = con.execute(f"""SELECT count(*) FROM filings WHERE period = DATE '{P}' AND cls = 'base' AND fd >= DATE '{d46}' AND fd < DATE '{d180}'
                            AND cik NOT IN (SELECT cik FROM filings WHERE period = DATE '{P}' AND cls = 'base' AND fd < DATE '{d46}')""").fetchone()[0]
    row["D46 之後才第一次申報的申報人(到 D180)"] = late
    row["D180 / D46 市值比"] = round(row["D180"]["總市值(十億美元)"] / max(row["D46"]["總市值(十億美元)"], 1e-9), 4)
    per[str(P)] = row
    print(P, row["法定期限"], row["D46"]["申報人"], row["D46"]["更正前總市值(十億美元)"], row["D46"]["總市值(十億美元)"], row["D46"]["單位更正"], flush=True)
Q["每季"] = per
# CUSIP 檢查碼(全部 D46 快照出現過的)
def cusip_ok(c):
    if not isinstance(c, str) or len(c) != 9:
        return False
    s = 0
    for i, ch in enumerate(c[:8]):
        v = int(ch) if ch.isdigit() else (ord(ch) - 55 if ch.isalpha() else {"*": 36, "@": 37, "#": 38}.get(ch))
        if v is None:
            return False
        if i % 2 == 1:
            v *= 2
        s += v // 10 + v % 10
    return c[8].isdigit() and (10 - s % 10) % 10 == int(c[8])
cus = con.execute(f"SELECT cusip, sum(value_fixed) v FROM read_parquet('{SN}/snap_D46__*.parquet') WHERE typ = 'SH' GROUP BY 1").fetchdf()
cus["ok"] = cus["cusip"].map(cusip_ok)
Q["CUSIP 檢查碼(D46 股票持股,全部季)"] = {"不同 CUSIP": int(len(cus)), "合格": int(cus["ok"].sum()), "不合格的市值占比%": round(100 * float(cus.loc[~cus["ok"], "v"].sum() / cus["v"].sum()), 3)}
json.dump(Q, open(os.path.join(OUT, "dl1_quality.json"), "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps({k: v for k, v in Q.items() if k != "每季"}, ensure_ascii=False, indent=1))
