#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盤感訓練 I1:做「經驗庫」(2010 起所有買點 / 頂點 + 後來的結果)和「練習題」(2026-07-01 ~ 09-15,不含結果)

用法:python3 research/intuition_2026-10-15/i1_build.py SCRATCH_DIR
輸入:SCRATCH_DIR/data/bars.json.gz(i0_fetch.py)
輸出:
  SCRATCH_DIR/bank.json.gz           經驗庫:每個歷史買點 / 頂點的特徵 + 結果(只有已結束的)
  SCRATCH_DIR/packs/<asof>.json      練習題:和正式盤感測試同格式的資料包(買點 + 頂點),**沒有任何 asof 之後的價格**
  SCRATCH_DIR/sealed/index.json      練習題的索引(算結果用;結果另外由 i3_outcomes.py 只對指定期間算)
規則和正式測試一樣(scripts/astra_data.py sw_series、astra_trades.py 乙 / 丙、astra_ledger.py packet()),全部照抄 import,不改。
  買點題:照網站賣法(乙 / 丙)每邊扣 0.1% 後有沒有賺
  頂點題(新):頂點隔天開盤 → 第 11 天開盤(10 個交易日)有沒有比較低 = 「這個頂是不是真的要跌」
練習題的資料包:每一檔截到 asof、取最後 1,250 根重算訊號(= 正式測試當天會看到的);候選先用全歷史訊號找,再用截斷視窗確認。
"""
import datetime as dt, gzip, json, os, sys
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import astra_data as AD, astra_trades as AT, astra_ledger as LG

S = sys.argv[1]
END = "2026-10-14"; BANK_START = "2010-01-01"; P_START, P_END = "2026-07-01", "2026-09-15"
COST = 0.001; KEEP = AD.KEEP
BARS = json.load(gzip.open(os.path.join(S, "data", "bars.json.gz")))
for s in BARS:
    BARS[s] = [b for b in BARS[s] if b[0] <= END]


def mkt_series(sym):
    B = BARS[sym]; D = [b[0] for b in B]; C = [b[4] for b in B]; out = {}
    for j in range(200, len(C)):
        out[D[j]] = {"r5": LG.pct(C[j], C[j - 5]), "r20": LG.pct(C[j], C[j - 20]), "vs200": LG.pct(C[j], sum(C[j - 199:j + 1]) / 200)}
    return out


MK = {"SPY": mkt_series("SPY"), "QQQ": mkt_series("QQQ")}
R = json.loads(AD.http_get(AD.PUB + "regime.json", 30, 2)); RI = {d: k for k, d in enumerate(R["d"])}


def panic_at(d):
    k = RI.get(d)
    return {"sc": R["sc"][k], "g": R["g"][k], "b": R["b"][k], "c": R["c"][k]} if k is not None else {"sc": None, "note": "大盤恐慌資料 2021-03 才開始"}


def mkt_at(d):
    if d not in MK["SPY"] or d not in MK["QQQ"]:
        return None
    return {"SPY": MK["SPY"][d], "QQQ": MK["QQQ"][d], "panic": panic_at(d)}


FEAT = ("chg1", "gap", "r5", "r20", "r60", "vs50", "vs200", "sma50_up", "pos52", "dd52", "vol20_daily", "vr", "days_since_top", "buys_20d")
SPY_D = [b[0] for b in BARS["SPY"]]
PDAYS = [d for d in SPY_D if P_START <= d <= P_END]

bank = []; cand = {}   # cand[(sym, asof)] = set('buy','top')
for s in sorted(BARS):
    B = BARS[s]; n = len(B)
    if n < 300:
        continue
    W = AD.sw_series(B); D = W["D"]; O = [x[1] for x in B]; sty = AT.style_of(s)
    T = AT.trades(W, O, sty); entries = {t["i"] for t in T}
    kinds = dict(AT.buy_points(W)); tops = set(W["top"])
    for i in sorted(set(kinds) | tops):
        d = D[i]
        if P_START <= d <= P_END:
            if i in kinds: cand.setdefault((s, d), set()).add("buy")
            if i in tops: cand.setdefault((s, d), set()).add("top")
        if d < BANK_START or i < 260:
            continue
        mk = mkt_at(d)
        if mk is None:
            continue
        for q in (["buy"] if i in kinds else []) + (["top"] if i in tops else []):
            p = LG.packet(s, B, W, i, kinds[i] if q == "buy" else "頂", mk, (i in entries) if q == "buy" else False, sty)
            row = {"sym": s, "date": d, "q": q, "kind": p["kind"], "type": p["type"], "style": sty["key"], "displayed": p["displayed_buy"],
                   **{k: p[k] for k in FEAT}, "SPY_r5": mk["SPY"]["r5"], "SPY_r20": mk["SPY"]["r20"], "SPY_vs200": mk["SPY"]["vs200"],
                   "QQQ_r5": mk["QQQ"]["r5"], "QQQ_r20": mk["QQQ"]["r20"], "QQQ_vs200": mk["QQQ"]["vs200"], "panic_sc": mk["panic"].get("sc")}
            if q == "buy":
                dd, why = AT.exit_of(W, O, i, sty)
                if dd is None or dd + 1 >= n:
                    continue
                row.update(exit_date=D[dd + 1], exit_why=why, hold=dd + 1 - (i + 1), ret=AT.ret(O, i + 1, dd + 1, COST), ret0=AT.ret(O, i + 1, dd + 1, 0.0))
                if row["ret"] is None:
                    continue
                row["win"] = row["ret"] > 0
            else:
                if i + 11 >= n or not (O[i + 1] > 0):
                    continue
                row.update(exit_date=D[i + 11], fr10=O[i + 11] / O[i + 1] - 1, fr20=(O[i + 21] / O[i + 1] - 1) if i + 21 < n else None)
                row["win"] = row["fr10"] < 0    # 頂點題:「對」= 10 天後比較低(未來報酬一律用 fr 開頭,不和特徵 r20 撞名)
            bank.append(row)

with gzip.open(os.path.join(S, "bank.json.gz"), "wt", encoding="utf-8") as fh:
    json.dump(bank, fh, separators=(",", ":"))

# ---------------- 練習題:截到 asof、最後 1,250 根重算(= 當天正式測試會看到的資料包)
DI = {s: {b[0]: k for k, b in enumerate(BARS[s])} for s in BARS}
index = []; npk = {}
for asof in PDAYS:
    mk = mkt_at(asof); marks = []
    for (s, d), qs in sorted(cand.items()):
        if d != asof:
            continue
        k = DI[s].get(asof)
        if k is None:
            continue
        Bt = BARS[s][max(0, k - KEEP + 1):k + 1]
        W = AD.sw_series(Bt); i = W["n"] - 1; O = [x[1] for x in Bt]; sty = AT.style_of(s)
        kinds = dict(AT.buy_points(W)); T = AT.trades(W, O, sty)
        if "buy" in qs and i in kinds:
            p = LG.packet(s, Bt, W, i, kinds[i], mk, bool(T and T[-1]["i"] == i), sty)
            p.update(id=f"{asof}:{s}", q="buy", style=sty["key"])
            marks.append(p); index.append({"id": p["id"], "sym": s, "date": asof, "q": "buy", "style": sty["key"], "type": p["type"]})
        if "top" in qs and i in set(W["top"]):
            p = LG.packet(s, Bt, W, i, "頂", mk, False, sty)
            p.pop("displayed_buy", None)
            p["displayed_sell"] = any(t["d"] == i and t["why"] == "頂" for t in T)
            p["rule"] = "頂點題:頂點隔天開盤 → 第 11 天開盤(10 個交易日後)有沒有比較低"
            p.update(id=f"{asof}:{s}:top", q="top", style=sty["key"])
            marks.append(p); index.append({"id": p["id"], "sym": s, "date": asof, "q": "top", "style": sty["key"], "type": p["type"]})
    out = {"asof": asof, "n": len(marks), "n_buy": sum(m["q"] == "buy" for m in marks), "n_top": sum(m["q"] == "top" for m in marks), "marks": marks}
    json.dump(out, open(os.path.join(S, "packs", asof + ".json"), "w"), ensure_ascii=False, indent=0)
    npk[asof] = (out["n_buy"], out["n_top"])
json.dump(index, open(os.path.join(S, "sealed", "index.json"), "w"), ensure_ascii=False)

# ---------------- 摘要(不含練習題的結果)
def rate(rows):
    return None if not rows else round(100 * sum(r["win"] for r in rows) / len(rows), 1)
pre = [r for r in bank if r["exit_date"] < P_START]
summ = {"bank_rows": len(bank), "bank_resolved_before_practice": len(pre),
        "base_rates_before_practice": {f"{q}_{t}": {"n": len([r for r in pre if r["q"] == q and r["type"] == t]),
                                                    "win%": rate([r for r in pre if r["q"] == q and r["type"] == t])}
                                       for q in ("buy", "top") for t in ("stock", "idx")},
        "practice_days": len(PDAYS), "practice_marks": {"buy": sum(v[0] for v in npk.values()), "top": sum(v[1] for v in npk.values())},
        "per_day": npk}
json.dump(summ, open(os.path.join(S, "build_summary.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in summ.items() if k != "per_day"}, ensure_ascii=False, indent=1))
