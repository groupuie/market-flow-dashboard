#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可行性試抓(不是 alpha 研究,不看股價):財報新聞稿(8-K Item 2.02 的 EX-99.1)裡有沒有「數字指引」、時間戳怎麼記。
- 20 檔大型股(跨板塊,依事前知名度挑,沒有看任何結果),每檔最近 4 份 Item 2.02 的 8-K(2025-07 起)
- 從 SEC 抓 filing index 與 EX-99.1 原檔;原檔存 gzip + SHA-256(之後可重建)
- 指引偵測(粗):同一句同時有「指引字眼」(outlook / guidance / expect / anticipate / forecast / project)+ 期間字眼(quarter / fiscal / full year / year)+ 數字(金額、%、區間)
- 時間:SEC submissions 的 acceptanceDateTime 原樣記下,另看時數分布(walk8 已發現它不是真的 UTC)
- User-Agent 從 w8/.sec_ua 讀(SEC 規定要有聯絡方式;不寫進程式碼、不印出)
用法:python3 -I p1_sec_guidance.py SCRATCH"""
import gzip, hashlib, json, os, re, sys, threading, time, urllib.error, urllib.request
from bs4 import BeautifulSoup

ROOT = sys.argv[1]; W8 = os.path.join(ROOT, "w8"); OUT = os.path.join(ROOT, "em"); RAW = os.path.join(OUT, "raw", "sec_ex99"); os.makedirs(RAW, exist_ok=True)
UA = open(os.path.join(W8, ".sec_ua")).read().strip()
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


M = json.load(open(os.path.join(W8, "data", "cik_map.json")))["map"]
TICK = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "JPM", "XOM", "JNJ", "WMT", "CAT", "NKE", "LMT", "NFLX", "AMD", "MU", "TSLA", "AVGO", "COST", "UNH"]
KW = re.compile(r"\b(outlook|guidance|expects?|expected|anticipates?|forecasts?|projects?|projected)\b", re.I)
PER = re.compile(r"\b(quarter|fiscal|full[- ]year|year|2026|2027)\b", re.I)
NUM = re.compile(r"(\$\s?\d[\d,\.]*\s?(billion|million)?|\d+(\.\d+)?\s?(%|percent)|\d+(\.\d+)?\s?(to|-|–)\s?\$?\d+(\.\d+)?)", re.I)
rows = []
for t in TICK:
    cik = M[t]; sub = json.load(gzip.open(os.path.join(W8, "raw", "subs", f"{cik}.json.gz"), "rt"))["rows"]
    eks = [r for r in sub if r["form"] == "8-K" and "2.02" in (r["items"] or "") and r["filingDate"] >= "2025-07-01"]
    eks = sorted(eks, key=lambda r: r["filingDate"], reverse=True)[:4]
    for r in eks:
        acc = r["accessionNumber"]; base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}"
        h = get(f"{base}/{acc}-index.htm"); cand = []; docs = []; accepted_et = None
        if h:
            soup = BeautifulSoup(h, "lxml")
            for hd in soup.select("div.infoHead"):
                if hd.get_text(strip=True) == "Accepted":
                    accepted_et = hd.find_next_sibling("div").get_text(strip=True)
            for tr in soup.select("table.tableFile tr"):
                td = [x.get_text(" ", strip=True) for x in tr.find_all("td")]
                a = tr.find("a")
                if len(td) >= 4 and a:
                    docs.append({"type": td[3], "name": a["href"].split("/")[-1], "desc": td[1]})
        ex = [d for d in docs if d["type"].upper().startswith("EX-99")]
        cand = [d["name"] for d in sorted(ex, key=lambda d: (0 if d["type"].upper() in ("EX-99.1", "EX-99") else 1, d["type"]))]
        rec = {"ticker": t, "cik": cik, "accession": acc, "filingDate": r["filingDate"], "reportDate": r["reportDate"],
               "acceptanceDateTime_raw": r["acceptanceDateTime"], "accepted_ET_index_page": accepted_et, "items": r["items"], "ex99_files": cand, "ex99_types": [d["type"] for d in ex]}
        if cand:
            b = get(base + "/" + cand[0])
            if b:
                sha = hashlib.sha256(b).hexdigest(); fn = f"{t}_{acc}_{cand[0]}.gz"
                with gzip.open(os.path.join(RAW, fn), "wb") as fh:
                    fh.write(b)
                txt = re.sub(r"\s+", " ", BeautifulSoup(b, "lxml").get_text(" ")).strip()
                sents = re.split(r"(?<=[\.\;])\s+(?=[A-Z•\-\(])", txt)
                g = [s for s in sents if KW.search(s) and PER.search(s) and NUM.search(s) and len(s) < 600]
                blocks = [txt[m.start():m.start() + 700] for m in re.finditer(r"\b(Business Outlook|Financial Outlook|Outlook|Guidance)\b", txt)]
                gb = [b_ for b_ in blocks if NUM.search(b_) and PER.search(b_)]
                rec.update({"ex99_sha256": sha, "ex99_saved": fn, "n_chars": len(txt), "n_guidance_sentences": len(g),
                            "guidance_snippets": [s[:260] for s in g[:3]], "n_outlook_blocks_with_numbers": len(gb), "outlook_block_sample": (gb[0][:400] if gb else ""),
                            "is_earnings_release": bool(re.search(r"per share|net income|net revenue|revenue", txt[:6000], re.I)),
                            "has_outlook_header": bool(re.search(r"\b(Outlook|Guidance|Business Outlook|Financial Outlook)\b", txt)),
                            "mentions_call": bool(re.search(r"conference call|webcast", txt, re.I))})
        rows.append(rec); print(t, r["filingDate"], "SEC-json", r["acceptanceDateTime"], "index頁(ET)", accepted_et, rec.get("ex99_types"), (rec.get("n_guidance_sentences"), rec.get("n_outlook_blocks_with_numbers")), flush=True)
json.dump(rows, open(os.path.join(OUT, "out", "p1_sec_guidance.json"), "w"), ensure_ascii=False, indent=1)
print("完成", len(rows))
