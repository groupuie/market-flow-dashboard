#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FS1 第 1 步:決定月 t、截止時間、抓 French 49 產業、算同截止的 S0_fwd,寫資料包 pending/{t}.packet.json。
已經封存過 t → 印「已完成」結束。用法:python3 -I forward/fs1/scripts/fs_prep.py [--now ISO時間(只給自我測試)] [--workdir 資料夾]"""
import os, sys, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import fs_common as C

ap = argparse.ArgumentParser(); ap.add_argument("--now"); ap.add_argument("--workdir", default=os.path.join(os.path.expanduser("~"), "fs1_work"))
ap.add_argument("--french-dir", help="自我測試用:改讀這個資料夾的 zip,不下載")
a = ap.parse_args()
now = C.parse_time(a.now) if a.now else C.now_utc()
t = C.decision_month(now); tm = C.month_str(t)
done = {e["decision_month"] for e in C.read_ledger()}
if tm in done:
    print(json.dumps({"status": "已完成", "decision_month": tm}, ensure_ascii=False)); sys.exit(0)
fo = C.first_open_utc(t)
if now >= fo:
    print(json.dumps({"status": "錯誤", "原因": f"已經過了 {C.iso(fo)}(月 {C.month_str(t + 1)} 第一個交易時段),這個月不能再封存"}, ensure_ascii=False)); sys.exit(2)

if a.french_dir:
    b49 = open(os.path.join(a.french_dir, "49_Industry_Portfolios_CSV.zip"), "rb").read(); bff = open(os.path.join(a.french_dir, "F-F_Research_Data_Factors_CSV.zip"), "rb").read()
    R, v49 = C.french_monthly(b49, "Average Value Weighted Returns -- Monthly"); FF, vff = C.french_monthly(bff, "The annual TBill return")
    F = {"R": R, "MKT": FF["Mkt-RF"] + FF["RF"], "RF": FF["RF"], "ind49_vintage": v49, "ff_vintage": vff, "ind49_sha256": C.sha256_bytes(b49), "ff_sha256": C.sha256_bytes(bff)}
else:
    F = C.load_french(a.workdir)
R = F["R"]; latest = R.index.max()
m = min(latest, t - 1)                           # S0 用到 m 為止(m = t−1 時就是 SR1 的 S0;French 晚一個月時是 R7 式的 j−13 ~ j−3)
s0 = C.s0_scores(R, m); rk = C.rank_codes(s0)
months = [p for p in R.index if m - 12 <= p <= m]
cum = lambda h: np.expm1(np.log1p(R[(R.index > m - h) & (R.index <= m)]).sum(min_count=h))
prev = C.read_ledger()[-1] if C.read_ledger() else None
pk = {"schema": "fs1-packet-v1", "decision_month": tm, "cutoff_utc": C.iso(now), "first_open_utc": C.iso(fo),
      "french": {k: F[k] for k in ("ind49_vintage", "ind49_sha256", "ff_vintage", "ff_sha256")} | {"latest_month": C.month_str(latest), "s0_end_month": C.month_str(m),
                 "s0_落後月數": int((t - m).n) if hasattr(t - m, "n") else None},
      "s0": {"說明": "S0_fwd = 月 m−10 ~ m 共 11 個月的累計報酬,m = min(French 最新月, t−1);同分照欄位順序",
             "window": [C.month_str(m - 10), C.month_str(m)], "ranking": rk,
             "values_pct": {c: (None if pd.isna(s0[c]) else round(100 * float(s0[c]), 4)) for c in C.CODES}},
      "returns_pct": {"months": [C.month_str(p) for p in months],
                      "industries": {c: [None if pd.isna(R.at[p, c]) else round(100 * float(R.at[p, c]), 4) for p in months] for c in C.CODES},
                      "market": [None if p not in F["MKT"].index else round(100 * float(F["MKT"][p]), 4) for p in months]},
      "cum_pct": {f"{h}m": {c: (None if pd.isna(v) else round(100 * float(v), 4)) for c, v in cum(h).items()} for h in (1, 3, 6, 12)},
      "industries": C.IND,
      "prev_card": None if prev is None else {"decision_month": prev["decision_month"], "path": f"forward/fs1/cards/{prev['decision_month']}.json", "sha256": prev["card_sha256"]},
      "scores_summary": "forward/fs1/scores/summary.md" if os.path.exists(os.path.join(C.SCORES, "summary.md")) else None,
      "rules": C.RULES}
os.makedirs(C.PENDING, exist_ok=True)
pp = os.path.join(C.PENDING, f"{tm}.packet.json")
b = json.dumps(pk, ensure_ascii=False, indent=1).encode("utf-8"); open(pp, "wb").write(b)
print(json.dumps({"status": "ok", "decision_month": tm, "cutoff_utc": pk["cutoff_utc"], "first_open_utc": pk["first_open_utc"],
                  "packet": os.path.relpath(pp), "packet_sha256": C.sha256_bytes(b), "card_out": os.path.relpath(os.path.join(C.PENDING, f"{tm}.card.json")),
                  "prev_card_sha256": None if prev is None else prev["card_sha256"], "french_latest": C.month_str(latest), "s0_window": pk["s0"]["window"]}, ensure_ascii=False))
