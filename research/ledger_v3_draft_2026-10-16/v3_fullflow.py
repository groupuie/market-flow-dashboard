#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盤感測試 v3 草案 5:**完整正式流程驗收**(Claude 2026-10-17 建、2026-10-21 改;回應 Astra v0.7.4 §5.2、v0.7.5 §3、v0.7.6 §3)
草案 5:正式判定在結案截止 + 24 小時後,只用截止前 GitHub 已收到的 ledger 狀態(截止視圖);試跑對照走 dry_collect(同一個視圖);
       另和舊規則(最新 ledger + 本機結案時間)逐事件比,列出分類改變的事件與截止後才到 GitHub 的 commit
草案 4 的正式判定 = 開跑登記(push 到 astra-ledger、拿到 GitHub 收件)→ 只用登記的輸入計算 → 判定檔 push 到 main、讀回核對;
這裡依序驗:登記前的 5 種停止(還沒成熟、API 掛、程式被改、本機快取壞 → 修復、登記被拒收)、登記後判定存不進去 → 停(未持久完成)、
登記後 ledger 又有新 commit → 重跑照登記重播並保存、再跑一次 / 另一個 checkout → 一模一樣不寫東西、竄改遠端判定 / 登記 → 停,
加上原本凍結相關的 7 種停止(共 15 種)

用「真的凍結收集程式」(scripts/astra_ledger.py 等三支,git 1ee593a 的原位元組)在暫存環境跑完整一輪,再用 v3 正式模式做唯一一次判定:
  - 暫存 GitHub:本機 bare repo 當 origin;push 到 astra-ledger 時由 post-receive hook 記一筆「ledger-receipt run」(時間 = 假時鐘);
    假的 gh 指令照 GitHub API 的格式回答(收集程式的 remote_receipt 與驗證程式的回條查詢都走它)
  - 假的 Yahoo:101 檔(99 檔股票含 GOOG / GOOGL + SPY / QQQ)真實日K(2019-06 起 480 個交易日)重新標成 2024-12 ~ 2026-10 的日期;
    收案期 2026-02-02 起 120 個交易日(收集程式與官方日曆在 2026 年一致)
  - 刻意放進去的狀況:早上第一次跑 SPY 還沒更新(下午補鎖成功)/ 整天失敗 / 晚鎖(過了截止)/ 真的零訊號日 /
    三檔配息(之後抓的資料把除息日以前 × 0.99)/ 一檔 1 拆 2(× 0.5)/ 一檔下市(之後沒有資料;它的判讀都是同意 → 缺的同意填 −100%)
  - 判讀:用 id 的雜湊決定同意 / 不同意(沒有判斷力);model = claude-opus-5-5
  - 凍結:main 上 research/ledger_v3/v3_manifest.json(make_manifest)+ 驗證程式;astra-ledger 上的凍結錨點在起日前 push
  - 正式判定:V.formal_run(時鐘換成成熟之後);結果要和 dry-run + decide 一樣;第二次要拒絕;git 歷史有就拒絕;
    連同還沒成熟、API 掛、程式被改、第二次等,共 12 種停止反例,每一種都要「停、不寫判定」
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
subprocess.run(['git', 'init', '-q', '--bare', '-b', 'main', ORIGIN], check=True)
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
CUT = V.close_utc(MAN['resolve_by']); mature = CUT + dt.timedelta(hours=25)        # 草案 5:結案截止 + 24 小時之後才能正式登記
def expect_stop(name, fn, want):
    try:
        fn(); RES.setdefault('stops', {})[name] = 'DID NOT STOP'; raise AssertionError(name)
    except SystemExit as e:
        assert want in str(e), (name, str(e)); RES.setdefault('stops', {})[name] = str(e)[:160]; log('stop ok', name, '|', str(e)[:70])
REJ = os.path.join(TD, 'reject_')               # pre-receive hook:有 reject_<分支> 這個檔就拒收那個分支的 push(模擬網路 / 權限失敗)
pre = os.path.join(ORIGIN, 'hooks', 'pre-receive')
open(pre, 'w').write(f'#!/usr/bin/env python3\nimport os, sys\nfor line in sys.stdin:\n    old, new, ref = line.split()\n'
                     f'    if os.path.exists({REJ!r} + ref.split("/")[-1]): sys.stderr.write("rejected by fixture"); sys.exit(1)\n')
os.chmod(pre, 0o755)
VP = os.path.join(MAIN, V.VERIFIER_PATH)
FR = lambda repo=MAIN, evdir=EVD: V.formal_run(repo, evdir=evdir, me_path=VP)
def remote_state():
    g_ = V.Git(MAIN); rm, rl = V.fetch_remote(g_, 'origin')
    return {'main': rm, 'ledger': rl, 'registration': g_.touching(rl, V.registration_path(MAN['experiment_id'])), 'look': g_.touching(rm, MAN['look_path'])}
def nothing_written():
    s = remote_state(); assert s['registration'] == [] and s['look'] == [], s
