# Claude 2026-10-16:只靠 supplement/p2_daily_dedup_<標籤>.csv.gz 重算「P2 去掉 FOX、NWS」的平均差與 97.5% 區間(凍結的 block_boot)
#   用法:python3 -I s2_replay_dedup.py <標籤>   → 和 supplement/s2_result_<標籤>.json 比對
import csv, gzip, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', '..', 'scripts'))
import numpy as np
import p_sharp_and_break as PB
TAG = sys.argv[1]
rows = list(csv.DictReader(gzip.open(os.path.join(HERE, 'supplement', f'p2_daily_dedup_{TAG}.csv.gz'), 'rt')))
days = [r['date'] for r in rows]
gb = (np.array([float(r['p2_break_dedup_sum']) for r in rows]), np.array([float(r['p2_break_dedup_n']) for r in rows]))
gu = (np.array([float(r['p2_uptrend_dedup_sum']) for r in rows]), np.array([float(r['p2_uptrend_dedup_n']) for r in rows]))
diff = 100 * (gb[0].sum() / gb[1].sum() - gu[0].sum() / gu[1].sum())
ci = PB.block_boot(days, {'b': gb, 'u': gu}, lambda a: (a['b'][0] / a['b'][1] - a['u'][0] / a['u'][1]) * 100 if a['b'][1] and a['u'][1] else None)
o = json.load(open(os.path.join(HERE, 'supplement', f's2_result_{TAG}.json')))['P2_issuer_dedup_drop_FOX_NWS']
print(json.dumps({'diff_pp': diff, 'ci97_5': ci, 'same_ci': ci == o['ci97_5'], 'diff_abs_err': abs(diff - o['diff_mean_pp'])}))
assert ci == o['ci97_5'] and abs(diff - o['diff_mean_pp']) < 1e-9
