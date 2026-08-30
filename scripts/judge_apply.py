#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把盤後場次寫好的小 JSON 併回 signals.json(2026-08-09)。

配合 judge_prep.py:模型只需交出 answer.json(僅 stance/conf/stance_note/plan),
其餘全部由本腳本處理 —— 不覆蓋任何 computed_* 欄、marks 只增不刪、自動蓋時間戳。
內建防呆:欄位型別檢查、字數上限、只允許 prep 挑出的標的、任何一檔壞掉不影響其他檔。

用法:
  python3 judge_apply.py --signals data/signals.json --answer out/answer.json \
      [--allow out/answer.tpl.json] [--checkpoint 盤後]
"""
import argparse, json, sys
from datetime import datetime, timezone

def utcs(): return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def num(v):
    if v is None: return None
    try: return round(float(v), 4)
    except Exception: return None

def clean_plan(p):
    if not isinstance(p, dict): return None
    out = {}
    ent = []
    for e in (p.get("entry") or [])[:3]:
        if not isinstance(e, dict): continue
        lo, hi = num(e.get("px_lo")), num(e.get("px_hi"))
        if lo is None and hi is None: continue
        ent.append({"px_lo": lo, "px_hi": hi, "note": str(e.get("note", ""))[:60]})
    if ent: out["entry"] = ent
    st = p.get("stop")
    if isinstance(st, dict) and num(st.get("px")) is not None:
        out["stop"] = {"px": num(st.get("px")), "note": str(st.get("note", ""))[:60]}
    tg = []
    for t in (p.get("targets") or [])[:3]:
        if isinstance(t, dict) and num(t.get("px")) is not None:
            tg.append({"px": num(t.get("px")), "note": str(t.get("note", ""))[:60]})
    if tg: out["targets"] = tg
    if p.get("horizon"): out["horizon"] = str(p["horizon"])[:24]
    if p.get("sizing"): out["sizing"] = str(p["sizing"])[:60]
    return out or None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--signals", default="data/signals.json")
    ap.add_argument("--answer", default="out/answer.json")
    ap.add_argument("--allow", default=None, help="answer.tpl.json;限制只能改 prep 挑出的標的")
    ap.add_argument("--checkpoint", default="盤後")
    a = ap.parse_args()

    S = json.load(open(a.signals, encoding="utf-8"))
    A = json.load(open(a.answer, encoding="utf-8"))
    allow = None
    if a.allow:
        try: allow = set((json.load(open(a.allow, encoding="utf-8")).get("symbols") or {}).keys())
        except Exception: allow = None

    ok, skip = [], []
    for sym, v in (A.get("symbols") or {}).items():
        try:
            if sym not in (S.get("symbols") or {}): skip.append(f"{sym}(不在引擎清單)"); continue
            if allow is not None and sym not in allow: skip.append(f"{sym}(不在待辦名單)"); continue
            if not isinstance(v, dict): skip.append(f"{sym}(格式)"); continue
            stance = str(v.get("stance") or "").strip()
            if not stance: skip.append(f"{sym}(stance 空白)"); continue
            node = S["symbols"][sym]
            node["stance"] = stance[:40]
            try: node["conf"] = max(0, min(3, int(v.get("conf", 2))))
            except Exception: node["conf"] = 2
            if v.get("stance_note"): node["stance_note"] = str(v["stance_note"])[:400]
            pl = clean_plan(v.get("plan"))
            if pl: node["plan"] = pl
            node["claude_updated_utc"] = utcs()
            node["claude_checkpoint"] = a.checkpoint
            rv = node.get("review") or {}
            rv["due"] = False; rv["done_utc"] = utcs()
            node["review"] = rv
            ok.append(sym)
        except Exception as e:
            skip.append(f"{sym}({str(e)[:40]})")

    if not ok:
        print("NO_CHANGE 沒有任何標的被更新"); print("skip:", "; ".join(skip)); sys.exit(2)
    S["updated_utc"] = utcs()
    json.dump(S, open(a.signals, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"已更新 {len(ok)} 檔:{', '.join(ok)}")
    if skip: print("略過:", "; ".join(skip))

if __name__ == "__main__":
    main()
