#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""圖形辨識練習 P2:匿名 K 線圖
- 題目圖:8 格(A–H),每格 126 根日 K,價格改成指數(第 1 根收盤 = 100)、20 / 50 / 200 日線、成交量(相對 20 日均量)、大盤(QQQ)同期走勢細線;沒有代號、沒有日期
- 揭曉圖:24 格(每回合),每格只畫最後 40 根 + 之後 10 根,標出目標價、洗盤價、結果
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.collections import LineCollection, PolyCollection
for f in fm.findSystemFonts():
    if "NotoSansCJK" in f and "Regular" in f:
        fm.fontManager.addfont(f); plt.rcParams["font.family"] = fm.FontProperties(fname=f).get_name(); break
plt.rcParams["axes.unicode_minus"] = False
UPC, DNC = "#d62728", "#2ca02c"; N = 126


def _candles(ax, B, base, x0=0):
    segs, cols, polys, pcols = [], [], [], []
    for x, b in enumerate(B):
        o, h, l, c = (v / base * 100 for v in (b[1], b[2], b[3], b[4])); col = UPC if c >= o else DNC
        segs.append([(x0 + x, l), (x0 + x, h)]); cols.append(col)
        lo, hi = min(o, c), max(o, c)
        if hi - lo < 1e-9:
            hi = lo + (h - l) * 0.02 + 1e-6
        polys.append([(x0 + x - 0.36, lo), (x0 + x + 0.36, lo), (x0 + x + 0.36, hi), (x0 + x - 0.36, hi)]); pcols.append(col)
    ax.add_collection(LineCollection(segs, colors=cols, linewidths=0.7)); ax.add_collection(PolyCollection(polys, facecolors=pcols, edgecolors=pcols, linewidths=0.3))


def draw_q(ax, av, label, bars, i, mkt):
    """bars[i] = 決定日;mkt = 大盤同期收盤(len N)"""
    B = bars[i - N + 1:i + 1]; base = B[0][4]; C = [b[4] for b in bars[:i + 1]]; off = i + 1 - N
    _candles(ax, B, base)
    for w, col in ((20, "#ff7f0e"), (50, "#1f77b4"), (200, "#9467bd")):
        ys = [(x, sum(C[off + x - w + 1:off + x + 1]) / w / base * 100) for x in range(N) if off + x - w + 1 >= 0]
        if ys:
            ax.plot([p[0] for p in ys], [p[1] for p in ys], color=col, linewidth=0.9)
    if mkt:   # 大盤畫在另一個刻度上(細虛線),不擠壓個股的 K 線
        ax2 = ax.twinx(); m0 = mkt[0]; mm = [m / m0 * 100 for m in mkt]; ax2.plot(range(N), mm, color="#888888", linewidth=0.8, linestyle="--")
        p2 = (max(mm) - min(mm)) * 0.06 + 0.1; ax2.set_ylim(min(mm) - p2, max(mm) + p2); ax2.set_yticks([]); ax2.set_xlim(-1, N)
    V = [b[5] for b in bars[:i + 1]]
    vr = [V[off + x] / (sum(V[off + x - 20:off + x]) / 20) if off + x >= 20 and sum(V[off + x - 20:off + x]) > 0 else 0 for x in range(N)]
    av.bar(range(N), vr, color=[UPC if b[4] >= b[1] else DNC for b in B], width=0.7); av.axhline(1, color="#555555", linewidth=0.6)
    lo_ = min(b[3] for b in B) / base * 100; hi_ = max(b[2] for b in B) / base * 100
    pad = (hi_ - lo_) * 0.04; ax.set_ylim(lo_ - pad, hi_ + pad); ax.set_xlim(-1, N)
    ax.yaxis.tick_left(); av.yaxis.tick_right(); av.set_yticks([1, 2]); av.tick_params(labelsize=7); ax.tick_params(labelsize=7)
    av.set_xticks(range(5, N, 20)); av.set_xticklabels([str(x - N + 1) for x in range(5, N, 20)], fontsize=7); plt.setp(ax.get_xticklabels(), visible=False)
    ax.grid(alpha=0.25); ax.set_title(f"{label}   今收 {B[-1][4] / base * 100:.1f}({100 * (B[-1][4] / B[-2][4] - 1):+.1f}%)", fontsize=10, loc="left", fontweight="bold")


