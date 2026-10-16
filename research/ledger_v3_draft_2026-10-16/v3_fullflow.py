#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盤感測試 v3 草案 3:**完整正式流程驗收**(Claude 2026-10-17;回應 Astra v0.7.4 §5.2「用實際凍結來源及構造成熟批次跑完整驗收」)

用「真的凍結收集程式」(scripts/astra_ledger.py 等三支,git 1ee593a 的原位元組)在暫存環境跑完整一輪,再用 v3 正式模式做唯一一次判定:
  - 暫存 GitHub:本機 bare repo 當 origin;push 到 astra-ledger 時由 post-receive hook 記一筆「ledger-receipt run」(時間 = 假時鐘);
    假的 gh 指令照 GitHub API 的格式回答(收集程式的 remote_receipt 與驗證程式的回條查詢都走它)
  - 假的 Yahoo:60 檔(58 檔股票含 GOOG / GOOGL + SPY / QQQ)真實日K(2019-06 起 480 個交易日)重新標成 2024-12 ~ 2026-10 的日期;
    收案期 2026-02-02 起 120 個交易日(收集程式與官方日曆在 2026 年一致)
  - 刻意放進去的狀況:早上第一次跑 SPY 還沒更新(下午補鎖成功)/ 整天失敗 / 晚鎖(過了截止)/ 真的零訊號日 /
    三檔配息(之後抓的資料把除息日以前 × 0.99)/ 一檔 1 拆 2(× 0.5)/ 一檔下市(之後沒有資料;它的判讀都是同意 → 缺的同意填 −100%)
  - 判讀:用 id 的雜湊決定同意 / 不同意(沒有判斷力);model = claude-opus-5-5
  - 凍結:main 上 research/ledger_v3/v3_manifest.json(make_manifest)+ 驗證程式;astra-ledger 上的凍結錨點在起日前 push
  - 正式判定:V.formal_run(時鐘換成成熟之後);結果要和 dry-run + decide 一樣;第二次要拒絕;git 歷史有就拒絕;
    再做 8 種竄改 / 時序反例,每一種都要「停、不寫判定」
