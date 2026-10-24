#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codex R2 的 408 個跳空事件:用 SEC 申報補「跳空前有沒有財報公告(8-K Item 2.02)、索引頁 Accepted 時間、跳空前還有哪些 8-K 項目」。v2(複核後)
**不看任何股價結果**(只用 SPY 的交易日曆找前一個交易日);不判斷指引(E3 已知正規表示式不可靠,指引欄維持 unverified)。
跳空前視窗:前一個交易日 P 的收盤(16:00 ET,提早收盤日 13:00)之後 ~ 事件日 D 的 09:30 ET。
Accepted 是 SEC 受理時間,**不等於公司第一次公開的時間**(新聞稿可能更早)→ first_public_time 一律 unknown;代碼 A 只證明「跳空前有 2.02 被受理」,不證明跳空是財報造成的。
代碼:A = 跳空前受理 2.02;B1 = 2.02 在 D 盤中受理且封面事件日在 P~D;B2 = 2.02 在 D 收盤後受理且封面事件日在 P~D;
      C = 2.02 在 P 收盤前(含更早)受理;O = 跳空前只有其他 8-K 項目;N = 跳空前沒有 8-K / 6-K(跳空後的項目另列)。
用法:python3 -I p2_tag_r2_events.py SCRATCH   → SCRATCH/em/r2tag/r2_event_tags.{json,csv}
輸入:SCRATCH/em/r2tag/r2_events_408.json(Codex 清單)、SCRATCH/w8(CIK 對照、submissions 快取、.sec_ua)、SCRATCH/w7/data/daily.pkl.gz(只用 SPY 的日期)"""
import csv, gzip, json, os, pickle, sys, threading, time, urllib.error, urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

ROOT = sys.argv[1]; W8 = os.path.join(ROOT, "w8"); OUT = os.path.join(ROOT, "em", "r2tag"); RAW = os.path.join(OUT, "raw"); os.makedirs(RAW, exist_ok=True)
UA = open(os.path.join(W8, ".sec_ua")).read().strip()
NY = ZoneInfo("America/New_York"); UTC = ZoneInfo("UTC")
EARLY = {"2018-07-03", "2018-11-23", "2018-12-24", "2019-07-03", "2019-11-29", "2019-12-24", "2020-11-27", "2020-12-24", "2021-11-26",
         "2022-11-25", "2023-07-03", "2023-11-24", "2024-07-03", "2024-11-29", "2024-12-24", "2025-07-03", "2025-11-28", "2025-12-24"}   # NYSE 13:00 收盤
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
WWE = 1091907   # World Wrestling Entertainment(TKO 2023-09-12 成立前);用 SEC 公司名核對過


def cik_for(sym, d):
    s = sym.replace(".", "-")
    if s == "TKO" and d < "2023-09-12":
        return WWE, "manual:WWE(TKO 成立前)"
    if s in M:
        return int(M[s]), "walk8_map"
    if s in SEC:
        return SEC[s], "sec_company_tickers(現在的代號)"
    return None, "unresolved"


SUBS = {}


def subs(cik):
    """回傳 (現名, 舊名清單, rows);rows 只留 2018-06 起"""
    if cik in SUBS:
        return SUBS[cik]
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
    SUBS[cik] = (j.get("name"), j.get("formerNames") or [], rows); return SUBS[cik]


def name_at(name, former, d):
    for f in former:
        if (f.get("from") or "")[:10] <= d <= (f.get("to") or "9999")[:10]:
            return f["name"]
    return name


def index_info(cik, acc):
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}"
    h = cached(os.path.join(RAW, f"idx_{acc}.htm"), f"{base}/{acc}-index.htm")
    if not h:
        return None
    for hd in BeautifulSoup(h, "lxml").select("div.infoHead"):
        if hd.get_text(strip=True) == "Accepted":
            return hd.find_next_sibling("div").get_text(strip=True)
    return None


B = pickle.load(gzip.open(os.path.join(ROOT, "w7", "data", "daily.pkl.gz")))["bars"]
CAL = list(B["SPY"]["d"]); POS = {d: k for k, d in enumerate(CAL)}   # 只用日期
del B

out = []
for e in EV:
    D = e["date"]; rec = dict(e); rec["first_public_time"] = "unknown"; rec["guidance_class"] = "unverified"
    if D not in POS:
        rec["status"] = "X 不是交易日"; out.append(rec); continue
    P = CAL[POS[D] - 1]; rec["prev_trading_day"] = P
    p_close = datetime.fromisoformat(P + ("T13:00" if P in EARLY else "T16:00")).replace(tzinfo=NY)
    d_open = datetime.fromisoformat(D + "T09:30").replace(tzinfo=NY)
    d_close = datetime.fromisoformat(D + ("T13:00" if D in EARLY else "T16:00")).replace(tzinfo=NY)
    cik, src = cik_for(e["symbol"], D); rec["cik"], rec["cik_source"] = cik, src
    if not cik:
        rec["status"] = "X CIK 對不到"; out.append(rec); continue
    name, former, rows = subs(cik); rec["sec_name_now"] = name; rec["sec_name_at_event"] = name_at(name, former, D)
    fil = []
    for r in rows:
        if not (P <= r["filingDate"] <= D and r["form"] in ("8-K", "8-K/A", "6-K", "6-K/A")):
            continue
        acc_et = index_info(cik, r["accessionNumber"])
        f = {"form": r["form"], "accession": r["accessionNumber"], "filingDate": r["filingDate"], "reportDate": r["reportDate"], "items": r["items"],
             "accepted_et_index": acc_et, "json_acceptanceDateTime_raw": r["acceptanceDateTime"], "is_202": "2.02" in (r["items"] or "")}
        if acc_et:
            a = datetime.fromisoformat(acc_et.replace(" ", "T")).replace(tzinfo=NY); f["_a"] = a
            f["accepted_utc"] = a.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            f["timing"] = ("P收盤前(含更早)" if a <= p_close else "跳空前(P收盤後~D開盤前)" if a <= d_open else "D盤中" if a <= d_close else "D收盤後")
            j = datetime.fromisoformat(r["acceptanceDateTime"].replace("Z", "+00:00"))
            f["json_minus_true_utc_h"] = round((j - a.astimezone(UTC)).total_seconds() / 3600, 1)
        fil.append(f)
    fil.sort(key=lambda f: f.get("_a") or datetime.max.replace(tzinfo=UTC))
    # 晚申報:D 之後才申報、封面事件日在 P~D 的 2.02
    d7 = (date.fromisoformat(D) + timedelta(days=7)).isoformat()
    late = [r["accessionNumber"] for r in rows if r["form"].startswith("8-K") and "2.02" in (r["items"] or "") and D < r["filingDate"] <= d7 and P <= (r["reportDate"] or "") <= D]
    rec["late_2_02"] = late
    cover_ok = lambda f: P <= (f.get("reportDate") or "") <= D
    pre = [f for f in fil if f.get("timing") == "跳空前(P收盤後~D開盤前)"]
    pre202 = [f for f in pre if f["is_202"] and f["form"].startswith("8-K")]
    rec["pre_gap_items"] = sorted({i for f in pre for i in (f["items"] or "").split(",") if i})
    rec["post_gap_items"] = sorted({i for f in fil if f.get("timing") in ("D盤中", "D收盤後") for i in (f["items"] or "").split(",") if i})
    rec["pre_gap_other_material"] = sorted(set(rec["pre_gap_items"]) - {"2.02", "9.01"})
    if pre202:
        st = "A"
    elif any(f["is_202"] and f.get("timing") == "D盤中" and cover_ok(f) for f in fil):
        st = "B1"
    elif any(f["is_202"] and f.get("timing") == "D收盤後" and cover_ok(f) for f in fil):
        st = "B2"
    elif late:
        st = "L"
    elif any(f["is_202"] and f.get("timing") == "P收盤前(含更早)" for f in fil):
        st = "C"
    elif any(f["form"].startswith("6-K") and f.get("timing") == "跳空前(P收盤後~D開盤前)" for f in fil):
        st = "F"
    elif pre:
        st = "O"
    else:
        st = "N"
    rec["status"] = st
    # 主要列:A 取跳空前最早的 2.02;其他取最早的 2.02
    main = pre202[:1] or [f for f in fil if f["is_202"]][:1]
    rec["main_202"] = {k: v for k, v in (main[0].items() if main else []) if k != "_a"}
    rec["filings"] = [{k: v for k, v in f.items() if k != "_a"} for f in fil]
    out.append(rec)

json.dump(out, open(os.path.join(OUT, "r2_event_tags.json"), "w"), ensure_ascii=False, indent=1)
with open(os.path.join(OUT, "r2_event_tags.csv"), "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["event_id", "symbol", "event_date", "prev_trading_day", "cik", "cik_source", "sec_name_at_event", "code", "accession_2.02", "accepted_et_index", "accepted_utc",
                "timing", "cover_date(reportDate)", "json_minus_true_utc_h", "pre_gap_items", "pre_gap_other_material", "post_gap_items", "first_public_time", "guidance_class"])
    for r in out:
        f = r.get("main_202") or {}
        w.writerow([r["event_id"], r["symbol"], r["date"], r.get("prev_trading_day"), r.get("cik"), r.get("cik_source"), r.get("sec_name_at_event"), r["status"],
                    f.get("accession"), f.get("accepted_et_index"), f.get("accepted_utc"), f.get("timing"), f.get("reportDate"), f.get("json_minus_true_utc_h"),
                    ";".join(r.get("pre_gap_items") or []), ";".join(r.get("pre_gap_other_material") or []), ";".join(r.get("post_gap_items") or []), r["first_public_time"], r["guidance_class"]])
print("完成", len(out))
