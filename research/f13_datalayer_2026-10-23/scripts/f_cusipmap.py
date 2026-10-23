#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""13F 資料層 CM1:歷史 CUSIP → 公司(CIK)→ 產業(SIC → French 49)對照。
範圍:任一季占乾淨股票持股 ≥ 0.003% 的 CUSIP(約 6,000 個,每季覆蓋 ≥ 97.7% 市值)。
來源:① EDGAR 全文檢索(SC 13D / 13G 與修正;同一 CUSIP 的申報裡最常出現的 CIK = 標的公司;同一筆檢索結果附各 CIK 的 SIC 與申報日);
      ② OpenFIGI(CUSIP → 代號、證券類型)+ SEC 今天的代號表(代號 → CIK),當備援與 ETF 判定;③ SEC submissions(CIK → 今天的 SIC),只補 ① 沒有 SIC 的。
用法:python3 -I f_cusipmap.py SCRATCH {fts|figi|sic|combine}
SEC 要求的聯絡方式只從本機檔案讀進請求標頭,不印出。"""
import os, sys, json, time, re, glob, zipfile, hashlib, collections, urllib.request, urllib.parse
import duckdb, pandas as pd

S = sys.argv[1]; PH = sys.argv[2]; F = os.path.join(S, "f13"); CM = os.path.join(S, "cm"); RAW = os.path.join(CM, "raw")
for d in ("fts", "sub"):
    os.makedirs(os.path.join(RAW, d), exist_ok=True)
UA = open(os.path.join(S, "w8", ".sec_ua")).read().strip()
THR = 3e-5
U = pd.read_parquet(os.path.join(CM, "cusip_universe.parquet")); U = U[U["mw"] >= THR].reset_index(drop=True)


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


def normalize(c):
    """檢查碼不對、結尾是 0 的,試著把結尾的 0 移回開頭(例:282410000 → 002824100);仍不對就原樣"""
    if cusip_ok(c):
        return c, "ok"
    for k in (1, 2, 3):
        if isinstance(c, str) and len(c) == 9 and c.endswith("0" * k):
            d = "0" * k + c[:9 - k]
            if cusip_ok(d):
                return d, f"移回 {k} 個 0"
    if isinstance(c, str) and 6 <= len(c) < 9:
        d = c.zfill(9)
        if cusip_ok(d):
            return d, "補前導 0"
    return c, "檢查碼不對"


def sec_get(url):
    for k in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:                                  # noqa: BLE001
            err = e; time.sleep(3 * (k + 1))
    raise RuntimeError(str(err)[:80])


if PH == "fts":
    from concurrent.futures import ThreadPoolExecutor

    def one(c):
        q, _ = normalize(c); out = os.path.join(RAW, "fts", f"{c}.json")
        if os.path.exists(out):
            return 0
        url = "https://efts.sec.gov/LATEST/search-index?" + urllib.parse.urlencode({"q": f'"{q}"', "forms": "SC 13G,SC 13G/A,SC 13D,SC 13D/A"})
        try:
            b = sec_get(url)
        except Exception as e:                                  # noqa: BLE001
            b = json.dumps({"error": str(e)}).encode()
        open(out, "wb").write(b); time.sleep(0.4)
        return 1
    done = 0
    with ThreadPoolExecutor(max_workers=6) as ex:                # 6 條線、每條每次後停 0.4 秒:實測每次約 1.5 秒 → 總共約每秒 3 次,低於 SEC 的每秒 10 次
        for k, r in enumerate(ex.map(one, list(U["cusip"]))):
            done += r
            if k % 500 == 0:
                print("fts", k, done, flush=True)
    print("fts done", done, flush=True)

elif PH == "fts2":
    # 第一輪 0 筆的 CUSIP:很多申報把 CUSIP 寫成「931142 10 3」或「931142-10-3」,用分段的寫法再查一次(實測 Walmart 0 → 23 筆)
    from concurrent.futures import ThreadPoolExecutor
    os.makedirs(os.path.join(RAW, "fts2"), exist_ok=True)
    def zero(c):
        try:
            return json.load(open(os.path.join(RAW, "fts", f"{c}.json")))["hits"]["total"]["value"] == 0
        except Exception:                                       # noqa: BLE001
            return True
    todo = [c for c in U["cusip"] if zero(c)]

    def one2(c):
        q, _ = normalize(c); out = os.path.join(RAW, "fts2", f"{c}.json")
        if os.path.exists(out) or len(q) != 9:
            return 0
        url = "https://efts.sec.gov/LATEST/search-index?" + urllib.parse.urlencode({"q": f'"{q[:6]} {q[6:8]} {q[8]}"', "forms": "SC 13G,SC 13G/A,SC 13D,SC 13D/A"})
        try:
            b = sec_get(url)
        except Exception as e:                                  # noqa: BLE001
            b = json.dumps({"error": str(e)}).encode()
        open(out, "wb").write(b); time.sleep(0.4)
        return 1
    with ThreadPoolExecutor(max_workers=6) as ex:
        n = sum(ex.map(one2, todo))
    print("fts2 done", len(todo), n, flush=True)

elif PH == "figi":
    figi_p = os.path.join(F, "map", "openfigi.json"); figi = json.load(open(figi_p)) if os.path.exists(figi_p) else {}
    full_p = os.path.join(CM, "openfigi_full.json"); full = json.load(open(full_p)) if os.path.exists(full_p) else {}
    todo = [c for c in U["cusip"] if c not in full]
    for i in range(0, len(todo), 10):
        batch = todo[i:i + 10]; res = None
        for k in range(4):
            try:
                req = urllib.request.Request("https://api.openfigi.com/v3/mapping", data=json.dumps([{"idType": "ID_CUSIP", "idValue": normalize(c)[0]} for c in batch]).encode(),
                                             headers={"Content-Type": "application/json", "User-Agent": "cm1-map/1.0"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    res = json.loads(r.read()); break
            except Exception:                                   # noqa: BLE001
                time.sleep(20 * (k + 1))
        if res is None:
            continue
        for c, r in zip(batch, res):
            full[c] = [{k_: x.get(k_) for k_ in ("ticker", "name", "securityType", "securityType2", "marketSector", "exchCode")} for x in (r.get("data") or [])][:30]
        if (i // 10) % 20 == 0:
            json.dump(full, open(full_p, "w")); print("figi", i, flush=True)
        time.sleep(2.6)
    json.dump(full, open(full_p, "w")); print("figi done", len(full), flush=True)

elif PH == "sic":
    # 只補 FTS 沒有 SIC 的 CIK(今天的 SIC)
    need = json.load(open(os.path.join(CM, "need_sic.json")))
    for cik in need:
        out = os.path.join(RAW, "sub", f"{cik}.json")
        if os.path.exists(out):
            continue
        try:
            js = json.loads(sec_get(f"https://data.sec.gov/submissions/CIK{cik}.json"))
            rec = {"sic": js.get("sic"), "sicDescription": js.get("sicDescription"), "name": js.get("name"), "tickers": js.get("tickers"), "formerNames": js.get("formerNames")}
        except Exception as e:                                  # noqa: BLE001
            rec = {"error": str(e)[:80]}
        json.dump(rec, open(out, "w")); time.sleep(0.25)
    print("sic done", len(need), flush=True)

elif PH == "combine":
    con = duckdb.connect(); SN = os.path.join(F, "snap")
    names = con.execute(f"SELECT cusip, mode(trim(name)) nm FROM read_parquet('{SN}/snap_D46__*.parquet') WHERE typ = 'SH' AND putcall = '' GROUP BY 1").fetchdf().set_index("cusip")["nm"].to_dict()
    tk_raw = json.load(open(os.path.join(F, "map", "company_tickers.json")))
    tk = {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in tk_raw.values()}
    full = json.load(open(os.path.join(CM, "openfigi_full.json"))) if os.path.exists(os.path.join(CM, "openfigi_full.json")) else {}
    toks = lambda s: set(re.findall(r"[A-Z0-9]{3,}", str(s).upper())) - {"INC", "CORP", "CO", "LTD", "PLC", "THE", "COM", "HOLDINGS", "GROUP", "CLASS", "NEW", "DEL"}
    rows, need = [], set()
    for c in U["cusip"]:
        cn, how = normalize(c); nm = names.get(c, "")
        # ① FTS
        fts_cik = None; sic_hist = []; nhit = 0; share = None; hits = []
        for sub_ in ("fts", "fts2"):
            p = os.path.join(RAW, sub_, f"{c}.json")
            if os.path.exists(p):
                try:
                    hits += json.load(open(p)).get("hits", {}).get("hits", [])
                except Exception:                               # noqa: BLE001
                    pass
        if hits:
            nhit = len(hits); cnt = collections.Counter(); disp = {}
            for h in hits:
                src = h.get("_source", {})
                for j, k in enumerate(src.get("ciks", [])):
                    cnt[k] += 1
                    if k not in disp and j < len(src.get("display_names", [])):
                        disp[k] = src["display_names"][j]
            if cnt:
                top = cnt.most_common(); best = top[0][1]
                cands = [k for k, n in top if n == best]
                if len(cands) > 1:                              # 同票:用 13F 上的發行人名稱比對
                    cands.sort(key=lambda k: -len(toks(disp.get(k, "")) & toks(nm)))
                fts_cik = cands[0]; share = best / nhit
                for h in hits:
                    src = h.get("_source", {})
                    if fts_cik in src.get("ciks", []):
                        j = src["ciks"].index(fts_cik); sics = src.get("sics", [])
                        if len(sics) == len(src["ciks"]) and sics[j] and sics[j] != "0000":     # 只在 SIC 與 CIK 一一對應時採用(有的結果少列沒有 SIC 的申報人,位置會錯開)
                            sic_hist.append((src.get("file_date"), sics[j]))
        # ② OpenFIGI + 今天的代號
        fl = full.get(c) or []
        def pick(d):
            for want in (lambda x: x.get("exchCode") == "US", lambda x: str(x.get("ticker") or "").upper().replace("/", "-") in tk):
                u = [x for x in d if want(x)]
                if u:
                    return u[0]
            return d[0] if d else None
        x = pick(fl); ticker = (x or {}).get("ticker"); stype = (x or {}).get("securityType2") or (x or {}).get("securityType")
        tk_cik = tk.get(str(ticker or "").upper().replace("/", "-"))
        etf = bool(re.search(r"ETP|Fund|Unit Inv|Closed-End", str(stype or ""), re.I)) or bool(re.search(r"\b(ETF|SPDR|ISHARES|TRUST UNIT|INDEX FD|SELECT SECTOR)\b", str(nm).upper()))
        cik = fts_cik or tk_cik; src = "fts" if fts_cik else ("ticker" if tk_cik else None)
        if cik and not sic_hist:
            need.add(cik)
        rows.append({"cusip": c, "cusip_norm": cn, "cusip_fix": how, "name13f": nm, "cik": cik, "cik_source": src, "fts_hits": nhit, "fts_share": share,
                     "tk_cik": tk_cik, "agree": None if not (fts_cik and tk_cik) else fts_cik == tk_cik, "ticker": ticker, "figi_type": stype, "etf": etf,
                     "sic_hist": json.dumps(sorted(sic_hist)), "sw": float(U.loc[U["cusip"] == c, "sw"].iloc[0])})
    json.dump(sorted(need), open(os.path.join(CM, "need_sic.json"), "w"))
    M = pd.DataFrame(rows); M.to_parquet(os.path.join(CM, "cusip_map_stage.parquet"))
    print(json.dumps({"CUSIP": len(M), "有 CIK": int(M["cik"].notna().sum()), "來自 FTS": int((M["cik_source"] == "fts").sum()), "來自代號": int((M["cik_source"] == "ticker").sum()),
                      "兩者都有": int(M["agree"].notna().sum()), "兩者一致": int((M["agree"] == True).sum()), "ETF": int(M["etf"].sum()),  # noqa: E712
                      "需要補今天 SIC 的 CIK": len(need), "CUSIP 修正": M["cusip_fix"].value_counts().to_dict()}, ensure_ascii=False, indent=1))

elif PH == "final":
    M = pd.read_parquet(os.path.join(CM, "cusip_map_stage.parquet"))
    cur = {}
    for f in glob.glob(os.path.join(RAW, "sub", "*.json")):
        js = json.load(open(f)); cur[os.path.basename(f)[:-5]] = js.get("sic") if "error" not in js else None
    M["sic_current"] = [cur.get(c) if isinstance(c, str) else None for c in M["cik"]]
    M["has_sic"] = [isinstance(c, str) and ((len(json.loads(h)) > 0) or (isinstance(sc, str) and sc not in ("", "0000"))) for c, h, sc in zip(M["cik"], M["sic_hist"], M["sic_current"])]
    M.to_parquet(os.path.join(CM, "cusip_map.parquet"))
    con = duckdb.connect(); SN = os.path.join(F, "snap"); con.register("M", M[["cusip", "etf", "cik", "has_sic"]])
    CL = "typ = 'SH' AND putcall = '' AND shares > 0 AND value_fixed > 0 AND NOT coalesce(price_outlier, false) AND NOT unit_undetermined"
    cov = con.execute(f"""WITH q AS (SELECT regexp_extract(filename, '__(.*)\\.parquet', 1) p, cusip, sum(value_fixed) v FROM read_parquet('{SN}/snap_D46__*.parquet', filename=true) WHERE {CL} GROUP BY 1, 2)
        SELECT q.p, sum(v) tot, sum(CASE WHEN M.cusip IS NOT NULL AND NOT M.etf AND M.cik IS NOT NULL AND M.has_sic THEN v ELSE 0 END) / sum(v) ind,
               sum(CASE WHEN M.etf THEN v ELSE 0 END) / sum(v) etf, sum(CASE WHEN M.cusip IS NULL THEN v ELSE 0 END) / sum(v) outside
        FROM q LEFT JOIN M USING (cusip) GROUP BY 1 ORDER BY 1""").fetchdf()
    cov.to_csv(os.path.join(CM, "cm1_coverage.csv"), index=False)
    print(json.dumps({"CUSIP": len(M), "有 CIK": int(M["cik"].notna().sum()), "有 SIC": int(M["has_sic"].sum()), "ETF": int(M["etf"].sum()),
                      "每季對到產業的市值占比%(最低 / 中位 / 最高)": [round(100 * cov["ind"].min(), 2), round(100 * cov["ind"].median(), 2), round(100 * cov["ind"].max(), 2)],
                      "ETF 占比%(中位)": round(100 * cov["etf"].median(), 2), "範圍外(< 0.003%)占比%(中位)": round(100 * cov["outside"].median(), 2)}, ensure_ascii=False, indent=1))
