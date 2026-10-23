#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EM1 資料層 B(v1.0):每家公司每一季的淨利「今年 vs 去年同季」(只用財報;不碰報酬)。
用法:python3 -I em_b_firmq.py SCRATCH   → SCRATCH/ern/out/firmq.parquet、firmq_qa.json
規則(PROTOCOL_EM1 §2):
  ① 只用原始申報 10-Q、10-K(不用 /A 修正與轉換期 10-QT / 10-KT);同一家公司同一季有兩份原始申報 → 用最早接受(accepted)的那份
  ② 數字:同一份申報裡的 NetIncomeLoss(沒有才用 ProfitLoss);當季 = ddate 等於申報的 period;去年同季 = ddate 早一年(資料集的日期都已取到月底)
  ③ 10-Q:3 個月(qtrs = 1)的當季與去年同季
  ④ 10-K:第 4 季 = 全年(qtrs = 4)− 前 9 個月(同一家公司 period 早 3 個月的那份原始 10-Q 裡的 qtrs = 3);當年與去年都這樣算,
     兩份申報用同一個標籤;找不到那份 10-Q 或缺數字 → 這一季沒有紀錄
  ⑤ 可用時點 = 觸發這一季的那份申報(10-Q 或 10-K)的 accepted 時間;產業用那份申報上的 SIC;申報人身分(afs)也照那份"""
import os, sys, json
import duckdb

S = sys.argv[1]; X = os.path.join(S, "ern", "ext"); OUT = os.path.join(S, "ern", "out"); os.makedirs(OUT, exist_ok=True)
c = duckdb.connect()
c.execute(f"create table sub as select * from read_parquet('{X}/sub_*.parquet')")
c.execute(f"create table ni as select * from read_parquet('{X}/ni_*.parquet')")
qa = {"原始資料": {"sub 列數": c.execute("select count(*) from sub").fetchone()[0], "淨利列數": c.execute("select count(*) from ni").fetchone()[0]}}
# 同一份申報、同一標籤 / 日期 / 期間有多個數字 → 記數;取絕對值最大的那個(通常只有一個)
qa["重複數字"] = c.execute("select count(*) from (select adsh, tag, ddate, qtrs, count(*) n, count(distinct value) nv from ni group by all having n > 1)").fetchone()[0]
c.execute("""create table v as select adsh, tag, ddate, qtrs, arg_max(value, abs(value)) value from ni group by all""")
c.execute("""create table f as
  select adsh, cast(cik as bigint) cik, name, sic, afs, form, fp,
         strptime(period, '%Y%m%d')::date period, strptime(substr(accepted, 1, 19), '%Y-%m-%d %H:%M:%S') accepted
  from sub where form in ('10-Q', '10-K') and period <> '' and accepted <> ''""")
# 同一家公司同一個 period、同一種表:最早接受的那份
c.execute("""create table f1 as select * from (
  select *, row_number() over (partition by cik, period, form order by accepted, adsh) rn from f) where rn = 1""")
qa["原始申報"] = {"10-Q": c.execute("select count(*) from f1 where form = '10-Q'").fetchone()[0], "10-K": c.execute("select count(*) from f1 where form = '10-K'").fetchone()[0],
                "同季重複(取最早)": c.execute("select count(*) from f where true").fetchone()[0] - c.execute("select count(*) from f1").fetchone()[0]}


def pick(q):
    """每份申報、每個標籤:當期(ddate = period)與早一年的數字(qtrs = q)"""
    return f"""select f1.adsh, v.tag,
        max(case when v.ddate = strftime(f1.period, '%Y%m%d') then v.value end) cur,
        max(case when v.ddate = strftime(last_day(f1.period - interval 1 year), '%Y%m%d') then v.value end) prev
      from f1 join v on v.adsh = f1.adsh and v.qtrs = {q} group by all"""


# 10-Q 當季
c.execute(f"create table q as {pick(1)}")
c.execute("""create table q1 as select f1.cik, f1.name, f1.sic, f1.afs, f1.period, f1.accepted, f1.adsh, 'Q' kind,
          coalesce(a.tag, b.tag) tag, coalesce(a.cur, b.cur) cur, coalesce(a.prev, b.prev) prev
  from f1 left join (select * from q where tag = 'NetIncomeLoss' and cur is not null and prev is not null) a on a.adsh = f1.adsh
          left join (select * from q where tag = 'ProfitLoss' and cur is not null and prev is not null) b on b.adsh = f1.adsh
  where f1.form = '10-Q'""")
# 10-K 全年與同一家公司早 3 個月那份 10-Q 的前 9 個月
c.execute(f"create table ann as {pick(4)}")
c.execute(f"create table ytd as {pick(3)}")
c.execute("""create table k4 as
  select k.cik, k.name, k.sic, k.afs, k.period, k.accepted, k.adsh, 'Q4' kind, a.tag,
         a.cur - y.cur cur, a.prev - y.prev prev
  from f1 k
  join ann a on a.adsh = k.adsh and a.cur is not null and a.prev is not null
  join f1 q3 on q3.cik = k.cik and q3.form = '10-Q' and q3.period = last_day(k.period - interval 3 month)
  join ytd y on y.adsh = q3.adsh and y.tag = a.tag and y.cur is not null and y.prev is not null
  where k.form = '10-K'""")
# 10-K:優先 NetIncomeLoss
c.execute("""create table k4b as select * from (
  select *, row_number() over (partition by adsh order by case when tag = 'NetIncomeLoss' then 0 else 1 end) rn from k4) where rn = 1""")
c.execute("""create table firmq as
  select cik, name, sic, afs, period, accepted, adsh, kind, tag, cur, prev from q1 where cur is not null and prev is not null
  union all select cik, name, sic, afs, period, accepted, adsh, kind, tag, cur, prev from k4b""")
# 同一家公司同一季(10-Q 與 10-K 不會同 period;保險起見再去重)
c.execute("""create table firmq2 as select * from (
  select *, row_number() over (partition by cik, period order by accepted, adsh) rn from firmq) where rn = 1""")
c.execute(f"copy (select cik, name, sic, afs, period, accepted, adsh, kind, tag, cur, prev from firmq2 order by accepted, cik) to '{OUT}/firmq.parquet' (format parquet)")
tot_q = c.execute("select count(*) from f1 where form = '10-Q'").fetchone()[0]; tot_k = c.execute("select count(*) from f1 where form = '10-K'").fetchone()[0]
qa["公司季紀錄"] = {"10-Q 有當季與去年同季": c.execute("select count(*) from q1 where cur is not null and prev is not null").fetchone()[0], "10-Q 總數": tot_q,
                 "10-K 算得出第 4 季": c.execute("select count(*) from k4b").fetchone()[0], "10-K 總數": tot_k,
                 "用 ProfitLoss 的": c.execute("select count(*) from firmq2 where tag = 'ProfitLoss'").fetchone()[0],
                 "最後總數": c.execute("select count(*) from firmq2").fetchone()[0]}
qa["每年(依 accepted)"] = {str(r[0]): {"紀錄": r[1], "公司": r[2], "大型 / 加速申報人紀錄": r[3]} for r in c.execute(
    "select year(accepted), count(*), count(distinct cik), sum(case when afs in ('1-LAF', '2-ACC', '3-SRA') then 1 else 0 end) from firmq2 group by 1 order by 1").fetchall()}
json.dump(qa, open(os.path.join(OUT, "firmq_qa.json"), "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps(qa, ensure_ascii=False, indent=1, default=str))
