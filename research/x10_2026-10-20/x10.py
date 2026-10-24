#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""x10:隨機抽 10 張過去 10 年的個股 K 線圖 → Claude 盲判 → 揭曉
子指令:
  sample BARS.json.gz SEED          抽 10 張(不同股票),股票與日期存 hidden.json,只印指紋
  charts BARS.json.gz               畫 10 張匿名截圖 q01..q10.png + info.json(每張的日均波動)
  reveal BARS.json.gz ANSWERS.json  算之後的走勢、對錯、畫揭曉圖 r01..r10.png、result.json
對錯的定義(抽樣之前就寫好):決定日收盤 C、atr = 前 20 天平均真實區間 ÷ C;看之後 20 個交易日
  買方:先碰 C×(1+2·atr) =「先漲一段」;先碰 C×(1−1.5·atr) =「先跌一段」(同一天都碰 = 先跌);都沒碰 =「都沒到」
        買點 → 先漲一段 = 對、先跌一段 = 錯、都沒到 = 平;「還要再等(低點 / 加碼點還沒到)」→ 先跌一段 = 對、先漲一段 = 錯、都沒到 = 平
  賣方:先碰 C×(1−2·atr) =「先跌一段」;先碰 C×(1+1.5·atr) =「先漲一段」(同一天都碰 = 先漲);都沒碰 =「都沒到」
        賣點 → 先跌一段 = 對、先漲一段 = 錯、都沒到 = 平;「還要再等,高點還沒到」→ 先漲一段 = 對、先跌一段 = 錯、都沒到 = 平
