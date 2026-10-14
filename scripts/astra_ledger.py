#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪 Astra 盤感測試帳 v2(Claude v2.4 I3 → 使用者 2026-10-14 23:45「全做」→ Astra v0.7.1 複核後改成 v2)

每天美股收盤後:網站規則算出的新「買」點(追蹤股 266 檔 + SPY、QQQ),Claude 在還不知道結果時寫「同意 / 不同意」,
鎖進 GitHub 的 astra-ledger 分支;之後照網站賣法自動算對錯。規則(含唯一一次的正式判定)見分支裡的 PROTOCOL.md。

v2 和 v1 的差別(Astra v0.7.1 附錄五):
  - 正式判定只有一次(固定收案批次、等全部成熟),每天只更新數量 / 覆蓋,不輸出「通過 / 不通過」
  - 主效果 = 扣成本後「同意 − 不同意」的平均報酬差(同一天、同一類型內配對),連續交易日區塊重抽
  - 規則程式凍結:prep / lock / score 先核對 engine_manifest.json 的 SHA-256,不一樣就停
  - 每個交易日都有批次紀錄(含 0 個買點、失敗);lock 的檔案一致性嚴格檢查;鎖定後向 GitHub 拿遠端收件時間(receipts/)
  - 交易所休市表;每檔日K要真的到 asof,不到的算失敗;SPY / QQQ 不新鮮就整批失敗
  - 已賣出的結果一旦記錄就不再重算(連用到的 K 線一起存);資料商修訂另記 revisions.jsonl

用法(在 repo 根目錄):
  python3 scripts/astra_ledger.py prep   [--asof YYYY-MM-DD] [--test]   抓日K、算訊號 → pending/<asof>.json + batches/<asof>.json + snap/,commit + push
  (Claude 讀 pending,寫 verdicts/<asof>.json)
  python3 scripts/astra_ledger.py lock   [--asof YYYY-MM-DD] [--test]   檢查判讀、加時間與指紋 → marks.jsonl,commit + push,然後拿遠端收件時間 → receipts/
  python3 scripts/astra_ledger.py score                                  未賣出的買點算到最新;固定批次;成熟後做唯一一次判定 → scores.json、summary.md
  python3 scripts/astra_ledger.py freeze --protocol v2 [--prompt FILE]   寫 engine_manifest.json(開新版本時才用)
  python3 scripts/astra_ledger.py init --universe F --protocol F [--readme F]
