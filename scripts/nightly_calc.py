#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盤後排程的純運算步驟(零 token;2026-08-31)
把「全市場掃描 scan.py」與「分析師 analyst_probe.py」包成一鍵:自動從 market_data.json
組出標的宇宙(當日K核心清單 + ext_universe + capital_flow 成員),再依參數執行。
用法:python3 scripts/nightly_calc.py [scan] [analyst]     # 不帶參數 = 兩者都跑
產出:data/scan.json、data/analyst.json(scan 約 2–4 分;analyst 約 20–30 分,Nasdaq 節流)。
"""
import json, os, subprocess, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")

def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)

def universe():
    cfg = json.load(open(os.path.join(ROOT, "config.json")))
    mdu = cfg["market_data_url"]
    md = json.loads(urllib.request.urlopen(urllib.request.Request(
        mdu + "?t=%d" % time.time(), headers={"User-Agent": "nightly"}), timeout=40).read().decode())
    uni = []
    for s in (list(md.get("kline_today") or {})            # 核心日K宇宙(=Mac 當日K清單)
              + list(md.get("ext_universe") or [])          # 擴充追蹤清單
              + [k.replace("US.", "") for k in (md.get("capital_flow") or {})]):
        s = str(s).strip().upper()
        if s and s not in uni: uni.append(s)
    return uni

def main():
    want = [a for a in sys.argv[1:] if a in ("scan", "analyst")] or ["scan", "analyst"]
    uni = universe()
    log(f"universe {len(uni)} 檔; steps={want}")
    symcsv = ",".join(uni)
    if "scan" in want:
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "scan.py"),
                            "--config", os.path.join(ROOT, "config.json"),
                            "--signals", os.path.join(ROOT, "data/signals.json"),
                            "--out", os.path.join(ROOT, "data/scan.json"),
                            "--kline-dir", os.path.join(ROOT, "data"),
                            "--symbols", symcsv], cwd=SCRIPTS)
        log("scan exit", r.returncode)
    if "analyst" in want:
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "analyst_probe.py"),
                            "--config", os.path.join(ROOT, "config.json"),
                            "--kline-dir", os.path.join(ROOT, "data"),
                            "--out", os.path.join(ROOT, "data/analyst.json"),
                            "--symbols", symcsv], cwd=SCRIPTS)
        log("analyst exit", r.returncode)

if __name__ == "__main__":
    main()