def render_q(items, out_png, cols=2, rows=4, cw=560, ch=315, dpi=70):
    """items = [(label, bars, i, mkt), …] 最多 8 個"""
    H = rows * ch / dpi + 0.45; fig = plt.figure(figsize=(cols * cw / dpi, H), dpi=dpi); top = 1 - 0.45 / H
    for j, (label, bars, i, mkt) in enumerate(items):
        r, c = divmod(j, cols); x0 = c / cols; y0 = top - (r + 1) * (top / rows); w = 1 / cols; h = top / rows
        ax = fig.add_axes([x0 + 0.05 * w, y0 + 0.30 * h, 0.85 * w, 0.58 * h]); av = fig.add_axes([x0 + 0.05 * w, y0 + 0.10 * h, 0.85 * w, 0.19 * h], sharex=ax)
        draw_q(ax, av, label, bars, i, mkt)
    fig.suptitle("匿名日K(126 根,最右邊 = 今天收盤;價格 = 指數,第 1 根 = 100)· 紅漲綠跌 · 橘 20 日線、藍 50 日線、紫 200 日線 · 灰虛線 = 大盤同期 · 下方 = 成交量 ÷ 20 日均量", fontsize=10, y=0.995)
    fig.savefig(out_png); plt.close(fig)


def draw_r(ax, label, bars, i, side_res, back=40, fwd=10):
    """揭曉:最後 back 根 + 之後 fwd 根;side_res = {"buy": {...}, "sell": {...}, "call": "buy"/"sell"/"wait"}"""
    B = bars[i - back + 1:i + 1 + fwd]; base = bars[i - N + 1][4]; c0 = bars[i][4] / base * 100
    _candles(ax, B, base, x0=-back + 1); a = side_res["atr"]
    ax.axvline(0.5, color="#000000", linewidth=0.8, linestyle=":")
    for y, col, lab in ((c0 * (1 + 2 * a), "#d62728", "買目標"), (c0 * (1 - 1.5 * a), "#2ca02c", "買洗盤"), (c0 * (1 - 2 * a), "#1f77b4", "賣目標"), (c0 * (1 + 1.5 * a), "#9467bd", "賣軋")):
        ax.axhline(y, color=col, linewidth=0.7, linestyle="--", alpha=0.8)
    lo_ = min(b[3] for b in B) / base * 100; hi_ = max(b[2] for b in B) / base * 100; pad = (hi_ - lo_) * 0.05
    ax.set_ylim(min(lo_, c0 * (1 - 2 * a)) - pad, max(hi_, c0 * (1 + 2 * a)) + pad); ax.set_xlim(-back, fwd + 1)
    ax.set_xticks([-30, -20, -10, 0, 5, 10]); ax.tick_params(labelsize=6); ax.yaxis.tick_right(); ax.grid(alpha=0.2)
    b, s = side_res["buy"], side_res["sell"]
    ax.set_title(f"{label} 買→{b['r']}({b['d']}天) 賣→{s['r']}({s['d']}天)  你:{side_res['call']}", fontsize=8, loc="left", fontweight="bold")


def render_r(items, out_png, cols=6, rows=4, cw=300, ch=200, dpi=70):
    """items = [(label, bars, i, side_res), …] 最多 24 個"""
    H = rows * ch / dpi + 0.5; fig = plt.figure(figsize=(cols * cw / dpi, H), dpi=dpi); top = 1 - 0.5 / H
    for j, (label, bars, i, res) in enumerate(items):
        r, c = divmod(j, cols); x0 = c / cols; y0 = top - (r + 1) * (top / rows); w = 1 / cols; h = top / rows
        ax = fig.add_axes([x0 + 0.04 * w, y0 + 0.12 * h, 0.84 * w, 0.72 * h]); draw_r(ax, label, bars, i, res)
    fig.suptitle("上一回合揭曉:最後 40 根 + 之後 10 根(黑點線 = 你判讀的那天)· 紅虛線 = 買的目標(+2×ATR)、綠虛線 = 買的洗盤價(−1.5×ATR)、藍虛線 = 賣的目標、紫虛線 = 賣被軋的價", fontsize=10, y=0.995)
    fig.savefig(out_png); plt.close(fig)


if __name__ == "__main__":
    import gzip, json, sys, time
    W = sys.argv[1]; D = json.load(gzip.open(W + "/data/bars.json.gz"))["bars"]; S = json.load(open(W + "/data/sample.json"))
    its = S["items"][:8]; Q = D["QQQ"]; qi = {b[0]: k for k, b in enumerate(Q)}
    t = time.time()
    render_q([(chr(65 + j), D[r["sym"]], r["idx"], [b[4] for b in Q[qi[r["date"]] - N + 1:qi[r["date"]] + 1]]) for j, r in enumerate(its)], W + "/test_q.png")
    rr = []
    for j, r in enumerate(S["items"][:24]):
        rr.append((f"{j // 8 + 1}{chr(65 + j % 8)}", D[r["sym"]], r["idx"], {"buy": r["buy"], "sell": r["sell"], "atr": r["feat"]["atr20"] / 100, "call": "wait"}))
    render_r(rr, W + "/test_r.png"); print("秒", round(time.time() - t, 2))
