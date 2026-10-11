# 價格口徑逐筆檢查表(回應 Astra v0.4 §5 第 4 點:「59/104 沒有逐筆表、無法重現」)
# 拿 Astra v0.3 診斷模型帳本的每一筆成交(研究價 = Alpaca、只除權),對照網站日K同一天的價格(Futu 前復權 / Yahoo 調整後)。
#   ・隔天開盤成交(*_NEXT_OPEN、GAP_STOP)→ 比網站開盤價;滿 63 天收盤(TIME_63_CLOSE)→ 比網站收盤價
#   ・盤中停損(STOP)成交價是停損線、不是某根K棒的價格 → 只檢查「停損線有沒有落在網站那天的高低之間」
# 網站日K = 2026-10-10 17:25 UTC 從 gist 抓的 kline_SYM.json(30 檔;檔案雜湊記在輸出裡)。
import json, os, sys, hashlib, collections
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude-0/-home-claude-market-flow-dashboard/6a667a86-bd96-51e3-8a50-02ea95c10282/scratchpad/v03/site"
T = json.load(open(os.path.join(HERE, "source", "logistic_C1_standardized__price_only__trades.json")))
rows, src, hashes = [], {}, {}
for c in T["trades"]:
    s = c["symbol"]
    if s not in src:
        p = os.path.join(SITE, s + ".json"); b = open(p, "rb").read(); hashes[s] = hashlib.sha256(b).hexdigest()
        k = json.loads(b); src[s] = {"src": k.get("src"), "bars": {x[0]: x for x in k["bars"]}}
    for f in c["fills"]:
        bar = src[s]["bars"].get(f["executionDate"])
        r = {"sym": s, "kind": f["kind"], "date": f["executionDate"], "reason": f["reason"], "research": f["rawPrice"], "siteSrc": src[s]["src"]}
        if bar is None: r["status"] = "網站沒有這天"; rows.append(r); continue
        o, h, l, cl = bar[1], bar[2], bar[3], bar[4]
        if f["reason"] == "STOP":
            r.update(site_low=l, site_high=h, status="停損線在網站高低之間" if l <= f["rawPrice"] <= h else "停損線不在網站高低之間")
        else:
            ref = cl if f["reason"] == "TIME_63_CLOSE" else o
            r.update(site=ref, relDiffPct=round((ref / f["rawPrice"] - 1) * 100, 4), status="比對")
        rows.append(r)
cmp_ = [r for r in rows if r["status"] == "比對"]
ad = sorted(abs(r["relDiffPct"]) for r in cmp_)
th = {t: sum(1 for a in ad if a > t) for t in (0.000001, 0.01, 0.1, 0.5, 1.0, 2.0)}
out = {"fills": len(rows), "compared": len(cmp_), "stopFills": sum(1 for r in rows if r["reason"] == "STOP"),
       "missingOnSite": sum(1 for r in rows if r["status"] == "網站沒有這天"),
       "absDiffPct_median": ad[len(ad) // 2] if ad else None, "absDiffPct_max": ad[-1] if ad else None,
       "countAbove_pct": th, "stopInsideSiteRange": sum(1 for r in rows if r["status"] == "停損線在網站高低之間"),
       "siteSource": dict(collections.Counter(r["siteSrc"] for r in rows)), "siteFileSha256": hashes, "rows": rows}
json.dump(out, open(os.path.join(HERE, "price_basis_check.json"), "w"), ensure_ascii=False, indent=1)
print({k: v for k, v in out.items() if k not in ("rows", "siteFileSha256")})
bys = collections.defaultdict(list)
for r in cmp_: bys[r["sym"]].append(r["relDiffPct"])
print("各檔中位差(%):", {s: sorted(v)[len(v) // 2] for s, v in sorted(bys.items())})
