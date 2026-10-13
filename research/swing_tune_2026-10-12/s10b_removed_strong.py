# s10b(2026-10-13,只描述):上行條件「濾掉的回」本身的成績(舊規則有、網站規則沒有、當天也不是底)
#   和 s10 同資料、同出場;分 強 / 一般、前段 / 後段、6 組。另列「網站規則才有」的回(冷卻順序不同多出來的)次數
import sys, os, json
sys.argv = [sys.argv[0]]
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "s10_b2_rule_check.py"), encoding="utf-8").read().split("CNT = {}")[0])
RM = {}; ADD = {}
for s, d in D6.items():
    O, H, L, C = (d[k].to_numpy(dtype=float) for k in "ohlc"); n = len(C)
    p = np.array([CI[x] for x in d.index])
    b0, t0, _ = swing(O, H, L, C); xe = exits(O, H, L, C, t0)["XT"]
    R = b2_rules(C); grp = [g for g, m in GS6.items() if s in m]
    for kind, mask in (("濾掉", R["舊"] & ~R["網站"] & ~b0), ("新多", R["網站"] & ~R["舊"] & ~b0)):
        for t in np.flatnonzero(mask):
            if t + 1 >= n: continue
            e = xe[t]
            if e >= n or e <= t + 1: continue
            win = int(O[e] / O[t + 1] - 1 > 0); dd = DSTR[p[t]]; st = "強" if strong(p[t]) else "一般"
            for pk, (a, b) in PER6.items():
                if not (a <= dd <= b): continue
                for g in grp:
                    c = (RM if kind == "濾掉" else ADD).setdefault((g, pk, st), [0, 0]); c[0] += 1; c[1] += win
out = {"濾掉": {f"{g}|{pk}|{st}": {"n": v[0], "win": round(100 * v[1] / v[0], 1)} for (g, pk, st), v in RM.items()},
       "新多": {f"{g}|{pk}|{st}": {"n": v[0], "win": round(100 * v[1] / v[0], 1)} for (g, pk, st), v in ADD.items()}}
json.dump(out, open(os.path.join(HERE, "s10b_result.json"), "w"), ensure_ascii=False, indent=1)
for g in ("IDX", "MAG7", "AI_HW", "AI_SW", "NDX", "ALL"):
    f = lambda k, pk, st: out[k].get(f"{g}|{pk}|{st}", {"n": 0, "win": None})
    print(f"{g:6s} 濾掉的回:強 {f('濾掉','前段','強')['win']}%({f('濾掉','前段','強')['n']})/ {f('濾掉','後段','強')['win']}%({f('濾掉','後段','強')['n']})"
          f" 一般 {f('濾掉','前段','一般')['win']}%({f('濾掉','前段','一般')['n']})/ {f('濾掉','後段','一般')['win']}%({f('濾掉','後段','一般')['n']})"
          f" | 新多 {sum(v['n'] for k, v in out['新多'].items() if k.startswith(g + '|'))} 次")