用法:python3 -I v3_fullflow.py <真實 repo> <astra_v050_data 資料夾> <輸出 json>
"""
import datetime as dt, gzip, hashlib, importlib.util, json, math, os, shutil, subprocess, sys, tempfile, time, types
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import v3_verify as V

REAL, DATA, OUT = sys.argv[1:4]
H = lambda b: hashlib.sha256(b).hexdigest()
MAIN0 = '1ee593a76cea13ca9c13954b93f40cddad35aace'
show = lambda ref, p: subprocess.run(['git', '-C', REAL, 'show', f'{ref}:{p}'], capture_output=True, check=True).stdout
T0 = time.time(); LOG = []
def log(*a):
    s = ' '.join(str(x) for x in a); LOG.append(s); print(s, f'[{round(time.time() - T0)}s]', flush=True)

TD = tempfile.mkdtemp(prefix='v3full_'); ORIGIN = os.path.join(TD, 'origin.git'); MAIN = os.path.join(TD, 'main'); WT = os.path.join(TD, 'ledger-wt')
FAKE = os.path.join(TD, 'bin'); RUNS = os.path.join(TD, 'runs.json'); CLOCK = os.path.join(TD, 'clock.txt'); EVD = os.path.join(TD, 'evidence')
os.makedirs(FAKE); json.dump([], open(RUNS, 'w'))
def git(cwd, *a, check=True):
    r = subprocess.run(['git', '-C', cwd, *a], capture_output=True, text=True)
    if check and r.returncode != 0: raise SystemExit(f'git {a}: {r.stderr}')
    return r.stdout.strip()

# ---------------------------------------------------------------- 假時鐘、假 GitHub
NOW = [dt.datetime(2026, 1, 20, 12, 0, tzinfo=dt.timezone.utc)]
def set_clock(t):
    NOW[0] = t; open(CLOCK, 'w').write(V.ts(t))
set_clock(NOW[0])
subprocess.run(['git', 'init', '-q', '--bare', ORIGIN], check=True)
hook = os.path.join(ORIGIN, 'hooks', 'post-receive')
open(hook, 'w').write(f'''#!/usr/bin/env python3
import json, sys
runs = json.load(open({RUNS!r})); now = open({CLOCK!r}).read().strip()
for line in sys.stdin:
    old, new, ref = line.split()
    if ref == 'refs/heads/astra-ledger' and set(new) != {{'0'}}:
        rid = 900000000 + len(runs)
        runs.append({{'id': rid, 'name': 'ledger-receipt', 'path': '.github/workflows/ledger-receipt.yml', 'event': 'push', 'head_branch': 'astra-ledger',
                     'head_sha': new, 'created_at': now, 'run_started_at': now, 'status': 'completed', 'conclusion': 'success',
                     'html_url': 'https://github.com/groupuie/market-flow-dashboard/actions/runs/%d' % rid, 'repository': {{'full_name': 'groupuie/market-flow-dashboard'}}}})
json.dump(runs, open({RUNS!r}, 'w'))
''')
os.chmod(hook, 0o755)
GH_BROKEN = os.path.join(TD, 'gh_broken')
open(os.path.join(FAKE, 'gh'), 'w').write(f'''#!/usr/bin/env python3
import json, os, re, sys
if os.path.exists({GH_BROKEN!r}): sys.stderr.write('HTTP 502'); sys.exit(1)
runs = json.load(open({RUNS!r})); p = sys.argv[2]
m = re.fullmatch(r'repos/groupuie/market-flow-dashboard/actions/runs/(\\d+)', p)
if m:
    r = [x for x in runs if x['id'] == int(m.group(1))]
    if not r: sys.stderr.write('HTTP 404'); sys.exit(1)
    print(json.dumps(r[0])); sys.exit(0)
if p.startswith('repos/groupuie/market-flow-dashboard/actions/runs?'):
    h = re.search(r'head_sha=([0-9a-f]{{40}})', p); rs = [x for x in runs if (not h or x['head_sha'] == h.group(1))]
    print(json.dumps({{'total_count': len(rs), 'workflow_runs': sorted(rs, key=lambda x: -x['id'])[:100]}})); sys.exit(0)
if p.startswith('repos/groupuie/market-flow-dashboard/events'): print('[]'); sys.exit(0)
sys.stderr.write('unknown ' + p); sys.exit(1)
''')
os.chmod(os.path.join(FAKE, 'gh'), 0o755); os.environ['PATH'] = FAKE + os.pathsep + os.environ['PATH']

# ---------------------------------------------------------------- main(凍結的三支 + receipt workflow)
subprocess.run(['git', 'clone', '-q', ORIGIN, MAIN], check=True, capture_output=True)
git(MAIN, 'checkout', '-q', '-b', 'main')
for p in ('scripts/astra_ledger.py', 'scripts/astra_trades.py', 'scripts/astra_data.py', '.github/workflows/ledger-receipt.yml'):
    b = show(MAIN0 if p.startswith('scripts') else 'origin/astra-ledger', p); os.makedirs(os.path.dirname(os.path.join(MAIN, p)), exist_ok=True); open(os.path.join(MAIN, p), 'wb').write(b)
git(MAIN, 'add', '-A'); git(MAIN, '-c', 'user.name=fixture', '-c', 'user.email=f@f', 'commit', '-qm', 'engine (frozen bytes from 1ee593a)'); git(MAIN, 'push', '-q', 'origin', 'main')
E = git(MAIN, 'rev-parse', 'HEAD')
FROZEN = {p: H(open(os.path.join(MAIN, p), 'rb').read()) for p in V.ENGINE_FILES}
assert all(FROZEN[p] == H(show(MAIN0, p)) for p in FROZEN)

# ---------------------------------------------------------------- 假的 Yahoo(真實日K重新標日期)
man = json.load(open(os.path.join(DATA, 'manifest.json')))['symbols']
spyb = json.load(open(os.path.join(DATA, 'adjusted/SPY.json')))['bars']; RD = [b[0] for b in spyb if b[0] >= '2019-06-03'][:480]
full = []
for s, v in sorted(man.items()):
    if s in ('SPY', 'QQQ'): continue
    ds = {x[0] for x in json.load(open(os.path.join(DATA, v['adjustedFile'])))['bars']}
    if all(d in ds for d in RD): full.append(s)
UNI = sorted(set(full[::2][:98]) | {'GOOG', 'GOOGL'}) + ['SPY', 'QQQ']
START = '2026-02-02'
pre = []; d0 = dt.date(2026, 1, 30)
while len(pre) < 300:
    if d0.weekday() < 5 and (d0.year < 2026 or V.is_session(d0)): pre.append(d0.isoformat())
    d0 -= dt.timedelta(days=1)
FD = sorted(pre) + V.sessions(START, '2026-12-31')[:180]; assert len(FD) == 480 and FD[300] == START
MAP = dict(zip(RD, FD))
RAW = {}
for s in UNI:
    b = {x[0]: x for x in json.load(open(os.path.join(DATA, man[s]['adjustedFile'])))['bars']}
    RAW[s] = [[MAP[d]] + [float(v) for v in b[d][1:5]] + [int(b[d][5] or 0)] for d in RD]
COH = V.sessions(START, V.add_sessions(START, 120)); END = COH[-1]
import importlib
spec = importlib.util.spec_from_file_location('fx_astra_data', os.path.join(MAIN, 'scripts/astra_data.py')); ADx = importlib.util.module_from_spec(spec); spec.loader.exec_module(ADx)
spec = importlib.util.spec_from_file_location('fx_astra_trades', os.path.join(MAIN, 'scripts/astra_trades.py')); ATx = importlib.util.module_from_spec(spec); spec.loader.exec_module(ATx)
rnd = lambda bars: [[x[0], ADx.rp(x[1]), ADx.rp(x[2]), ADx.rp(x[3]), ADx.rp(x[4]), x[5]] for x in bars][-ADx.KEEP:]
def first_buy(sym, after):
    """凍結引擎在原始資料上的第一個收案期買點(之後 3 個交易日放公司行動 → 一定有部位跨過它)"""
    for d in COH:
        if d < after or d > COH[100]: continue
        pb = rnd([b for b in RAW[sym] if b[0] <= d])
        if (len(pb) - 1) in dict(ATx.buy_points(ADx.sw_series(pb))): return d
    return None
# 先用凍結引擎預估每一天的買點(只看到那天為止的資料 → 和逐日算的一樣),挑特別日
BP = {}
for s_ in UNI:
    pb = rnd(RAW[s_]); W_ = ADx.sw_series(pb); O_ = [b[1] for b in pb]
    for i_, k_ in ATx.buy_points(W_):
        d_, w_ = ATx.exit_of(W_, O_, i_, ATx.style_of(s_)); BP.setdefault(pb[i_][0], []).append((s_, None if d_ is None or d_ + 1 >= len(pb) else pb[d_ + 1][0]))
busy = [d for d in COH if len(BP.get(d, [])) >= 3]
X1 = next(d for d in busy if d >= COH[5]); X2 = COH[20]; X3 = next(d for d in busy if d >= COH[35]); X4 = COH[50]   # 早上失敗下午補 / 整天失敗 / 晚鎖 / 零訊號
cand = [(d, s_, x_) for d in COH[60:90] for s_, x_ in BP.get(d, []) if s_ not in ('SPY', 'QQQ') and x_ and x_ > V.add_sessions(d, 6)]
DD_, DELIST, _ = cand[0]; DELIST_AFTER = V.add_sessions(DD_, 3)                     # 進場之後、出場之前就下市
EVENTS = {}
for k, (sym, f, kind) in enumerate([(UNI[3], 0.99, 'div'), (UNI[11], 0.99, 'div'), (UNI[19], 0.99, 'div'), (UNI[27], 0.5, 'split')]):
    if sym == DELIST: continue
    bd = first_buy(sym, COH[10 + 20 * k])
    if bd: EVENTS[sym] = [(V.add_sessions(bd, 4), f, kind)]
CUR = {'asof': None, 'omit_idx_last': False}
def fake_yahoo(sym, p1, p2, cache=None):
    if sym not in RAW: return []
    asof = CUR['asof']; bars = [list(b) for b in RAW[sym] if b[0] <= asof]
    if sym == DELIST: bars = [b for b in bars if b[0] <= DELIST_AFTER]
    if CUR['omit_idx_last'] and sym in ('SPY', 'QQQ'): bars = [b for b in bars if b[0] < asof]
    for e, f, kind in EVENTS.get(sym, []):
        if e <= asof:
            for b in bars:
                if b[0] < e or kind == 'split': b[1:5] = [x * f for x in b[1:5]]
    return [tuple(b) for b in bars]
# 零訊號日:每檔那一天換成「不是買點」的平盤 K 線(只動那一根;用假 Yahoo 實際會給的資料、凍結引擎逐檔核對)
ix4 = FD.index(X4); CUR['asof'] = X4
for s in UNI:
    bars = RAW[s]; prev = bars[ix4 - 1]; lo7, hi7 = min(b[4] for b in bars[ix4 - 6:ix4]), max(b[4] for b in bars[ix4 - 6:ix4])
    for c in ((lo7 + hi7) / 2, (prev[3] + prev[2]) / 2, prev[4], (prev[4] + prev[2]) / 2, hi7, prev[3]):
        c = min(c, prev[2]); bars[ix4] = [X4, c, c, c, c, bars[ix4][5]]
        pb = rnd(fake_yahoo(s, 0, 0))
        if pb[-1][0] == X4 and (len(pb) - 1) not in dict(ATx.buy_points(ADx.sw_series(pb))): break
    else: raise SystemExit(f'{s}: 找不到零訊號的收盤')

# ---------------------------------------------------------------- 真的凍結收集程式(在程式裡換掉時鐘、資料、睡覺)
os.environ['ASTRA_LEDGER_WT'] = WT
spec = importlib.util.spec_from_file_location('astra_ledger_fx', os.path.join(MAIN, 'scripts/astra_ledger.py')); AL = importlib.util.module_from_spec(spec)
sys.path.insert(0, os.path.join(MAIN, 'scripts')); spec.loader.exec_module(AL); sys.path.remove(os.path.join(MAIN, 'scripts'))
assert os.path.dirname(os.path.abspath(AL.AD.__file__)) == os.path.join(MAIN, 'scripts') and H(open(AL.AD.__file__, 'rb').read()) == FROZEN['scripts/astra_data.py']
AL.utcnow = lambda: NOW[0]; AL.last_done = lambda now=None: CUR['asof']; AL.regime_fetch = lambda: (None, {'note': 'fixture', 'fetched_utc': V.ts(NOW[0])})
AL.time.sleep = lambda s: None; AL.AD.yahoo = fake_yahoo
NS = lambda **k: types.SimpleNamespace(**k)
tmpf = lambda name, b: (open(os.path.join(TD, name), 'wb').write(b), os.path.join(TD, name))[1]
AL.cmd_init(NS(universe=tmpf('universe.txt', ('\n'.join(UNI) + '\n').encode()), protocol=tmpf('PROTOCOL.md', show('origin/astra-ledger', 'PROTOCOL.md')), readme=''))
AL.cmd_freeze(NS(protocol='v2', prompt=tmpf('prompt_v2.md', show('origin/astra-ledger', 'prompt_v2.md'))))
V2SHA = H(open(os.path.join(WT, 'engine_manifest.json'), 'rb').read()); log('v2 freeze', V2SHA[:12], 'universe', len(UNI))

# ---------------------------------------------------------------- 凍結 v3(manifest 在 main,錨點在 astra-ledger)
os.makedirs(os.path.join(MAIN, 'research/ledger_v3'), exist_ok=True)
VB = open(os.path.join(HERE, 'v3_verify.py'), 'rb').read(); open(os.path.join(MAIN, V.VERIFIER_PATH), 'wb').write(VB)
MAN = V.make_manifest(START, 120, 'none', V2SHA, VB, 1.0, 'fixture'); MB = (json.dumps(MAN, ensure_ascii=False, indent=1) + '\n').encode()
open(os.path.join(MAIN, V.MANIFEST_PATH), 'wb').write(MB)
set_clock(dt.datetime(2026, 1, 30, 12, 0, tzinfo=dt.timezone.utc))
git(MAIN, 'add', '-A'); git(MAIN, '-c', 'user.name=fixture', '-c', 'user.email=f@f', 'commit', '-qm', 'freeze v3'); git(MAIN, 'push', '-q', 'origin', 'main'); F = git(MAIN, 'rev-parse', 'HEAD')
AL.worktree(); ap = os.path.join(WT, MAN['anchor_path']); os.makedirs(os.path.dirname(ap), exist_ok=True)
json.dump(V.anchor_json(MB, F), open(ap, 'w'), indent=1); A_ = AL.commit_push('v3 freeze anchor', [MAN['anchor_path']])
log('v3 frozen', MAN['experiment_id'], 'F', F[:10], 'anchor', A_[:10])

# ---------------------------------------------------------------- 每天:prep → 判讀 → lock → score
def verdicts(asof):
    pp = os.path.join(WT, 'pending', asof + '.json'); P = json.load(open(pp)); vm = []
    for m in P['marks']:
        h = int(hashlib.sha256(m['id'].encode()).hexdigest()[:8], 16)
        v = 'agree' if (m['sym'] == DELIST or h % 100 < 45) else 'disagree'
        vm.append({'id': m['id'], 'v': v, 'p': 0.6 if v == 'agree' else 0.4, 'why': 'fixture(id 雜湊,沒有判斷力)'})
    vp = pp.replace(os.sep + 'pending' + os.sep, os.sep + 'verdicts' + os.sep); os.makedirs(os.path.dirname(vp), exist_ok=True)
    json.dump({'asof': asof, 'model': 'claude-opus-5-5', 'marks': vm}, open(vp, 'w'), ensure_ascii=False, indent=1)
    return len(vm)

def at(d, hh, mm):   # 美股日 d 收盤後:台北隔天 hh:mm(UTC = 台北 − 8)
    n = dt.date.fromisoformat(d) + dt.timedelta(days=1)
    return dt.datetime(n.year, n.month, n.day, hh, mm, tzinfo=dt.timezone.utc)

def prep(d, t, omit=False):
    set_clock(t); CUR.update(asof=d, omit_idx_last=omit)
    try: AL.cmd_prep(NS(asof=d, test=False)); return True
    except SystemExit as e: log('prep stop', d, str(e)[:60]); return False

STAT = {'locked': 0, 'no_signals': 0, 'failed': 0, 'late': 0, 'marks': 0}
for d in FD[FD.index(START):]:
    if d <= END:
        if d == X2: prep(d, at(d, 0, 40), omit=True); prep(d, at(d, 5, 14), omit=True); STAT['failed'] += 1
        else:
            if d == X1: prep(d, at(d, 0, 40), omit=True)
            prep(d, at(d, 5, 14)); b = json.load(open(os.path.join(WT, 'batches', d + '.json')))
            if b['status'] == 'pending_verdict':
                STAT['marks'] += verdicts(d)
                t = (V.deadline_utc(d) + dt.timedelta(minutes=30)) if d == X3 else at(d, 5, 15)
                set_clock(t); AL.cmd_lock(NS(asof=d, test=False)); STAT['late' if d == X3 else 'locked'] += 1
            else: STAT[b['status']] = STAT.get(b['status'], 0) + 1
    set_clock(at(d, 5, 16)); CUR.update(asof=d, omit_idx_last=False)
    if d > END and d < COH[-1]: pass
    AL.cmd_score(NS())
    if d >= V.add_sessions(END, 53): break
sc = json.load(open(os.path.join(WT, 'scores.json'))); LAST = d
log('collector done', STAT, 'last', LAST, 'scores', sc['counts'])
assert STAT['no_signals'] >= 1 and json.load(open(os.path.join(WT, 'batches', X4 + '.json')))['status'] == 'no_signals'
git(MAIN, 'fetch', '-q', 'origin')

# ---------------------------------------------------------------- 正式判定
RES = {'fixture': {'universe': UNI, 'start': START, 'end': END, 'special_days': {'idx_late_morning_then_ok': X1, 'failed_all_day': X2, 'late_lock': X3, 'no_signals': X4},
                   'delisted': [DELIST, DELIST_AFTER], 'events': EVENTS, 'collector_status_counts': STAT, 'collector_scores_counts': sc['counts'],
                   'frozen_engine_sha256': FROZEN, 'experiment_id': MAN['experiment_id'], 'manifest_sha256': H(MB)}}
def now_set(t): V.clock = lambda: t
mature = dt.datetime.fromisoformat(V.add_sessions(END, 52) + 'T20:30:00+00:00')
def expect_stop(name, fn, want):
    try:
        fn(); RES.setdefault('stops', {})[name] = 'DID NOT STOP'; raise AssertionError(name)
    except SystemExit as e:
        assert want in str(e), (name, str(e)); RES.setdefault('stops', {})[name] = str(e)[:160]; log('stop ok', name, '|', str(e)[:70])
lp = os.path.join(MAIN, MAN['look_path'])
now_set(dt.datetime.fromisoformat(V.add_sessions(END, 20) + 'T20:30:00+00:00'))
expect_stop('not_mature_yet', lambda: V.formal_run(MAIN, evdir=EVD, me_path=os.path.join(MAIN, V.VERIFIER_PATH)), '還不能判定')
assert not os.path.exists(lp)
open(GH_BROKEN, 'w').write('x'); now_set(mature)
expect_stop('github_api_down_no_look', lambda: V.formal_run(MAIN, evdir=EVD + '_down', me_path=os.path.join(MAIN, V.VERIFIER_PATH)), '不寫判定'); os.remove(GH_BROKEN)
assert not os.path.exists(lp)
bad = os.path.join(TD, 'v3_verify_modified.py'); open(bad, 'wb').write(VB + b'\n# changed\n')
expect_stop('modified_verifier', lambda: V.formal_run(MAIN, evdir=EVD, me_path=bad), '不是凍結的驗證程式')
look, lp2 = V.formal_run(MAIN, evdir=EVD, me_path=os.path.join(MAIN, V.VERIFIER_PATH)); assert lp2 == lp and os.path.exists(lp)
log('FORMAL', look['decision'], 'go_live', look['go_live_candidate'], 'coverage', look['status']['batch_coverage']['ok'], '/', look['status']['batch_coverage']['seen'],
    'counts', look['status']['counts'])
# 同一份資料用試跑重算一次 → 判定與數字要一樣
cfg = dict(V.SPEC, cohort_sessions=120, h2_mode='none', start=START, v2_manifest_sha256=V2SHA)
g = V.Git(MAIN); store = V.Evidence(EVD, online=True)
pub, closed, missing, cal, cov = V.collect(g, g.verify('origin/astra-ledger'), g.verify('origin/main'), cfg, mature.astimezone(V.ET).date().isoformat(), mature, store)
dres = V.decide(closed, missing, cal, cfg, cov)
same = (dres['decision'] == look['decision'] and dres['decision_by_h2_mode'] == look['result']['decision_by_h2_mode']
        and json.dumps(dres['excluded_missing'], sort_keys=True) == json.dumps(look['result']['excluded_missing'], sort_keys=True))
assert same
expect_stop('second_formal_run_refused', lambda: V.formal_run(MAIN, evdir=EVD, me_path=os.path.join(MAIN, V.VERIFIER_PATH)), '已經做過')
git(MAIN, 'add', MAN['look_path']); git(MAIN, '-c', 'user.name=fixture', '-c', 'user.email=f@f', 'commit', '-qm', 'look'); os.remove(lp)
expect_stop('refused_after_delete_git_history', lambda: V.formal_run(MAIN, evdir=EVD, me_path=os.path.join(MAIN, V.VERIFIER_PATH)), '已經做過')
git(MAIN, 'reset', '-q', '--hard', 'HEAD~1')
# 竄改 / 時序反例:各自在分支上做,main_ref / ledger_ref 指向它
def branch_case(name, setup, want, ledger=None):
    git(MAIN, 'checkout', '-q', '-B', 'case-' + name, 'origin/main'); setup(); git(MAIN, 'add', '-A')
    git(MAIN, '-c', 'user.name=fixture', '-c', 'user.email=f@f', 'commit', '-qm', 'case ' + name, '--allow-empty')
    expect_stop(name, lambda: V.formal_run(MAIN, ledger_ref=ledger or 'origin/astra-ledger', main_ref='case-' + name, evdir=EVD, me_path=os.path.join(MAIN, V.VERIFIER_PATH)), want)
    git(MAIN, 'checkout', '-q', 'main'); git(MAIN, 'reset', '-q', '--hard', 'origin/main')
def edit_manifest(k, v):
    def f():
        m = json.loads(open(os.path.join(MAIN, V.MANIFEST_PATH), 'rb').read()); m[k] = v; open(os.path.join(MAIN, V.MANIFEST_PATH), 'w').write(json.dumps(m, ensure_ascii=False, indent=1) + '\n')
    return f
branch_case('manifest_edited_after_freeze', edit_manifest('note', 'changed later'), '個 commit 改過')
branch_case('verifier_edited_after_freeze', lambda: open(os.path.join(MAIN, V.VERIFIER_PATH), 'ab').write(b'\n'), '不同')
# 換一份「從頭就不同」的 manifest(只被一個 commit 寫過):固定規格被改 / 起日在錨點之前
def fresh_manifest(name, mutate, want, anchor_time=None, start=START):
    git(MAIN, 'checkout', '-q', '-B', 'case-' + name, E)
    m = V.make_manifest(start, 120, 'none', V2SHA, VB, 1.0, 'case ' + name); mutate(m); mb = (json.dumps(m, ensure_ascii=False, indent=1) + '\n').encode()
    os.makedirs(os.path.join(MAIN, 'research/ledger_v3'), exist_ok=True); open(os.path.join(MAIN, V.VERIFIER_PATH), 'wb').write(VB); open(os.path.join(MAIN, V.MANIFEST_PATH), 'wb').write(mb)
    git(MAIN, 'add', '-A'); git(MAIN, '-c', 'user.name=fixture', '-c', 'user.email=f@f', 'commit', '-qm', 'freeze ' + name); f = git(MAIN, 'rev-parse', 'HEAD')
    lref = 'origin/astra-ledger'
    if anchor_time:
        set_clock(anchor_time); AL.worktree(); p = os.path.join(WT, m['anchor_path']); os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(V.anchor_json(mb, f), open(p, 'w'), indent=1); AL.commit_push('anchor ' + name, [m['anchor_path']]); git(MAIN, 'fetch', '-q', 'origin')
    expect_stop(name, lambda: V.formal_run(MAIN, ledger_ref=lref, main_ref='case-' + name, evdir=EVD, me_path=os.path.join(MAIN, V.VERIFIER_PATH)), want)
    git(MAIN, 'checkout', '-q', 'main'); git(MAIN, 'reset', '-q', '--hard', 'origin/main')
fresh_manifest('fixed_spec_changed', lambda m: m['spec'].update(min_closed=200), '固定規格')
fresh_manifest('calendar_changed', lambda m: m.update(calendar_sha256='0' * 64), '日曆')
fresh_manifest('no_anchor', lambda m: m.update(note='no anchor'), '凍結錨點')
fresh_manifest('anchor_after_start', lambda m: m.update(note='late anchor'), '不早於起日', anchor_time=dt.datetime(2026, 2, 3, 22, 0, tzinfo=dt.timezone.utc), start='2026-02-03')
fresh_manifest('h2_not_allowed', lambda m: m['spec'].update(h2_mode='best_of_three'), '不在允許的選項')
# 結果整理
st = look['status']; res = look['result']; ex = res['excluded_missing']
flags = st['flags']; resc = {k: v for k, v in flags.items() if 'rescaled' in v}; unrep = {k: v for k, v in flags.items() if v.startswith('unreproducible')}
RES['formal'] = {'decision': look['decision'], 'decision_by_h2_mode': res['decision_by_h2_mode'], 'go_live_candidate': look['go_live_candidate'],
                 'gates': res['gates'], 'n_closed': res['n_closed'], 'n_missing': res['n_missing'], 'agree': res['agree'], 'disagree': res['disagree'],
                 'h1_pp': ex['h1_pp'], 'h1_lb_pp': ex['h1_lb_pp'], 'h1_ub_pp': ex['h1_ub_pp'], 'paired_dates': ex['paired_dates'],
                 'issuers': [ex['issuers_agree'], ex['issuers_disagree']], 'coverage': {k: st['batch_coverage'][k] for k in ('ok', 'seen', 'rate')},
                 'rejected_days': {d: v for d, v in st['batch_coverage']['by_date'].items() if not v['accepted']},
                 'no_signals_day': st['batch_coverage']['by_date'][X4], 'idx_late_morning_day': st['batch_coverage']['by_date'][X1],
                 'counts': st['counts'], 'rescaled_marks': resc, 'unreproducible': unrep, 'look_sha256': H(open(os.path.join(MAIN, MAN['look_path']), 'rb').read()) if os.path.exists(os.path.join(MAIN, MAN['look_path'])) else None,
                 'same_as_dry_run_decide': same, 'evidence_files_used': len(st['evidence_used'])}
assert RES['formal']['coverage']['ok'] == RES['formal']['coverage']['seen'] - 2 and set(RES['formal']['rejected_days']) == {X2, X3}
assert RES['formal']['no_signals_day']['accepted'] and RES['formal']['idx_late_morning_day']['accepted'] and len(resc) > 0
RES['meta'] = {'seconds': round(time.time() - T0), 'verifier_sha256': H(VB), 'log': LOG}
json.dump(RES, open(OUT, 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps({k: RES['formal'][k] for k in ('decision', 'decision_by_h2_mode', 'coverage', 'n_closed', 'n_missing', 'h1_pp', 'h1_lb_pp')}, ensure_ascii=False))
shutil.rmtree(TD, ignore_errors=True)