"""
import gzip, hashlib, json, math, os, random, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); H = 20; N = 126; AFTER = 60; LO_DATE = "2016-10-20"


def load(bz):
    D = json.load(gzip.open(bz)); return D["bars"], set(D["etf"])


def atr(b, i):
    tr = [max(b[k][2], b[k - 1][4]) - min(b[k][3], b[k - 1][4]) for k in range(i - 19, i + 1)]
    return sum(tr) / 20 / b[i][4]


def ok(b, i):
    if i < 252 or i + AFTER >= len(b):
        return False
    w = b[i - N + 1:i + AFTER + 1]
    if any(x[5] <= 0 for x in w):
        return False
    return sum(1 for k in range(1, len(w)) if w[k][4] == w[k - 1][4]) <= 0.02 * len(w)


def outcome(b, i):
    C = b[i][4]; a = atr(b, i); res = {}
    for side, up, dn in (("buy", 2.0, 1.5), ("sell", 1.5, 2.0)):
        r, d = "都沒到", H
        for j in range(1, H + 1):
            hi, lo = b[i + j][2] >= C * (1 + up * a), b[i + j][3] <= C * (1 - dn * a)
            if side == "buy" and lo:
                r, d = "先跌一段", j; break
            if side == "buy" and hi:
                r, d = "先漲一段", j; break
            if side == "sell" and hi:
                r, d = "先漲一段", j; break
            if side == "sell" and lo:
                r, d = "先跌一段", j; break
        res[side] = [r, d]
    c20, c60 = b[i + H][4] / C - 1, b[i + AFTER][4] / C - 1
    mx = max(x[2] for x in b[i + 1:i + H + 1]) / C - 1; mn = min(x[3] for x in b[i + 1:i + H + 1]) / C - 1
    return res, {"20天後": round(100 * c20, 1), "60天後": round(100 * c60, 1), "20天內最高": round(100 * mx, 1), "20天內最低": round(100 * mn, 1), "atr%": round(100 * a, 2)}


if __name__ == "__main__":
    cmd, bz = sys.argv[1], sys.argv[2]; B, ETF = load(bz)
    if cmd == "sample":
        seed = int(sys.argv[3]); rnd = random.Random(seed)
        pool = [(s, i) for s in sorted(B) if s not in ETF for i in range(len(B[s])) if B[s][i][0] >= LO_DATE and ok(B[s], i)]
        rnd.shuffle(pool); pick, seen = [], set()
        for s, i in pool:
            if s not in seen:
                pick.append({"n": len(pick) + 1, "sym": s, "i": i, "date": B[s][i][0]}); seen.add(s)
            if len(pick) == 10:
                break
        raw = json.dumps({"seed": seed, "pool": len(pool), "items": pick}, ensure_ascii=False, sort_keys=True).encode()
        open(os.path.join(HERE, "hidden.json"), "wb").write(raw)
        print("候選", len(pool), "抽了", len(pick), "hidden.json SHA-256", hashlib.sha256(raw).hexdigest())
        # 隨便猜的基準(所有候選日子)
        cnt = {"buy": {}, "sell": {}}
        for s, i in random.Random(1).sample(pool, 20000):
            r, _ = outcome(B[s], i)
            for side in cnt:
                cnt[side][r[side][0]] = cnt[side].get(r[side][0], 0) + 1
        base = {side: {k: round(100 * v / 20000, 1) for k, v in d.items()} for side, d in cnt.items()}
        json.dump(base, open(os.path.join(HERE, "base.json"), "w"), ensure_ascii=False, indent=1); print("基準(抽 2 萬個候選日子)", base)
    elif cmd == "charts":
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        sys.path.insert(0, os.path.join(HERE, "..", "walk4")); from p2_chart import draw_q
        hid = json.load(open(os.path.join(HERE, "hidden.json")))["items"]; Q = B["QQQ"]; qi = {x[0]: k for k, x in enumerate(Q)}; info = {}
        for it in hid:
            b = B[it["sym"]]; i = it["i"]; k = qi[it["date"]]; mk = [x[4] for x in Q[k - N + 1:k + 1]]
            fig = plt.figure(figsize=(1000 / 90, 620 / 90), dpi=90)
            ax = fig.add_axes([0.06, 0.30, 0.88, 0.60]); av = fig.add_axes([0.06, 0.08, 0.88, 0.20], sharex=ax)
            draw_q(ax, av, f"第 {it['n']} 張", b, i, mk)
            a = atr(b, i); ax.set_title(ax.get_title(loc="left") + f"   日均波動 {100 * a:.1f}%", fontsize=12, loc="left", fontweight="bold")
            fig.suptitle("匿名日K(最近 126 根,最右邊 = 今天收盤;價格 = 指數,第 1 根 = 100)· 紅漲綠跌 · 橘 20 日線、藍 50 日線、紫 200 日線 · 灰虛線 = 大盤同期 · 下方 = 成交量 ÷ 20 日均量", fontsize=9, y=0.985)
            fig.savefig(os.path.join(HERE, f"q{it['n']:02d}.png")); plt.close(fig); info[f"{it['n']}"] = {"日均波動%": round(100 * a, 2)}
        json.dump(info, open(os.path.join(HERE, "info.json"), "w"), ensure_ascii=False, indent=1); print("畫好", len(info), "張")
    elif cmd == "reveal":
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        sys.path.insert(0, os.path.join(HERE, "..", "walk4")); from p2_chart import _candles
        hid = json.load(open(os.path.join(HERE, "hidden.json")))["items"]; A = json.load(open(sys.argv[3]))["ans"]; base = json.load(open(os.path.join(HERE, "base.json")))
        rows = []
        for it in hid:
            b = B[it["sym"]]; i = it["i"]; res, st = outcome(b, i); a = st["atr%"] / 100; C = b[i][4]; ans = A[str(it["n"])]
            gb = {"先漲一段": "對", "先跌一段": "錯", "都沒到": "平"}[res["buy"][0]] if ans["買方"] == "買點" else {"先漲一段": "錯", "先跌一段": "對", "都沒到": "平"}[res["buy"][0]]
            gs = {"先跌一段": "對", "先漲一段": "錯", "都沒到": "平"}[res["sell"][0]] if ans["賣方"] == "賣點" else {"先跌一段": "錯", "先漲一段": "對", "都沒到": "平"}[res["sell"][0]]
            rows.append({"n": it["n"], "sym": it["sym"], "date": it["date"], "買方判斷": ans["買方"], "買方結果": res["buy"], "買方對錯": gb, "賣方判斷": ans["賣方"], "賣方結果": res["sell"], "賣方對錯": gs, **st})
            # 揭曉圖:前 60 根 + 後 60 根
            back = 60; B0 = b[i - back + 1:i + AFTER + 1]
            fig = plt.figure(figsize=(1000 / 90, 520 / 90), dpi=90); ax = fig.add_axes([0.06, 0.10, 0.88, 0.76])
            _candles(ax, B0, C, x0=-back + 1)   # 價格改成「今收 = 100」
            ax.axvspan(0.5, H + 0.5, color="#ffd54f", alpha=0.18, lw=0)
            ax.axvline(0.5, color="#000", lw=1, ls=":")
            for y, col, lab in ((100 * (1 + 2 * a), "#d62728", "買:漲一段 +2×波動"), (100 * (1 - 1.5 * a), "#2ca02c", "買:洗盤 −1.5×波動"),
                                (100 * (1 - 2 * a), "#1f77b4", "賣:跌一段 −2×波動"), (100 * (1 + 1.5 * a), "#9467bd", "賣:被軋 +1.5×波動")):
                ax.plot([0.5, H + 0.5], [y, y], color=col, lw=1, ls="--"); ax.text(H + 1, y, lab, fontsize=8, color=col, va="center")
            lo_ = min(x[3] for x in B0) / C * 100; hi_ = max(x[2] for x in B0) / C * 100; pad = (hi_ - lo_) * 0.05
            ax.set_ylim(min(lo_, 100 * (1 - 2 * a)) - pad, max(hi_, 100 * (1 + 2 * a)) + pad); ax.set_xlim(-back, AFTER + 1); ax.grid(alpha=0.25)
            ax.set_title(f"第 {it['n']} 張 = {it['sym']} {it['date']}(今收 = 100)· 黃底 = 之後 20 個交易日(算對錯的範圍)· 20 天後 {st['20天後']:+.1f}%、60 天後 {st['60天後']:+.1f}%", fontsize=10, loc="left")
            fig.savefig(os.path.join(HERE, f"r{it['n']:02d}.png")); plt.close(fig)
        sc = {side: {g: sum(1 for r in rows if r[side + "對錯"] == g) for g in ("對", "錯", "平")} for side in ("買方", "賣方")}
        json.dump({"items": rows, "成績": sc, "隨便猜的基準%": base}, open(os.path.join(HERE, "result.json"), "w"), ensure_ascii=False, indent=1)
        print(json.dumps(sc, ensure_ascii=False))
