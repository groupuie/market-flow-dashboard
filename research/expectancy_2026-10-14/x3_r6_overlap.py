# Claude(2026-10-14):第 6 輪(r6,2026-10-12)實際跑過哪些股票 → 和 Astra 的 345 / 351 候選名單重疊多少
#   r6 實際執行名單 = r6 當時寫出的 /home/claude/work/swing_tune/r6_sig.pkl 的代號(r6_factors.py 第 238 行輸出),
#   另用 r6 當時讀的 /home/claude/work/macro/universe.json 重建 STK(r6_factors.py 第 32 行同式)交叉核對
#   345 = astra-data uni.json(commit 3833bda)的 sp500 ∪ ndx ∪ top100 − 舊 266;351 = 全部發布名單 − 舊 266 − SPY/QQQ
import json, pickle, hashlib, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
SIGP = '/home/claude/work/swing_tune/r6_sig.pkl'; UNIP = '/home/claude/work/macro/universe.json'; U2P = '/home/claude/work/uni_3833bda.json'
sig = pickle.load(open(SIGP, 'rb'))['SIG']
r6_run = sorted(sig.keys())
uni6 = json.load(open(UNIP))
old_list_file = os.path.join(REPO, 'research/swing_tune_2026-10-12')
old266 = [s.strip() for s in open(os.path.join(REPO, 'research/inst_flow_2026-10-11/universe_266.txt')) if s.strip() and not s.startswith('#')]
u2 = json.load(open(U2P))
three = set(u2['sp500']) | set(u2['ndx']) | set(u2['top100'])
c345 = sorted(three - set(old266))
allpub = three | set(u2.get('ai', {}).keys()) | set(u2.get('mag7', []))
c351 = sorted(allpub - set(old266) - {'SPY', 'QQQ'})
R = set(r6_run)
out = {
  'sources': {'r6_sig.pkl': sha(SIGP), 'macro/universe.json(r6 輸入)': sha(UNIP), 'uni.json@3833bda': sha(U2P)},
  'r6_executed': {'n': len(r6_run), 'includes_SPY_QQQ': sorted(R & {'SPY', 'QQQ'})},
  'r6_input_lists': {k: len(v) for k, v in uni6.items() if isinstance(v, list)},
  'candidates': {'c345': len(c345), 'c351': len(c351), 'c351_minus_c345': sorted(set(c351) - set(c345))},
  'overlap': {'c345_in_r6': len(set(c345) & R), 'c345_not_in_r6': sorted(set(c345) - R),
              'c351_in_r6': len(set(c351) & R), 'c351_not_in_r6': sorted(set(c351) - R),
              'old266_in_r6': len(set(old266) & R)},
  'r6_executed_list': r6_run,
}
json.dump(out, open(os.path.join(HERE, 'x3_r6_overlap.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in out.items() if k != 'r6_executed_list'}, ensure_ascii=False, indent=1))
