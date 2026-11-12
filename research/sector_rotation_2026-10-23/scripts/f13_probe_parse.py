#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""13F 可行性抽查:解析 f13_probe_fetch.py 抓的兩份 Berkshire 13F;核對列數與封面合計;KO / CVX 的股數與市值變化。
注意單位:2023-01-03 以後送件的 13F 金額以美元申報,之前以千美元。用法:python3 -I f13_probe_parse.py SCRATCH"""
import os, sys, re, json
import xml.etree.ElementTree as ET
S = sys.argv[1]; RAW = os.path.join(S, "f13", "raw")
def strip(t): return t.split("}")[-1]
def rows(fn):
    root = ET.parse(os.path.join(RAW, fn)).getroot(); out = []
    for it in root:
        d = {}
        for c in it.iter():
            tag = strip(c.tag)
            if c.text and c.text.strip():
                d[tag] = c.text.strip()
        out.append(d)
    return out
def cover(fn):
    root = ET.parse(os.path.join(RAW, fn)).getroot(); d = {}
    for c in root.iter():
        tag = strip(c.tag)
        if tag in ("periodOfReport", "reportCalendarOrQuarter", "isAmendment", "amendmentType", "tableEntryTotal", "tableValueTotal", "otherIncludedManagersCount", "reportType", "confidentialOmitted", "amendmentNo") and c.text:
            d[tag] = c.text.strip()
    return d
def accepted(fn):
    h = open(os.path.join(RAW, fn), encoding="utf-8", errors="replace").read()
    g = lambda lab: (re.search(lab + r'</div>\s*<div class="info">([^<]+)</div>', h) or [None, None])[1]
    return {"Filing Date": g("Filing Date"), "Accepted": g("Accepted"), "Period of Report": g("Period of Report")}
res = {}
for acc, info in (("000095012322012275", "18337.xml"), ("000095012323002585", "20651.xml")):
    R = rows(f"{acc}_{info}"); C = cover(f"{acc}_primary_doc.xml"); A = accepted(f"{acc}_index.htm")
    tot = sum(int(r["value"]) for r in R)
    agg = {}
    for r in R:
        if r.get("cusip") in ("191216100", "166764100"):
            k = (r["cusip"], r.get("nameOfIssuer"), r.get("titleOfClass"), r.get("putCall", ""))
            a = agg.setdefault(k, {"列數": 0, "股數": 0, "市值(申報單位)": 0})
            a["列數"] += 1; a["股數"] += int(r["sshPrnamt"]); a["市值(申報單位)"] += int(r["value"])
            assert r.get("sshPrnamtType") == "SH"
    res[acc] = {"封面": C, "索引頁": A, "列數": len(R), "市值合計(申報單位)": tot, "KO/CVX": {" | ".join(k): v for k, v in agg.items()}}
q3, q4 = res["000095012322012275"], res["000095012323002585"]
# 單位:2023-01-03 以後送件的 13F 金額以美元申報;之前以千美元
for name, cus in (("KO", "191216100"), ("CVX", "166764100")):
    a = [v for k, v in q3["KO/CVX"].items() if k.startswith(cus)][0]; b = [v for k, v in q4["KO/CVX"].items() if k.startswith(cus)][0]
    v3 = a["市值(申報單位)"] * 1000; v4 = b["市值(申報單位)"]
    res[name] = {"Q3 股數": a["股數"], "Q4 股數": b["股數"], "股數變化%": round(100 * (b["股數"] / a["股數"] - 1), 3),
                 "Q3 市值(美元,千元×1000)": v3, "Q4 市值(美元)": v4, "市值變化%": round(100 * (v4 / v3 - 1), 3),
                 "Q3 每股隱含價": round(v3 / a["股數"], 4), "Q4 每股隱含價": round(v4 / b["股數"], 4)}
print(json.dumps(res, ensure_ascii=False, indent=1))
json.dump(res, open(os.path.join(S, "f13", "parse_result.json"), "w"), ensure_ascii=False, indent=1)
