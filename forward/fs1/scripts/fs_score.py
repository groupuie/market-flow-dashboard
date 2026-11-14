#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FS1 評分:French 資料涵蓋 t+1 ~ t+h 之後,替每張已封存的卡算 1 / 3 / 6 個月的結果,追加到 scores/scores.jsonl(只追加),
重寫 scores/summary.md(描述性)。主要檢定(協定 §7)只在 2026-10 ~ 2029-09 的 3 個月結果都到齊時算一次,寫 scores/final_primary.json(之後不覆寫)。
用法:python3 -I forward/fs1/scripts/fs_score.py [--no-git] [--french-dir 資料夾(自我測試)] [--workdir 資料夾]"""
import os, sys, json, math, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import fs_common as C

PRIMARY = (pd.Period("2026-10", "M"), pd.Period("2029-09", "M")); HS = (1, 3, 6)


def spearman(a, b):
    a, b = pd.Series(a, dtype=float), pd.Series(b, dtype=float)
    m = a.notna() & b.notna()
    if m.sum() < 5 or a[m].nunique() < 2 or b[m].nunique() < 2:
        return None
    return float(a[m].rank().corr(b[m].rank()))


def _betacf(a, b, x):
    """不完全 Beta 函數的連分式(Numerical Recipes);不需要 scipy"""
    tiny = 1e-300; qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0; d = 1.0 - qab * x / qap; d = 1.0 / (d if abs(d) > tiny else tiny); h = d
    for m in range(1, 300):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((qam + m2) * (a + m2)), -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1.0 + aa * d; d = 1.0 / (d if abs(d) > tiny else tiny)
            c = 1.0 + aa / c; c = c if abs(c) > tiny else tiny
            de = d * c; h *= de
        if abs(de - 1.0) < 1e-14:
            break
    return h


def t_two_sided_p(t, df):
    """Student t 雙尾 p = I_{df/(df+t²)}(df/2, 1/2)"""
    if not (t == t) or df <= 0:
        return float("nan")
    x = df / (df + t * t); a, b = df / 2, 0.5
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(a * math.log(x) + b * math.log1p(-x) - lbeta) if 0 < x < 1 else 0.0
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    ib = front * _betacf(a, b, x) / a if x < (a + 1) / (a + b + 2) else 1 - front * _betacf(b, a, 1 - x) / b
    return float(min(1.0, max(0.0, ib)))


def nw_t(d, lag):
    d = np.asarray(d, float); n = len(d); mu = d.mean(); e = d - mu; s = np.dot(e, e) / n
    for L in range(1, lag + 1):
        s += 2 * (1 - L / (lag + 1)) * np.dot(e[L:], e[:-L]) / n
    se = math.sqrt(s / n) if s > 0 else float("nan")
    t = mu / se if se and se == se else float("nan")
    return {"n": n, "mean": mu, "nw_se": se, "t": t, "p_two_sided": t_two_sided_p(t, n - 1), "lag": lag}


def holm(ps):
    k = sorted(ps, key=lambda x: ps[x]); m = len(k); out = {}; run = 0
    for j, key in enumerate(k):
        run = max(run, min(1.0, (m - j) * ps[key])); out[key] = run
    return out


def score_card(card, packet, F, t, h):
    R, MKT, RF = F["R"], F["MKT"], F["RF"]
    ms = [t + k for k in range(1, h + 1)]
    sub = R.loc[ms]; full = sub.notna().all()
    Rh = np.expm1(np.log1p(sub).sum()).where(full)
    mk = float(np.prod([1 + MKT[p] for p in ms]) - 1)
    rc = {c: -i for i, c in enumerate(card["ranking"])}; rs = {c: -i for i, c in enumerate(packet["s0"]["ranking"])}
    icc, ics = spearman(rc, Rh.to_dict()), spearman(rs, Rh.to_dict())
    top = lambda rk: float(np.nanmean([Rh[c] for c in rk[:10]]))
    row = {"decision_month": C.month_str(t), "h": h, "ic_claude": icc, "ic_s0": ics, "diff": None if icc is None or ics is None else icc - ics,
           "top10_claude_pct": 100 * top(card["ranking"]), "top10_s0_pct": 100 * top(packet["s0"]["ranking"]), "market_pct": 100 * mk,
           "n_ind": int(full.sum()), "months": [C.month_str(p) for p in ms]}
    if h == 1:
        w = card["weights"]; p1 = ms[0]
        port = sum(v * (R.at[p1, k] if pd.notna(R.at[p1, k]) else RF[p1]) for k, v in w.items() if k != "CASH") + w.get("CASH", 0) * RF[p1]
        row["weights_port_pct"] = 100 * float(port); row["weights_minus_market_pct"] = 100 * (float(port) - mk)
    if h == 3:
        b = [(x["p_beat_market_3m"] - (1.0 if Rh[x["industry"]] > mk else 0.0)) ** 2 for x in card["calls"] if pd.notna(Rh[x["industry"]])]
        row["brier_calls"] = float(np.mean(b)) if b else None; row["n_calls"] = len(b)
    return row


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--no-git", action="store_true"); ap.add_argument("--french-dir")
    ap.add_argument("--workdir", default=os.path.join(os.path.expanduser("~"), "fs1_work")); a = ap.parse_args()
    if a.french_dir:
        b49 = open(os.path.join(a.french_dir, "49_Industry_Portfolios_CSV.zip"), "rb").read(); bff = open(os.path.join(a.french_dir, "F-F_Research_Data_Factors_CSV.zip"), "rb").read()
        R, v49 = C.french_monthly(b49, "Average Value Weighted Returns -- Monthly"); FF, vff = C.french_monthly(bff, "The annual TBill return")
        F = {"R": R, "MKT": FF["Mkt-RF"] + FF["RF"], "RF": FF["RF"], "ind49_vintage": v49, "ind49_sha256": C.sha256_bytes(b49)}
    else:
        F = C.load_french(a.workdir)
    latest = min(F["R"].index.max(), F["MKT"].index.max())
    os.makedirs(C.SCORES, exist_ok=True); sp = os.path.join(C.SCORES, "scores.jsonl")
    have = set()
    if os.path.exists(sp):
        have = {(r["decision_month"], r["h"]) for r in map(json.loads, filter(str.strip, open(sp, encoding="utf-8")))}
    new, problems = [], []
    for e in C.read_ledger():
        t = pd.Period(e["decision_month"], "M")
        cpath, ppath = os.path.join(C.CARDS, f"{e['decision_month']}.json"), os.path.join(C.PACKETS, f"{e['decision_month']}.json")
        cb, pb = open(cpath, "rb").read(), open(ppath, "rb").read()
        if C.sha256_bytes(cb) != e["card_sha256"] or C.sha256_bytes(pb) != e["packet_sha256"]:
            problems.append(f"{e['decision_month']}:檔案指紋和 ledger 不同(不評分)"); continue
        card, packet = json.loads(cb), json.loads(pb)
        for h in HS:
            if (e["decision_month"], h) in have or t + h > latest:
                continue
            r = score_card(card, packet, F, t, h)
            r.update({"late": e["late"], "model": e["model"], "french_ind49_vintage": F["ind49_vintage"], "french_ind49_sha256": F["ind49_sha256"], "scored_utc": C.iso(C.now_utc())})
            new.append(r)
    if new:
        with open(sp, "a", encoding="utf-8") as f:
            for r in new:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    rows = [json.loads(l) for l in open(sp, encoding="utf-8") if l.strip()] if os.path.exists(sp) else []
    write_summary(rows, latest, problems)
    fin = os.path.join(C.SCORES, "final_primary.json"); final_written = False
    if latest >= PRIMARY[1] + 3 and not os.path.exists(fin):
        json.dump(final_test(rows), open(fin, "w", encoding="utf-8"), ensure_ascii=False, indent=1); final_written = True
    out = {"status": "ok", "french_latest": C.month_str(latest), "new_scores": len(new), "problems": problems, "final_written": final_written}
    if not a.no_git:
        paths = [x for x in (sp, os.path.join(C.SCORES, "summary.md"), fin) if os.path.exists(x)]
        out["commit"] = C.git_commit_push(paths, f"fs1:評分 {len(new)} 列(French {F['ind49_vintage']})")
    print(json.dumps(out, ensure_ascii=False))


def eligible(rows, h):
    return sorted([r for r in rows if r["h"] == h and not r["late"] and PRIMARY[0] <= pd.Period(r["decision_month"], "M") <= PRIMARY[1] and r["diff"] is not None],
                  key=lambda r: r["decision_month"])


def final_test(rows):
    """協定 §7:主要 D3 = IC(Claude, 3m) − IC(S0, 3m) 的平均,NW 落後 2、雙尾 5%;次要 4 個 Holm"""
    e3 = eligible(rows, 3); e1 = eligible(rows, 1); e6 = eligible(rows, 6)
    res = {"協定": "PROTOCOL_FS1.md §7", "主要 D3": nw_t([r["diff"] for r in e3], 2) if len(e3) >= 2 else None, "決定月數(主要)": len(e3)}
    sec = {}
    if len(e1) >= 2:
        sec["D1"] = nw_t([r["diff"] for r in e1], 1)
        sec["權重組合 − 市場(1 個月)"] = nw_t([r["weights_minus_market_pct"] for r in e1], 1)
    if len(e6) >= 2:
        sec["D6"] = nw_t([r["diff"] for r in e6], 5)
    if len(e3) >= 2:
        sec["前 10 名 Claude − S0(3 個月)"] = nw_t([r["top10_claude_pct"] - r["top10_s0_pct"] for r in e3], 2)
    res["次要"] = sec; res["次要 Holm"] = holm({k: v["p_two_sided"] for k, v in sec.items()}) if sec else {}
    return res


def fmt(x, d=3):
    return "—" if x is None or (isinstance(x, float) and x != x) else f"{x:+.{d}f}"


def write_summary(rows, latest, problems):
    L = ["# FS1 往前封存:評分摘要(描述性;主要檢定只在 2029-09 的 3 個月結果到齊後算一次)", "",
         f"- French 最新月份:{C.month_str(latest)};已封存卡:{len(C.read_ledger())} 張(遲到 {sum(e['late'] for e in C.read_ledger())} 張)", ""]
    if problems:
        L += ["- 問題:" + ";".join(problems), ""]
    by = {}
    for r in rows:
        by.setdefault(r["decision_month"], {})[r["h"]] = r
    L += ["| 決定月 | 模型 | IC Claude 3m | IC S0 3m | D1 | D3 | D6 | 前 10 名 Claude − S0(3m,百分點) | 遲到 |", "|---|---|---|---|---|---|---|---|---|"]
    for t in sorted(by):
        g = by[t]; r3 = g.get(3, {}); any_r = next(iter(g.values()))
        L.append(f"| {t} | {any_r.get('model', '')} | {fmt(r3.get('ic_claude'))} | {fmt(r3.get('ic_s0'))} | {fmt(g.get(1, {}).get('diff'))} | {fmt(r3.get('diff'))} | "
                 f"{fmt(g.get(6, {}).get('diff'))} | {fmt(None if not r3 else r3['top10_claude_pct'] - r3['top10_s0_pct'], 2)} | {'是' if any_r.get('late') else ''} |")
    for h in HS:
        e = eligible(rows, h)
        if e:
            L.append(f"\n- h = {h}:{len(e)} 個決定月,D{h} 平均 {fmt(float(np.mean([r['diff'] for r in e])))}(描述性,不是檢定)")
    L += ["", "不是投資建議。"]
    open(os.path.join(C.SCORES, "summary.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
