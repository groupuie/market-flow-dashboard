#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪 Astra 盤感測試帳(Claude v2.4 I3;使用者 2026-10-14 23:45「全做」)

每天美股收盤後:網站規則算出的新「買」點(追蹤股 266 檔 + SPY、QQQ),Claude 在還不知道結果時寫「同意 / 不同意」,
鎖進 GitHub 的 astra-ledger 分支;之後照網站賣法自動算對錯,比較「同意的」vs「全部的」。規則見分支裡的 PROTOCOL.md。

用法(在 repo 根目錄):
  python3 scripts/astra_ledger.py prep  [--asof YYYY-MM-DD] [--test]   抓日K、算訊號 → ledger/pending/<asof>.json(要判讀的買點 + 資料包)
  (Claude 讀 pending,寫 ledger/verdicts/<asof>.json)
  python3 scripts/astra_ledger.py lock  [--asof YYYY-MM-DD] [--test]   檢查判讀、加時間與指紋 → marks.jsonl,commit + push
  python3 scripts/astra_ledger.py score                                 重算所有鎖定的買點 → scores.json、summary.md,commit + push
  python3 scripts/astra_ledger.py init                                  第一次:建立 astra-ledger 分支(PROTOCOL.md、universe.txt)
帳本放在 git worktree(預設 /tmp/astra-ledger-wt),不動 main 的任何檔案。只讀公開資料;不碰金鑰。
"""
import argparse, datetime as dt, hashlib, json, os, random, subprocess, sys, time
from zoneinfo import ZoneInfo
import concurrent.futures as cf

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import astra_data as AD      # yahoo()、rp()、sw_series()、last_done()、KEEP、FETCH_DAYS、PUB(和網站同一套)
import astra_trades as AT    # 一次一筆的買 / 賣、乙 / 丙 賣法(= index.html swTradesJS)

ET = ZoneInfo("America/New_York")
BR = "astra-ledger"
WT = os.environ.get("ASTRA_LEDGER_WT", "/tmp/astra-ledger-wt")
COST = 0.001                      # 主判定:每邊 0.1%
VERSION = "v1"


# ---------------------------------------------------------------- git / worktree
def sh(*a, cwd=None, check=True):
    r = subprocess.run(list(a), cwd=cwd or REPO, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"git 失敗:{' '.join(a)}\n{r.stdout}\n{r.stderr}")
    return r.stdout.strip()


def worktree(create=False):
    """astra-ledger 分支的 worktree;遠端沒有這個分支 → create=True 才建立(孤兒分支)"""
    has_remote = bool(sh("git", "ls-remote", "--heads", "origin", BR, check=False))
    if has_remote:   # 單一分支的 clone 不會自動建 origin/astra-ledger → 明確指定 refspec
        sh("git", "fetch", "-q", "origin", f"+refs/heads/{BR}:refs/remotes/origin/{BR}")
    if os.path.isdir(os.path.join(WT, ".git")) or os.path.isfile(os.path.join(WT, ".git")):
        if has_remote:
            sh("git", "checkout", "-q", "-B", BR, "origin/" + BR, cwd=WT)
        return WT
    sh("git", "worktree", "prune", check=False)
    if has_remote:
        sh("git", "worktree", "add", "-q", "-f", "-B", BR, WT, "origin/" + BR)
    elif create:
        sh("git", "worktree", "add", "-q", "-f", "--detach", WT)
        sh("git", "checkout", "-q", "--orphan", BR, cwd=WT)
        sh("git", "rm", "-rq", "--cached", ".", cwd=WT, check=False)
        for f in os.listdir(WT):
            if f != ".git":
                p = os.path.join(WT, f)
                subprocess.run(["rm", "-rf", p])
    else:
        raise SystemExit("遠端還沒有 astra-ledger 分支:先跑 `python3 scripts/astra_ledger.py init`")
    return WT


def commit_push(msg, paths):
    for p in paths:
        sh("git", "add", "--", p, cwd=WT)
    if not sh("git", "status", "--porcelain", cwd=WT):
        print("沒有變更,不用 commit"); return False
    sh("git", "-c", "user.name=Claude", "-c", "user.email=noreply@anthropic.com", "commit", "-q", "-m",
       msg + "\n\nCo-Authored-By: Claude <noreply@anthropic.com>", cwd=WT)
    for k in range(3):
        r = subprocess.run(["git", "push", "-q", "origin", "HEAD:" + BR], cwd=WT, capture_output=True, text=True)
        if r.returncode == 0:
            print("已推到 origin/" + BR); return True
        sh("git", "fetch", "-q", "origin", f"+refs/heads/{BR}:refs/remotes/origin/{BR}", cwd=WT, check=False)
        sh("git", "rebase", "-q", "origin/" + BR, cwd=WT, check=False); time.sleep(3)
    raise SystemExit("push 失敗:" + r.stderr[-400:])


def J(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)


def sha(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- 資料
def universe():
    p = os.path.join(WT, "universe.txt")
    U = [s.strip() for s in open(p) if s.strip() and not s.startswith("#")]
    return U, sha(open(p, "rb").read())


def fetch(U, asof):
    now = int(time.time()); p1 = now - AD.FETCH_DAYS * 86400
    BARS, FAIL = {}, {}

    def job(s):
        try:
            return s, AD.yahoo(s, p1, now + 86400), None
        except Exception as e:
            return s, None, str(e)[:120]
    with cf.ThreadPoolExecutor(8) as ex:
        for s, b, err in ex.map(job, U):
            if err or not b:
                FAIL[s] = err or "沒有資料"; continue
            b = [x for x in b if x[0] <= asof]
            pb = [[x[0], AD.rp(x[1]), AD.rp(x[2]), AD.rp(x[3]), AD.rp(x[4]), x[5]] for x in b[-AD.KEEP:]]
            if len(pb) >= 30:
                BARS[s] = pb
            else:
                FAIL[s] = "日K不夠"
    return BARS, FAIL


def regime_at(asof):
    try:
        R = json.loads(AD.http_get(AD.PUB + "regime.json", 30, 2))
        if asof in R["d"]:
            i = R["d"].index(asof); return {"sc": R["sc"][i], "g": R["g"][i], "b": R["b"][i], "c": R["c"][i], "src_asof": R["asof"]}
        return {"sc": None, "src_asof": R.get("asof"), "note": "regime.json 還沒更新到這天"}
    except Exception as e:
        return {"sc": None, "note": "regime.json 抓不到:" + str(e)[:80]}


def next_open_utc(asof):
    d = dt.date.fromisoformat(asof) + dt.timedelta(days=1)
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return dt.datetime(d.year, d.month, d.day, 9, 30, tzinfo=ET).astimezone(dt.timezone.utc)


def pct(a, b):
    return None if (a is None or b is None or b == 0) else round(100 * (a / b - 1), 2)


def packet(s, B, W, i, kind, mkt, path_buy, sty):
    """給 Claude 判讀的資料包:只用到第 i 根(= asof)為止"""
    C = [x[4] for x in B]; O = [x[1] for x in B]; V = [x[5] for x in B]; H = [x[2] for x in B]; L = [x[3] for x in B]
    def sma(w):
        return sum(C[i - w + 1:i + 1]) / w if i >= w - 1 else None
    s50, s200 = sma(50), sma(200)
    s50p = sum(C[i - 59:i - 9]) / 50 if i >= 59 else None
    hi = max(H[max(0, i - 251):i + 1]); lo = min(L[max(0, i - 251):i + 1])
    rets = [C[k] / C[k - 1] - 1 for k in range(max(1, i - 19), i + 1)]
    m = sum(rets) / len(rets); vol = (sum((r - m) ** 2 for r in rets) / max(1, len(rets) - 1)) ** 0.5
    av20 = sum(V[i - 20:i]) / 20 if i >= 20 else None
    tops = [k for k in W["top"] if k <= i]; buys = [k for k in sorted(W["bot"] + W["b2"]) if k < i]
    return {"sym": s, "date": B[i][0], "kind": kind, "why": W["why"].get(i, "") or ("收盤 7 天最低、在 50/200 日線上(上行中的回檔)" if kind == "回" else ""),
            "close": C[i], "chg1": pct(C[i], C[i - 1]), "gap": pct(O[i], C[i - 1]), "r5": pct(C[i], C[i - 5]), "r20": pct(C[i], C[i - 20]),
            "r60": pct(C[i], C[i - 60]) if i >= 60 else None, "vs50": pct(C[i], s50), "vs200": pct(C[i], s200),
            "sma50_up": None if s50p is None else bool(s50 >= s50p), "pos52": round(100 * (C[i] - lo) / (hi - lo), 1) if hi > lo else None,
            "dd52": pct(C[i], hi), "vol20_daily": round(100 * vol, 2), "vr": round(V[i] / av20, 2) if av20 else None,
            "days_since_top": (i - tops[-1]) if tops else None, "buys_20d": sum(1 for k in buys if k >= i - 20),
            "closes_30": [round(x, 2) for x in C[max(0, i - 29):i + 1]],
            "rule": AT.STY[sty["key"]]["name"] + ":" + ("頂到了 / 收盤 ≤ 隔天開盤 × 0.92 / 第 20 天" if sty["stop"] else "第一個頂 / 第 40 天"),
            "displayed_buy": path_buy, "market": mkt}


# ---------------------------------------------------------------- prep / lock / score
def cmd_prep(A):
    worktree()
    asof = A.asof or AD.last_done()
    sub = os.path.join("test", asof) if A.test else ""
    marks_path = os.path.join(WT, "marks.jsonl")
    if not A.test and os.path.exists(marks_path) and any(json.loads(l).get("date") == asof for l in open(marks_path) if l.strip()):
        print(f"{asof} 已經鎖過,不用再判讀"); return
    U, usha = universe()
    for k in range(3):   # Yahoo 偶爾晚更新:SPY 還沒有 asof → 等 5 分鐘再試(最多 2 次);休市也會停在這裡(排程當天 13:13 會再跑一次)
        BARS, FAIL = fetch(U, asof)
        if "SPY" in BARS and BARS["SPY"][-1][0] == asof:
            break
        if k == 2:
            raise SystemExit(f"SPY 日K還沒有 {asof}(可能休市或 Yahoo 未更新)→ 這次不判讀")
        print("SPY 還沒有", asof, "→ 等 5 分鐘"); time.sleep(300)
    if len(FAIL) > 0.1 * len(U):
        raise SystemExit(f"失敗太多({len(FAIL)} 檔)→ 不判讀:{list(FAIL.items())[:5]}")
    mk = {}
    for s in ("SPY", "QQQ"):
        B = BARS[s]; C = [x[4] for x in B]; i = len(C) - 1
        mk[s] = {"r5": pct(C[i], C[i - 5]), "r20": pct(C[i], C[i - 20]), "vs200": pct(C[i], sum(C[i - 199:i + 1]) / 200)}
    mk["panic"] = regime_at(asof)
    marks = []
    for s in U:
        B = BARS.get(s)
        if not B or B[-1][0] != asof:
            continue
        W = AD.sw_series(B); n = W["n"]; i = n - 1
        kinds = dict(AT.buy_points(W))
        if i not in kinds:
            continue
        sty = AT.style_of(s); O = [x[1] for x in B]
        T = AT.trades(W, O, sty); path_buy = bool(T and T[-1]["i"] == i)
        p = packet(s, B, W, i, kinds[i], mk, path_buy, sty)
        p["id"] = f"{asof}:{s}"; p["style"] = sty["key"]; p["bars_sha256"] = sha(json.dumps(B, separators=(",", ":")))
        marks.append(p)
    out = {"asof": asof, "version": VERSION, "gen_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "deadline_utc": next_open_utc(asof).strftime("%Y-%m-%dT%H:%M:%SZ"), "universe_sha256": usha, "n_universe": len(U),
           "fail": FAIL, "test": bool(A.test), "n": len(marks), "marks": marks}
    path = os.path.join(WT, sub, "pending", asof + ".json") if sub else os.path.join(WT, "pending", asof + ".json")
    J(path, out)
    vpath = path.replace(os.sep + "pending" + os.sep, os.sep + "verdicts" + os.sep)
    print(json.dumps({"asof": asof, "買點": len(marks), "pending": path, "verdicts 要寫到": vpath,
                      "截止(隔天開盤,UTC)": out["deadline_utc"], "失敗": len(FAIL)}, ensure_ascii=False))


def cmd_lock(A):
    worktree()
    asof = A.asof or AD.last_done()
    base = os.path.join(WT, "test", asof) if A.test else WT
    pp = os.path.join(base, "pending", asof + ".json"); vp = os.path.join(base, "verdicts", asof + ".json")
    P = json.load(open(pp, encoding="utf-8")); V = json.load(open(vp, encoding="utf-8"))
    vm = {m["id"]: m for m in V.get("marks", [])}
    miss = [m["id"] for m in P["marks"] if m["id"] not in vm]
    bad = [k for k, m in vm.items() if m.get("v") not in ("agree", "disagree") or not str(m.get("why", "")).strip()]
    extra = [k for k in vm if k not in {m["id"] for m in P["marks"]}]
    if miss or bad or extra:
        raise SystemExit(f"判讀檔不完整:缺 {miss[:5]}、格式錯 {bad[:5]}、多出 {extra[:5]}")
    if not str(V.get("model", "")).strip():
        raise SystemExit("判讀檔要寫 model(你的模型 ID)")
    now = dt.datetime.now(dt.timezone.utc); late = now >= dt.datetime.fromisoformat(P["deadline_utc"].replace("Z", "+00:00"))
    psha = sha(open(pp, "rb").read()); vsha = sha(open(vp, "rb").read())
    rows = []
    for m in P["marks"]:
        v = vm[m["id"]]
        pv = v.get("p"); pv = None if pv is None else max(0.0, min(1.0, float(pv)))
        rows.append({"id": m["id"], "date": asof, "sym": m["sym"], "kind": m["kind"], "style": m["style"], "displayed_buy": m["displayed_buy"],
                     "panic_sc": (m["market"].get("panic") or {}).get("sc"), "v": v["v"], "p": pv, "why": str(v["why"])[:300],
                     "model": V["model"], "locked_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "late": late, "test": bool(A.test),
                     "pending_sha256": psha, "verdicts_sha256": vsha, "bars_sha256": m["bars_sha256"], "version": P["version"]})
    mp = os.path.join(base, "marks.jsonl") if A.test else os.path.join(WT, "marks.jsonl")
    if not A.test and os.path.exists(mp) and any(json.loads(l).get("date") == asof for l in open(mp) if l.strip()):
        raise SystemExit(f"{asof} 已經鎖過(不重複鎖)")
    with open(mp, "a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    na = sum(r["v"] == "agree" for r in rows)
    rel = lambda p: os.path.relpath(p, WT)
    commit_push(f"{'TEST ' if A.test else ''}lock {asof}:{len(rows)} 個買點(同意 {na} / 不同意 {len(rows) - na}){' LATE' if late else ''}",
                [rel(pp), rel(vp), rel(mp)])
    print(json.dumps({"asof": asof, "鎖定": len(rows), "同意": na, "晚了": late}, ensure_ascii=False))


def cmd_score(A):
    worktree()
    mp = os.path.join(WT, "marks.jsonl")
    M = [json.loads(l) for l in open(mp, encoding="utf-8") if l.strip()] if os.path.exists(mp) else []
    syms = sorted({m["sym"] for m in M})
    asof = AD.last_done()
    BARS, FAIL = fetch(syms, asof) if syms else ({}, {})
    WS = {s: AD.sw_series(B) for s, B in BARS.items()}
    try:
        RG = json.loads(AD.http_get(AD.PUB + "regime.json", 30, 2)); RGm = dict(zip(RG["d"], RG["sc"]))
    except Exception:
        RGm = {}
    out = []
    for m in M:
        r = dict(m); B = BARS.get(m["sym"]); r.update(status="no_data")
        if r.get("panic_sc") is None and m["date"] in RGm:
            r["panic_sc_filled"] = RGm[m["date"]]
        if B:
            W = WS[m["sym"]]; D = W["D"]
            if m["date"] in D:
                i = D.index(m["date"]); O = [x[1] for x in B]
                r["sig_ok"] = i in dict(AT.buy_points(W))
                d, why = AT.exit_of(W, O, i, AT.STY[m["style"]])
                if d is not None and d + 1 < W["n"]:
                    r.update(status="closed", exit_why=why, entry=D[i + 1], exit=D[d + 1], hold=d + 1 - (i + 1),
                             ret0=round(AT.ret(O, i + 1, d + 1, 0.0), 5), ret=round(AT.ret(O, i + 1, d + 1, COST), 5))
                else:
                    r.update(status="open", entry=D[i + 1] if i + 1 < W["n"] else None,
                             unreal=round(B[-1][4] / O[i + 1] - 1, 5) if i + 1 < W["n"] else None)
        out.append(r)
    S = summarize([r for r in out if not r.get("test") and not r.get("late")])
    J(os.path.join(WT, "scores.json"), {"gen_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "data_asof": asof,
                                         "summary": S, "marks": out})
    write_summary(S, asof, len(out))
    commit_push(f"score {asof}:已結束 {S['all']['n']} / 共 {S['n_marks']}", ["scores.json", "summary.md"])


def grp(rows):
    c = [r for r in rows if r.get("status") == "closed"]
    if not c:
        return {"n": 0}
    w = sum(r["ret"] > 0 for r in c); w0 = sum(r["ret0"] > 0 for r in c)
    return {"n": len(c), "win": round(100 * w / len(c), 1), "win_cost0": round(100 * w0 / len(c), 1),
            "mean": round(100 * sum(r["ret"] for r in c) / len(c), 2), "worst": round(100 * min(r["ret"] for r in c), 1)}


def boot_diff(rows, B=2000, seed=20261014):
    """同意 − 不同意 的勝率差,95% 區間(以訊號日期為單位重抽,同一天的點一起抽)"""
    c = [r for r in rows if r.get("status") == "closed"]
    days = sorted({r["date"] for r in c}); byd = {d: [r for r in c if r["date"] == d] for d in days}
    if len(days) < 10:
        return None
    rnd = random.Random(seed); ds = []
    for _ in range(B):
        pick = [x for _ in days for x in byd[rnd.choice(days)]]
        a = [x for x in pick if x["v"] == "agree"]; b = [x for x in pick if x["v"] == "disagree"]
        if a and b:
            ds.append(sum(x["ret"] > 0 for x in a) / len(a) - sum(x["ret"] > 0 for x in b) / len(b))
    ds.sort()
    return [round(100 * ds[int(0.025 * len(ds))], 1), round(100 * ds[int(0.975 * len(ds)) - 1], 1)] if ds else None


def summarize(rows):
    S = {"n_marks": len(rows), "n_open": sum(r.get("status") == "open" for r in rows),
         "all": grp(rows), "agree": grp([r for r in rows if r["v"] == "agree"]), "disagree": grp([r for r in rows if r["v"] == "disagree"]),
         "shown_all": grp([r for r in rows if r["displayed_buy"]]), "shown_agree": grp([r for r in rows if r["displayed_buy"] and r["v"] == "agree"]),
         "ci_agree_minus_disagree": boot_diff(rows)}
    a, al = S["agree"], S["all"]
    ready = al["n"] >= 300 and a["n"] >= 60 and S["disagree"]["n"] >= 60
    if not ready:
        S["decision"] = f"還在累積:已結束 {al['n']} / 300 筆(同意 {a['n']}、不同意 {S['disagree']['n']},各要 ≥ 60)"
    else:
        ok = (a["win"] - al["win"] >= 10) and (a["mean"] > al["mean"]) and S["ci_agree_minus_disagree"] and S["ci_agree_minus_disagree"][0] > 0
        S["decision"] = ("通過:同意組勝率比全部高 ≥ 10 個百分點、平均也比較高、區間不跨 0 → 建議網站只亮同意的點(要使用者點頭)"
                         if ok else "沒通過:照常顯示全部的點;繼續累積到 600 筆再看最後一次")
    return S


def write_summary(S, asof, n):
    f = lambda g: "—" if not g.get("n") else f"{g['n']} 筆 · 勝率 {g['win']}%(不扣成本 {g['win_cost0']}%)· 平均 {g['mean']:+.2f}% · 最慘 {g['worst']}%"
    ci = S["ci_agree_minus_disagree"]
    txt = (f"# 盤感測試成績(自動更新)\n\n- 資料到 {asof} 收盤;鎖定的買點 {S['n_marks']} 個,還沒賣的 {S['n_open']} 個\n"
           f"- **判定**:{S['decision']}\n\n| 組 | 結果(每邊扣 0.1%)|\n|---|---|\n"
           f"| 全部的買點 | {f(S['all'])} |\n| Claude 同意的 | {f(S['agree'])} |\n| Claude 不同意的 | {f(S['disagree'])} |\n"
           f"| 圖上真的會畫的「買」(一次一筆) | {f(S['shown_all'])} |\n| 其中 Claude 同意的 | {f(S['shown_agree'])} |\n\n"
           f"- 同意 − 不同意 的勝率差,95% 區間:{'還不夠算(要 ≥ 10 個交易日)' if not ci else f'{ci[0]} ~ {ci[1]} 個百分點'}\n"
           f"- 規則見 PROTOCOL.md;測試(test/)和晚鎖(隔天開盤後才鎖)的不算\n")
    with open(os.path.join(WT, "summary.md"), "w", encoding="utf-8") as fh:
        fh.write(txt)


def cmd_init(A):
    worktree(create=True)
    import shutil
    shutil.copy(A.universe, os.path.join(WT, "universe.txt"))
    shutil.copy(A.protocol, os.path.join(WT, "PROTOCOL.md"))
    if A.readme:
        shutil.copy(A.readme, os.path.join(WT, "README.md"))
    commit_push("astra-ledger 開帳:PROTOCOL v1 + 名單", ["universe.txt", "PROTOCOL.md"] + (["README.md"] if A.readme else []))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    for c in ("prep", "lock"):
        p = sp.add_parser(c); p.add_argument("--asof", default=""); p.add_argument("--test", action="store_true")
    sp.add_parser("score")
    p = sp.add_parser("init"); p.add_argument("--universe", required=True); p.add_argument("--protocol", required=True); p.add_argument("--readme", default="")
    A = ap.parse_args()
    {"prep": cmd_prep, "lock": cmd_lock, "score": cmd_score, "init": cmd_init}[A.cmd](A)
