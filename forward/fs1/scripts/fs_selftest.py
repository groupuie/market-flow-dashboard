#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FS1 自我測試:只用亂數假資料(假的 French 檔、假的資料卡),在暫存資料夾裡跑 prep → validate → seal → score,含正反例。
不需要網路、不碰 git。用法:python3 -I forward/fs1/scripts/fs_selftest.py"""
import os, sys, io, json, copy, shutil, zipfile, tempfile, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
import fs_common as C

RES = []


def check(name, cond):
    RES.append((name, bool(cond))); print(("PASS " if cond else "FAIL ") + name)


def french_zip(path, kind, last, seed=1, future=None):
    """假的 French 檔(格式同真檔);future = {月份字串: {代號: 報酬%}} 可指定特定月份"""
    rng = np.random.default_rng(seed); months = pd.period_range("2000-01", last, freq="M")
    if kind == "ind49":
        lines = ["This file was created using the %s CRSP database." % last.replace("-", ""), "", "  Average Value Weighted Returns -- Monthly", "," + ",".join(f"{c:5s}" for c in C.CODES)]
        for p in months:
            v = rng.normal(0.9, 5, 49)
            if future and str(p) in future:
                v = np.array([future[str(p)][c] for c in C.CODES])
            lines.append(p.strftime("%Y%m") + "," + ",".join(f"{x:7.2f}" for x in v))
        lines += ["", "  Average Equal Weighted Returns -- Monthly", ",x", "200001,1"]
        name = "49_Industry_Portfolios.csv"
    else:
        lines = ["This file was created using the %s CRSP database." % last.replace("-", ""), "The 1-month TBill ...", "The annual TBill return is compounded from the monthly T-bill rates from January to December. ", "", ",Mkt-RF,SMB,HML,RF"]
        for p in months:
            lines.append(p.strftime("%Y%m") + f",{rng.normal(0.6, 4):7.2f},{0:7.2f},{0:7.2f},{0.3:7.2f}")
        lines += ["", " Annual Factors: January-December ", ",Mkt-RF,SMB,HML,RF", "2000,1,1,1,1"]
        name = "F-F_Research_Data_Factors.csv"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(name, "\r\n".join(lines) + "\r\n")
    open(path, "wb").write(buf.getvalue())


def run(script, *args, base):
    env = dict(os.environ, FS1_BASE=base)
    r = subprocess.run([sys.executable, "-I", os.path.join(HERE, script), *args], capture_output=True, text=True, env=env, cwd=base)
    out = r.stdout.strip().splitlines()
    try:
        js = json.loads(r.stdout) if r.stdout.strip().startswith("{") and r.stdout.strip().endswith("}") else json.loads(out[-1])
    except Exception:                                          # noqa: BLE001
        js = {"raw": r.stdout[-500:], "err": r.stderr[-500:]}
    return r.returncode, js


def make_card(pk, prev_sha, rk=None):
    rk = rk or list(pk["s0"]["ranking"])
    claims = [{"id": f"c{i}", "text": f"假事實 {i}", "source_url": f"https://example.com/{i}", "published": "2026-10-15", "consensus": "unknown"} for i in range(1, 7)]
    calls = [{"industry": rk[i], "side": "over", "p_beat_market_3m": 0.6, "horizon_months": 3, "thesis": "假論點", "differs_from_consensus": "假",
              "marginal_buyer": "假", "catalysts": ["假"], "falsifiers": ["假"], "add_if": [], "exit_if": ["假"], "claim_ids": ["c1"]} for i in range(3)]
    calls.append({**calls[0], "industry": rk[-1], "side": "under", "p_beat_market_3m": 0.3})
    w = {c: 0.1 for c in rk[:9]}; w["CASH"] = 0.1
    return {"schema": "fs1-card-v1", "decision_month": pk["decision_month"], "cutoff_utc": pk["cutoff_utc"], "packet_sha256": None,
            "prev_card_sha256": prev_sha, "model": "synthetic-test", "regime_view": "假", "ranking": rk,
            "exp_excess_3m_pct": {c: 5 - 0.2 * i for i, c in enumerate(rk)}, "weights": w, "calls": calls, "claims": claims,
            "notes": {c: "假" for c in rk}, "changes_vs_prev": None if prev_sha is None else "假的變化", "searches_used": 3}


def main():
    # ---- 時間 ----
    T = C.parse_time
    check("決定月:2026-11-01 00:41Z(美東 10/31 晚上)→ 2026-10", str(C.decision_month(T("2026-11-01T00:41:00Z"))) == "2026-10")
    check("決定月:2026-11-02 06:00Z(美東 11/2 凌晨)→ 2026-10", str(C.decision_month(T("2026-11-02T06:00:00Z"))) == "2026-10")
    check("決定月:2026-10-30 19:00Z(最後一個平日收盤前)→ 2026-09", str(C.decision_month(T("2026-10-30T19:00:00Z"))) == "2026-09")
    check("封存期限:2026-10 → 2026-11-02T14:30:00Z", C.iso(C.first_open_utc(pd.Period("2026-10", "M"))) == "2026-11-02T14:30:00Z")
    check("封存期限:2026-12 → 2027-01-01T14:30:00Z(假日不另外處理,偏保守)", C.iso(C.first_open_utc(pd.Period("2026-12", "M"))) == "2027-01-01T14:30:00Z")
    check("封存期限:2027-05 → 2027-06-01T13:30:00Z(夏令時間)", C.iso(C.first_open_utc(pd.Period("2027-05", "M"))) == "2027-06-01T13:30:00Z")
    # ---- 主要檢定的統計函式(不需要 scipy)----
    import fs_score as SC
    check("t 分布雙尾 p:t = 2.0、df = 35 → 0.053308", abs(SC.t_two_sided_p(2.0, 35) - 0.05330765186319679) < 1e-9)
    check("t 分布雙尾 p:t = 1.0、df = 10 → 0.340893", abs(SC.t_two_sided_p(1.0, 10) - 0.34089313230206) < 1e-9)
    fake = [{"decision_month": str(pd.Period("2026-10", "M") + k), "h": h, "late": k == 5, "diff": 0.01 * ((k * 7) % 5 - 2), "top10_claude_pct": 1.0, "top10_s0_pct": 0.5,
             "weights_minus_market_pct": 0.1} for k in range(40) for h in (1, 3, 6)]
    ft = SC.final_test(fake)
    check("主要檢定只用 2026-10 ~ 2029-09 準時的卡(36 − 1 遲到 = 35)", ft["決定月數(主要)"] == 35 and ft["主要 D3"]["n"] == 35 and ft["主要 D3"]["lag"] == 2)
    check("次要 4 個都有、Holm 4 個", len(ft["次要"]) == 4 and len(ft["次要 Holm"]) == 4)
    base = tempfile.mkdtemp(prefix="fs1test_"); fr = os.path.join(base, "fr"); os.makedirs(fr)
    try:
        french_zip(os.path.join(fr, "49_Industry_Portfolios_CSV.zip"), "ind49", "2026-09"); french_zip(os.path.join(fr, "F-F_Research_Data_Factors_CSV.zip"), "ff", "2026-09")
        rc, js = run("fs_prep.py", "--now", "2026-11-02T15:00:00Z", "--french-dir", fr, base=base)
        check("過了 t+1 第一個交易時段 → prep 拒絕", rc == 2)
        rc, js = run("fs_prep.py", "--now", "2026-11-01T00:41:00Z", "--french-dir", fr, base=base)
        check("prep 成功", rc == 0 and js.get("status") == "ok")
        pp = os.path.join(base, "pending", "2026-10.packet.json"); pb = open(pp, "rb").read(); pk = json.loads(pb)
        check("資料包:S0 排序 49 個、視窗 2025-11 ~ 2026-09", len(pk["s0"]["ranking"]) == 49 and pk["s0"]["window"] == ["2025-11", "2026-09"])
        R, _ = C.french_monthly(open(os.path.join(fr, "49_Industry_Portfolios_CSV.zip"), "rb").read(), "Average Value Weighted Returns -- Monthly")
        s0 = C.s0_scores(R, pd.Period("2026-09", "M"))
        check("資料包:S0 排序 = 重算", C.rank_codes(s0) == pk["s0"]["ranking"])
        check("資料包:報酬表 13 個月、49 產業", len(pk["returns_pct"]["months"]) == 13 and len(pk["returns_pct"]["industries"]) == 49)
        # ---- 檢查:正例與反例 ----
        from fs_validate import validate
        good = make_card(pk, None); good["packet_sha256"] = C.sha256_bytes(pb)
        V = lambda c, prev=None: validate(json.dumps(c, ensure_ascii=False).encode("utf-8"), pb, prev)
        check("正例通過", V(good) == [])
        neg = []
        KEY = {'ranking 少一個': 'ranking', 'ranking 重複': 'ranking', 'ranking 有不認得的代號': 'ranking', 'weights 加總不是 1': '加總', '單一權重超過上限': '權重不能超過', '權重是負的': '≥ 0', 'weights 有不認得的代號': '不認得的代號', '預期超額沒有照排序': '由大到小', 'over 不在前 10 名': 'over 必須', 'under 不在後 10 名': 'under 必須', '機率超出 0 ~ 1': 'p_beat_market_3m', 'horizon 超出 1 ~ 6': 'horizon_months', '沒有反證': 'falsifiers', '沒有退出條件': 'exit_if', 'claim_ids 指到不存在的': 'claim_ids 指到', 'over calls 太少': 'over calls', '來源發布時間晚於截止': '晚於截止', '來源網址不是 http(s)': 'source_url', 'consensus 空白': 'consensus', 'claims 太少': 'claims 至少', 'claim id 重複': '重複', 'notes 少一個產業': 'notes', 'note 太長': 'notes', '截止時間沒照抄': 'cutoff_utc', '資料包指紋不對': 'packet_sha256', '決定月不對': 'decision_month', 'schema 不對': 'schema', '搜尋次數超過上限': 'searches_used', '多出欄位': '多出', '缺欄位': '缺欄位', 'model 空白': 'model', '有上一張卡卻沒有 changes_vs_prev': 'changes_vs_prev', 'prev_card_sha256 和帳本不同': 'prev_card_sha256'}
        def bad(name, f, prev=None):
            c = copy.deepcopy(good); f(c); neg.append((name, V(c, prev)))
        bad("ranking 少一個", lambda c: c["ranking"].pop())
        bad("ranking 重複", lambda c: c["ranking"].__setitem__(1, c["ranking"][0]))
        bad("ranking 有不認得的代號", lambda c: c["ranking"].__setitem__(0, "XXX"))
        bad("weights 加總不是 1", lambda c: c["weights"].__setitem__("CASH", 0.3))
        bad("單一權重超過上限", lambda c: (c["weights"].__setitem__(c["ranking"][0], 0.2), c["weights"].__setitem__("CASH", 0.0)))
        bad("權重是負的", lambda c: c["weights"].__setitem__("CASH", -0.1))
        bad("weights 有不認得的代號", lambda c: c["weights"].__setitem__("SPY", 0.0))
        bad("預期超額沒有照排序", lambda c: c["exp_excess_3m_pct"].__setitem__(c["ranking"][5], 99))
        bad("over 不在前 10 名", lambda c: c["calls"][0].__setitem__("industry", c["ranking"][20]))
        bad("under 不在後 10 名", lambda c: c["calls"][3].__setitem__("industry", c["ranking"][20]))
        bad("機率超出 0 ~ 1", lambda c: c["calls"][0].__setitem__("p_beat_market_3m", 1.2))
        bad("horizon 超出 1 ~ 6", lambda c: c["calls"][0].__setitem__("horizon_months", 9))
        bad("沒有反證", lambda c: c["calls"][0].__setitem__("falsifiers", []))
        bad("沒有退出條件", lambda c: c["calls"][0].__setitem__("exit_if", []))
        bad("claim_ids 指到不存在的", lambda c: c["calls"][0].__setitem__("claim_ids", ["c99"]))
        bad("over calls 太少", lambda c: c.__setitem__("calls", c["calls"][:1] + c["calls"][3:]))
        bad("來源發布時間晚於截止", lambda c: c["claims"][0].__setitem__("published", "2026-11-05"))
        bad("來源網址不是 http(s)", lambda c: c["claims"][0].__setitem__("source_url", "ftp://x"))
        bad("consensus 空白", lambda c: c["claims"][0].__setitem__("consensus", ""))
        bad("claims 太少", lambda c: c.__setitem__("claims", c["claims"][:4]))
        bad("claim id 重複", lambda c: c["claims"][1].__setitem__("id", "c1"))
        bad("notes 少一個產業", lambda c: c["notes"].pop(c["ranking"][0]))
        bad("note 太長", lambda c: c["notes"].__setitem__(c["ranking"][0], "長" * 61))
        bad("截止時間沒照抄", lambda c: c.__setitem__("cutoff_utc", "2026-11-01T00:00:00Z"))
        bad("資料包指紋不對", lambda c: c.__setitem__("packet_sha256", "0" * 64))
        bad("決定月不對", lambda c: c.__setitem__("decision_month", "2026-09"))
        bad("schema 不對", lambda c: c.__setitem__("schema", "v0"))
        bad("搜尋次數超過上限", lambda c: c.__setitem__("searches_used", 16))
        bad("多出欄位", lambda c: c.__setitem__("hint", 1))
        bad("缺欄位", lambda c: c.pop("regime_view"))
        bad("model 空白", lambda c: c.__setitem__("model", ""))
        bad("有上一張卡卻沒有 changes_vs_prev", lambda c: c.__setitem__("prev_card_sha256", "a" * 64), prev="a" * 64)
        bad("prev_card_sha256 和帳本不同", lambda c: None, prev="b" * 64)
        for name, errs in neg:
            check(f"反例被擋下:{name}(錯誤訊息含「{KEY[name]}」)", errs != [] and any(KEY[name] in e for e in errs))
        # ---- 封存 ----
        cp = os.path.join(base, "pending", "2026-10.card.json"); open(cp, "w", encoding="utf-8").write(json.dumps(good, ensure_ascii=False))
        rc, js = run("fs_seal.py", cp, "--no-git", base=base)
        check("封存成功", rc == 0 and js.get("status") == "已封存" and not js.get("late"))
        led = C.read_ledger(os.path.join(base, "ledger.jsonl"))
        check("ledger 一列、指紋 = 卡片檔", len(led) == 1 and led[0]["card_sha256"] == C.sha256_file(os.path.join(base, "cards", "2026-10.json")))
        rc, js = run("fs_prep.py", "--now", "2026-11-01T03:00:00Z", "--french-dir", fr, base=base)
        check("同一個月再 prep → 已完成", js.get("status") == "已完成")
        os.makedirs(os.path.join(base, "pending"), exist_ok=True)
        open(cp, "w", encoding="utf-8").write(json.dumps(good, ensure_ascii=False)); shutil.copy(os.path.join(base, "packets", "2026-10.json"), cp.replace(".card.json", ".packet.json"))
        rc, js = run("fs_seal.py", cp, "--no-git", base=base)
        check("已封存的月份不能再封存", rc == 2)
        for x in (cp, cp.replace(".card.json", ".packet.json")):
            os.remove(x)
        # 第二個月:French 多晚一個月(最新 2026-09,決定月 2026-11)
        rc, js = run("fs_prep.py", "--now", "2026-12-01T00:41:00Z", "--french-dir", fr, base=base)
        pp2 = os.path.join(base, "pending", "2026-11.packet.json"); pb2 = open(pp2, "rb").read(); pk2 = json.loads(pb2)
        check("French 多晚一個月:S0 視窗停在 2026-09、落後 2 個月", pk2["s0"]["window"] == ["2025-11", "2026-09"] and pk2["french"]["s0_落後月數"] == 2)
        g2 = make_card(pk2, led[0]["card_sha256"]); g2["packet_sha256"] = C.sha256_bytes(pb2)
        cp2 = os.path.join(base, "pending", "2026-11.card.json"); open(cp2, "w", encoding="utf-8").write(json.dumps(g2, ensure_ascii=False))
        rc, js = run("fs_seal.py", cp2, "--no-git", base=base)
        led = C.read_ledger(os.path.join(base, "ledger.jsonl"))
        check("第二張卡封存、雜湊鏈接上", rc == 0 and len(led) == 2 and led[1]["prev_card_sha256"] == led[0]["card_sha256"])
        # ---- 評分 ----
        rk = good["ranking"]; fut = {}
        for k, p in enumerate(["2026-10", "2026-11", "2026-12", "2027-01", "2027-02", "2027-03", "2027-04"]):
            fut[p] = {c: 3.0 - 0.1 * i for i, c in enumerate(rk)}      # 和 2026-10 卡的排序完全一致 → 3 個月 IC = 1
        french_zip(os.path.join(fr, "49_Industry_Portfolios_CSV.zip"), "ind49", "2027-04", future=fut); french_zip(os.path.join(fr, "F-F_Research_Data_Factors_CSV.zip"), "ff", "2027-04")
        rc, js = run("fs_score.py", "--no-git", "--french-dir", fr, base=base)
        rows = [json.loads(l) for l in open(os.path.join(base, "scores", "scores.jsonl"), encoding="utf-8")]
        r3 = [r for r in rows if r["decision_month"] == "2026-10" and r["h"] == 3][0]
        check("評分:2026-10 的 1 / 3 / 6 個月都有", sorted(r["h"] for r in rows if r["decision_month"] == "2026-10") == [1, 3, 6])
        check("評分:排序完全一致 → IC = 1", abs(r3["ic_claude"] - 1) < 1e-12)
        check("評分:IC 差 = IC Claude − IC S0", abs(r3["diff"] - (r3["ic_claude"] - r3["ic_s0"])) < 1e-12)
        rc, js = run("fs_score.py", "--no-git", "--french-dir", fr, base=base)
        rows2 = [json.loads(l) for l in open(os.path.join(base, "scores", "scores.jsonl"), encoding="utf-8")]
        check("再評一次不重複追加", len(rows2) == len(rows) and js.get("new_scores") == 0)
        cf = os.path.join(base, "cards", "2026-11.json"); b = open(cf, "rb").read(); open(cf, "wb").write(b.replace(b"synthetic-test", b"synthetic-tamp"))
        french_zip(os.path.join(fr, "49_Industry_Portfolios_CSV.zip"), "ind49", "2027-06", future=fut); french_zip(os.path.join(fr, "F-F_Research_Data_Factors_CSV.zip"), "ff", "2027-06")
        rc, js = run("fs_score.py", "--no-git", "--french-dir", fr, base=base)
        check("卡片被改過 → 不評分並回報", any("指紋" in x for x in js.get("problems", [])))
        check("摘要檔存在", os.path.exists(os.path.join(base, "scores", "summary.md")))
    finally:
        shutil.rmtree(base, ignore_errors=True)
    n_ok = sum(ok for _, ok in RES)
    print(json.dumps({"通過": n_ok, "總數": len(RES)}, ensure_ascii=False))
    sys.exit(0 if n_ok == len(RES) else 1)


if __name__ == "__main__":
    main()
