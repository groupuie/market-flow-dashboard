#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk7 D2:解析每年 1 月 1 日的 S&P 500 成分股(Wikipedia 當時版本的第一個大表)
用法:python3 d2_sp500.py OUT_DIR → OUT_DIR/data/sp500_jan1.json  {年: [{sym, name, cik}]}"""
import html.parser, json, os, re, sys


class Tables(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(); self.tables = []; self.depth = 0; self.cur = None; self.row = None; self.cell = None

    def handle_starttag(self, tag, a):
        a = dict(a)
        if tag == "table":
            self.depth += 1
            if self.depth == 1 and "wikitable" in (a.get("class") or ""):
                self.cur = []
        elif self.cur is not None and self.depth == 1:
            if tag == "tr":
                self.row = []
            elif tag in ("td", "th") and self.row is not None:
                self.cell = []

    def handle_endtag(self, tag):
        if tag == "table":
            if self.depth == 1 and self.cur is not None:
                self.tables.append(self.cur); self.cur = None
            self.depth -= 1
        elif self.cur is not None and self.depth == 1:
            if tag in ("td", "th") and self.cell is not None and self.row is not None:
                self.row.append(re.sub(r"\s+", " ", "".join(self.cell)).strip()); self.cell = None
            elif tag == "tr" and self.row is not None:
                if self.row:
                    self.cur.append(self.row)
                self.row = None

    def handle_data(self, d):
        if self.cell is not None:
            self.cell.append(d)


def ysym(s):
    return re.sub(r"\[.*?\]", "", str(s)).strip().upper().replace(".", "-").replace("/", "-")


OUT = sys.argv[1]; res = {}
for Y in range(2016, 2027):
    p = os.path.join(OUT, "raw", f"sp500_rev_{Y}.html")
    if not os.path.exists(p):
        continue
    t = Tables(); t.feed(open(p).read())
    best = max(t.tables, key=len); hdr = [h.lower() for h in best[0]]
    i = next(k for k, h in enumerate(hdr) if "symbol" in h or "ticker" in h)
    n = next((k for k, h in enumerate(hdr) if "security" in h or "company" in h), None)
    c = next((k for k, h in enumerate(hdr) if "cik" in h), None)
    mem = []
    for r in best[1:]:
        if len(r) <= i:
            continue
        s = ysym(r[i])
        if re.fullmatch(r"[A-Z][A-Z0-9\-]{0,6}", s):
            mem.append({"sym": s, "name": r[n] if n is not None and len(r) > n else "", "cik": (r[c].lstrip("0") if c is not None and len(r) > c else "")})
    res[Y] = mem; print(Y, "header", best[0][:8], "成分股", len(mem))
json.dump(res, open(os.path.join(OUT, "data", "sp500_jan1.json"), "w"), ensure_ascii=False, indent=0)
