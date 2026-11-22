#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""資料稽核(不看任何預測好壞;回應 Codex 2026-10-23 02:39:18 第 2.1–2.3、5.1 點):walk7 日 K 的補值列、缺價變現、證券身份,實際被 E9 / E9b / FL3 / E6 用到幾次。
背景:walk7 d3_daily.py 第 61 行在 Yahoo 原始開 / 高 / 低缺值或 ≤ 0 時,用當天還原收盤補;原始回應沒有保存 → 「哪幾列是補的」已無法逐列確認。
  F_O    = 還原開盤 == 還原收盤(位元相同)→ 補開盤的**上界**(真的開盤 = 收盤也會被算進來)
  F_FLAT = 開高低收四價相同;F_V0 = 成交量 0;F_SYN = F_FLAT 且 F_V0(最像「沒有交易」的列)
身份:比對 S&P 500 名單當年的公司(CIK、名稱)和 Yahoo 現在這個代號的公司名稱;同代號換公司、而且價格在名單年份裡有資料 → 標「身份錯接」。
用法:python3 -I x9_price_audit.py SCRATCH   → SCRATCH/em/out/x9_price_audit.json、x9_identity.csv、x9_flagged_picks.csv(另有全部選股的 x9_flag_usage_e9.csv,不進 repo)"""
import csv, difflib, gzip, json, os, pickle, re, sys
from collections import Counter, defaultdict
import numpy as np, pandas as pd

ROOT = sys.argv[1]; OUT = os.path.join(ROOT, "em", "out")
D = pickle.load(gzip.open(os.path.join(ROOT, "w7", "data", "daily.pkl.gz"))); B = D["bars"]; YMAP = D["ymap"]
U = json.load(open(os.path.join(ROOT, "wt", "research", "walk7_2026-10-21", "out", "universe.json")))
SP = json.load(open(os.path.join(ROOT, "w7", "data", "sp500_jan1.json")))
CAL = list(B["SPY"]["d"]); HOLD_FROM = "2026-07-01"
IDX = {s: {d: k for k, d in enumerate(B[s]["d"])} for s in B}
FLAG = {}; PRE = {}                       # PRE = 2026-07-01 以前的列(保留季 H 的列不算進任何彙總)
for s, b in B.items():
    o, h, l, ac, c, v = b["x"].T
    fo = o == ac; ff = (o == h) & (h == l) & (l == ac); fv = v == 0
    FLAG[s] = {"O": fo, "FLAT": ff, "V0": fv, "SYN": ff & fv, "H": h == np.maximum(o, ac), "L": l == np.minimum(o, ac)}
    PRE[s] = np.array([d < HOLD_FROM for d in b["d"]])
res = {"說明": __doc__.split("\n")[0]}

# ---------- A. 列層級 ----------
tot = int(sum(PRE[s].sum() for s in B))
cnt = {k: int(sum((FLAG[s][k] & PRE[s]).sum() for s in B)) for k in ("O", "FLAT", "V0", "SYN", "H", "L")}
by_year = Counter(); by_sym = Counter()
for s, b in B.items():
    m = FLAG[s]["O"] & PRE[s]
    for d in np.array(b["d"])[m]:
        by_year[d[:4]] += 1
    by_sym[s] = int(m.sum())
top8 = sum(v for _, v in by_sym.most_common(8))
res["A 列層級(只算 2026-07-01 以前)"] = {"總列數": tot, "F_O 開盤=收盤(補值上界)": cnt["O"], "F_FLAT 四價相同": cnt["FLAT"], "F_V0 量 0": cnt["V0"], "F_SYN 四價相同且量 0": cnt["SYN"],
                "F_H 高 = max(開, 收)(補高價的上界;真的沒有上影線也算)": cnt["H"], "F_L 低 = min(開, 收)(補低價的上界;真的沒有下影線也算)": cnt["L"],
                "比例%": {k: round(100 * cnt[k] / tot, 2) for k in ("O", "H", "L")}, "F_O 依年": dict(sorted(by_year.items())),
                "F_O 最多的 15 檔": by_sym.most_common(15), "F_O 前 8 檔佔%": round(100 * top8 / cnt["O"], 1),
                "F_O 的代號數": sum(1 for s in B if (FLAG[s]["O"] & PRE[s]).any())}

# ---------- B. 身份 ----------
STOP = {"inc", "corp", "corporation", "company", "co", "plc", "ltd", "limited", "holdings", "holding", "group", "the", "class", "a", "b", "c",
        "common", "stock", "shares", "sa", "nv", "ag", "se", "lp", "llc", "trust", "international", "technologies", "technology", "and", "of"}


def norm(n):
    return [t for t in re.sub(r"[^a-z0-9 ]", " ", (n or "").lower().replace("&", " and ")).split() if t not in STOP]


def same_name(a, b):
    ta, tb = norm(a), norm(b)
    if not ta or not tb:
        return None
    if set(t for t in ta if len(t) >= 4) & set(t for t in tb if len(t) >= 4):
        return True
    return difflib.SequenceMatcher(None, " ".join(ta), " ".join(tb)).ratio() >= 0.6


latest = {}                      # cik → (年, 代號, 名稱) 名單裡最後一次出現
for Y in sorted(SP, key=int):
    for m in SP[Y]:
        if m.get("cik"):
            latest[m["cik"]] = (Y, m["sym"], m.get("name"))
cik_2026 = {YMAP.get(m["sym"], m["sym"]): m.get("cik") for m in SP.get("2026", [])}
ident = []                       # 每個 (年, B 代號):當年名單的公司 vs Yahoo 現在的公司
for Y in sorted(U, key=int):
    mem = defaultdict(list)
    for m in SP[Y]:
        mem[YMAP.get(m["sym"], m["sym"])].append(m)
    for s in U[Y]["sp"]:
        ms = mem.get(s, [])
        yname = B[s].get("name", "") if s in B else ""
        nbar = sum(1 for d in B[s]["d"] if d[:4] == Y) if s in B else 0
        for m in ms:
            lt = latest.get(m.get("cik"), (Y, m["sym"], m.get("name")))
            ok_name = same_name(yname, lt[2])
            reuse = (s in cik_2026 and m.get("cik") and cik_2026[s] and cik_2026[s] != m.get("cik"))
            if ok_name is False or reuse:
                ident.append({"年": Y, "B代號": s, "名單代號": m["sym"], "名單CIK": m.get("cik"), "名單名稱": m.get("name"), "該CIK最後名稱": lt[2],
                              "Yahoo名稱": yname, "名稱相符": ok_name, "2026同代號CIK不同": bool(reuse), "當年K棒數": nbar,
                              "判定": "身份錯接(當年有價格)" if nbar > 0 else "缺(當年沒有價格,自動排除)"})
# 人工判定(看過 x9_identity.csv 每一組之後寫死;自動規則會把改名 / 控股公司改組也標出來)
TRUE_BAD = {"PARA": ("2021", "2025", "名單是 CBS / ViacomCBS / Paramount Global,價格是 Banzai International(前身是 SPAC)"),
            "IR": ("2017", "2020", "名單是 Ingersoll-Rand plc(2020 改名 Trane,代號 TT),價格是 Gardner Denver / Ingersoll Rand Inc."),
            "SE": ("2017", "2017", "名單是 Spectra Energy,價格是 Sea Ltd(2017-10 才上市)")}
GRAY = {"CB": "2016 名單的舊 Chubb,價格是存續的 Chubb Ltd(前 ACE)", "JCI": "2016 名單的舊 Johnson Controls,價格是合併後的 JCI plc",
        "DD": "2016–17 名單的 E.I. du Pont,價格是 DowDuPont / DuPont de Nemours", "FTI": "2016–17 名單的 FMC Technologies,價格是 TechnipFMC"}
SAME = {"APA", "AVGO", "BLK", "CI", "CNX", "DIS", "KHC", "MDT", "JKHY", "NOV", "OI", "SLB", "IBM", "WAB", "BIO"}
for r in ident:
    s, Y = r["B代號"], r["年"]
    if r["當年K棒數"] == 0:
        r["人工判定"] = "缺:當年沒有價格(自動排除;倖存者偏差)"
    elif s in TRUE_BAD and TRUE_BAD[s][0] <= Y <= TRUE_BAD[s][1]:
        r["人工判定"] = "錯接:" + TRUE_BAD[s][2]
    elif s in GRAY:
        r["人工判定"] = "灰色(承繼公司):" + GRAY[s]
    elif s in SAME:
        r["人工判定"] = "同一家(改名 / 控股公司改組 / 名稱比對誤判)"
    else:
        r["人工判定"] = "未判定"
BAD = {(r["年"], r["B代號"]) for r in ident if r["人工判定"].startswith("錯接")}
cov = {}
for Y in sorted(U, key=int):
    have = [s for s in U[Y]["sp"] if s in B and B[s]["d"][0][:4] <= Y <= B[s]["d"][-1][:4]]   # 序列沒有 > 5 日的中斷,所以範圍涵蓋 = 當年有 K 棒
    bad = [s for s in U[Y]["sp"] if (Y, s) in BAD]
    cov[Y] = {"名單 sp 數": len(U[Y]["sp"]), "當年有價格": len(have), "其中身份錯接": len(bad), "名單外缺(sp_missing)": len(U[Y].get("sp_missing", []))}
res["B 身份"] = {"自動標記列數": len(ident), "人工判定": dict(Counter(r["人工判定"].split(":")[0] for r in ident)),
               "未判定": [(r["年"], r["B代號"]) for r in ident if r["人工判定"] == "未判定"],
               "錯接(年, 代號)": sorted(BAD), "缺(代號, 年)": sorted({(r["B代號"], r["年"]) for r in ident if r["人工判定"].startswith("缺")}), "依年覆蓋": cov,
               "說明": "名稱比對會漏掉「同名不同公司」(例 SNDK);另查 2026 名單同代號的 CIK。序列中斷 > 5 個交易日:0 檔(先前檢查)。"}


with open(os.path.join(OUT, "x9_identity.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(ident[0].keys())); w.writeheader(); w.writerows(ident)


# ---------- C. E9 / E9b 實際用到 ----------
def names(year, sp_only=False):
    u = U[str(year)]; return sorted(set(u["sp"]) if sp_only else set(u["sp"]) | set(u["dv"].keys()))


def price(s, d, col):
    k = IDX[s].get(d)
    return None if k is None else float(B[s]["x"][k, col])


def last_close_upto(s, d):
    dd = B[s]["d"]; k = np.searchsorted(dd, d, side="right") - 1
    return (float(B[s]["x"][k, 3]), dd[k]) if k >= 0 else (None, None)


def features(s, d):
    k = IDX[s].get(d)
    if k is None or k < 253:
        return None
    c = B[s]["x"][:k, 3]
    if np.any(~np.isfinite(c[-253:])) or np.any(c[-253:] <= 0):
        return None
    lr = np.diff(np.log(c[-64:]))
    return {"r252": c[-1] / c[-253] - 1, "m121": c[-22] / c[-253] - 1, "vol": lr.std(ddof=1) * np.sqrt(252)}


def picks_run(rule, kind, start, end, end_list=None):
    days = [d for d in CAL if start <= d <= end]; reb = days[::21]
    if reb[-1] != days[-1]:
        reb.append(days[-1])
    out = []
    for a, b in zip(reb[:-1], reb[1:]):
        lst = {"PIT": lambda: names(int(a[:4])), "PIT_SP": lambda: names(int(a[:4]), True), "END": lambda: end_list[0], "END_SP": lambda: end_list[1]}[kind]()
        cand = {}
        for s in lst:
            if s not in B or price(s, a, 0) is None:
                continue
            f = features(s, a)
            if f:
                cand[s] = f
        if rule == "TSMOM_LONG":
            pick = sorted([s for s in cand if cand[s]["r252"] > 0 and cand[s]["vol"] > 0], key=lambda s: -cand[s]["r252"] / cand[s]["vol"])[:20]
        elif rule == "MOM12_1":
            pick = sorted(cand, key=lambda s: -cand[s]["m121"])[:20]
        else:
            pick = sorted(cand)
        last = b == reb[-1]
        for s in pick:
            ka, kb = IDX[s][a], IDX[s].get(b)
            fw = slice(ka - 253, ka)
            rec = {"規則": rule, "名單": kind, "期間": f"{start}~{end}", "a": a, "b": b, "代號": s,
                   "進場F_O": bool(FLAG[s]["O"][ka]), "進場F_SYN": bool(FLAG[s]["SYN"][ka]),
                   "出場價": "收盤" if last else "開盤", "出場缺價": kb is None,
                   "出場F_O": (bool(FLAG[s]["O"][kb]) if (kb is not None and not last) else False),
                   "出場F_SYN": (bool(FLAG[s]["SYN"][kb]) if kb is not None else False),
                   "特徵窗F_SYN列數": int(FLAG[s]["SYN"][fw].sum()), "身份錯接": (a[:4], s) in BAD}
            if kb is None:
                lc, ld = last_close_upto(s, b)
                rec["出場缺價_最後收盤日"] = ld
                rec["出場缺價_原因"] = "序列在此結束(下市 / 併購 / 改代號)" if B[s]["d"][-1] < b else "當天沒有 K 棒(停牌或資料缺)"
            out.append(rec)
    return out


END_LIST = (names(2026), names(2026, True))
recs = []
for rule in ("TSMOM_LONG", "MOM12_1"):                                  # 等權(EW)每期買全部,另外只算件數
    for kind in ("PIT", "END", "PIT_SP", "END_SP"):
        recs += picks_run(rule, kind, "2024-01-02", "2026-06-30", END_LIST)
    for sp_only, kind in ((False, "PIT"), (True, "PIT_SP")):
        recs += picks_run(rule, kind, "2017-01-03", "2023-12-29")
        for y in range(2017, 2027):
            ys = [d for d in CAL if d[:4] == str(y) and d < HOLD_FROM]
            recs += picks_run(rule, kind, ys[0], ys[-1] if y < 2026 else "2026-06-30")
P = pd.DataFrame(recs)
P.to_csv(os.path.join(OUT, "x9_flag_usage_e9.csv"), index=False)
keycols = ["進場F_O", "進場F_SYN", "出場F_O", "出場F_SYN", "出場缺價", "身份錯接"]
summ = {}
for (rule, kind, per), g in P.groupby(["規則", "名單", "期間"]):
    if per in ("2024-01-02~2026-06-30", "2017-01-03~2023-12-29"):
        summ[f"{rule}|{kind}|{per}"] = {"選股次數": len(g), **{k: int(g[k].sum()) for k in keycols}, "特徵窗有F_SYN的選股": int((g["特徵窗F_SYN列數"] > 0).sum())}
hit = P[P[keycols].any(axis=1) | (P["特徵窗F_SYN列數"] > 0)]
hit.to_csv(os.path.join(OUT, "x9_flagged_picks.csv"), index=False)      # 只留有旗標的選股(全部選股的 x9_flag_usage_e9.csv 約 2 MB,不進 repo)
ew = Counter()                                                          # 等權帳戶:每期買全部候選,算進場列有幾個 F_O
days = [d for d in CAL if "2024-01-02" <= d <= "2026-06-30"]
for a in days[::21]:
    for kind, lst in (("PIT", names(int(a[:4]))), ("END", END_LIST[0])):
        for s in lst:
            if s in B and price(s, a, 0) is not None and features(s, a):
                ew[(kind, "n")] += 1; ew[(kind, "F_O")] += int(FLAG[s]["O"][IDX[s][a]]); ew[(kind, "bad")] += int((a[:4], s) in BAD)
summ["EW 進場(2024-01 ~ 2026-06)"] = {f"{k}|{t}": v for (k, t), v in sorted(ew.items())}
res["C E9/E9b 選股用到"] = {"彙總(連續兩段)": summ,
                         "有任何旗標的選股(去重:代號, a)": sorted({(r["代號"], r["a"]) for _, r in hit.iterrows()}),
                         "出場缺價清單(去重)": sorted({(r["代號"], r["a"], r["b"], r.get("出場缺價_最後收盤日"), r.get("出場缺價_原因")) for _, r in P[P["出場缺價"]].iterrows()})}

# ---------- D. FL3 標籤 ----------
FL = pd.read_pickle(os.path.join(OUT, "fl3_rows.pkl"))
FL = FL[pd.to_datetime(FL["date"]) < HOLD_FROM]                          # 只用 2026-07-01 以前(第一版沒有這行,含保留季 2,377 列;見 E10 更正)
ent_o, ent_syn, win_flat, win_v0, atr_syn, badid, win_l, atr_hl = [], [], [], [], [], [], [], []
for s, g in FL.groupby("sym", sort=False):
    I = g["i"].values.astype(int); n = len(B[s]["d"]); fo, ff, fv, fs = (FLAG[s][k] for k in ("O", "FLAT", "V0", "SYN"))
    j1 = np.minimum(I + 1, n - 1)
    ent_o.append(pd.Series(fo[j1], index=g.index)); ent_syn.append(pd.Series(fs[j1], index=g.index))
    wf = np.zeros(len(I), bool); wv = np.zeros(len(I), bool)
    for k in (1, 2, 3):
        j = np.minimum(I + k, n - 1); wf |= ff[j]; wv |= fv[j]
    win_flat.append(pd.Series(wf, index=g.index)); win_v0.append(pd.Series(wv, index=g.index))
    wl = np.zeros(len(I), bool)
    for k in (1, 2, 3):
        wl |= FLAG[s]["L"][np.minimum(I + k, n - 1)]
    win_l.append(pd.Series(wl, index=g.index))
    hl = FLAG[s]["H"] | FLAG[s]["L"]; ch = np.r_[0, np.cumsum(hl)]
    atr_hl.append(pd.Series((ch[I + 1] - ch[np.maximum(I - 59, 0)]) > 0, index=g.index))
    cs = np.r_[0, np.cumsum(fs)]; lo = np.maximum(I - 59, 0)
    atr_syn.append(pd.Series((cs[I + 1] - cs[lo]) > 0, index=g.index))
    badid.append(pd.Series([(str(d)[:4], s) in BAD for d in g["date"]], index=g.index))
FL["entF_O"] = pd.concat(ent_o); FL["entF_SYN"] = pd.concat(ent_syn); FL["winFLAT"] = pd.concat(win_flat); FL["winV0"] = pd.concat(win_v0)
FL["atrSYN"] = pd.concat(atr_syn); FL["badID"] = pd.concat(badid); FL["winL"] = pd.concat(win_l); FL["atrHL"] = pd.concat(atr_hl)
FL["any"] = FL[["entF_O", "winFLAT", "winV0", "atrSYN", "badID"]].any(axis=1)
ev = FL[(FL.ev_lag >= 0) & (FL.FL3_A60.notna())]


def br(g):
    return round(100 * g.FL3_A60.mean(), 2)


res["D FL3 標籤(只用 2026-07-01 以前)"] = {"說明": "fl3_rows 來自 walk7 S7(w1_build:[i−125, i+20] 量都 > 0、收盤不變 ≤ 2%、i+20 < n)→ 已經用未來 20 天的資料篩過列,所以 winFLAT / winV0 / atrSYN 為 0 是篩選造成的,不代表資料乾淨",
                   "全部列": len(FL), "事件窗列": len(ev),
                   "事件窗 winL(t+1..t+3 有低 = min(開, 收) 的列;補低價上界)": int(ev["winL"].sum()), "事件窗 atrHL(ATR60 窗有高或低等於開收的列)%": round(100 * ev["atrHL"].mean(), 1),
                   **{f"事件窗 {k}": int(ev[k].sum()) for k in ("entF_O", "entF_SYN", "winFLAT", "winV0", "atrSYN", "badID", "any")},
                   **{f"全部列 {k}": int(FL[k].sum()) for k in ("entF_O", "winFLAT", "atrSYN", "badID", "any")},
                   "事件窗 FL3_A60 基準率%:全部 / 去掉有旗標的列": [br(ev), br(ev[~ev["any"]])],
                   "事件窗 entF_O 列的 FL3_A60%": br(ev[ev.entF_O]) if ev.entF_O.any() else None,
                   "身份錯接的事件窗列(代號, 年, 列數)": sorted(Counter((r.sym, str(r.date)[:4]) for r in ev[ev.badID].itertuples()).items())}

# ---------- E. E6 財報跳空 ----------
E = FL[(FL.ev_lag == 0) & (FL.date >= "2016-10-01") & (FL.date < "2026-04-01")]
fo_r = []; fo_r1 = []
for t in E.itertuples():
    k = int(t.i); fo_r.append(bool(FLAG[t.sym]["O"][k])); fo_r1.append(bool(FLAG[t.sym]["O"][min(k + 1, len(B[t.sym]["d"]) - 1)]))
E = E.assign(gF_O=fo_r, eF_O=fo_r1)
gap = np.array([B[t.sym]["x"][int(t.i), 0] / B[t.sym]["x"][int(t.i) - 1, 3] - 1 for t in E.itertuples()]) * 100
E = E.assign(gap=gap)
res["E E6 跳空(反應日 2016-10 ~ 2026-03;查三個旗標:反應日 F_O、進場日 F_O、身份接錯)"] = {"反應日列(2016-10 ~ 2026-03)": len(E), "反應日開盤 F_O": int(E.gF_O.sum()), "進場日開盤 F_O": int(E.eF_O.sum()),
                  "身份錯接": int(E.badID.sum()), "跳空 ≥ 10% 的事件": int((E.gap >= 10).sum()),
                  "跳空 ≥ 10% 且任一旗標": int(((E.gap >= 10) & (E.gF_O | E.eF_O | E.badID)).sum()),
                  "跳空 ≥ 10% 且任一旗標(代號, 日期)": [(t.sym, str(t.date)[:10]) for t in E[(E.gap >= 10) & (E.gF_O | E.eF_O | E.badID)].itertuples()]}
json.dump(res, open(os.path.join(OUT, "x9_price_audit.json"), "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps({k: v for k, v in res.items() if k != "C E9/E9b 選股用到"}, ensure_ascii=False, indent=1, default=str)[:9000])
print(json.dumps(res["C E9/E9b 選股用到"]["彙總(連續兩段)"], ensure_ascii=False, indent=0))
print("flagged picks", len(res["C E9/E9b 選股用到"]["有任何旗標的選股(去重:代號, a)"]), res["C E9/E9b 選股用到"]["有任何旗標的選股(去重:代號, a)"][:40])
print("missing exits", res["C E9/E9b 選股用到"]["出場缺價清單(去重)"])