now_set(dt.datetime.fromisoformat(V.add_sessions(END, 20) + 'T20:30:00+00:00'))
expect_stop('not_mature_yet', FR, '還不能判定'); nothing_written()
open(GH_BROKEN, 'w').write('x'); now_set(mature)
expect_stop('github_api_down_no_look', lambda: FR(evdir=EVD + '_down'), '不寫判定'); os.remove(GH_BROKEN); nothing_written()
bad = os.path.join(TD, 'v3_verify_modified.py'); open(bad, 'wb').write(VB + b'\n# changed\n')
expect_stop('modified_verifier', lambda: V.formal_run(MAIN, evdir=EVD, me_path=bad), '不是凍結的驗證程式'); nothing_written()
CF = sorted(f for f in os.listdir(EVD) if f.startswith(('run-', 'runs-for-')))[0]; open(os.path.join(EVD, CF), 'w').write('{local cache damaged')   # GitHub 正常、只有本機快取壞
# (草案 5:「還沒成熟」在讀批次收件之前就停 → 這時資料夾裡只有凍結錨點的 run 清單 runs-for-<錨點>.json;壞的是它)
expect_stop('local_cache_damaged_no_registration', FR, 'repair-evidence'); nothing_written()
REPAIR = V.repair_evidence(EVD, CF); assert REPAIR['status'] == 'repaired', REPAIR
open(REJ + 'astra-ledger', 'w').close(); expect_stop('registration_push_rejected', FR, '開跑登記沒有送到遠端'); os.remove(REJ + 'astra-ledger'); nothing_written()
open(REJ + 'main', 'w').close(); expect_stop('look_push_rejected_after_registration', FR, '未持久完成'); os.remove(REJ + 'main')
S1 = remote_state(); assert len(S1['registration']) == 1 and S1['look'] == [], S1
# 登記之後收集程式照常 push 新 commit → 重跑只用登記的輸入
set_clock(NOW[0] + dt.timedelta(hours=1)); AL.worktree(); open(os.path.join(WT, 'notes_after_registration.txt'), 'w').write('collector kept going\n')
AL.commit_push('after v3 registration', ['notes_after_registration.txt'])
look, info = FR(); S2 = remote_state(); REG = look['registration']['record']
assert info['mode'] == 'REPLAY' and info['status'] == 'PERSISTED' and len(S2['look']) == 1, info
assert look['status']['refs']['ledger'] == REG['ledger_view_commit'] and S2['ledger'] != REG['ledger_view_commit'] and look['analysis_time_utc'] == V.ts(CUT)
log('FORMAL', look['decision'], 'go_live', look['go_live_candidate'], 'coverage', look['status']['batch_coverage']['ok'], '/', look['status']['batch_coverage']['seen'],
    'counts', look['status']['counts'], '| registration', info['registration_commit'][:10], 'look', info['look_commit'][:10])
# 同一份資料用試跑重算一次(試跑和正式同一個截止語義:截止 + 24 小時之後只用截止視圖、分析時點 = 截止收盤)→ 判定與數字要一樣
cfg = dict(V.SPEC, cohort_sessions=120, h2_mode='none', start=START, v2_manifest_sha256=V2SHA)
g = V.Git(MAIN); store = V.Evidence(EVD + '_dry', online=True); HEAD_L = g.verify('origin/astra-ledger')
pub, closed, missing, cal, cov = V.dry_collect(g, HEAD_L, g.verify('origin/main'), cfg, mature.astimezone(V.ET).date().isoformat(), mature, store, analyze=True)
VIEW = pub['cutoff_view']; VC, VT = VIEW['commit'], VIEW['received_utc']
assert (VC, VT, VIEW['receipt_run_id']) == (REG['ledger_view_commit'], REG['ledger_view_received_utc'], REG['ledger_view_receipt_run_id'])   # 從更晚的 head 選出同一個視圖
# 和舊規則(最新 ledger + 本機結案時間 = 草案 4 的語義)逐事件比:哪些事件的分類因為截止視圖而改變
pub_o, closed_o, missing_o, *_ = V.collect(g, HEAD_L, g.verify('origin/main'), cfg, mature.astimezone(V.ET).date().isoformat(), mature, V.Evidence(EVD + '_old', online=True))
kc, ko, mc_, mo = {c[:4] for c in closed}, {c[:4] for c in closed_o}, set(missing), set(missing_o)
CHG = {'closed_view_only': sorted(kc - ko), 'closed_local_rule_only': sorted(ko - kc), 'missing_view_only': sorted(mc_ - mo), 'missing_local_rule_only': sorted(mo - mc_),
       'counts_view_closed_missing': [len(closed), len(missing)], 'counts_local_rule_closed_missing': [len(closed_o), len(missing_o)],
       'closed_after_cutoff_flags_local_rule': sorted(k for k, v in pub_o['flags'].items() if v.startswith('closed_after_cutoff')), 'missing_keys_view': sorted(mc_)}
