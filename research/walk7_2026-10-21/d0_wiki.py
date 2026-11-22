#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk7 D0:S&P 500 每年 1 月 1 日的成分股(Wikipedia「List of S&P 500 companies」當時的版本)
用法:python3 d0_wiki.py OUT_DIR   → OUT_DIR/raw/sp500_rev_YYYY.html、raw/sp500_revs.json"""
import json, os, sys, time, urllib.parse, urllib.error
sys.path.insert(0, "/home/claude/market-flow-dashboard/scripts")
import astra_data as AD

OUT = sys.argv[1]; H = {"User-Agent": AD.WIKI_UA}


def get(url):
    for k in range(6):
        try:
            return AD.http_get(url, 60, 1, H)
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            time.sleep(30 * (k + 1))
    raise RuntimeError("429 太多次 " + url)


revs = {}
p = os.path.join(OUT, "raw", "sp500_revs.json")
if os.path.exists(p):
    revs = {int(k): v for k, v in json.load(open(p)).items()}
for Y in range(2016, 2027):
    if Y not in revs:
        # api.php 會被 429 擋;改用「歷史」頁(index.php?action=history&offset=Y0101000000&limit=1)取那天之前最後一個版本
        hh = get(f"https://en.wikipedia.org/w/index.php?title=List_of_S%26P_500_companies&action=history&offset={Y}0101000000&limit=1").decode("utf-8", "ignore")
        import re as _re
        revs[Y] = {"revid": int(_re.findall(r"oldid=(\d+)", hh)[0]), "timestamp": _re.findall(r'class="mw-changeslist-date"[^>]*>([^<]+)<', hh)[0]}
        json.dump(revs, open(p, "w"), indent=1); print(Y, revs[Y], flush=True); time.sleep(8)
    f = os.path.join(OUT, "raw", f"sp500_rev_{Y}.html")
    if not os.path.exists(f):
        html = get(f"https://en.wikipedia.org/w/index.php?oldid={revs[Y]['revid']}").decode("utf-8", "ignore")
        open(f, "w").write(html); print(Y, "html", len(html), flush=True); time.sleep(8)
print("done")
