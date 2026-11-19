#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盤感訓練 I2:經驗庫的「最像的過去」(k 個最近鄰,事先寫死,不調參)

用法:python3 research/intuition_2026-10-15/i2_knn.py SCRATCH_DIR validate|practice
  validate:歷史驗證。池子 = 2021-01-01 以前就已經結束的點;題目 = 2021-01 ~ 2026-06 的點(結果在 2026-07-01 前已知)
            → 經驗庫本身有沒有預測力(AUC、十分位)。和練習題無關。
  practice:池子 = 2026-07-01 以前就已經結束的點;題目 = 練習題(packs/)→ analogs.json(只有過去的統計,沒有練習題的結果)
事先寫死的設定(PRE-REGISTERED,2026-10-15,在看任何練習題結果之前):
  分組:題型(買點 / 頂點)× 類型(個股 / 指數)× 買點種類(底 / 回;頂點只有一種)
  特徵 19 個:chg1 gap r5 r20 r60 vs50 vs200 pos52 dd52 vol20_daily vr min(days_since_top,60) buys_20d
             SPY_r5 SPY_r20 SPY_vs200 QQQ_r5 QQQ_r20 QQQ_vs200(缺值 = 中位數)
  標準化:每組池子的中位數 / 四分位距(IQR/1.349;IQR=0 用標準差;都 0 就不用這個特徵),截在 ±4
  距離:歐氏距離,等權;k = 個股 100、指數 30
  輸出:k 個最像的過去 → 對的比例(買點 = 扣成本後賺;頂點 = 10 天後比較低)、平均報酬、中位數、停損比例;和同組池子的平常比例
