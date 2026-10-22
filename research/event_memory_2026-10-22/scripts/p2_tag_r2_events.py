#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codex R2 的 408 個跳空事件:用 SEC 申報補「跳空前後有沒有財報 8-K(Item 2.02)、索引頁 Accepted 時間、還有哪些 8-K 項目」。
**不看任何股價結果**(只用 SPY 的交易日曆找前一個交易日);不判斷指引(E3 已知正規表示式不可靠,指引欄維持 unverified)。
視窗:前一個交易日 P 的 16:00 ET 之後 ~ 事件日 D 的 09:30 ET(能解釋 D 開盤跳空的時段);另記 P 盤中、D 開盤後的 2.02。
Accepted 是 SEC 受理時間,**不等於公司第一次公開的時間**(新聞稿可能更早)→ first_public_time 一律 unknown。
用法:python3 -I p2_tag_r2_events.py SCRATCH   → SCRATCH/em/r2tag/r2_event_tags.{json,csv}"""
import csv, gzip, json, os, pickle, sys, threading, time, urllib.error, urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

ROOT = sys.argv[1]; W8 = os.path.join(ROOT, "w8"); OUT = os.path.join(ROOT, "em", "r2tag"); RAW = os.path.join(OUT, "raw"); os.makedirs(RAW, exist_ok=True)
UA = open(os.path.join(W8, ".sec_ua")).read().strip()
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


def cached(path, url):
    if os.path.exists(path):
        return open(path, "rb").read()
    b = get(url)
    if b:
        open(path, "wb").write(b)
    return b


EV = json.load(open(os.path.join(OUT, "r2_events_408.json")))
M = json.load(open(os.path.join(W8, "data", "cik_map.json")))["map"]
CT = json.loads(cached(os.path.join(RAW, "company_tickers.json"), "https://www.sec.gov/files/company_tickers.json"))
SEC = {}
for v in CT.values():
    SEC.setdefault(v["ticker"].replace(".", "-").upper(), int(v["cik_str"]))
WWE = 1091907   # World Wrestling Entertainment(TKO 2023-09-12 成立前);下面會用 submissions 的公司名核對


def cik_for(sym, date):
    s = sym.replace(".", "-")
    if s == "TKO" and date < "2023-09-12":
        return WWE, "manual:WWE(TKO 成立前)"
    if s in M:
        return int(M[s]), "walk8_map"
    if s in SEC:
        return SEC[s], "sec_company_tickers(現在的代號)"
    return None, "unresolved"


SUBS = {}


def subs(cik):
    if cik in SUBS:
        return SUBS[cik]
    p = os.path.join(W8, "raw", "subs", f"{cik}.json.gz")
    if os.path.exists(p):
        d = json.load(gzip.open(p, "rt")); SUBS[cik] = (d.get("name"), d["rows"]); return SUBS[cik]
    j = json.loads(cached(os.path.join(RAW, f"subs_{cik}.json"), f"https://data.sec.gov/submissions/CIK{cik:010d}.json"))
    KEEP = ["accessionNumber", "filingDate", "reportDate", "acceptanceDateTime", "form", "items"]; rows = []

    def take(blk):
        n = len(blk["form"])
        for k in range(n):
            if blk["filingDate"][k] >= "2018-06-01":
                rows.append({f: (blk.get(f) or [""] * n)[k] for f in KEEP})
    take(j["filings"]["recent"])
    for f in j["filings"].get("files", []):
        if f["filingTo"] >= "2018-06-01":
            take(json.loads(cached(os.path.join(RAW, f["name"]), "https://data.sec.gov/submissions/" + f["name"])))
    SUBS[cik] = (j.get("name"), rows); return SUBS[cik]


def index_info(cik, acc):
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}"
    h = cached(os.path.join(RAW, f"idx_{acc}.htm"), f"{base}/{acc}-index.htm")
    if not h:
        return None, []
    soup = BeautifulSoup(h, "lxml"); acc_et = None
    for hd in soup.select("div.infoHead"):
        if hd.get_text(strip=True) == "Accepted":
            acc_et = hd.find_next_sibling("div").get_text(strip=True)
    types = []
    for tr in soup.select("table.tableFile tr"):
        td = [x.get_text(" ", strip=True) for x in tr.find_all("td")]
        if len(td) >= 4:
            types.append(td[3])
    return acc_et, types


# 交易日曆(只用 SPY 的日期,不用任何價格)
B = pickle.load(gzip.open(os.path.join(ROOT, "w7", "data", "daily.pkl.gz")))["bars"]
CAL = list(B["SPY"]["d"]); POS = {d: k for k, d in enumerate(CAL)}

out = []
for e in EV:
    D = e["date"]; rec = dict(e); rec["first_public_time"] = "unknown"; rec["guidance_class"] = "unverified"
    if D not in POS:
        rec["status"] = "date_not_trading_day"; out.append(rec); continue
    P = CAL[POS[D] - 1]; rec["prev_trading_day"] = P
    lo = datetime.fromisoformat(P + "T16:00").replace(tzinfo=NY); hi = datetime.fromisoformat(D + "T09:30").replace(tzinfo=NY)
    cik, src = cik_for(e["symbol"], D); rec["cik"], rec["cik_source"] = cik, src
    if not cik:
        rec["status"] = "cik_unresolved"; out.append(rec); continue
    name, rows = subs(cik); rec["sec_name"] = name
    cand = [r for r in rows if P <= r["filingDate"] <= D and r["form"] in ("8-K", "8-K/A", "6-K", "6-K/A")]
    rec["forms_P_to_D"] = sorted({r["form"] for r in cand})
    rec["items_8k_P_to_D"] = sorted({i for r in cand if r["form"].startswith("8-K") for i in (r["items"] or "").split(",") if i})
    filings = []
    for r in cand:
        if r["form"].startswith("8-K") and "2.02" not in (r["items"] or ""):
            continue
        acc_et, types = index_info(cik, r["accessionNumber"])
        f = {"form": r["form"], "accession": r["accessionNumber"], "filingDate": r["filingDate"], "items": r["items"],
             "accepted_et_index": acc_et, "json_acceptanceDateTime_raw": r["acceptanceDateTime"], "has_ex99": any(t.upper().startswith("EX-99") for t in types)}
        if acc_et:
            a = datetime.fromisoformat(acc_et.replace(" ", "T")).replace(tzinfo=NY)
            f["accepted_utc"] = a.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            f["timing"] = ("P盤中或更早" if a <= lo else "P收盤後~D開盤前" if a <= hi else "D開盤後")
            j = datetime.fromisoformat(r["acceptanceDateTime"].replace("Z", "+00:00"))
            f["json_minus_true_utc_h"] = round((j - a.astimezone(UTC)).total_seconds() / 3600, 1)
        filings.append(f)
    rec["filings"] = filings
    # 晚申報:Item 2.02 最晚可在公布後 4 個營業日內申報;用 8-K 封面的「事件日」(reportDate)找 P ~ D 公布、之後才申報的
    from datetime import date as _d
    p0 = (_d.fromisoformat(P) - timedelta(days=3)).isoformat(); d7 = (_d.fromisoformat(D) + timedelta(days=7)).isoformat()
    late = []
    for r in rows:
        if r["form"].startswith("8-K") and "2.02" in (r["items"] or "") and p0 <= r["filingDate"] <= d7 and P <= (r["reportDate"] or "") <= D and r["filingDate"] > D:
            acc_et, types = index_info(cik, r["accessionNumber"])
            late.append({"form": r["form"], "accession": r["accessionNumber"], "filingDate": r["filingDate"], "reportDate": r["reportDate"], "items": r["items"], "accepted_et_index": acc_et, "timing": "D之後才申報(封面事件日在 P~D)"})
    rec["late_2_02"] = late
    for f in filings:
        f["reportDate"] = next((r["reportDate"] for r in rows if r["accessionNumber"] == f["accession"]), None)
    in_win = [f for f in filings if f.get("timing") == "P收盤後~D開盤前"]
    e202 = [f for f in filings if f["form"].startswith("8-K")]
    k6 = [f for f in filings if f["form"].startswith("6-K")]
    if any(f["form"].startswith("8-K") for f in in_win):
        st = "8-K 2.02 在跳空前(P 收盤後 ~ D 開盤前)"
    elif late:
        st = "8-K 2.02 晚申報(封面事件日在 P~D)"
    elif any(f.get("timing") == "D開盤後" for f in e202):
        st = "8-K 2.02 在 D 開盤後才受理(新聞稿可能更早)"
    elif any(f.get("timing") == "P盤中或更早" for f in e202):
        st = "8-K 2.02 在 P 盤中受理"
    elif k6:
        st = "只有 6-K(外國發行人;內容未核)"
    elif rec["items_8k_P_to_D"]:
        st = "有其他 8-K 項目、沒有 2.02"
    else:
        st = "P ~ D 沒有 8-K / 6-K"
    rec["status"] = st
    out.append(rec)
    print(e["event_id"], e["symbol"], D, st, flush=True)

json.dump(out, open(os.path.join(OUT, "r2_event_tags.json"), "w"), ensure_ascii=False, indent=1)
with open(os.path.join(OUT, "r2_event_tags.csv"), "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["event_id", "symbol", "event_date", "prev_trading_day", "cik", "cik_source", "sec_name", "status", "accession_2.02", "accepted_et_index", "accepted_utc", "timing", "json_minus_true_utc_h", "items_8k_P_to_D", "forms_P_to_D", "first_public_time", "guidance_class"])
    for r in out:
        f = (r.get("filings") or [{}])
        f = sorted(f, key=lambda x: {"P收盤後~D開盤前": 0, "D開盤後": 1, "P盤中或更早": 2}.get(x.get("timing"), 3))[0] if f else {}
        w.writerow([r["event_id"], r["symbol"], r["date"], r.get("prev_trading_day"), r.get("cik"), r.get("cik_source"), r.get("sec_name"), r["status"],
                    f.get("accession"), f.get("accepted_et_index"), f.get("accepted_utc"), f.get("timing"), f.get("json_minus_true_utc_h"),
                    ";".join(r.get("items_8k_P_to_D") or []), ";".join(r.get("forms_P_to_D") or []), r["first_public_time"], r["guidance_class"]])
print("完成", len(out))
