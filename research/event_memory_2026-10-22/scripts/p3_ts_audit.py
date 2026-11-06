#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""時間戳逐份稽核(回應 Codex v1.0 12:19:54 第 10.5 點):E7 用到的每一份 8-K Item 2.02,列出
索引頁 Accepted 原字串(美東)、SGML 檔頭 ACCEPTANCE-DATETIME 原值、submissions JSON acceptanceDateTime 原值、時區換算與差值。
不看任何股價。輸入:SCRATCH/em/r2tag/r2_event_tags.json(p2 v2 的輸出;索引頁已快取在 em/r2tag/raw)。
用法:python3 -I p3_ts_audit.py SCRATCH   → SCRATCH/em/r2tag/sec_ts_audit_2_02.csv、sec_ts_audit_summary.json"""
import csv, gzip, json, os, re, sys, threading, time, urllib.error, urllib.request
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = sys.argv[1]; OUT = os.path.join(ROOT, "em", "r2tag"); RAW = os.path.join(OUT, "raw")
UA = open(os.path.join(ROOT, "w8", ".sec_ua")).read().strip()
NY = ZoneInfo("America/New_York"); UTC = ZoneInfo("UTC")
_lock = threading.Lock(); _last = [0.0]


def get(url, tries=5):
    for k in range(tries):
        with _lock:
            w = _last[0] + 0.25 - time.time()
            if w > 0:
                time.sleep(w)
            _last[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=60) as r:
                b = r.read(); return gzip.decompress(b) if r.headers.get("Content-Encoding") == "gzip" else b
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(10 * (k + 1) if e.code == 429 else 3 * (k + 1))
        except Exception:
            time.sleep(3 * (k + 1))
    return None


R = json.load(open(os.path.join(OUT, "r2_event_tags.json")))
F = {}
for r in R:
    for f in r.get("filings", []):
        if f.get("is_202") and f["form"].startswith("8-K") and f.get("accepted_et_index"):
            g = F.setdefault(f["accession"], dict(f, cik=r["cik"], name=r.get("sec_name_at_event"), events=[]))
            g["events"].append(r["event_id"])
rows = []
for acc, f in sorted(F.items()):
    cik = f["cik"]; nod = acc.replace("-", "")
    u_idx = f"https://www.sec.gov/Archives/edgar/data/{cik}/{nod}/{acc}-index.htm"
    u_hdr = f"https://www.sec.gov/Archives/edgar/data/{cik}/{nod}/{acc}.hdr.sgml"
    p = os.path.join(RAW, f"hdr_{acc}.sgml")
    if not os.path.exists(p):
        b = get(u_hdr)
        if b:
            open(p, "wb").write(b)
    sg = None
    if os.path.exists(p):
        m = re.search(rb"<ACCEPTANCE-DATETIME>\s*(\d{14})", open(p, "rb").read())
        sg = m.group(1).decode() if m else None
    idx = f["accepted_et_index"]                         # 例:2025-11-03 06:44:14(美東,沒有時區字)
    idx14 = re.sub(r"\D", "", idx)
    a = datetime.fromisoformat(idx.replace(" ", "T")).replace(tzinfo=NY)
    j = datetime.fromisoformat(f["json_acceptanceDateTime_raw"].replace("Z", "+00:00"))
    rows.append({"accession": acc, "cik": cik, "sec_name_at_event": f["name"], "event_ids": ";".join(f["events"]), "form": f["form"],
                 "filingDate": f["filingDate"], "reportDate(封面事件日)": f.get("reportDate"), "items": f["items"],
                 "index_accepted_raw": idx, "sgml_acceptance_datetime_raw": sg, "index_eq_sgml": (sg == idx14) if sg else None,
                 "tz_rule": "America/New_York(依當天夏令 / 冬令)", "utc_offset": a.strftime("%z"), "accepted_utc": a.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "submissions_acceptanceDateTime_raw": f["json_acceptanceDateTime_raw"], "json_minus_true_utc_h": round((j - a.astimezone(UTC)).total_seconds() / 3600, 1),
                 "url_index": u_idx, "url_sgml_header": u_hdr, "url_submissions": f"https://data.sec.gov/submissions/CIK{cik:010d}.json"})
with open(os.path.join(OUT, "sec_ts_audit_2_02.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
iss = defaultdict(set)
for r in rows:
    iss[r["cik"]].add(r["json_minus_true_utc_h"] == 0)
summ = {"份數": len(rows), "公司數": len(iss), "索引頁 = SGML": sum(1 for r in rows if r["index_eq_sgml"] is True),
        "索引頁 ≠ SGML": sum(1 for r in rows if r["index_eq_sgml"] is False), "SGML 抓不到": sum(1 for r in rows if r["index_eq_sgml"] is None),
        "JSON 差值分布(小時:份數)": {str(k): sum(1 for r in rows if r["json_minus_true_utc_h"] == k) for k in sorted({r["json_minus_true_utc_h"] for r in rows})},
        "公司:JSON 都對": sum(1 for v in iss.values() if v == {True}), "公司:JSON 都錯": sum(1 for v in iss.values() if v == {False}), "公司:混用": sum(1 for v in iss.values() if len(v) > 1)}
json.dump(summ, open(os.path.join(OUT, "sec_ts_audit_summary.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps(summ, ensure_ascii=False))
