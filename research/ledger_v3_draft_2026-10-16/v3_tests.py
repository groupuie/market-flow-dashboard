#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3 草案 2 的離線測試(Claude 2026-10-16 晚)
   含 Astra v0.7.3 附錄五的 8 個反例(換成 v3 該有的行為)+ 附錄四的統計反例 + 日曆 / 重播 / 登記
   自己做一個暫存 git repo(main 放凍結的兩支引擎、astra-ledger 放一批鎖定);回條用存好的 API 原件(不連網)
   用法:python3 -I v3_tests.py <真實 repo(要有 origin/astra-ledger)>"""
import datetime as dt, gzip, hashlib, json, os, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import v3_verify as V

REPO = sys.argv[1]; R = []
def ok(name, cond, proof=None):
    assert cond, (name, proof); R.append({'name': name, 'pass': True, 'proof': proof})
H = lambda b: hashlib.sha256(b).hexdigest()
real_show = lambda ref, p: subprocess.run(['git', '-C', REPO, 'show', f'{ref}:{p}'], capture_output=True).stdout
MAIN0 = '1ee593a76cea13ca9c13954b93f40cddad35aace'
ENG = {p: real_show(MAIN0, p) for p in ('scripts/astra_data.py', 'scripts/astra_trades.py', 'scripts/astra_ledger.py')}
SNAP = json.loads(gzip.decompress(real_show('origin/astra-ledger', 'snap/2026-10-14/ADI.json.gz')))['bars']
REAL = json.loads(real_show('origin/astra-ledger', 'marks.jsonl').decode().splitlines()[0])   # 2026-10-14:ADI(stock / 乙)

# ---- 1. 日曆
ok('good_friday_2027', V.deadline_utc('2027-03-25').isoformat() == '2027-03-29T13:30:00+00:00')
ok('christmas_2026', V.deadline_utc('2026-12-24').isoformat() == '2026-12-28T14:30:00+00:00')
ok('christmas_observed_2027', V.deadline_utc('2027-12-23').isoformat() == '2027-12-27T14:30:00+00:00')
ok('juneteenth_observed_2027', V.deadline_utc('2027-06-17').isoformat() == '2027-06-21T13:30:00+00:00')
ok('independence_observed_2027', V.deadline_utc('2027-07-02').isoformat() == '2027-07-06T13:30:00+00:00')
try:
    V.is_session('2029-01-02'); ok('calendar_out_of_range_stops', False)
except SystemExit as e: ok('calendar_out_of_range_stops', True, str(e))
ok('cohort_end_by_calendar', V.add_sessions('2026-10-19', 120) == V.sessions('2026-10-19', '2027-12-31')[119])


# ---- 2. 暫存 repo:main(引擎)+ astra-ledger(一批 2026-10-14 的 ADI)
def mkrepo(td, *, pending_marks=None, row_patch=None, dup_row=False, verdict_patch=None, run_head=None):
    g = lambda *a: subprocess.run(['git', '-C', td, *a], capture_output=True, text=True, check=True).stdout.strip()
    W = lambda p, b: (os.makedirs(os.path.dirname(os.path.join(td, p)) or td, exist_ok=True), open(os.path.join(td, p), 'wb').write(b))
    subprocess.run(['git', 'init', '-q', '-b', 'main', td], check=True)
    for p, b in ENG.items(): W(p, b)
    g('add', '-A'); g('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'engine'); mc = g('rev-parse', 'HEAD')
    g('checkout', '-q', '--orphan', 'astra-ledger'); g('rm', '-rq', '--cached', '.'); [shutil.rmtree(os.path.join(td, 'scripts'))]
    prompt, prot, uni = b'judge prompt v2', b'protocol v2', b'ADI\n'
    man = {'protocol': 'v2', 'main_commit': mc, 'files': {p: H(b) for p, b in ENG.items()}, 'prompt_sha256': H(prompt), 'protocol_sha256': H(prot), 'universe_sha256': H(uni)}
    mb = json.dumps(man).encode()
    for p, b in (('prompt_v2.md', prompt), ('PROTOCOL.md', prot), ('universe.txt', uni), ('engine_manifest.json', mb)): W(p, b)
    g('add', '-A'); g('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'freeze')
    d = '2026-10-14'
    pm = [{'id': REAL['id'], 'sym': 'ADI', 'kind': REAL['kind'], 'type': 'stock', 'style': 'b', 'displayed_buy': REAL['displayed_buy'], 'bars_sha256': REAL['bars_sha256']}]
    pm = pm if pending_marks is None else pending_marks
    pend = json.dumps({'asof': d, 'protocol': 'v2', 'test': False, 'n': len(pm), 'marks': pm}).encode()
    vm = {'id': REAL['id'], 'v': REAL['v'], 'p': 0.6, 'why': 't'}; vm.update(verdict_patch or {})
    verd = json.dumps({'asof': d, 'model': 'claude-opus-5-5', 'marks': [vm]}).encode()
    W(f'pending/{d}.json', pend); W(f'verdicts/{d}.json', verd)
    W(f'snap/{d}/ADI.json.gz', gzip.compress(json.dumps({'sym': 'ADI', 'asof': d, 'bars': SNAP}, separators=(',', ':')).encode()))
    row = dict(REAL, model='claude-opus-5-5', p=0.6, why='t', pending_sha256=H(pend), verdicts_sha256=H(verd), engine_manifest_sha256=H(mb)); row.update(row_patch or {})
    line = (json.dumps(row, ensure_ascii=False) + '\n').encode()
    W('marks.jsonl', line * (2 if dup_row else 1))
    W(f'batches/{d}.json', json.dumps({'asof': d, 'status': 'locked', 'n': 2 if dup_row else 1}).encode())
    g('add', '-A'); g('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'lock'); lc = g('rev-parse', 'HEAD')
    rc = {'asof': d, 'lock_commit': lc, 'run_id': 777, 'remote_received_utc': '2026-10-15T05:15:06Z', 'verified': True}
    W(f'receipts/{d}.json', json.dumps(rc).encode()); W('scores.json', b'{"marks":{}}')
    g('add', '-A'); g('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'receipt')
    ev = os.path.join(td, '_evidence'); os.makedirs(ev)
    api = {'id': 777, 'name': 'ledger-receipt', 'path': V.RECEIPT_WF, 'event': 'push', 'head_branch': 'astra-ledger', 'head_sha': run_head or lc,
           'created_at': '2026-10-15T05:15:06Z', 'repository': V.OWNER_REPO}
    json.dump({'api': api}, open(os.path.join(ev, 'run-777.json'), 'w'))
    return {'g': V.Git(td), 'lc': lc, 'mc': mc, 'man': man, 'msha': H(mb), 'rc': rc, 'ev': ev, 'row': row}


def batch(**kw):
    with tempfile.TemporaryDirectory() as td:
        X = mkrepo(td, **kw); g = X['g']
        head = [json.loads(l) for l in (g.show('astra-ledger', 'marks.jsonl') or b'').decode().splitlines() if l.strip()]
        bw = V.check_receipt(X['rc'], '2026-10-14', X['ev'], online=False)
        bw2, per, _ = V.check_batch(g, '2026-10-14', X['rc'], head, X['msha'])
        return bw + bw2, per


bw, per = batch(); ok('clean_batch_accepted', bw == [] and per[REAL['id']] == [], (bw, per))
bw, _ = batch(run_head='0' * 40); ok('receipt_for_other_commit_rejected', 'receipt_head_sha' in bw, bw)                                         # Astra 反例 1
bw, per = batch(pending_marks=[]); ok('mark_not_in_pending_rejected', 'id_sets_differ' in bw and 'counts_differ' in bw, bw)                     # 反例 2
bw, per = batch(row_patch={'type': 'idx', 'style': 'c', 'kind': '回' if REAL['kind'] == '底' else '底', 'p': 0.99})
ok('field_changes_rejected', {'field_type', 'field_style', 'field_kind', 'type_style_rule', 'verdict_p'} <= set(per[REAL['id']]), per)          # 反例 3
bw, per = batch(dup_row=True); ok('duplicate_rows_rejected', 'duplicate_id_in_locked' in bw, bw)                                                # 反例 4
bw, per = batch(verdict_patch={'why': 'changed later'}); ok('verdict_text_mismatch_rejected', 'verdict_fields' in per[REAL['id']], per)

# ---- 3. 引擎從 git 物件載入:就算 sys.path 前面放了一個被改過的 astra_trades,也不會用到(Astra 反例 5)
with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as fake:
    X = mkrepo(td)
    open(os.path.join(fake, 'astra_trades.py'), 'w').write(ENG['scripts/astra_trades.py'].decode() + '\ndef ret(O, e, x, cost=0.0):\n    return 0.123456789\n')
    sys.path.insert(0, fake); sys.modules.pop('astra_trades', None)
    prov = V.load_engine(X['g'], X['mc'], X['man']['files'])
    sys.path.remove(fake)
    ok('engine_loaded_from_git_not_local', V.AT.ret([100, 100, 89], 1, 2, 0.0) != 0.123456789 and prov['scripts/astra_trades.py']['loaded_from'].startswith('git:'), prov)
    try:
        bad = dict(X['man']['files']); bad['scripts/astra_trades.py'] = '0' * 64; V.load_engine(X['g'], X['mc'], bad); ok('engine_hash_mismatch_stops', False)
    except SystemExit as e: ok('engine_hash_mismatch_stops', True, str(e))
    try:
        V.engine_changes_on_main(X['g'], 'no-such-ref', X['mc']); ok('history_query_failure_stops', False)
    except SystemExit as e: ok('history_query_failure_stops', True, str(e)[:60])
    ok('no_engine_change_after_freeze', V.engine_changes_on_main(X['g'], 'main', X['mc']) == [])

# ---- 4. 出場重播(真實快照 + 自己做的之後 K 線:第 2 根收盤跌破 8% → 停損)
i = len(SNAP) - 1; o1 = SNAP[i][4]
fwd = [['2026-10-15', o1, o1 * 1.01, o1 * .99, o1, 1], ['2026-10-16', o1, o1, o1 * .88, o1 * .90, 1], ['2026-10-19', o1 * .89, o1 * .9, o1 * .87, o1 * .88, 1]]
B = SNAP + fwd; O = [x[1] for x in B]
rec = {'status': 'closed', 'entry': '2026-10-15', 'exit': '2026-10-19', 'exit_why': '停損', 'ret': V.AT.ret(O, i + 1, i + 3, .001), 'bars_used': B[i - 1:], 'closed_utc': '2026-10-20T00:30:00Z'}
m = dict(REAL)
st, r, note = V.replay(m, rec, SNAP, V.SPEC); ok('replay_reproduces_within_tolerance', st == 'closed' and abs(r - rec['ret']) < 1e-15, (st, r, note))
ok('replay_wrong_return_unreproducible', V.replay(m, dict(rec, ret=0.123456789), SNAP, V.SPEC)[0] == 'unreproducible')
ok('replay_wrong_reason_unreproducible', V.replay(m, dict(rec, exit_why='頂'), SNAP, V.SPEC)[0] == 'unreproducible')
ok('missing_bars_unreproducible', V.replay(m, dict(rec, bars_used=B[i - 1:i + 2]), SNAP, V.SPEC)[0] == 'unreproducible')
wk = [['2026-10-17'] + fwd[0][1:], ['2026-10-18'] + fwd[1][1:], ['2026-10-19'] + fwd[2][1:]]                                                  # 反例 6:週末
st6, _, n6 = V.replay(m, dict(rec, bars_used=SNAP[i - 1:] + wk, entry='2026-10-17'), SNAP, V.SPEC); ok('weekend_bars_rejected', st6 == 'unreproducible', n6)
gap = [fwd[0], fwd[2]]                                                                                                                          # 少一個交易日
ok('gap_in_window_rejected', V.replay(m, dict(rec, bars_used=SNAP[i - 1:] + gap), SNAP, V.SPEC)[0] == 'unreproducible')
st7, _, n7 = V.replay(m, dict(rec, closed_utc='2026-10-14T21:00:00Z'), SNAP, V.SPEC); ok('recorded_before_available_rejected', st7 == 'unreproducible', n7)   # 反例 7
ok('late_close_flagged', V.replay(m, dict(rec, closed_utc='2026-11-05T00:00:00Z'), SNAP, V.SPEC)[2] == 'late_close')
# 尺度不同(配息重新還原):bars_used 的訊號日以前全部 × 0.99 → 對齊後仍可重現
sc = [[b[0]] + [V.AD.rp(x * 0.99) for x in b[1:5]] + [b[5]] for b in SNAP[i - 1:]] + fwd
st8, r8, n8 = V.replay(m, dict(rec, bars_used=sc), SNAP, V.SPEC); ok('rescaled_snapshot_reconciled', st8 == 'closed' and 'rescaled' in n8, (st8, n8))

# ---- 5. 判定(正式估計量,2,000 次)
cal = V.sessions('2026-10-19', V.add_sessions('2026-10-19', 120)); cfg = dict(V.SPEC)
def rows_(n_days, ag, dg, ra, rd, syms=80, typ='stock'):
    out = []
    for t in range(n_days):
        for k in range(ag): out.append((cal[t], typ, f'S{(t * 7 + k) % syms}', 'agree', ra(t, k)))
        for k in range(dg): out.append((cal[t], typ, f'S{(t * 11 + k + 40) % syms}', 'disagree', rd(t, k)))
    return out
# a. Astra 統計反例:400 筆已知(同意 +0.1%、不同意 −0.1%)、100 配對日、80 檔重複出現,再加 1 筆缺的「同意」
base = rows_(100, 2, 2, lambda t, k: .001, lambda t, k: -.001)
miss1 = [(cal[3], 'stock', 'S5', 'agree')]
a = V.decide(base, miss1, cal, cfg)
ok('missing_agree_uses_minus_100pct', a['decision'] == 'NO_PASS' and a['excluded_missing']['H1'] and not a['agree_missing_at_minus_100pct']['H1'] and a['stress_q05_q95']['H1'],
   {'excl_lb': a['excluded_missing']['h1_lb_pp'], 'minus100_h1': a['agree_missing_at_minus_100pct']['h1_pp'], 'stress_h1': a['stress_q05_q95']['h1_pp']})
fp = a['flip_points']['agree']; ok('flip_point_reported', fp is not None and abs(V.h1_point(base + [miss1[0] + (fp,)])) < 1e-9 and -1 < fp < 0, fp)
b = V.decide(base, [(cal[3], 'stock', 'S6', 'disagree')], cal, cfg)
ok('missing_disagree_is_insufficient', b['decision'] == 'INSUFFICIENT' and not b['gates']['no_missing_disagree'])
# b. 平均差 +2 點但兩邊都全贏 → 勝率差 0(Astra 例)
allwin = rows_(100, 2, 2, lambda t, k: .03 + .001 * ((t + k) % 3), lambda t, k: .01 + .001 * ((t + k) % 3))
c1 = V.decide(allwin, [], cal, cfg); c2 = V.decide(allwin, [], cal, dict(cfg, h2_mode='none'))
ok('h1_without_win_gap_fails_h2', c1['decision'] == 'NO_PASS' and c1['excluded_missing']['H1'] and not c1['excluded_missing']['H2'] and c2['decision'] == 'PASS',
   {'h1_pp': c1['excluded_missing']['h1_pp'], 'win_a': c1['excluded_missing']['win_agree_pct'], 'win_d': c1['excluded_missing']['win_disagree_pct']})
# c. 一個配對日 → 資訊不足
one = [(cal[0], 'stock', f'S{i}', 'agree' if i < 100 else 'disagree', .01 if i < 100 else -.01) for i in range(200)] + [(cal[1], 'stock', f'S{i}', 'agree', .01) for i in range(200, 300)]
ok('one_paired_date_insufficient', V.decide(one, [], cal, cfg)['decision'] == 'INSUFFICIENT')
# d. 強效果 → PASS;批次覆蓋 < 90% → 資訊不足
strong = rows_(100, 2, 2, lambda t, k: .02 + .001 * ((t * 7 + k) % 5 - 2), lambda t, k: -.01 + .001 * ((t * 3 + k) % 5 - 2))
d1 = V.decide(strong, [], cal, cfg); ok('strong_effect_passes', d1['decision'] == 'PASS' and d1['go_live_candidate'], {k: d1['excluded_missing'][k] for k in ('h1_pp', 'h1_lb_pp', 'win_gap_ad_lb_pp')})
ok('low_batch_coverage_insufficient', V.decide(strong, [], cal, cfg, coverage=0.85)['decision'] == 'INSUFFICIENT')
# e. 發行人:GOOG / GOOGL 算同一家
ok('goog_googl_one_issuer', len({V.issuer(s) for s in ('GOOG', 'GOOGL', 'AAPL')}) == 2)
# f. H2 恆等式:同意勝率 − 全部勝率 = (1 − 同意比例) × (同意勝率 − 不同意勝率)
e = V.stats(strong, cal, cfg); lhs = e['win_agree_pct'] - e['win_all_pct']; rhs = (1 - e['agree_share']) * (e['win_agree_pct'] - e['win_disagree_pct'])
ok('h2_identity', abs(lhs - rhs) < 1e-9, (lhs, rhs))

# ---- 6. 唯一一次:登記綁在實驗 ID 與固定位置(Astra 反例 8:換 --out 也擋得住)
with tempfile.TemporaryDirectory() as td:
    subprocess.run(['git', 'init', '-q', td], check=True)
    lp = V.look_path(td, 'EXP-TEST'); os.makedirs(os.path.dirname(lp)); open(lp, 'w').write('{}')
    subprocess.run(['git', '-C', td, 'add', '-A'], check=True); subprocess.run(['git', '-C', td, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'look'], check=True)
    os.remove(lp)   # 就算工作區刪掉,git 歷史裡有就算做過
    ok('look_registry_blocks_even_if_file_deleted', V.look_exists(td, lp))
    out = subprocess.run([sys.executable, '-I', os.path.join(HERE, 'v3_verify.py'), 'analyze', '--repo', td, '--experiment-id', 'EXP-TEST'], capture_output=True, text=True)
    ok('formal_analyze_refuses_after_look', '不再做' in out.stdout, out.stdout.strip()[:80])
    out2 = subprocess.run([sys.executable, '-I', os.path.join(HERE, 'v3_verify.py'), 'analyze', '--repo', td, '--dry-run', '--out', os.path.dirname(lp)], capture_output=True, text=True)
    ok('dry_run_cannot_write_registry', out2.returncode != 0 and '不能寫進正式' in (out2.stderr + out2.stdout), (out2.stderr + out2.stdout).strip()[-60:])
out3 = subprocess.run([sys.executable, '-I', os.path.join(HERE, 'v3_verify.py'), 'status', '--repo', REPO], capture_output=True, text=True)
ok('formal_mode_needs_frozen_manifest', out3.returncode != 0 and 'v3_manifest' in (out3.stderr + out3.stdout))

json.dump({'tests': len(R), 'all_pass': True, 'results': R}, open(os.path.join(HERE, 'v3_tests_result.json'), 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps({'tests': len(R), 'all_pass': True}, ensure_ascii=False))
