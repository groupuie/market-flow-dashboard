#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EM1 資料層 A(v1.0):SEC Financial Statement Data Sets → 每季的申報清單與淨利數字(只取需要的列;不碰報酬)。
用法:python3 -I em_a_extract.py SCRATCH
  輸入:SCRATCH/ern/zips/{YYYY}q{Q}.zip(SEC DERA,https://www.sec.gov/files/dera/data/financial-statement-data-sets/)
  輸出:SCRATCH/ern/ext/sub_{q}.parquet(10-Q / 10-K 與修正、轉換期申報)、ni_{q}.parquet(NetIncomeLoss、ProfitLoss;USD;
        沒有 segments、沒有 coreg 的合併數字)
規則:sub 保留 form ∈ {10-Q, 10-K, 10-QT, 10-KT 與各自的 /A};num 只保留 tag ∈ {NetIncomeLoss, ProfitLoss}、uom = USD、segments 與 coreg 都空白。"""
import io, os, sys, csv, glob, zipfile, json
import pyarrow as pa, pyarrow.parquet as pq

S = sys.argv[1]; Z = os.path.join(S, "ern", "zips"); X = os.path.join(S, "ern", "ext"); os.makedirs(X, exist_ok=True)
FORMS = {"10-Q", "10-K", "10-QT", "10-KT", "10-Q/A", "10-K/A", "10-QT/A", "10-KT/A"}
TAGS = (b"\tNetIncomeLoss\t", b"\tProfitLoss\t")
SUBF = ["adsh", "cik", "name", "sic", "countryinc", "afs", "fye", "form", "period", "fy", "fp", "filed", "accepted", "prevrpt", "nciks"]
qa = {}
for zp in sorted(glob.glob(os.path.join(Z, "*.zip"))):
    q = os.path.basename(zp)[:-4]
    if os.path.exists(os.path.join(X, f"ni_{q}.parquet")):
        continue
    z = zipfile.ZipFile(zp)
    names = {os.path.basename(n): n for n in z.namelist()}
    with z.open(names["sub.txt"]) as f:
        rd = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"), delimiter="\t", quoting=csv.QUOTE_NONE)
        subs = [{k: (r.get(k) or "") for k in SUBF} for r in rd if (r.get("form") or "") in FORMS]
    keep = {r["adsh"] for r in subs}
    pq.write_table(pa.Table.from_pylist(subs, schema=pa.schema([(k, pa.string()) for k in SUBF])), os.path.join(X, f"sub_{q}.parquet"))   # 空的季也要有欄位
    rows = []; nlines = 0
    with z.open(names["num.txt"]) as f:
        hdr = f.readline().decode("utf-8").rstrip("\r\n").split("\t"); ix = {h: i for i, h in enumerate(hdr)}
        has_seg = "segments" in ix
        for line in f:
            nlines += 1
            if not (TAGS[0] in line or TAGS[1] in line):
                continue
            p = line.decode("utf-8", "replace").rstrip("\r\n").split("\t")
            if p[ix["uom"]] != "USD" or p[ix["coreg"]] != "" or (has_seg and p[ix["segments"]] != ""):
                continue
            if p[ix["adsh"]] not in keep or p[ix["tag"]] not in ("NetIncomeLoss", "ProfitLoss"):
                continue
            try:
                v = float(p[ix["value"]])
            except ValueError:
                continue
            rows.append({"adsh": p[ix["adsh"]], "tag": p[ix["tag"]], "ddate": p[ix["ddate"]], "qtrs": int(p[ix["qtrs"]]), "value": v})
    pq.write_table(pa.Table.from_pylist(rows, schema=pa.schema([("adsh", pa.string()), ("tag", pa.string()), ("ddate", pa.string()),
                                                               ("qtrs", pa.int32()), ("value", pa.float64())])), os.path.join(X, f"ni_{q}.parquet"))
    qa[q] = {"sub 10-Q/10-K(含 /A)": len(subs), "num 行數": nlines, "保留淨利列": len(rows), "num 有 segments 欄": has_seg}
    print(q, qa[q], flush=True)
old = {}
qf = os.path.join(X, "extract_qa.json")
if os.path.exists(qf):
    old = json.load(open(qf))
json.dump(old | qa, open(qf, "w"), ensure_ascii=False, indent=1)
