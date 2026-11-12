#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk7 W2:抽 2,000 張考題 + 8 張範例,畫匿名日 K(不放大盤線)
- 考題:固定種子 20261021;PRE = 決定日 2016-10-21 ~ 2026-05-29 抽 1,000;POST = 2026-07-01 ~ 最後決定日 抽 1,000(Claude 訓練資料之後)
  抽樣只用「名單 + 日期」,不看答案。洗牌後編號 0001–2000,每 25 張一批(b01–b80);每批隨機分到 B1(直接盲判)或 B2(先看 8 張範例),各 40 批
- 範例(只給 B2):決定日 ≤ 2022-12-31、不在考題裡;3 張「先漲一段」、3 張「先跌一段」、2 張「先跌、後來又軋上去」(依答案分層抽,範例本來就要附答案)
- 圖:800×500;最近 126 根日K,價格 = 指數(第 1 根收盤 = 100);20 / 50 / 200 日線;下方成交量 ÷ 20 日均量;標題有今收與日均波動
用法:python3 -I w2_sample.py OUT_DIR [--render]   → OUT_DIR/_sealed/hidden_w7.json、judge/bNN/qXXXX.png、judge/examples/eN.png、judge/plan.json"""
import gzip, hashlib, json, os, pickle, sys
import numpy as np, pandas as pd

OUT = sys.argv[1]; RENDER = "--render" in sys.argv; SEED = 20261021; N = 126
S = pd.read_pickle(os.path.join(OUT, "out", "S7.pkl"))[["sym", "date", "i", "year", "in_sp", "dv_rank", "a", "buy", "sell", "r20", "buy_day", "sell_day"]]
LASTDEC = S.date.max(); rng = np.random.default_rng(SEED)
pre = S[S.date <= "2026-05-29"]; post = S[(S.date >= "2026-07-01") & (S.date <= LASTDEC)]
ip = rng.choice(pre.index.values, 1000, replace=False); iq = rng.choice(post.index.values, 1000, replace=False)
T = pd.concat([S.loc[ip].assign(pool="PRE"), S.loc[iq].assign(pool="POST")])
T = T.iloc[rng.permutation(len(T))].reset_index().rename(columns={"index": "row"})
T["id"] = [f"{k + 1:04d}" for k in range(len(T))]; T["batch"] = [f"b{k // 25 + 1:02d}" for k in range(len(T))]
var = np.array(["B1"] * 40 + ["B2"] * 40); rng.shuffle(var); T["variant"] = [var[int(b[1:]) - 1] for b in T.batch]
# 範例(B2)
ex_pool = S[(S.date <= "2022-12-31") & ~S.index.isin(T.row)]
ex = []
for (b, s_), k in (((1, 0), 3), ((0, 1), 3), ((0, 0), 2)):
    g = ex_pool[(ex_pool.buy == b) & (ex_pool.sell == s_)]; ex.append(g.loc[rng.choice(g.index.values, k, replace=False)])
E = pd.concat(ex); E = E.iloc[rng.permutation(len(E))].reset_index().rename(columns={"index": "row"}); E["id"] = [f"e{k + 1}" for k in range(len(E))]
os.makedirs(os.path.join(OUT, "_sealed"), exist_ok=True)
hid = {"seed": SEED, "pool_n": {"PRE": len(pre), "POST": len(post)}, "lastdec": LASTDEC,
       "items": T[["id", "batch", "variant", "pool", "sym", "date", "i"]].to_dict("records"), "examples": E[["id", "sym", "date", "i"]].to_dict("records")}
raw = json.dumps(hid, ensure_ascii=False, sort_keys=True, default=int).encode(); open(os.path.join(OUT, "_sealed", "hidden_w7.json"), "wb").write(raw)
print("考題", len(T), "PRE", int((T.pool == "PRE").sum()), "POST", int((T.pool == "POST").sum()), "POST 日期數", T[T.pool == "POST"].date.nunique(),
      "B1 批", int((var == "B1").sum()), "hidden SHA-256", hashlib.sha256(raw).hexdigest())
NAMES = {"buy": {1: "先漲一段(先碰 +2 個波動)", 0: "先跌(先碰 −1.5 個波動)", 2: "20 天內都沒碰到"}, "sell": {1: "先跌一段(先碰 −2 個波動)", 0: "被軋(先碰 +1.5 個波動)", 2: "20 天內都沒碰到"}}
exs = [{"id": e.id, "買方結果": NAMES["buy"][int(e.buy)] + f",第 {int(e.buy_day)} 天", "賣方結果": NAMES["sell"][int(e.sell)] + f",第 {int(e.sell_day)} 天",
        "20 天後": f"{100 * e.r20:+.1f}%"} for e in E.itertuples()]
plan = {"batches": {b: {"variant": g.variant.iloc[0], "ids": list(g.id)} for b, g in T.groupby("batch")}, "examples": exs}
os.makedirs(os.path.join(OUT, "judge"), exist_ok=True); json.dump(plan, open(os.path.join(OUT, "judge", "plan.json"), "w"), ensure_ascii=False, indent=1)

if RENDER:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    sys.path.insert(0, os.path.join(OUT, "..", "walk4")); from p2_chart import _candles, UPC, DNC  # noqa: E402
    BARS = pickle.load(gzip.open(os.path.join(OUT, "data", "daily.pkl.gz")))["bars"]

    def draw(path, label, s, i):
        x = BARS[s]["x"]; rows = [[None, *x[k, :4], x[k, 5]] for k in range(i - N + 1, i + 1)]; base = rows[0][4]; C = x[:i + 1, 3]; off = i + 1 - N
        fig = plt.figure(figsize=(8, 5), dpi=100); ax = fig.add_axes([0.07, 0.31, 0.89, 0.58]); av = fig.add_axes([0.07, 0.08, 0.89, 0.21], sharex=ax)
        _candles(ax, rows, base)
        for w, col in ((20, "#ff7f0e"), (50, "#1f77b4"), (200, "#9467bd")):
            xs = [k for k in range(N) if off + k - w + 1 >= 0]
            if xs:
                ax.plot(xs, [C[off + k - w + 1:off + k + 1].mean() / base * 100 for k in xs], color=col, linewidth=1.0)
        V = x[:i + 1, 5]; vr = [V[off + k] / V[off + k - 20:off + k].mean() if off + k >= 20 and V[off + k - 20:off + k].sum() > 0 else 0 for k in range(N)]
        av.bar(range(N), vr, color=[UPC if r[4] >= r[1] else DNC for r in rows], width=0.7); av.axhline(1, color="#555555", linewidth=0.6)
        lo_ = min(r[3] for r in rows) / base * 100; hi_ = max(r[2] for r in rows) / base * 100; pad = (hi_ - lo_) * 0.04
        ax.set_ylim(lo_ - pad, hi_ + pad); ax.set_xlim(-1, N); ax.yaxis.tick_left(); av.yaxis.tick_right(); av.set_yticks([1, 2]); av.tick_params(labelsize=8); ax.tick_params(labelsize=8)
        av.set_xticks(range(5, N, 20)); av.set_xticklabels([str(k - N + 1) for k in range(5, N, 20)], fontsize=8); plt.setp(ax.get_xticklabels(), visible=False); ax.grid(alpha=0.25)
        tr = [max(x[k, 1], x[k - 1, 3]) - min(x[k, 2], x[k - 1, 3]) for k in range(i - 19, i + 1)]; a = sum(tr) / 20 / x[i, 3]
        ax.set_title(f"{label}   今收 {rows[-1][4] / base * 100:.1f}({100 * (rows[-1][4] / rows[-2][4] - 1):+.1f}%)   日均波動 {100 * a:.1f}%", fontsize=12, loc="left", fontweight="bold")
        fig.text(0.07, 0.955, "匿名日K:最近 126 根,最右邊 = 今天收盤;價格 = 指數(第 1 根 = 100)· 紅漲綠跌 · 橘 20 日線、藍 50 日線、紫 200 日線 · 下方 = 成交量 ÷ 20 日均量", fontsize=8)
        fig.savefig(path); plt.close(fig)

    for b in sorted(T.batch.unique()):
        os.makedirs(os.path.join(OUT, "judge", b), exist_ok=True)
    os.makedirs(os.path.join(OUT, "judge", "examples"), exist_ok=True)
    for e in E.itertuples():
        draw(os.path.join(OUT, "judge", "examples", f"{e.id}.png"), f"範例 {e.id[1:]}", e.sym, int(e.i))
    for k, t in enumerate(T.itertuples()):
        draw(os.path.join(OUT, "judge", t.batch, f"q{t.id}.png"), f"第 {t.id} 張", t.sym, int(t.i))
        if (k + 1) % 250 == 0:
            print("畫好", k + 1, flush=True)
    print("畫完")
