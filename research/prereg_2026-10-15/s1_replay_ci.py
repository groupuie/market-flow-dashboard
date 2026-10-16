# Claude 2026-10-16:只用 repo 裡的每日彙總(supplement/daily_aggregates_<標籤>.csv.gz)重算 P1 / P2 的主統計和 97.5% 區間,
#   和原結果檔逐位比對(不需要原始行情);區塊重抽用凍結的 p_sharp_and_break.block_boot
#   用法:python3 -I s1_replay_ci.py <標籤 c345|d266> <原結果 json>
import csv, gzip, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', '..', 'scripts'))
import numpy as np
import p_sharp_and_break as PB
TAG, ORIG = sys.argv[1], sys.argv[2]
rows = list(csv.DictReader(gzip.open(os.path.join(HERE, 'supplement', f'daily_aggregates_{TAG}.csv.gz'), 'rt')))
days = [r['date'] for r in rows]
G = {k: (np.array([float(r[k + '_sum']) for r in rows]), np.array([float(r[k + '_n']) for r in rows])) for k in ('p1_sharp', 'p1_other', 'p2_break', 'p2_uptrend')}
o = json.load(open(ORIG)); out = {}
for name, a, b in (('P1', 'p1_sharp', 'p1_other'), ('P2', 'p2_break', 'p2_uptrend')):
    diff = (G[a][0].sum() / G[a][1].sum() - G[b][0].sum() / G[b][1].sum()) * 100
    ci = PB.block_boot(days, {'a': G[a], 'b': G[b]}, lambda q: (q['a'][0] / q['a'][1] - q['b'][0] / q['b'][1]) * 100 if q['a'][1] and q['b'][1] else None)
    out[name] = {'diff_pp': diff, 'ci97_5': ci, 'orig_diff_pp': o[name]['diff_mean_pp'], 'orig_ci97_5': o[name]['ci97_5'],
                 'same_ci': ci == o[name]['ci97_5'], 'diff_abs_err': abs(diff - o[name]['diff_mean_pp'])}
print(json.dumps(out, ensure_ascii=False, indent=1))
assert all(v['same_ci'] and v['diff_abs_err'] < 1e-9 for v in out.values())