after = g.run('rev-list', '--first-parent', '--reverse', f'{VC}..{HEAD_L}').decode().split(); RUNS_ = json.load(open(RUNS))   # 截止之後才到 GitHub 的 ledger commit
AFTER_VIEW = [{'commit': c[:10], 'receipts_utc': sorted(r['created_at'] for r in RUNS_ if r['head_sha'] == c),
               'files': [x for x in g.run('diff-tree', '--no-commit-id', '--name-only', '-r', c).decode().split('\n') if x][:6]} for c in after]
log('cutoff view', VC[:10], VT, 'run', VIEW['receipt_run_id'], '| commits after view', len(after), '| changes vs local-time rule',
    {k: len(v) for k, v in CHG.items() if k.endswith('_only')}, CHG['counts_view_closed_missing'], CHG['counts_local_rule_closed_missing'])
dres = V.decide(closed, missing, cal, cfg, cov)
same = (dres['decision'] == look['decision'] and dres['decision_by_h2_mode'] == look['result']['decision_by_h2_mode']
        and json.dumps(dres['excluded_missing'], sort_keys=True) == json.dumps(look['result']['excluded_missing'], sort_keys=True))
assert same
look2, info2 = FR(); S3 = remote_state()
assert info2['status'] == 'ALREADY_PERSISTED_IDENTICAL' and info2['look_sha256'] == info['look_sha256'] and (S3['main'], S3['ledger']) == (S2['main'], S2['ledger']), info2
CL = os.path.join(TD, 'other-checkout'); subprocess.run(['git', 'clone', '-q', ORIGIN, CL], check=True)
look3, info3 = FR(repo=CL, evdir=os.path.join(TD, 'evidence_other'))
assert info3['status'] == 'ALREADY_PERSISTED_IDENTICAL' and info3['look_sha256'] == info['look_sha256'], info3
REPLAYS = {'after_failed_save': {k: info[k] for k in ('mode', 'status', 'look_sha256')}, 'second_run': {k: info2[k] for k in ('mode', 'status', 'look_sha256')},
           'other_checkout': {k: info3[k] for k in ('mode', 'status', 'look_sha256')}, 'ledger_input_commit': REG['ledger_input_commit'],
           'ledger_view_commit': REG['ledger_view_commit'], 'ledger_view_received_utc': REG['ledger_view_received_utc'], 'ledger_head_now': S2['ledger']}
def tamper(branch, path, edit, name, want, restore_to):
    c = os.path.join(TD, 'tamper-' + name); subprocess.run(['git', 'clone', '-q', '-b', branch, ORIGIN, c], check=True)
    p_ = os.path.join(c, path); open(p_, 'wb').write(edit(open(p_, 'rb').read()))
    git(c, 'add', '-A'); git(c, '-c', 'user.name=fixture', '-c', 'user.email=f@f', 'commit', '-qm', 'tamper ' + name); git(c, 'push', '-q', 'origin', branch)
    expect_stop(name, FR, want)
    git(MAIN, 'push', '-q', '-f', 'origin', f'{restore_to}:refs/heads/{branch}'); git(MAIN, 'fetch', '-q', 'origin')
tamper('main', MAN['look_path'], lambda b: b.replace(b'"decision": "NO_PASS"', b'"decision": "PASS"', 1), 'remote_look_tampered', '不同', S2['main'])
tamper(V.LEDGER_BRANCH, V.registration_path(MAN['experiment_id']), lambda b: b.replace(b'"schema"', b'"note": "edited", "schema"', 1), 'registration_tampered', '開跑登記被改過', S2['ledger'])
assert FR()[1]['status'] == 'ALREADY_PERSISTED_IDENTICAL'
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
                 'counts': st['counts'], 'rescaled_marks': resc, 'unreproducible': unrep, 'look_sha256': info['look_sha256'],
                 'same_as_dry_run_decide': same, 'evidence_files_used': len(st['evidence_used']),
                 'registration': {'commit': info['registration_commit'], 'remote_received_utc': look['registration']['remote_received_utc'], 'record': REG},
                 'persistence': {k: info[k] for k in ('mode', 'status', 'look_commit', 'look_path')}, 'replays': REPLAYS, 'cache_repair': REPAIR,
                 'analysis_time_utc': look['analysis_time_utc'], 'resolve_by': st['cohort']['resolve_by'], 'formal_earliest_utc': st['cohort']['formal_earliest_utc'],
                 'cutoff_view': VIEW, 'classification_vs_local_time_rule': CHG, 'ledger_commits_after_view': AFTER_VIEW}
assert RES['formal']['coverage']['ok'] == RES['formal']['coverage']['seen'] - 2 and set(RES['formal']['rejected_days']) == {X2, X3}
assert RES['formal']['no_signals_day']['accepted'] and RES['formal']['idx_late_morning_day']['accepted'] and len(resc) > 0
RES['meta'] = {'seconds': round(time.time() - T0), 'verifier_sha256': H(VB), 'log': LOG}
json.dump(RES, open(OUT, 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps({k: RES['formal'][k] for k in ('decision', 'decision_by_h2_mode', 'coverage', 'n_closed', 'n_missing', 'h1_pp', 'h1_lb_pp')}, ensure_ascii=False))
shutil.rmtree(TD, ignore_errors=True)
