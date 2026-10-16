#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3 草案的離線測試(Claude 2026-10-16):Astra v0.7.2 附錄五的 9 個探針,換成 v3 應該有的行為
   只用暫存資料夾裡自己做的 git repo + 一份真實快照(10/14 的 ADI);不連網、不動遠端
   用法:python3 -I v3_tests.py <repo(要有 origin/astra-ledger)>"""
import datetime as dt, gzip, hashlib, json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import v3_verify as V
import astra_data as AD, astra_trades as AT

REPO = sys.argv[1]; R = []
def ok(name, cond, proof=None):
    assert cond, name; R.append({'name': name, 'pass': True, 'proof': proof})
H = lambda b: hashlib.sha256(b).hexdigest()

# ---- 1. 日曆(官方 2026–2028)
ok('good_friday_2027', V.deadline_utc('2027-03-25').isoformat() == '2027-03-29T13:30:00+00:00', V.deadline_utc('2027-03-25').isoformat())
ok('christmas_2026', V.deadline_utc('2026-12-24').isoformat() == '2026-12-28T14:30:00+00:00')
ok('christmas_observed_2027', V.deadline_utc('2027-12-23').isoformat() == '2027-12-27T14:30:00+00:00')
ok('juneteenth_observed_2027', V.deadline_utc('2027-06-17').isoformat() == '2027-06-21T13:30:00+00:00')
ok('independence_observed_2027', V.deadline_utc('2027-07-02').isoformat() == '2027-07-06T13:30:00+00:00')
try:
    V.is_session('2029-01-02'); ok('calendar_out_of_range_stops', False)
except SystemExit as e:
    ok('calendar_out_of_range_stops', True, str(e))

# ---- 2. 收案期固定 120 個交易日(和有沒有買點無關)
ok('cohort_end_by_calendar', V.add_sessions('2026-10-19', 120) == V.sessions('2026-10-19', '2027-12-31')[119], V.add_sessions('2026-10-19', 120))

# ---- 3. 收案資格:自己做一個 git repo,放一批「鎖定」與收件
snap = json.loads(gzip.decompress(subprocess.run(['git', '-C', REPO, 'show', 'origin/astra-ledger:snap/2026-10-14/ADI.json.gz'], capture_output=True).stdout))['bars']
real = json.loads(subprocess.run(['git', '-C', REPO, 'show', 'origin/astra-ledger:marks.jsonl'], capture_output=True, text=True).stdout.splitlines()[0])


def mkrepo(td, *, prompt_changed=False, verified=True, recv='2026-10-15T05:15:06Z', model='claude-opus-5-5', tamper_verdicts=False):
    g = lambda *a: subprocess.run(['git', '-C', td, *a], capture_output=True, text=True, check=True).stdout.strip()
    subprocess.run(['git', 'init', '-q', '-b', 'astra-ledger', td], check=True)
    W = lambda p, b: (os.makedirs(os.path.dirname(os.path.join(td, p)) or td, exist_ok=True), open(os.path.join(td, p), 'wb').write(b))
    prompt = b'judge prompt v2'; prot = b'protocol v2'; uni = b'ADI\n'
    man = {'protocol': 'v2', 'main_commit': None, 'files': {}, 'prompt_sha256': H(prompt), 'protocol_sha256': H(prot), 'universe_sha256': H(uni)}
    mb = json.dumps(man).encode()
    for p, b in (('prompt_v2.md', prompt), ('PROTOCOL.md', prot), ('universe.txt', uni), ('engine_manifest.json', mb)): W(p, b)
    g('add', '-A'); g('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'freeze')
    d = '2026-10-14'
    pend = json.dumps({'asof': d, 'marks': [{'id': real['id']}]}).encode()
    verd = json.dumps({'asof': d, 'model': model, 'marks': [{'id': real['id'], 'v': real['v'], 'p': 0.6, 'why': 't'}]}).encode()
    W(f'pending/{d}.json', pend); W(f'verdicts/{d}.json', verd)
    W(f'snap/{d}/ADI.json.gz', gzip.compress(json.dumps({'sym': 'ADI', 'asof': d, 'bars': snap}, separators=(',', ':')).encode()))
    if prompt_changed: W('prompt_v2.md', b'judge prompt v2 -- quietly edited')
    row = dict(real, model=model, pending_sha256=H(pend), verdicts_sha256=H(verd) if not tamper_verdicts else '0' * 64, engine_manifest_sha256=H(mb))
    W('marks.jsonl', (json.dumps(row, ensure_ascii=False) + '\n').encode())
    g('add', '-A'); g('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'lock'); lc = g('rev-parse', 'HEAD')
    rc = {'asof': d, 'lock_commit': lc, 'run_id': 1, 'remote_received_utc': recv if verified else None, 'verified': verified, 'deadline_utc': '2026-10-15T13:30:00Z'}
    W(f'receipts/{d}.json', json.dumps(rc).encode()); W('scores.json', b'{"marks":{}}')
    g('add', '-A'); g('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'receipt')
    return row, H(mb)


def elig(**kw):
    with tempfile.TemporaryDirectory() as td:
        row, msha = mkrepo(td, **kw)
        g = V.Git(td); marks, rc, sc, _ = V.load_ledger(g, 'astra-ledger')
        cfg = dict(V.V3, start='2026-10-14', v2_manifest_sha256=msha)
        return V.eligibility(g, marks[0], rc, cfg, {})


ok('eligible_when_everything_matches', elig() == [], elig())
ok('prompt_change_rejected', 'prompt_sha' in elig(prompt_changed=True), elig(prompt_changed=True))
ok('unverified_receipt_rejected', 'no_verified_receipt' in elig(verified=False))
ok('late_remote_receipt_rejected', 'late_remote' in elig(recv='2026-10-15T13:30:01Z'))
ok('other_model_rejected', 'model' in elig(model='some-other-model'))
ok('verdict_hash_mismatch_rejected', 'verdicts_sha' in elig(tamper_verdicts=True))

# ---- 4. 判定
cal = V.sessions('2026-10-19', V.add_sessions('2026-10-19', 120)); cfg = dict(V.V3)
# a. 只有一個有配對的日期(v2 會 PASS)→ 資訊不足
rows = [(cal[0], 'stock', f'S{i}', 'agree' if i < 100 else 'disagree', .01 if i < 100 else -.01) for i in range(200)] + [(cal[1], 'stock', f'S{i}', 'agree', .01) for i in range(200, 300)]
a = V.analyze(rows, [], cal, cfg); ok('one_paired_date_is_insufficient', a['decision'] == 'INSUFFICIENT' and not a['gates']['paired_dates'], a['gates'])
# b. 很強的效果、100 天、沒有缺漏 → PASS(也是上線候選)
strong = [(cal[t], 'stock', f'A{t}{k}', 'agree', .02 + .001 * ((t * 7 + k) % 5 - 2)) for t in range(100) for k in range(2)] + \
         [(cal[t], 'stock', f'D{t}{k}', 'disagree', -.01 + .001 * ((t * 3 + k) % 5 - 2)) for t in range(100) for k in range(2)]
b = V.analyze(strong, [], cal, cfg); ok('strong_effect_passes', b['decision'] == 'PASS' and b['go_live_candidate'], {k: b['excluded_missing'][k] for k in ('h1_pp', 'h1_lb_min_pp', 'paired_dates')})
# c. 缺漏超過 3% → 資訊不足
miss = [(cal[t], 'stock', f'M{t}', 'agree') for t in range(13)]
c = V.analyze(strong, miss, cal, cfg); ok('missing_over_3pct_is_insufficient', c['decision'] == 'INSUFFICIENT' and not c['gates']['missing_frac'], c['n_missing'])
# d. 排除缺漏會過、最壞情境不過 → NO_PASS(v2 會 PASS)
base = [(cal[t], 'stock', f'A{t}{k}', 'agree', .01) for t in range(100) for k in range(2)] + [(cal[t], 'stock', f'D{t}', 'disagree', -.005) for t in range(100)]
losers = [(cal[100 + t], 'stock', f'L{t}', 'disagree', -.50) for t in range(20)]
miss9 = [(cal[t], 'stock', f'X{t}', 'agree') for t in range(9)]
d = V.analyze(base + losers, miss9, cal, cfg)
ok('worst_case_missing_blocks_pass', d['decision'] == 'NO_PASS' and d['excluded_missing']['H1'] and not d['worst_case_missing']['H1'],
   {'excl_lb': d['excluded_missing']['h1_lb_min_pp'], 'worst_lb': d['worst_case_missing']['h1_lb_min_pp'], 'missing_frac_ok': d['gates']['missing_frac']})

# ---- 5. 出場重播(真實快照 + 自己做的之後 3 根:第 2 根收盤跌破 8% → 停損)
i = len(snap) - 1; o1 = snap[i][4]
fwd = [['2026-10-15', o1, o1 * 1.01, o1 * .99, o1, 1], ['2026-10-16', o1, o1, o1 * .88, o1 * .90, 1], ['2026-10-19', o1 * .89, o1 * .9, o1 * .87, o1 * .88, 1]]
B = snap + fwd; O = [x[1] for x in B]
rec = {'status': 'closed', 'entry': '2026-10-15', 'exit': '2026-10-19', 'exit_why': '停損', 'ret': AT.ret(O, i + 1, i + 3, .001), 'bars_used': B[i - 1:], 'closed_utc': '2026-10-20T00:30:00Z'}
m = dict(real)
st, r, note = V.replay(m, rec, snap, V.V3); ok('replay_reproduces_recorded_exit', st == 'closed' and abs(r - rec['ret']) < 1e-15, (st, r, note))
st2, _, note2 = V.replay(m, dict(rec, exit_why='頂'), snap, V.V3); ok('replay_mismatch_is_unreproducible', st2 == 'unreproducible', note2)
st3, _, note3 = V.replay(m, dict(rec, bars_used=B[i - 1:i + 2]), snap, V.V3); ok('missing_bars_is_unreproducible', st3 == 'unreproducible', note3)
st4, _, note4 = V.replay(m, dict(rec, closed_utc='2026-11-05T00:00:00Z'), snap, V.V3); ok('late_close_flagged', st4 == 'closed' and note4 == 'late_close')

# ---- 6. 唯一一次:v3_look.json 已存在 → 不再算(不需要 repo)
with tempfile.TemporaryDirectory() as td:
    open(os.path.join(td, 'v3_look.json'), 'w').write('{"decision":"NO_PASS"}')
    out = subprocess.run([sys.executable, '-I', os.path.join(HERE, 'v3_verify.py'), 'analyze', '--repo', '/nonexistent', '--out', td], capture_output=True, text=True)
    ok('look_once_only', out.returncode == 0 and '不再做' in out.stdout, out.stdout.strip())

json.dump({'tests': len(R), 'all_pass': True, 'results': R}, open(os.path.join(HERE, 'v3_tests_result.json'), 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps({'tests': len(R), 'all_pass': True}, ensure_ascii=False))