帳本放在 git worktree(預設 /tmp/astra-ledger-wt),不動 main 的任何檔案。只讀公開資料;不碰金鑰。
"""
import argparse, datetime as dt, gzip, hashlib, json, os, random, subprocess, sys, time
from zoneinfo import ZoneInfo
import concurrent.futures as cf

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import astra_data as AD      # yahoo()、rp()、sw_series()、KEEP、FETCH_DAYS、PUB、http_get(和網站同一套)
import astra_trades as AT    # 一次一筆的買 / 賣、乙 / 丙 賣法(= index.html swTradesJS)

ET = ZoneInfo("America/New_York")
BR = "astra-ledger"
WT = os.environ.get("ASTRA_LEDGER_WT", "/tmp/astra-ledger-wt")
OWNER_REPO = "groupuie/market-flow-dashboard"
COST = 0.001                      # 主判定:每邊 0.1%
VERSION = "v2"
ENGINE_FILES = ("scripts/astra_ledger.py", "scripts/astra_trades.py", "scripts/astra_data.py")
# 2026 美股休市(= scripts/tech_judge.py HOLIDAYS;半日 11-27、12-24 照常是交易日)
HOLIDAYS = {"2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19",
            "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
            "2027-01-01", "2027-01-18", "2027-02-15"}
# 判定計畫(PROTOCOL v2 §4;改任何一個 = 新版本)
PLAN = {"min_marks": 300, "min_agree": 60, "min_disagree": 60, "max_sessions": 120, "horizon_sessions": 41,
        "unresolved_after": 10, "block_sessions": 5, "boot_draws": 2000, "seed": 20261014, "win_gap_pp": 10.0}


# ---------------------------------------------------------------- 交易日曆
def is_session(d):
    return d.weekday() < 5 and d.isoformat() not in HOLIDAYS


def next_session(d):
    d = d + dt.timedelta(days=1)
    while not is_session(d):
        d += dt.timedelta(days=1)
    return d


def last_done(now=None):
    """最近已收盤的美東交易日(16:15 後當天才算;週末、休市日往前找)"""
    now = now or dt.datetime.now(ET); d = now.date()
    if (now.hour, now.minute) < (16, 15) or not is_session(d):
        d -= dt.timedelta(days=1)
        while not is_session(d):
            d -= dt.timedelta(days=1)
    return d.isoformat()


def deadline_utc(asof):
    """截止 = asof 之後的下一個交易日 09:30 美東(換成 UTC)"""
    n = next_session(dt.date.fromisoformat(asof))
    return dt.datetime(n.year, n.month, n.day, 9, 30, tzinfo=ET).astimezone(dt.timezone.utc)


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def ts(x):
    return x.strftime("%Y-%m-%dT%H:%M:%SZ")


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
                subprocess.run(["rm", "-rf", os.path.join(WT, f)])
    else:
        raise SystemExit("遠端還沒有 astra-ledger 分支:先跑 `python3 scripts/astra_ledger.py init`")
    return WT


def commit_push(msg, paths):
    """commit + push;回傳 commit SHA(沒有變更 → None)"""
    for p in paths:
        sh("git", "add", "--", p, cwd=WT)
    if not sh("git", "status", "--porcelain", cwd=WT):
        print("沒有變更,不用 commit"); return None
    sh("git", "-c", "user.name=Claude", "-c", "user.email=noreply@anthropic.com", "commit", "-q", "-m",
       msg + "\n\nCo-Authored-By: Claude <noreply@anthropic.com>", cwd=WT)
    for k in range(3):
        r = subprocess.run(["git", "push", "-q", "origin", "HEAD:" + BR], cwd=WT, capture_output=True, text=True)
        if r.returncode == 0:
            h = sh("git", "rev-parse", "HEAD", cwd=WT); print("已推到 origin/" + BR, h[:10]); return h
        sh("git", "fetch", "-q", "origin", f"+refs/heads/{BR}:refs/remotes/origin/{BR}", cwd=WT, check=False)
        sh("git", "rebase", "-q", "origin/" + BR, cwd=WT, check=False); time.sleep(3)
    raise SystemExit("push 失敗:" + r.stderr[-400:])


def remote_receipt(commit, tries=4, wait=20):
    """GitHub 事件 API 裡這個 commit 的 PushEvent created_at = 遠端收件時間(第三方時間戳;公開 repo 任何人可查)"""
    for k in range(tries):
        try:
            try:
                raw = subprocess.run(["gh", "api", f"repos/{OWNER_REPO}/events?per_page=50"], capture_output=True, text=True, timeout=60)
                data = json.loads(raw.stdout) if raw.returncode == 0 else None
            except Exception:
                data = None
            if data is None:
                data = json.loads(AD.http_get(f"https://api.github.com/repos/{OWNER_REPO}/events?per_page=50", 30, 1,
                                              {"User-Agent": "astra-ledger", "Accept": "application/vnd.github+json"}))
            for e in data:
                if e.get("type") == "PushEvent" and (e.get("payload") or {}).get("head") == commit:
                    return {"source": "github events api", "event_id": e.get("id"), "remote_received_utc": e.get("created_at"),
                            "ref": e["payload"].get("ref"), "fetched_utc": ts(utcnow())}
        except Exception as ex:
            err = str(ex)[:120]
        time.sleep(wait)
    return {"source": "github events api", "remote_received_utc": None, "note": "事件 API 沒找到這個 commit 的 PushEvent", "fetched_utc": ts(utcnow())}


# ---------------------------------------------------------------- 小工具
def J(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)


def L(path, default=None):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else default


def sha(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode("utf-8")).hexdigest()


def fsha(path):
    return sha(open(path, "rb").read())


def rel(p):
    return os.path.relpath(p, WT)


def base_dir(test, asof):
    return os.path.join(WT, "test", asof) if test else WT


def marks_path(test, asof):
    return os.path.join(base_dir(test, asof), "marks.jsonl")


def read_marks(test=False, asof=""):
    p = marks_path(test, asof)
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if os.path.exists(p) else []


# ---------------------------------------------------------------- 凍結
def engine_hashes():
    return {f: fsha(os.path.join(REPO, f)) for f in ENGINE_FILES}


def check_freeze():
    """規則程式(三支)+ PROTOCOL + 名單的 SHA-256 要和 engine_manifest.json 一樣;不一樣 = 規則變了 → 停(要開新版本就 freeze)"""
    m = L(os.path.join(WT, "engine_manifest.json"))
    if not m:
        raise SystemExit("沒有 engine_manifest.json:先 `python3 scripts/astra_ledger.py freeze --protocol v2`")
    cur = engine_hashes(); bad = [f for f in ENGINE_FILES if cur[f] != m["files"].get(f)]
    if m.get("protocol_sha256") != fsha(os.path.join(WT, "PROTOCOL.md")): bad.append("PROTOCOL.md")
    if m.get("universe_sha256") != fsha(os.path.join(WT, "universe.txt")): bad.append("universe.txt")
    if bad:
        raise SystemExit("規則已經變了,和凍結的不一樣:" + ", ".join(bad) + " → 不跑;要開新版本請用 freeze(舊紀錄保留)")
    if m.get("protocol") != VERSION:
        raise SystemExit(f"凍結的是 {m.get('protocol')},程式是 {VERSION}")
    return m


def cmd_freeze(A):
    worktree()
    m = {"protocol": A.protocol, "frozen_utc": ts(utcnow()), "main_commit": sh("git", "rev-parse", "HEAD"),
         "files": engine_hashes(), "protocol_sha256": fsha(os.path.join(WT, "PROTOCOL.md")),
         "universe_sha256": fsha(os.path.join(WT, "universe.txt")), "plan": PLAN, "cost_per_side": COST}
    if A.prompt:
        import shutil
        shutil.copy(A.prompt, os.path.join(WT, f"prompt_{A.protocol}.md")); m["prompt_sha256"] = fsha(os.path.join(WT, f"prompt_{A.protocol}.md"))
    J(os.path.join(WT, "engine_manifest.json"), m)
    paths = ["engine_manifest.json"] + ([f"prompt_{A.protocol}.md"] if A.prompt else [])
    commit_push(f"freeze {A.protocol}:規則程式與 PROTOCOL 指紋", paths)
    print(json.dumps(m, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------- 資料
def universe():
    p = os.path.join(WT, "universe.txt")
    U = [s.strip() for s in open(p) if s.strip() and not s.startswith("#")]
    return U, fsha(p)


def fetch(U, asof, require_fresh=True):
    """每檔:Yahoo → 照網站四捨五入 → 最後 1,250 根(≤ asof)。require_fresh:最後一根不是 asof → 算失敗(不會悄悄跳過)"""
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
            if len(pb) < 30:
                FAIL[s] = "日K不夠"
            elif require_fresh and pb[-1][0] != asof:
                FAIL[s] = "日K只到 " + pb[-1][0]
            else:
                BARS[s] = pb
    return BARS, FAIL


def regime_fetch():
    try:
        raw = AD.http_get(AD.PUB + "regime.json", 30, 2)
        R = json.loads(raw)
        return R, {"src_asof": R.get("asof"), "src_gen": R.get("gen"), "sha256": sha(raw), "fetched_utc": ts(utcnow())}
    except Exception as e:
        return None, {"note": "regime.json 抓不到:" + str(e)[:80], "fetched_utc": ts(utcnow())}


def regime_at(R, meta, asof):
    if R and asof in R["d"]:
        i = R["d"].index(asof)
        return {"sc": R["sc"][i], "g": R["g"][i], "b": R["b"][i], "c": R["c"][i], **meta}
    return {"sc": None, "note": "regime.json 還沒更新到這天(判讀時沒有這個資訊;事後補的值會另標)", **meta}


def pct(a, b):
    return None if (a is None or b is None or b == 0) else round(100 * (a / b - 1), 2)


def packet(s, B, W, i, kind, mkt, path_buy, sty):
    """給 Claude 判讀的資料包:只用到第 i 根(= asof)為止"""
    C = [x[4] for x in B]; O = [x[1] for x in B]; V = [x[5] for x in B]; H = [x[2] for x in B]; Lo = [x[3] for x in B]
    def sma(w):
        return sum(C[i - w + 1:i + 1]) / w if i >= w - 1 else None
    s50, s200 = sma(50), sma(200)
    s50p = sum(C[i - 59:i - 9]) / 50 if i >= 59 else None
    hi = max(H[max(0, i - 251):i + 1]); lo = min(Lo[max(0, i - 251):i + 1])
    rets = [C[k] / C[k - 1] - 1 for k in range(max(1, i - 19), i + 1)]
    m = sum(rets) / len(rets); vol = (sum((r - m) ** 2 for r in rets) / max(1, len(rets) - 1)) ** 0.5
    av20 = sum(V[i - 20:i]) / 20 if i >= 20 else None
    tops = [k for k in W["top"] if k <= i]; buys = [k for k in sorted(W["bot"] + W["b2"]) if k < i]
    return {"sym": s, "date": B[i][0], "kind": kind, "type": "idx" if s in AT.IDX else "stock",
            "why": W["why"].get(i, "") or ("收盤 7 天最低、在 50/200 日線上(上行中的回檔)" if kind == "回" else ""),
            "close": C[i], "chg1": pct(C[i], C[i - 1]), "gap": pct(O[i], C[i - 1]), "r5": pct(C[i], C[i - 5]), "r20": pct(C[i], C[i - 20]),
            "r60": pct(C[i], C[i - 60]) if i >= 60 else None, "vs50": pct(C[i], s50), "vs200": pct(C[i], s200),
            "sma50_up": None if s50p is None else bool(s50 >= s50p), "pos52": round(100 * (C[i] - lo) / (hi - lo), 1) if hi > lo else None,
            "dd52": pct(C[i], hi), "vol20_daily": round(100 * vol, 2), "vr": round(V[i] / av20, 2) if av20 else None,
            "days_since_top": (i - tops[-1]) if tops else None, "buys_20d": sum(1 for k in buys if k >= i - 20),
            "closes_30": [round(x, 2) for x in C[max(0, i - 29):i + 1]],
            "rule": sty["name"] + ":" + ("頂到了 / 收盤 ≤ 隔天開盤 × 0.92 / 第 20 天" if sty["stop"] else "第一個頂 / 第 40 天"),
            "displayed_buy": path_buy, "market": mkt}


def write_batch(test, asof, status, extra=None, commit=True, msg=""):
    rec = {"asof": asof, "protocol": VERSION, "status": status, "updated_utc": ts(utcnow()), "test": bool(test), **(extra or {})}
    p = os.path.join(base_dir(test, asof), "batches", asof + ".json")
    old = L(p) or {}
    rec["history"] = (old.get("history") or []) + [{"status": status, "utc": rec["updated_utc"]}]
    J(p, rec)
    if commit:
        commit_push(msg or f"{'TEST ' if test else ''}batch {asof}:{status}", [rel(p)])
    return rec


def snap_save(test, asof, sym, B):
    p = os.path.join(base_dir(test, asof), "snap", asof, sym + ".json.gz")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with gzip.open(p, "wt", encoding="utf-8") as fh:
        json.dump({"sym": sym, "asof": asof, "bars": B}, fh, separators=(",", ":"))
    return p


# ---------------------------------------------------------------- prep
def cmd_prep(A):
    worktree(); FR = check_freeze()
    asof = A.asof or last_done()
    if not is_session(dt.date.fromisoformat(asof)):
        raise SystemExit(f"{asof} 不是交易日")
    bp = os.path.join(base_dir(A.test, asof), "batches", asof + ".json"); old = L(bp)
    if old and old.get("status") in ("locked", "no_signals"):
        print(json.dumps({"asof": asof, "已完成": old["status"]}, ensure_ascii=False)); return
    pp0 = os.path.join(base_dir(A.test, asof), "pending", asof + ".json")
    if old and old.get("status") == "pending_verdict" and os.path.exists(pp0) and fsha(pp0) == old.get("pending_sha256"):
        P0 = L(pp0)   # 第一次做好的資料包已經推上去了 → 沿用,不重做(資料包以第一次 commit 的為準)
        print(json.dumps({"asof": asof, "買點": P0["n"], "status": "pending_verdict", "pending": pp0,
                          "verdicts 要寫到": pp0.replace(os.sep + "pending" + os.sep, os.sep + "verdicts" + os.sep),
                          "截止(隔天開盤,UTC)": P0["deadline_utc"], "失敗": len(P0.get("fail") or {}), "note": "沿用已推上去的資料包"}, ensure_ascii=False)); return
    if not A.test and any(m.get("date") == asof for m in read_marks()):
        print(json.dumps({"asof": asof, "已完成": "marks.jsonl 已有這天"}, ensure_ascii=False)); return
    U, usha = universe()
    for k in range(3):   # Yahoo 偶爾晚更新:SPY / QQQ 還沒有 asof → 等 5 分鐘再試(最多 2 次)
        BARS, FAIL = fetch(U, asof)
        if "SPY" in BARS and "QQQ" in BARS:
            break
        if k == 2:
            write_batch(A.test, asof, "failed", {"reason": f"SPY/QQQ 日K還沒有 {asof}(可能 Yahoo 未更新)", "fail": {s: FAIL[s] for s in ("SPY", "QQQ") if s in FAIL}})
            raise SystemExit(f"SPY/QQQ 日K還沒有 {asof} → 這次不判讀(已記失敗批次;下一次排程會再試)")
        print("SPY/QQQ 還沒有", asof, "→ 等 5 分鐘"); time.sleep(300)
    if len(FAIL) > 0.1 * len(U):
        write_batch(A.test, asof, "failed", {"reason": f"失敗 / 不新鮮太多({len(FAIL)} 檔)", "fail": FAIL})
        raise SystemExit(f"失敗太多({len(FAIL)} 檔)→ 不判讀(已記失敗批次):{list(FAIL.items())[:5]}")
    R, rmeta = regime_fetch()
    mk = {}
    for s in ("SPY", "QQQ"):
        B = BARS[s]; C = [x[4] for x in B]; i = len(C) - 1
        mk[s] = {"r5": pct(C[i], C[i - 5]), "r20": pct(C[i], C[i - 20]), "vs200": pct(C[i], sum(C[i - 199:i + 1]) / 200)}
    mk["panic"] = regime_at(R, rmeta, asof)
    marks = []; snaps = []
    for s in U:
        B = BARS.get(s)
        if not B:
            continue
        W = AD.sw_series(B); i = W["n"] - 1
        kinds = dict(AT.buy_points(W))
        if i not in kinds:
            continue
        sty = AT.style_of(s); O = [x[1] for x in B]
        T = AT.trades(W, O, sty); path_buy = bool(T and T[-1]["i"] == i)
        p = packet(s, B, W, i, kinds[i], mk, path_buy, sty)
        p["id"] = f"{asof}:{s}"; p["style"] = sty["key"]; p["bars_sha256"] = sha(json.dumps(B, separators=(",", ":")))
        marks.append(p); snaps.append(snap_save(A.test, asof, s, B))
    for s in ("SPY", "QQQ"):
        snaps.append(snap_save(A.test, asof, s, BARS[s]))
    out = {"asof": asof, "protocol": VERSION, "gen_utc": ts(utcnow()), "deadline_utc": ts(deadline_utc(asof)),
           "universe_sha256": usha, "n_universe": len(U), "n_fresh": len(BARS), "fail": FAIL, "test": bool(A.test),
           "engine_manifest_sha256": fsha(os.path.join(WT, "engine_manifest.json")), "n": len(marks), "marks": marks}
    pp = os.path.join(base_dir(A.test, asof), "pending", asof + ".json"); J(pp, out)
    vp = pp.replace(os.sep + "pending" + os.sep, os.sep + "verdicts" + os.sep)
    status = "no_signals" if not marks else "pending_verdict"
    write_batch(A.test, asof, status, {"n": len(marks), "n_fresh": len(BARS), "n_fail": len(FAIL), "pending_sha256": fsha(pp),
                                       "deadline_utc": out["deadline_utc"]}, commit=False)
    commit_push(f"{'TEST ' if A.test else ''}prep {asof}:{len(marks)} 個買點({status})",
                [rel(pp), rel(bp)] + [rel(x) for x in snaps])
    print(json.dumps({"asof": asof, "買點": len(marks), "status": status, "pending": pp, "verdicts 要寫到": vp,
                      "截止(隔天開盤,UTC)": out["deadline_utc"], "失敗": len(FAIL)}, ensure_ascii=False))


# ---------------------------------------------------------------- lock
def cmd_lock(A):
    worktree(); check_freeze()
    asof = A.asof or last_done()
    bp = os.path.join(base_dir(A.test, asof), "batches", asof + ".json"); batch = L(bp)
    if not batch or batch.get("status") != "pending_verdict":
        raise SystemExit(f"{asof} 的批次不是 pending_verdict(現在:{(batch or {}).get('status')})→ 不鎖")
    pp = os.path.join(base_dir(A.test, asof), "pending", asof + ".json"); vp = pp.replace(os.sep + "pending" + os.sep, os.sep + "verdicts" + os.sep)
    if fsha(pp) != batch.get("pending_sha256"):
        raise SystemExit("pending 檔和批次紀錄的指紋不一樣 → 不鎖")
    P = L(pp); V = L(vp)
    if V is None:
        raise SystemExit("沒有判讀檔:" + vp)
    # 嚴格一致性(Astra v0.7.1 附錄三 P2-6)
    if P.get("asof") != asof or V.get("asof") != asof or P.get("protocol") != VERSION:
        raise SystemExit(f"日期 / 版本不一致:命令 {asof}、pending {P.get('asof')}/{P.get('protocol')}、verdicts {V.get('asof')}")
    pids = [m["id"] for m in P["marks"]]; vlist = V.get("marks") or []; vids = [m.get("id") for m in vlist]
    if len(set(vids)) != len(vids):
        raise SystemExit("判讀檔有重複的 id")
    if set(pids) != set(vids):
        raise SystemExit(f"判讀檔的 id 和 pending 不一樣:缺 {sorted(set(pids) - set(vids))[:5]}、多 {sorted(set(vids) - set(pids))[:5]}")
    if any(not str(i).startswith(asof + ":") for i in pids):
        raise SystemExit("有 mark 的 id 不是這一天")
    vm = {m["id"]: m for m in vlist}
    for k, m in vm.items():
        if m.get("v") not in ("agree", "disagree"): raise SystemExit(f"{k}:v 要是 agree / disagree")
        if not str(m.get("why", "")).strip(): raise SystemExit(f"{k}:why 不能空白")
        if m.get("p") is not None and not (0 <= float(m["p"]) <= 1): raise SystemExit(f"{k}:p 要在 0–1")
    if not str(V.get("model", "")).strip():
        raise SystemExit("判讀檔要寫 model(你的模型 ID)")
    now = utcnow(); dl = dt.datetime.fromisoformat(P["deadline_utc"].replace("Z", "+00:00")); late_local = now >= dl
    psha, vsha, msha = fsha(pp), fsha(vp), fsha(os.path.join(WT, "engine_manifest.json"))
    rows = []
    for m in P["marks"]:
        v = vm[m["id"]]
        rows.append({"id": m["id"], "date": asof, "sym": m["sym"], "kind": m["kind"], "type": m.get("type", "idx" if m["sym"] in AT.IDX else "stock"),
                     "style": m["style"], "displayed_buy": m["displayed_buy"], "panic_sc": (m["market"].get("panic") or {}).get("sc"),
                     "v": v["v"], "p": None if v.get("p") is None else float(v["p"]), "why": str(v["why"])[:300],
                     "model": V["model"], "protocol": VERSION, "locked_local_utc": ts(now), "deadline_utc": P["deadline_utc"],
                     "late_local": late_local, "test": bool(A.test), "pending_sha256": psha, "verdicts_sha256": vsha,
                     "bars_sha256": m["bars_sha256"], "engine_manifest_sha256": msha})
    mp = marks_path(A.test, asof)
    if any(r.get("date") == asof for r in read_marks(A.test, asof)):
        raise SystemExit(f"{asof} 已經鎖過(不重複鎖)")
    with open(mp, "a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    na = sum(r["v"] == "agree" for r in rows)
    write_batch(A.test, asof, "locked", {"n": len(rows), "n_agree": na, "verdicts_sha256": vsha, "locked_local_utc": ts(now), "late_local": late_local}, commit=False)
    h = commit_push(f"{'TEST ' if A.test else ''}lock {asof}:{len(rows)} 個買點(同意 {na} / 不同意 {len(rows) - na}){' LATE' if late_local else ''}",
                    [rel(pp), rel(vp), rel(mp), rel(bp)])
    # 遠端收件時間(第三方時間戳)→ receipts/<asof>.json;late 以它為準,拿不到就標 unverified
    rc = remote_receipt(h) if h else {"remote_received_utc": None, "note": "沒有新的 commit"}
    rc.update({"asof": asof, "lock_commit": h, "deadline_utc": P["deadline_utc"], "locked_local_utc": ts(now), "test": bool(A.test)})
    rr = rc.get("remote_received_utc")
    rc["late"] = (dt.datetime.fromisoformat(rr.replace("Z", "+00:00")) >= dl) if rr else None
    rc["verified"] = bool(rr)
    rp_ = os.path.join(base_dir(A.test, asof), "receipts", asof + ".json"); J(rp_, rc)
    commit_push(f"{'TEST ' if A.test else ''}receipt {asof}:{'遠端收件 ' + rr if rr else '拿不到遠端收件時間'}", [rel(rp_)])
    print(json.dumps({"asof": asof, "鎖定": len(rows), "同意": na, "本機晚了": late_local, "遠端收件": rr, "遠端判定晚了": rc["late"]}, ensure_ascii=False))


# ---------------------------------------------------------------- score
def cmd_score(A):
    worktree(); FR = check_freeze()
    M = [m for m in read_marks() if not m.get("test") and m.get("protocol") == VERSION]
    RCP = {}
    rdir = os.path.join(WT, "receipts")
    if os.path.isdir(rdir):
        for f in os.listdir(rdir):
            r = L(os.path.join(rdir, f)); RCP[r["asof"]] = r
    SC = L(os.path.join(WT, "scores.json"), {"marks": {}})
    prev = SC.get("marks") or {}
    asof = last_done()
    # 1. 還沒結束的買點:重抓這些股票的日K(已結束的不再動)
    todo = {m["id"]: m for m in M if (prev.get(m["id"]) or {}).get("status") != "closed"}
    syms = sorted({m["sym"] for m in todo.values()} | {"SPY"})
    BARS, FAIL = fetch(syms, asof, require_fresh=False)
    spy = [x[0] for x in BARS["SPY"]] if "SPY" in BARS else None
    if not spy:
        raise SystemExit("SPY 抓不到 → 這次不計分")
    R, rmeta = regime_fetch(); RGm = dict(zip(R["d"], R["sc"])) if R else {}
    rev_path = os.path.join(WT, "revisions.jsonl"); revs = []
    out = dict(prev)
    for mid, m in todo.items():
        r = {k: m[k] for k in ("id", "date", "sym", "kind", "type", "style", "displayed_buy", "v", "p", "model", "protocol")}
        rc = RCP.get(m["date"]); r["late"] = (rc.get("late") if rc and rc.get("late") is not None else m.get("late_local")); r["late_verified"] = bool(rc and rc.get("verified"))
        r["panic_sc"] = m.get("panic_sc")
        if r["panic_sc"] is None and m["date"] in RGm:
            r["panic_sc_filled_after"] = RGm[m["date"]]   # 事後補值:判讀時沒有,只當描述
        B = BARS.get(m["sym"])
        if not B or m["date"] not in [x[0] for x in B]:
            r.update(status="no_data", note=FAIL.get(m["sym"], "日K裡沒有訊號日"))
            out[mid] = r; continue
        W = AD.sw_series(B); D = W["D"]; O = [x[1] for x in B]; i = D.index(m["date"])
        r["sig_ok"] = i in dict(AT.buy_points(W))   # 後來重算是否還是買點(只是描述;原鎖定事件不因此刪除)
        # 資料修訂:判讀時存的快照 vs 現在重抓,訊號日收盤差超過 0.05% 就記一筆
        sp = os.path.join(WT, "snap", m["date"], m["sym"] + ".json.gz")
        if os.path.exists(sp):
            try:
                with gzip.open(sp, "rt", encoding="utf-8") as fh:
                    old = json.load(fh)["bars"][-1]
                if old[0] == m["date"] and abs(B[i][4] / old[4] - 1) > 0.0005:
                    revs.append({"id": mid, "field": "close@signal", "snapshot": old[4], "now": B[i][4], "seen_utc": ts(utcnow())})
            except Exception:
                pass
        d, why = AT.exit_of(W, O, i, AT.STY[m["style"]])
        if d is not None and d + 1 < W["n"]:
            r.update(status="closed", exit_why=why, entry=D[i + 1], exit=D[d + 1], hold=d + 1 - (i + 1),
                     entry_open=O[i + 1], exit_open=O[d + 1],
                     ret0=AT.ret(O, i + 1, d + 1, 0.0), ret=AT.ret(O, i + 1, d + 1, COST), closed_utc=ts(utcnow()),
                     bars_used=B[max(0, i - 1):d + 2])   # 結果一旦記錄就不再重算;用到的 K 線一起存,之後任何人可重播
        else:
            si = spy.index(m["date"]) if m["date"] in spy else None
            elapsed = (len(spy) - 1 - si) if si is not None else None
            if elapsed is not None and elapsed > PLAN["horizon_sessions"] + PLAN["unresolved_after"] and i + 1 >= W["n"]:
                r.update(status="unresolved", note="過了最長持有期還沒有進場 K 線")
            else:
                r.update(status="open", entry=D[i + 1] if i + 1 < W["n"] else None, elapsed_sessions=elapsed,
                         unreal=(B[-1][4] / O[i + 1] - 1) if i + 1 < W["n"] else None)
        out[mid] = r
    if revs:
        with open(rev_path, "a", encoding="utf-8") as fh:
            for x in revs:
                fh.write(json.dumps(x, ensure_ascii=False) + "\n")
    # 2. 固定收案批次(只看筆數,和結果無關)
    cohort = L(os.path.join(WT, "cohort.json")) or {"protocol": VERSION, "start": None, "end": None, "end_reason": None}
    formal = [m for m in M if not (RCP.get(m["date"], {}).get("late") if RCP.get(m["date"], {}).get("late") is not None else m.get("late_local"))]
    days = sorted({m["date"] for m in M})
    if days and not cohort["start"]:
        cohort["start"] = days[0]
    if cohort["start"] and not cohort["end"]:
        cum = agree = dis = 0
        for d in days:
            dm = [m for m in formal if m["date"] == d]
            cum += len(dm); agree += sum(x["v"] == "agree" for x in dm); dis += sum(x["v"] == "disagree" for x in dm)
            sessions = spy.index(d) - spy.index(cohort["start"]) + 1 if (d in spy and cohort["start"] in spy) else None
            if cum >= PLAN["min_marks"] and agree >= PLAN["min_agree"] and dis >= PLAN["min_disagree"]:
                cohort.update(end=d, end_reason=f"筆數到了(全部 {cum}、同意 {agree}、不同意 {dis})", fixed_utc=ts(utcnow())); break
            if sessions is not None and sessions >= PLAN["max_sessions"]:
                cohort.update(end=d, end_reason=f"滿 {PLAN['max_sessions']} 個交易日(全部 {cum}、同意 {agree}、不同意 {dis})", fixed_utc=ts(utcnow())); break
    J(os.path.join(WT, "cohort.json"), cohort)
    # 3. 成熟 → 唯一一次判定
    look = L(os.path.join(WT, "look_ledger.json")) or {"protocol": VERSION, "looks": []}
    matured = False
    if cohort["end"] and cohort["end"] in spy:
        after = len(spy) - 1 - spy.index(cohort["end"])
        cm = [out[m["id"]] for m in formal if m["date"] <= cohort["end"] and m["id"] in out]
        pending_open = [x for x in cm if x.get("status") in ("open", "no_data")]
        matured = after >= PLAN["horizon_sessions"] and (not pending_open or after >= PLAN["horizon_sessions"] + PLAN["unresolved_after"])
    status = "FINAL" if look["looks"] else ("MATURED_PENDING_LOOK" if matured else ("MATURING" if cohort["end"] else "COLLECTING"))
    analysis = look["looks"][0] if look["looks"] else None
    if matured and not look["looks"]:
        cm = [out[m["id"]] for m in formal if m["date"] <= cohort["end"] and m["id"] in out]
        analysis = analyze(cm, spy, cohort)
        analysis.update(look_id=1, performed_utc=ts(utcnow()), data_asof=asof, FINAL=True)
        look["looks"].append(analysis); J(os.path.join(WT, "look_ledger.json"), look); status = "FINAL"
    SC = {"gen_utc": ts(utcnow()), "data_asof": asof, "protocol": VERSION, "status": status, "cohort": cohort,
          "counts": counts(out, M, RCP), "marks": out}
    J(os.path.join(WT, "scores.json"), SC)
    write_summary(SC, analysis)
    commit_push(f"score {asof}:{status};已結束 {SC['counts']['closed']} / 鎖定 {SC['counts']['locked']}",
                ["scores.json", "summary.md", "cohort.json"] + (["look_ledger.json"] if os.path.exists(os.path.join(WT, "look_ledger.json")) else [])
                + (["revisions.jsonl"] if os.path.exists(rev_path) else []))
    print(json.dumps({"status": status, **SC["counts"]}, ensure_ascii=False))


def counts(out, M, RCP):
    st = {}
    for r in out.values():
        st[r.get("status", "?")] = st.get(r.get("status", "?"), 0) + 1
    late = sum(1 for m in M if (RCP.get(m["date"], {}).get("late") if RCP.get(m["date"], {}).get("late") is not None else m.get("late_local")))
    return {"locked": len(M), "agree": sum(m["v"] == "agree" for m in M), "disagree": sum(m["v"] == "disagree" for m in M), "late": late,
            "days": len({m["date"] for m in M}), "closed": st.get("closed", 0), "open": st.get("open", 0),
            "no_data": st.get("no_data", 0), "unresolved": st.get("unresolved", 0)}


# ---------------------------------------------------------------- 唯一一次的判定(PROTOCOL v2 §4)
def grp(rows):
    c = [r for r in rows if r.get("status") == "closed"]
    if not c:
        return {"n": 0}
    w = sum(r["ret"] > 0 for r in c); w0 = sum(r["ret0"] > 0 for r in c)
    wins = [r["ret"] for r in c if r["ret"] > 0]; loss = [r["ret"] for r in c if r["ret"] < 0]
    return {"n": len(c), "win": 100 * w / len(c), "win_cost0": 100 * w0 / len(c), "mean": 100 * sum(r["ret"] for r in c) / len(c),
            "avg_win": 100 * sum(wins) / len(wins) if wins else None, "avg_loss": 100 * sum(loss) / len(loss) if loss else None,
            "p05": 100 * sorted(r["ret"] for r in c)[int(0.05 * len(c))], "worst": 100 * min(r["ret"] for r in c)}


def paired_cells(closed):
    """(訊號日, 類型) 格子:同意、不同意都有已結束的筆 → d = mean(同意) − mean(不同意)(扣成本)"""
    cells = {}
    for r in closed:
        cells.setdefault((r["date"], r["type"]), {"agree": [], "disagree": []})[r["v"]].append(r["ret"])
    out = {}
    for (d, t), g in cells.items():
        if g["agree"] and g["disagree"]:
            out.setdefault(d, []).append(sum(g["agree"]) / len(g["agree"]) - sum(g["disagree"]) / len(g["disagree"]))
    return out   # date -> [d_cell,...]


def block_boot(cells, sessions, B, blk, seed):
    """連續交易日區塊重抽(保留跨日關聯;沒有格子的交易日也在日曆上):每次抽 ceil(N/blk) 個長度 blk 的區塊接成一條日曆,取其中有格子的日子的 d 平均"""
    n = len(sessions)
    if n == 0 or not cells:
        return None
    rnd = random.Random(seed); stats = []
    starts = list(range(0, max(1, n - blk + 1)))
    for _ in range(B):
        picked = []
        while len(picked) < n:
            s0 = rnd.choice(starts); picked.extend(sessions[s0:s0 + blk])
        vals = [v for d in picked[:n] for v in cells.get(d, [])]
        if vals:
            stats.append(sum(vals) / len(vals))
    if len(stats) < B * 0.5:
        return None
    stats.sort()
    return {"lo": 100 * stats[int(0.025 * len(stats))], "hi": 100 * stats[int(0.975 * len(stats)) - 1], "draws": len(stats)}


def analyze(cm, spy, cohort):
    closed = [r for r in cm if r.get("status") == "closed"]
    sessions = [d for d in spy if cohort["start"] <= d <= cohort["end"]]
    cells = paired_cells(closed)
    vals = [v for vs in cells.values() for v in vs]
    primary = {"stat_pp": 100 * sum(vals) / len(vals) if vals else None, "cells": len(vals), "days_with_cells": len(cells),
               "ci95": block_boot(cells, sessions, PLAN["boot_draws"], PLAN["block_sessions"], PLAN["seed"])}
    A_, D_, ALL = grp([r for r in closed if r["v"] == "agree"]), grp([r for r in closed if r["v"] == "disagree"]), grp(closed)
    h1 = bool(primary["ci95"] and primary["ci95"]["lo"] > 0)
    h2 = bool(A_.get("n") and ALL.get("n") and (A_["win"] - ALL["win"]) >= PLAN["win_gap_pp"])
    enough = ALL.get("n", 0) >= PLAN["min_marks"] and A_.get("n", 0) >= PLAN["min_agree"] and D_.get("n", 0) >= PLAN["min_disagree"]
    if not enough:
        decision = "INSUFFICIENT"; text = f"樣本不足(已結束 {ALL.get('n', 0)}、同意 {A_.get('n', 0)}、不同意 {D_.get('n', 0)}),只描述、不判定;要再測要開新版本"
    elif h1 and h2:
        decision = "PASS"; text = "通過:同意 − 不同意 的扣成本平均報酬差 95% 區間下界 > 0,而且同意組勝率比全部高 ≥ 10 個百分點 → 建議網站只亮 Claude 同意的買(要使用者點頭才改)"
    else:
        decision = "NO_PASS"; text = "沒通過(" + ("主效果區間跨 0" if not h1 else "勝率差不到 10 個百分點") + "):網站照常;這一批到此為止,要再測要開新版本"
    return {"decision": decision, "text": text, "H1_mean_diff_lb_gt_0": h1, "H2_win_gap_ge_10pp": h2, "enough": enough,
            "primary_paired_mean_diff": primary, "agree": A_, "disagree": D_, "all": ALL,
            "shown_all": grp([r for r in closed if r["displayed_buy"]]), "shown_agree": grp([r for r in closed if r["displayed_buy"] and r["v"] == "agree"]),
            "by_type": {t: {"agree": grp([r for r in closed if r["type"] == t and r["v"] == "agree"]), "all": grp([r for r in closed if r["type"] == t])} for t in ("idx", "stock")},
            "coverage": {"cohort_marks": len(cm), "closed": len(closed), "open": sum(r.get("status") == "open" for r in cm),
                         "no_data": sum(r.get("status") == "no_data" for r in cm), "unresolved": sum(r.get("status") == "unresolved" for r in cm),
                         "approval_rate": sum(r["v"] == "agree" for r in cm) / len(cm) if cm else None},
            "plan": PLAN, "cost_per_side": COST}


def write_summary(SC, analysis):
    c = SC["counts"]; co = SC["cohort"]
    f1 = lambda v: "—" if v is None else f"{v:.1f}"
    f2 = lambda v: "—" if v is None else f"{v:+.2f}"
    txt = [f"# 盤感測試(v2)進度 — 自動更新", "",
           f"- 狀態:**{SC['status']}**(COLLECTING 收案中 / MATURING 收案結束、等最後一筆成熟 / FINAL 已做唯一一次判定)",
           f"- 資料到 {SC['data_asof']} 收盤;鎖定 {c['locked']} 個買點({c['days']} 個交易日;同意 {c['agree']}、不同意 {c['disagree']};晚鎖 {c['late']})",
           f"- 已賣出 {c['closed']}、持有中 {c['open']}、沒資料 {c['no_data']}、無法結案 {c['unresolved']}",
           f"- 收案批次:{co.get('start') or '—'} ~ {co.get('end') or '(還沒固定;筆數到 300 / 同意 60 / 不同意 60,或滿 120 個交易日時固定)'}" + (f"({co.get('end_reason')})" if co.get("end") else ""),
           "- 正式判定只做一次(PROTOCOL v2 §4);在那之前這裡不顯示勝率、不做判定", ""]
    if analysis:
        g = lambda x: "—" if not x.get("n") else f"{x['n']} 筆 · 勝率 {f1(x['win'])}%(不扣成本 {f1(x['win_cost0'])}%)· 平均 {f2(x['mean'])}% · 最慘 {f1(x['worst'])}%"
        p = analysis["primary_paired_mean_diff"]; ci = p["ci95"]
        txt += [f"## 唯一一次判定({analysis['performed_utc']},資料到 {analysis['data_asof']})", "",
                f"- **判定:{analysis['decision']}** — {analysis['text']}",
                f"- 主效果(同一天、同一類型內,同意 − 不同意 的扣成本平均報酬差):{f2(p['stat_pp'])} 個百分點;95% 區間 " + (f"{f2(ci['lo'])} ~ {f2(ci['hi'])}" if ci else "算不出(格子太少)") + f";{p['cells']} 個格子、{p['days_with_cells']} 天",
                "", "| 組 | 結果(每邊扣 0.1%)|", "|---|---|",
                f"| 全部的買點 | {g(analysis['all'])} |", f"| Claude 同意的 | {g(analysis['agree'])} |", f"| Claude 不同意的 | {g(analysis['disagree'])} |",
                f"| 圖上真的會畫的「買」(一次一筆) | {g(analysis['shown_all'])} |", f"| 其中 Claude 同意的 | {g(analysis['shown_agree'])} |",
                f"| 指數:同意 / 全部 | {g(analysis['by_type']['idx']['agree'])} / {g(analysis['by_type']['idx']['all'])} |",
                f"| 個股:同意 / 全部 | {g(analysis['by_type']['stock']['agree'])} / {g(analysis['by_type']['stock']['all'])} |", "",
                f"- 覆蓋:{analysis['coverage']}", "- 每個買點各算一次(同股重疊的點也算);這是事件判斷力的測試,不是帳戶績效"]
    with open(os.path.join(WT, "summary.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(txt) + "\n")


def cmd_init(A):
    worktree(create=True)
    import shutil
    shutil.copy(A.universe, os.path.join(WT, "universe.txt"))
    shutil.copy(A.protocol, os.path.join(WT, "PROTOCOL.md"))
    if A.readme:
        shutil.copy(A.readme, os.path.join(WT, "README.md"))
    commit_push("astra-ledger 開帳:PROTOCOL + 名單", ["universe.txt", "PROTOCOL.md"] + (["README.md"] if A.readme else []))


def _self_test():
    assert next_session(dt.date(2026, 12, 24)).isoformat() == "2026-12-28"          # 聖誕節休市 → 12/28
    assert next_session(dt.date(2026, 11, 25)).isoformat() == "2026-11-27"          # 感恩節
    assert deadline_utc("2026-12-24").isoformat() == "2026-12-28T14:30:00+00:00"
    assert last_done(dt.datetime(2026, 12, 25, 18, 0, tzinfo=ET)) == "2026-12-24"   # 休市日 → 前一個交易日
    assert last_done(dt.datetime(2026, 10, 15, 9, 0, tzinfo=ET)) == "2026-10-14"
    assert last_done(dt.datetime(2026, 10, 14, 16, 30, tzinfo=ET)) == "2026-10-14"
    # 區塊重抽:固定種子可重現;格子為空 → None
    cells = {f"d{i}": [0.01] for i in range(20)}; sess = [f"d{i}" for i in range(30)]
    a = block_boot(cells, sess, 200, 5, 1); b = block_boot(cells, sess, 200, 5, 1)
    assert a == b and abs(a["lo"] - 1.0) < 1e-9 and block_boot({}, sess, 10, 5, 1) is None
    # 唯一一次判定:300 未過 → 301 不會再判(由 look_ledger 控制,這裡測 analyze 本身的門檻)
    rows = [{"id": str(i), "date": f"2026-01-{1 + i % 20:02d}", "type": "stock", "v": "agree" if i < 60 else "disagree", "status": "closed",
             "ret": 0.01 if (i < 7 or i >= 60) else -0.01, "ret0": 0.012, "displayed_buy": True} for i in range(300)]
    spy = [f"2026-01-{d:02d}" for d in range(1, 21)]
    r = analyze(rows, spy, {"start": "2026-01-01", "end": "2026-01-20"})
    assert r["enough"] and r["decision"] in ("NO_PASS", "PASS")
    print("astra_ledger self-test ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    for c in ("prep", "lock"):
        p = sp.add_parser(c); p.add_argument("--asof", default=""); p.add_argument("--test", action="store_true")
    sp.add_parser("score"); sp.add_parser("selftest")
    p = sp.add_parser("freeze"); p.add_argument("--protocol", required=True); p.add_argument("--prompt", default="")
    p = sp.add_parser("init"); p.add_argument("--universe", required=True); p.add_argument("--protocol", required=True); p.add_argument("--readme", default="")
    A = ap.parse_args()
    {"prep": cmd_prep, "lock": cmd_lock, "score": cmd_score, "freeze": cmd_freeze, "init": cmd_init, "selftest": lambda a: _self_test()}[A.cmd](A)
