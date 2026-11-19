#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk8 E0:SEC 資料(財報日、8-K、EPS、內部人交易)
- User-Agent 從環境變數 SEC_UA 或檔案 .sec_ua 讀(SEC 規定要有聯絡方式;不寫進程式碼、不印出)
- 速度:≤ 5 個請求 / 秒,429 就退避
子指令:
  cik    → data/cik_map.json(walk7 的 613 檔 → CIK;S&P 歷年名單的 CIK 優先,其餘用 SEC company_tickers.json)
  subs   → raw/subs/CIK.json.gz(每檔 2015-06 以後的全部申報:表格、日期、8-K items、報告期間)
  eps    → raw/eps/CIK.json.gz(XBRL:EarningsPerShareDiluted / BasicAndDiluted / Basic)
  f345   → raw/f345/YYYYqN_form345.zip(2015q3 ~ 2026q3 內部人交易季資料)
用法:python3 e0_sec.py OUT_DIR 子指令 [W7_DIR]"""
import concurrent.futures as cf, gzip, json, os, re, sys, threading, time, urllib.error, urllib.request

OUT, CMD = sys.argv[1], sys.argv[2]; W7 = sys.argv[3] if len(sys.argv) > 3 else None
UA = os.environ.get("SEC_UA") or open(os.path.join(OUT, ".sec_ua")).read().strip()
_lock = threading.Lock(); _last = [0.0]


def get(url, tries=6):
    for k in range(tries):
        with _lock:   # 全域節流:兩個請求之間至少 0.2 秒
            w = _last[0] + 0.2 - time.time()
            if w > 0:
                time.sleep(w)
            _last[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=90) as r:
                b = r.read(); return gzip.decompress(b) if r.headers.get("Content-Encoding") == "gzip" else b
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(10 * (k + 1) if e.code == 429 else 3 * (k + 1))
        except Exception:
            time.sleep(3 * (k + 1))
    raise RuntimeError("失敗:" + url.split("/")[-1])


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, "wt") as fh:
        json.dump(obj, fh)


if CMD == "cik":
    import pandas as pd
    S = pd.read_pickle(os.path.join(W7, "out", "S7.pkl"), compression=None)[["sym"]].drop_duplicates()
    SP = json.load(open(os.path.join(W7, "data", "sp500_jan1.json")))
    import pickle
    ymap = pickle.load(gzip.open(os.path.join(W7, "data", "daily.pkl.gz")))["ymap"]
    wiki = {}
    for Y in sorted(SP, key=int):
        for m in SP[Y]:
            if m.get("cik"):
                wiki[ymap.get(m["sym"], m["sym"])] = int(m["cik"])
    ct = json.loads(get("https://www.sec.gov/files/company_tickers.json")); sec = {}
    for v in ct.values():
        sec.setdefault(v["ticker"].replace(".", "-").upper(), int(v["cik_str"]))
    out, miss = {}, []
    for s in sorted(S.sym):
        c = wiki.get(s) or sec.get(s)
        if c:
            out[s] = c
        else:
            miss.append(s)
    json.dump({"map": out, "src": {s: ("wiki" if s in wiki else "sec") for s in out}, "missing": miss}, open(os.path.join(OUT, "data", "cik_map.json"), "w"), indent=0)
    print("對到 CIK", len(out), "/", len(S), "沒對到", miss)

elif CMD == "subs":
    M = json.load(open(os.path.join(OUT, "data", "cik_map.json")))["map"]; ciks = sorted(set(M.values()))
    KEEP = ["accessionNumber", "filingDate", "reportDate", "acceptanceDateTime", "form", "items"]

    def one(c):
        p = os.path.join(OUT, "raw", "subs", f"{c}.json.gz")
        if os.path.exists(p):
            return c, "已有"
        j = json.loads(get(f"https://data.sec.gov/submissions/CIK{c:010d}.json")); rows = []

        def take(blk):
            n = len(blk["form"])
            for k in range(n):
                if blk["filingDate"][k] >= "2015-06-01":
                    rows.append({f: (blk.get(f) or [""] * n)[k] for f in KEEP})
        take(j["filings"]["recent"])
        for f in j["filings"].get("files", []):
            if f["filingTo"] >= "2015-06-01":
                take(json.loads(get("https://data.sec.gov/submissions/" + f["name"])))
        save(p, {"cik": c, "name": j.get("name"), "tickers": j.get("tickers"), "rows": rows}); return c, len(rows)

    t0 = time.time()
    with cf.ThreadPoolExecutor(4) as ex:
        for n, (c, r) in enumerate(ex.map(one, ciks)):
            if (n + 1) % 50 == 0:
                print(n + 1, "/", len(ciks), round(time.time() - t0), "秒", flush=True)
    print("submissions 完成", len(ciks))

elif CMD == "eps":
    M = json.load(open(os.path.join(OUT, "data", "cik_map.json")))["map"]; ciks = sorted(set(M.values()))
    TAGS = ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted", "EarningsPerShareBasic"]

    def one(c):
        p = os.path.join(OUT, "raw", "eps", f"{c}.json.gz")
        if os.path.exists(p):
            return c, "已有"
        got = {}
        for t in TAGS:
            b = get(f"https://data.sec.gov/api/xbrl/companyconcept/CIK{c:010d}/us-gaap/{t}.json")
            if b:
                u = json.loads(b).get("units", {}); got[t] = [x for k_, v in u.items() for x in v if "/" in k_ or k_.lower().startswith("usd")]
                if t == "EarningsPerShareDiluted" and got[t]:
                    break
        save(p, {"cik": c, "eps": got}); return c, sum(len(v) for v in got.values())

    t0 = time.time()
    with cf.ThreadPoolExecutor(4) as ex:
        for n, (c, r) in enumerate(ex.map(one, ciks)):
            if (n + 1) % 100 == 0:
                print(n + 1, "/", len(ciks), round(time.time() - t0), "秒", flush=True)
    print("EPS 完成", len(ciks))

elif CMD == "f345":
    page = get("https://www.sec.gov/dera/data/form-345").decode("utf-8", "ignore")
    links = sorted(set(re.findall(r'href="([^"]*insider-transactions-data-sets/(\d{4})q(\d)_form345\.zip)"', page)))
    want = [(l, int(y), int(q)) for l, y, q in links if (int(y), int(q)) >= (2015, 3)]
    os.makedirs(os.path.join(OUT, "raw", "f345"), exist_ok=True)
    for l, y, q in want:
        p = os.path.join(OUT, "raw", "f345", f"{y}q{q}_form345.zip")
        if os.path.exists(p):
            continue
        b = get("https://www.sec.gov" + l)
        if b:
            open(p, "wb").write(b); print(f"{y}q{q}", round(len(b) / 1e6, 1), "MB", flush=True)
    print("Form 345 完成", len(want))
