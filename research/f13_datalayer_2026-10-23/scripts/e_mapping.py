#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""13F 資料層 DL1 步驟 e:CUSIP → 產業的可行性抽查(不是正式對照)。兩季(2014-12-31、2026-06-30)各取市值前 1,000 個 CUSIP:
OpenFIGI(CUSIP → 代號、證券類型)→ SEC company_tickers(代號 → CIK,今天的)→ SEC submissions(CIK → 今天的 SIC)→ French 49 產業(Siccodes49)。
回報各層的市值覆蓋率。今天的 SIC 不能回填歷史(DL1_SPEC §5)。用法:python3 -I e_mapping.py SCRATCH"""
import os, sys, json, time, re, zipfile, hashlib, urllib.request
import duckdb

S = sys.argv[1]; F = os.path.join(S, "f13"); SN, MP, OUT = (os.path.join(F, x) for x in ("snap", "map", "out")); os.makedirs(MP, exist_ok=True)
UA = open(os.path.join(S, "w8", ".sec_ua")).read().strip()        # 只放在送給 SEC 的請求標頭,不印出
PER = ["2014-12-31", "2026-06-30"]; TOPN = 1000
con = duckdb.connect()
CLEAN = "typ = 'SH' AND putcall = '' AND shares > 0 AND value_fixed > 0 AND NOT coalesce(price_outlier, false)"
top, tot = {}, {}
for p in PER:
    df = con.execute(f"SELECT cusip, sum(value_fixed) v, min(name) name FROM '{SN}/snap_D46__{p}.parquet' WHERE {CLEAN} GROUP BY 1 ORDER BY v DESC").fetchdf()
    tot[p] = float(df["v"].sum()); top[p] = df.head(TOPN)
allc = sorted(set().union(*[set(t["cusip"]) for t in top.values()]))


def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "User-Agent": "dl1-probe/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def get_sec(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


tick_p = os.path.join(MP, "company_tickers.json")
if not os.path.exists(tick_p):
    open(tick_p, "wb").write(get_sec("https://www.sec.gov/files/company_tickers.json"))
tk = {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in json.load(open(tick_p)).values()}
figi_p = os.path.join(MP, "openfigi.json"); figi = json.load(open(figi_p)) if os.path.exists(figi_p) else {}
USX = ("US", "UN", "UQ", "UW", "UA", "UR", "UP", "UF", "UV", "UD", "UT", "UB", "UM", "UX", "UC")


def pick(d):
    """先選 US 綜合代號;沒有就選 SEC 代號表認得的代號;再來美國交易所;最後才用第一筆
    (v1.0 直接用第一筆 → Exxon 選到非美國掛牌;v1.1 加美國交易所仍漏掉 Exxon 的 UZ / OU)"""
    for want in (lambda x: x.get("exchCode") == "US", lambda x: str(x.get("ticker") or "").upper().replace("/", "-") in tk, lambda x: x.get("exchCode") in USX):
        u = [x for x in d if want(x)]
        if u:
            return u[0]
    return d[0] if d else None


todo = [c for c in allc if c not in figi or (figi[c] is not None and figi[c].get("exchCode") != "US"
                                             and str(figi[c].get("ticker") or "").upper().replace("/", "-") not in tk and not figi[c].get("_v3"))]
for i in range(0, len(todo), 10):
    batch = todo[i:i + 10]
    for k in range(4):
        try:
            res = post("https://api.openfigi.com/v3/mapping", [{"idType": "ID_CUSIP", "idValue": c} for c in batch]); break
        except Exception as e:                                  # noqa: BLE001
            time.sleep(15 * (k + 1)); res = None
    if res is None:
        continue
    for c, r in zip(batch, res):
        d = r.get("data") or []
        x = pick(d)
        figi[c] = None if x is None else {**{k_: x.get(k_) for k_ in ("ticker", "name", "securityType", "securityType2", "marketSector", "exchCode")}, "_v3": True}
    json.dump(figi, open(figi_p, "w"))
    time.sleep(2.6)                                              # 沒有 API key:每分鐘 25 次
sic_p = os.path.join(MP, "sic.json"); sic = json.load(open(sic_p)) if os.path.exists(sic_p) else {}
ciks = sorted({tk.get((v or {}).get("ticker", "").upper().replace("/", "-")) for v in figi.values() if v} - {None})
for cik in [c for c in ciks if c not in sic]:
    try:
        js = json.loads(get_sec(f"https://data.sec.gov/submissions/CIK{cik}.json"))
        sic[cik] = {"sic": js.get("sic"), "sicDescription": js.get("sicDescription"), "name": js.get("name")}
    except Exception as e:                                      # noqa: BLE001
        sic[cik] = {"error": str(e)[:60]}
    time.sleep(0.25)
json.dump(sic, open(sic_p, "w"))
# French 49 的 SIC 範圍
t = zipfile.ZipFile(os.path.join(S, "fs", "raw", "Siccodes49.zip")).read("Siccodes49.txt").decode("latin-1"); rng = []; cur = None
for l in t.splitlines():
    m = re.match(r"^\s*(\d{1,2})\s+([A-Za-z]+)\s+\S", l); r = re.match(r"^\s+(\d{4})-(\d{4})", l)
    if m and not r:
        cur = m.group(2)
    elif r and cur:
        rng.append((int(r.group(1)), int(r.group(2)), cur))


def ff49(s):
    try:
        s = int(s)
    except Exception:                                           # noqa: BLE001
        return None
    for lo, hi, c in rng:
        if lo <= s <= hi:
            return c
    return "Other"


res = {"說明": "可行性抽查;今天的代號與 SIC,不能回填歷史", "每季": {}}
for p in PER:
    d = top[p].copy(); T = tot[p]
    d["figi"] = d["cusip"].map(lambda c: figi.get(c)); d["stype"] = d["figi"].map(lambda v: (v or {}).get("securityType2") or (v or {}).get("securityType"))
    d["ticker"] = d["figi"].map(lambda v: (v or {}).get("ticker"))
    d["cik"] = d["ticker"].map(lambda x: tk.get(str(x).upper().replace("/", "-")) if x else None)
    d["sic"] = d["cik"].map(lambda c: (sic.get(c) or {}).get("sic") if c else None)
    d["ff49"] = d["sic"].map(lambda s: ff49(s) if s not in (None, "") else None)
    etf = d["stype"].fillna("").str.contains("ETP|Mutual Fund|Closed-End Fund|Fund", case=False)
    row = {"這一季乾淨持股總市值(十億美元)": round(T / 1e9, 1), "前 1,000 個 CUSIP 占比%": round(100 * d["v"].sum() / T, 2),
           "OpenFIGI 有對到%": round(100 * d.loc[d["figi"].notna(), "v"].sum() / T, 2), "ETF / 基金類%": round(100 * d.loc[etf, "v"].sum() / T, 2),
           "對到今天的 CIK%": round(100 * d.loc[d["cik"].notna(), "v"].sum() / T, 2),
           "對到 SIC 與 French 49 產業(非 ETF)%": round(100 * d.loc[d["ff49"].notna() & ~etf, "v"].sum() / T, 2),
           "前 1,000 個裡沒對到產業也不是 ETF%": round(100 * d.loc[d["ff49"].isna() & ~etf, "v"].sum() / T, 2)}
    row["沒對到的前 10 大(市值十億美元)"] = [(r.cusip, r.name, round(r.v / 1e9, 1)) for r in d.loc[d["ff49"].isna() & ~etf].head(10).itertuples()]
    res["每季"][p] = row
res["原檔指紋"] = {os.path.basename(x): hashlib.sha256(open(x, "rb").read()).hexdigest()[:16] for x in (figi_p, tick_p, sic_p)}
json.dump(res, open(os.path.join(OUT, "dl1_mapping_probe.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
