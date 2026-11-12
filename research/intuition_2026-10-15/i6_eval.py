#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盤感訓練 I6:成績(和正式 PROTOCOL v2 同式的主效果 + AUC / Brier / 校準)

當模組用:from i6_eval import evaluate;evaluate(rows, sessions) → dict
rows:每題一列 {id, date, q, type, v, p, win, ret(買點)/fr10(頂點)};只放已結束的
sessions:練習期間的交易日曆(區塊重抽用)
"""
import random


def mean(x):
    return sum(x) / len(x) if x else None


def auc(score, y):
    pos = [s for s, t in zip(score, y) if t]; neg = [s for s, t in zip(score, y) if not t]
    if not pos or not neg:
        return None
    # Mann-Whitney:同分算一半
    allv = sorted(set(score)); rank = {}
    srt = sorted(score); i = 0
    while i < len(srt):
        j = i
        while j + 1 < len(srt) and srt[j + 1] == srt[i]:
            j += 1
        rank[srt[i]] = (i + j + 2) / 2; i = j + 1
    rp = sum(rank[s] for s in pos)
    return (rp - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def block_boot(cells, sessions, B=2000, blk=5, seed=20261015):
    n = len(sessions)
    if n == 0 or not cells:
        return None
    rnd = random.Random(seed); st = []; starts = list(range(0, max(1, n - blk + 1)))
    for _ in range(B):
        pk = []
        while len(pk) < n:
            s0 = rnd.choice(starts); pk.extend(sessions[s0:s0 + blk])
        vals = [v for d in pk[:n] for v in cells.get(d, [])]
        if vals:
            st.append(sum(vals) / len(vals))
    if len(st) < B * 0.5:
        return None
    st.sort()
    return [st[int(0.025 * len(st))], st[int(0.975 * len(st)) - 1]]


def evaluate(rows, sessions, base=None):
    """base = {(q,type): 平常比例};回傳每個題型的成績"""
    out = {}
    for q in ("buy", "top"):
        R = [r for r in rows if r["q"] == q]
        if not R:
            continue
        val = (lambda r: r["ret"]) if q == "buy" else (lambda r: r["fr10"])
        A = [r for r in R if r["v"] == "agree"]; Dg = [r for r in R if r["v"] == "disagree"]
        # 主效果:同一天、同一類型的格子內,同意 − 不同意(頂點題反過來:不同意 − 同意,跌越多越好)
        cells = {}
        for r in R:
            cells.setdefault((r["date"], r["type"]), {"agree": [], "disagree": []})[r["v"]].append(val(r))
        cd = {}
        for (d, t), g in cells.items():
            if g["agree"] and g["disagree"]:
                diff = mean(g["agree"]) - mean(g["disagree"])
                cd.setdefault(d, []).append(diff if q == "buy" else -diff)
        vals = [v for vs in cd.values() for v in vs]
        ci = block_boot(cd, sessions)
        pr = [r for r in R if r.get("p") is not None]
        bs = mean([(float(r["p"]) - (1.0 if r["win"] else 0.0)) ** 2 for r in pr]) if pr else None
        bb = None
        if base and pr:
            bb = mean([(base[(q, r["type"])] - (1.0 if r["win"] else 0.0)) ** 2 for r in pr])
        cal = []
        for lo, hi in ((0, .35), (.35, .45), (.45, .55), (.55, .65), (.65, 1.01)):
            g = [r for r in pr if lo <= float(r["p"]) < hi]
            if g:
                cal.append({"p_bin": f"{lo:.2f}-{min(hi, 1):.2f}", "n": len(g), "mean_p": mean([float(r["p"]) for r in g]), "actual": mean([1.0 if r["win"] else 0.0 for r in g])})
        o = {"n": len(R), "n_agree": len(A), "n_disagree": len(Dg),
             "hit_all": mean([1.0 if r["win"] else 0.0 for r in R]), "hit_agree": mean([1.0 if r["win"] else 0.0 for r in A]),
             "hit_disagree": mean([1.0 if r["win"] else 0.0 for r in Dg]),
             "mean_all": mean([val(r) for r in R]), "mean_agree": mean([val(r) for r in A]), "mean_disagree": mean([val(r) for r in Dg]),
             "primary": {"stat": mean(vals), "cells": len(vals), "days": len(cd), "ci95": ci},
             "auc_p": auc([float(r["p"]) for r in pr], [bool(r["win"]) for r in pr]) if pr else None,
             "brier": bs, "brier_base": bb, "brier_skill": (1 - bs / bb) if (bs is not None and bb) else None,
             "mean_p": mean([float(r["p"]) for r in pr]) if pr else None, "calibration": cal}
        out[q] = o
    return out


def fmt(o, q):
    """一行白話摘要"""
    unit = "平均報酬" if q == "buy" else "10 天後平均漲跌"
    pct = lambda v: "—" if v is None else f"{100 * v:+.2f}%"
    rt = lambda v: "—" if v is None else f"{100 * v:.1f}%"
    ci = o["primary"]["ci95"]
    auc_s = "—" if o["auc_p"] is None else "%.3f" % o["auc_p"]
    bsk_s = "—" if o["brier_skill"] is None else "%+.3f" % o["brier_skill"]
    ci_s = (pct(ci[0]) + " ~ " + pct(ci[1])) if ci else "—"
    return (f"{o['n']} 題;同意 {o['n_agree']}(對 {rt(o['hit_agree'])}、{unit} {pct(o['mean_agree'])})/ 不同意 {o['n_disagree']}(對 {rt(o['hit_disagree'])}、{pct(o['mean_disagree'])})/ 全部對 {rt(o['hit_all'])};"
            f"主效果 {pct(o['primary']['stat'])}(95% 區間 {ci_s},{o['primary']['cells']} 格);AUC {auc_s};Brier 技巧 {bsk_s};平均 p {rt(o['mean_p'])}")