"""
import gzip, json, os, sys
import numpy as np

F = ["chg1", "gap", "r5", "r20", "r60", "vs50", "vs200", "pos52", "dd52", "vol20_daily", "vr", "dst", "buys_20d",
     "SPY_r5", "SPY_r20", "SPY_vs200", "QQQ_r5", "QQQ_r20", "QQQ_vs200"]
K = {"stock": 100, "idx": 30}


def fv(r):
    x = []
    for f in F:
        if f == "dst":
            v = r.get("days_since_top"); v = 60 if v is None else min(v, 60)
        else:
            v = r.get(f)
        x.append(np.nan if v is None else float(v))
    return x


def gkey(r):
    return (r["q"], r["type"], r["kind"] if r["q"] == "buy" else "頂")


def fit_scale(X):
    med = np.nanmedian(X, 0); q1, q3 = np.nanpercentile(X, 25, 0), np.nanpercentile(X, 75, 0)
    sc = (q3 - q1) / 1.349; sd = np.nanstd(X, 0)
    sc = np.where(sc > 0, sc, sd); use = sc > 0
    return med, np.where(use, sc, 1.0), use


def zs(X, med, sc, use):
    Z = (X - med) / sc
    Z = np.where(np.isnan(Z), 0.0, Z)
    return np.clip(Z, -4, 4)[:, use]


def knn_stats(pool, queries):
    """pool / queries:同一組的 list[dict];回傳每題的統計"""
    Xp = np.array([fv(r) for r in pool], float); med, sc, use = fit_scale(Xp); Zp = zs(Xp, med, sc, use)
    win = np.array([bool(r["win"]) for r in pool]); q = pool[0]["q"]
    val = np.array([r["ret"] if q == "buy" else r["fr10"] for r in pool], float)
    stop = np.array([r.get("exit_why") == "停損" for r in pool]) if q == "buy" else None
    k = min(K[pool[0]["type"]], len(pool)); base = float(win.mean())
    out = []
    Zq = zs(np.array([fv(r) for r in queries], float), med, sc, use)
    pp = (Zp ** 2).sum(1)
    for a in range(0, len(Zq), 1000):
        Zc = Zq[a:a + 1000]
        D = (Zc ** 2).sum(1)[:, None] + pp[None, :] - 2.0 * Zc @ Zp.T     # = 歐氏距離平方
        nn = np.argpartition(D, k - 1, axis=1)[:, :k]
        for row in nn:
            w = win[row]; v = val[row]
            o = {"k": int(k), "n_pool": len(pool), "hit": float(w.mean()), "base": base, "mean": float(v.mean()), "median": float(np.median(v))}
            if q == "buy":
                o.update(avg_win=float(v[v > 0].mean()) if (v > 0).any() else None, avg_loss=float(v[v < 0].mean()) if (v < 0).any() else None,
                         stop=float(stop[row].mean()))
            out.append(o)
    return out


def auc(score, y):
    score = np.asarray(score, float); y = np.asarray(y, bool)
    if y.all() or (~y).all():
        return None
    order = np.argsort(score, kind="mergesort"); ranks = np.empty(len(score)); ranks[order] = np.arange(1, len(score) + 1)
    # 同分取平均名次
    s_sorted = score[order]; i = 0
    while i < len(s_sorted):
        j = i
        while j + 1 < len(s_sorted) and s_sorted[j + 1] == s_sorted[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j + 2) / 2
        i = j + 1
    n1 = y.sum(); n0 = len(y) - n1
    return float((ranks[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def load_bank(S):
    return json.load(gzip.open(os.path.join(S, "bank.json.gz"), "rt", encoding="utf-8"))


def main(S, MODE):
  bank = load_bank(S)
  if MODE == "validate":
      pool = [r for r in bank if r["exit_date"] < "2021-01-01"]
      qs = [r for r in bank if "2021-01-01" <= r["date"] <= "2026-06-30" and r["exit_date"] < "2026-07-01"]
      res = {}
      for g in sorted({gkey(r) for r in qs}):
          P = [r for r in pool if gkey(r) == g]; Q = [r for r in qs if gkey(r) == g]
          if len(P) < 50 or len(Q) < 30:
              continue
          st = knn_stats(P, Q); sc = np.array([o["hit"] for o in st]); y = np.array([bool(r["win"]) for r in Q])
          val = np.array([r["ret"] if g[0] == "buy" else r["fr10"] for r in Q], float)
          dec = np.argsort(sc); n = len(sc); lo = dec[: n // 10]; hi = dec[-(n // 10):]
          agree = sc > st[0]["base"]
          res["/".join(g)] = {"n_pool": len(P), "n_query": len(Q), "auc": auc(sc, y), "query_base_hit%": 100 * y.mean(),
                              "top10%_hit%": 100 * y[hi].mean(), "bottom10%_hit%": 100 * y[lo].mean(),
                              "top10%_mean%": 100 * val[hi].mean(), "bottom10%_mean%": 100 * val[lo].mean(),
                              "knn_says_above_base": {"n": int(agree.sum()), "hit%": 100 * y[agree].mean() if agree.any() else None,
                                                      "mean%": 100 * val[agree].mean() if agree.any() else None},
                              "knn_says_below_base": {"n": int((~agree).sum()), "hit%": 100 * y[~agree].mean() if (~agree).any() else None,
                                                      "mean%": 100 * val[~agree].mean() if (~agree).any() else None}}
          print("/".join(g), json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in res["/".join(g)].items() if not isinstance(v, dict)}, ensure_ascii=False))
      json.dump(res, open(os.path.join(S, "knn_validate.json"), "w"), ensure_ascii=False, indent=1)
  else:
      pool = [r for r in bank if r["exit_date"] < "2026-07-01"]
      Q = []
      for f in sorted(os.listdir(os.path.join(S, "packs"))):
          P = json.load(open(os.path.join(S, "packs", f)))
          for m in P["marks"]:
              r = {k: m.get(k) for k in ("chg1", "gap", "r5", "r20", "r60", "vs50", "vs200", "pos52", "dd52", "vol20_daily", "vr", "days_since_top", "buys_20d")}
              mk = m["market"]
              r.update(id=m["id"], q=m["q"], type=m["type"], kind=m["kind"], SPY_r5=mk["SPY"]["r5"], SPY_r20=mk["SPY"]["r20"], SPY_vs200=mk["SPY"]["vs200"],
                       QQQ_r5=mk["QQQ"]["r5"], QQQ_r20=mk["QQQ"]["r20"], QQQ_vs200=mk["QQQ"]["vs200"])
              Q.append(r)
      out = {}
      for g in sorted({gkey(r) for r in Q}):
          P = [r for r in pool if gkey(r) == g]; QQ = [r for r in Q if gkey(r) == g]
          for r, o in zip(QQ, knn_stats(P, QQ)):
              out[r["id"]] = o
      json.dump(out, open(os.path.join(S, "analogs.json"), "w"), ensure_ascii=False)
      print("analogs for", len(out), "questions;", {"/".join(g): len([r for r in pool if gkey(r) == g]) for g in sorted({gkey(r) for r in Q})})


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
