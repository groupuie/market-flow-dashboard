#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3 草案 5 的離線測試(Claude 2026-10-21;草案 4 的 102 項 + Astra v0.7.6 的結案截止反例)
   草案 3:草案 2 的 39 項(行為改了的照新規則改寫)+ Astra v0.7.4 的反例:統計反例(原樣重現草案 2 的 PASS,新版要 NO_PASS)、
   零訊號蓋掉鎖定事件、單列錯誤整批照收、改過的回條快取、重疊行情不一致、只改訊號日收盤、整段縮放後再捨入取消原買點
   草案 4(Astra v0.7.5):半日市(13:00 收盤)的凍結錨點與出場紀錄時間、正式模式遇到本機快取壞掉要停(不寫登記與判定)+ 修復、
   開跑登記 + 決定性重播(刪掉本機檔、另一個 checkout、登記之後的新資料、保存失敗後重跑、竄改遠端判定或登記)、結案截止
   暫存 git repo:main(凍結的三支引擎)+ astra-ledger(freeze → 批次);GitHub 用假的 gh(本機 JSON)或釘選的證據檔(不連網);
   要 push 的正式流程用本機 bare repo 當 origin,hook 模擬 ledger-receipt run 與 push 被拒
   用法:python3 -I v3_tests.py <真實 repo(要有 origin/astra-ledger、a654145、4bfe44d)>"""
import datetime as dt, gzip, hashlib, importlib.util, json, os, shutil, stat, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import v3_verify as V

REPO = sys.argv[1]; R = []
def ok(name, cond, proof=None):
    assert cond, (name, proof); R.append({'name': name, 'pass': True, 'proof': proof})
H = lambda b: hashlib.sha256(b).hexdigest()
real_show = lambda ref, p: subprocess.run(['git', '-C', REPO, 'show', f'{ref}:{p}'], capture_output=True, check=True).stdout
MAIN0 = '1ee593a76cea13ca9c13954b93f40cddad35aace'; DRAFT2 = 'a654145'
ENG = {p: real_show(MAIN0, p) for p in ('scripts/astra_data.py', 'scripts/astra_trades.py', 'scripts/astra_ledger.py')}
snap_of = lambda d, s: json.loads(gzip.decompress(real_show('origin/astra-ledger', f'snap/{d}/{s}.json.gz')))['bars']
SNAP = snap_of('2026-10-14', 'ADI'); TSNAP = snap_of('2026-10-14', 'T')
SPY15, QQQ15 = snap_of('2026-10-15', 'SPY'), snap_of('2026-10-15', 'QQQ')
REAL = json.loads(real_show('origin/astra-ledger', 'marks.jsonl').decode().splitlines()[0])   # 2026-10-14:ADI(stock / 乙)
LEG = None


def legacy():
    """草案 2 原樣(git a654145)— 只用來證明舊行為、對照新版"""
    global LEG
    if LEG is None:
        b = real_show(DRAFT2, 'research/ledger_v3_draft_2026-10-16/v3_verify.py'); assert H(b) == 'b3294fbcd8ba1dd21eba5eac9579d4474dcad9c2f8a649f618a7fb6cb3f2b3de'
        p = os.path.join(tempfile.mkdtemp(prefix='v3leg_'), 'v3_verify_draft2.py'); open(p, 'wb').write(b)
        spec = importlib.util.spec_from_file_location('v3_verify_draft2', p); LEG = importlib.util.module_from_spec(spec); spec.loader.exec_module(LEG)
    return LEG


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
# 半日市(Astra v0.7.5 §3.1;NYSE 官方 13:00 提早收盤)— 草案 3 一律當 16:00
EC = {d: V.ts(V.close_utc(d)) for d in ('2026-11-27', '2026-12-24', '2027-11-26', '2028-07-03', '2028-11-24')}
ok('early_close_official_1300', EC == {'2026-11-27': '2026-11-27T18:00:00Z', '2026-12-24': '2026-12-24T18:00:00Z', '2027-11-26': '2027-11-26T18:00:00Z',
                                       '2028-07-03': '2028-07-03T17:00:00Z', '2028-11-24': '2028-11-24T18:00:00Z'}, EC)
ok('normal_and_dst_closes_unchanged', [V.ts(V.close_utc(d)) for d in ('2026-11-30', '2026-10-30', '2026-03-06', '2026-03-09')]
   == ['2026-11-30T21:00:00Z', '2026-10-30T20:00:00Z', '2026-03-06T21:00:00Z', '2026-03-09T20:00:00Z']
   and V.ts(V.deadline_utc('2026-11-25')) == '2026-11-27T14:30:00Z')
try:
    V.close_utc('2026-11-26'); ok('holiday_has_no_close_time', False)
except SystemExit as e: ok('holiday_has_no_close_time', True, str(e))
fp0 = V.calendar_fingerprint(); _ec = dict(V.EARLY_CLOSE); V.EARLY_CLOSE.pop('2026-12-24'); fp1 = V.calendar_fingerprint(); V.EARLY_CLOSE.clear(); V.EARLY_CLOSE.update(_ec)
ok('calendar_fingerprint_covers_early_closes', fp0 != fp1 and V.calendar_fingerprint() == fp0 and len(V.session_table()) == len(V.sessions(V.CAL_START, V.CAL_END)))
def draft3():
    b = real_show('4bfe44d', 'research/ledger_v3_draft_2026-10-16/v3_verify.py'); assert H(b) == '67de35793c6e244e91fafb74dbd62304cece9088705212903fae67293ed0dc53'
    p = os.path.join(tempfile.mkdtemp(prefix='v3d3_'), 'v3_verify_draft3.py'); open(p, 'wb').write(b)
    spec = importlib.util.spec_from_file_location('v3_verify_draft3', p); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
D3 = draft3()
ok('draft3_used_1600_on_early_close', V.ts(D3.close_utc('2026-11-27')) == '2026-11-27T21:00:00Z')


# ---- 2. 暫存 repo
GIT = lambda td, *a: subprocess.run(['git', '-C', td, *a], capture_output=True, text=True, check=True).stdout.strip()
def WR(td, p, b):
    os.makedirs(os.path.dirname(os.path.join(td, p)) or td, exist_ok=True); open(os.path.join(td, p), 'wb').write(b)
def COMMIT(td, msg):
    GIT(td, 'add', '-A'); GIT(td, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', msg); return GIT(td, 'rev-parse', 'HEAD')
gz = lambda sym, d, bars: gzip.compress(json.dumps({'sym': sym, 'asof': d, 'bars': bars}, separators=(',', ':')).encode())
bsha = lambda bars: H(json.dumps(bars, separators=(',', ':')).encode())


def evidence_record(source, api):
    return {'schema': 'v3-evidence-2', 'fetched_utc': '2026-10-16T00:00:00Z', 'source': source, 'api': api, 'api_subset_sha256': H(json.dumps(api, sort_keys=True).encode())}


def run_api(run_id, head, created):
    return {'id': run_id, 'name': 'ledger-receipt', 'path': V.RECEIPT_WF, 'event': 'push', 'head_branch': 'astra-ledger', 'head_sha': head,
            'created_at': created, 'repository': V.OWNER_REPO}


class Fx:
    """main(凍結的三支引擎)+ astra-ledger(freeze → 批次);證據檔放 _evidence,pins 記指紋"""
    def __init__(self, td, universe=b'ADI\nT\nSPY\nQQQ\n'):
        self.td = td; subprocess.run(['git', 'init', '-q', '-b', 'main', td], check=True)
        for p, b in ENG.items(): WR(td, p, b)
        self.mc = COMMIT(td, 'engine')
        GIT(td, 'checkout', '-q', '--orphan', 'astra-ledger'); GIT(td, 'rm', '-rq', '--cached', '.'); shutil.rmtree(os.path.join(td, 'scripts'))
        self.uni = universe; prompt, prot = b'judge prompt v2', b'protocol v2'
        self.man = {'protocol': 'v2', 'main_commit': self.mc, 'files': {p: H(b) for p, b in ENG.items()}, 'prompt_sha256': H(prompt), 'protocol_sha256': H(prot), 'universe_sha256': H(universe)}
        self.mb = json.dumps(self.man).encode(); self.msha = H(self.mb)
        for p, b in (('prompt_v2.md', prompt), ('PROTOCOL.md', prot), ('universe.txt', universe), ('engine_manifest.json', self.mb)): WR(td, p, b)
        COMMIT(td, 'freeze'); self.ev = os.path.join(td, '_evidence'); os.makedirs(self.ev); self.marks = b''; self.next_run = 777
        WR(td, 'scores.json', b'{"marks":{}}'); COMMIT(td, 'scores')
        self.g = V.Git(td); V.load_engine(self.g, self.mc, self.man['files'])

    def pending_header(self, d, n, marks):
        return {'asof': d, 'protocol': 'v2', 'gen_utc': '2026-10-15T05:14:27Z', 'deadline_utc': V.ts(V.deadline_utc(d)), 'universe_sha256': H(self.uni),
                'n_universe': V.n_universe(self.uni), 'n_fresh': V.n_universe(self.uni), 'fail': {}, 'test': False, 'engine_manifest_sha256': self.msha, 'n': n, 'marks': marks}

    def lock(self, d, items, *, row_patch=None, dup_row=False, verdict_patch=None, run_head=None, pending_marks=None, received=None):
        """items: [(sym, bars, v)];鎖定列一律照 items 算(凍結引擎),pending_marks 只改 pending 檔(做「pending 缺一筆」的反例);回傳 (lock commit, receipt)"""
        td = self.td; pm, vm, rows = [], [], []
        for sym, bars, v in items:
            W = V.AD.sw_series(bars); j = len(bars) - 1; kind = dict(V.AT.buy_points(W))[j]; T = V.AT.trades(W, [b[1] for b in bars], V.AT.style_of(sym))
            typ = 'idx' if sym in V.IDX else 'stock'; sty = 'c' if typ == 'idx' else 'b'
            pm.append({'id': f'{d}:{sym}', 'sym': sym, 'kind': kind, 'type': typ, 'style': sty, 'displayed_buy': bool(T and T[-1]['i'] == j), 'bars_sha256': bsha(bars)})
            vm.append(dict({'id': f'{d}:{sym}', 'v': v, 'p': 0.6, 'why': 't'}, **(verdict_patch or {})))
            WR(td, f'snap/{d}/{sym}.json.gz', gz(sym, d, bars))
        pfile = pm if pending_marks is None else pending_marks
        pend = json.dumps(self.pending_header(d, len(pfile), pfile)).encode(); verd = json.dumps({'asof': d, 'model': 'claude-opus-5-5', 'marks': vm}).encode()
        WR(td, f'pending/{d}.json', pend); WR(td, f'verdicts/{d}.json', verd)
        for p0, v0 in zip(pm, vm):
            row = {'id': p0['id'], 'date': d, 'sym': p0['sym'], 'kind': p0['kind'], 'type': p0['type'], 'style': p0['style'], 'displayed_buy': p0['displayed_buy'],
                   'panic_sc': None, 'v': v0['v'], 'p': 0.6, 'why': 't', 'model': 'claude-opus-5-5', 'protocol': 'v2', 'locked_local_utc': '2026-10-15T05:15:02Z',
                   'deadline_utc': V.ts(V.deadline_utc(d)), 'late_local': False, 'test': False, 'pending_sha256': H(pend), 'verdicts_sha256': H(verd),
                   'bars_sha256': p0['bars_sha256'], 'engine_manifest_sha256': self.msha}
            row.update(row_patch or {}); rows.append(row)
        line = b''.join((json.dumps(r, ensure_ascii=False) + '\n').encode() for r in rows)
        self.marks += line * (2 if dup_row else 1); WR(td, 'marks.jsonl', self.marks)
        k = 2 if dup_row else 1
        WR(td, f'batches/{d}.json', json.dumps({'asof': d, 'protocol': 'v2', 'status': 'locked', 'test': False, 'n': len(rows) * k,
                                                 'n_agree': sum(r['v'] == 'agree' for r in rows) * k, 'verdicts_sha256': H(verd)}).encode())
        lc = COMMIT(td, f'lock {d}'); rid = self.next_run; self.next_run += 1
        rec_t = received or V.ts(V.deadline_utc(d) - dt.timedelta(hours=8))
        rc = {'source': 'github actions run (ledger-receipt)', 'asof': d, 'lock_commit': lc, 'run_id': rid, 'remote_received_utc': rec_t, 'verified': True}
        WR(td, f'receipts/{d}.json', json.dumps(rc).encode()); COMMIT(td, f'receipt {d}')
        self.put_run(rid, run_head or lc, rec_t)
        return lc, rc

    def put_run(self, rid, head, created):
        api = run_api(rid, head, created)
        json.dump(evidence_record(f'GET repos/{V.OWNER_REPO}/actions/runs/{rid}', api), open(os.path.join(self.ev, f'run-{rid}.json'), 'w'))
        return api

    def put_runs_for(self, commit, runs):
        src = f'GET repos/{V.OWNER_REPO}/actions/runs?branch={V.LEDGER_BRANCH}&event=push&head_sha={commit}&per_page=100'
        json.dump(evidence_record(src, sorted(runs, key=lambda x: x['id'])), open(os.path.join(self.ev, f'runs-for-{commit}.json'), 'w'))

    def no_signals(self, d, *, pending_patch=None, receipt='ontime', spy=None, qqq=None):
        td = self.td; pen = self.pending_header(d, 0, []); pen.update(pending_patch or {}); pb = json.dumps(pen).encode()
        WR(td, f'pending/{d}.json', pb)
        WR(td, f'snap/{d}/SPY.json.gz', gz('SPY', d, spy or SPY15)); WR(td, f'snap/{d}/QQQ.json.gz', gz('QQQ', d, qqq or QQQ15))
        WR(td, f'batches/{d}.json', json.dumps({'asof': d, 'protocol': 'v2', 'status': 'no_signals', 'test': False, 'n': 0, 'n_fresh': 4, 'n_fail': 0,
                                                 'pending_sha256': H(pb), 'deadline_utc': V.ts(V.deadline_utc(d))}).encode())
        C = COMMIT(td, f'prep {d}: 0')
        if receipt:
            t = V.deadline_utc(d) - dt.timedelta(hours=8) if receipt == 'ontime' else V.deadline_utc(d) + dt.timedelta(minutes=5)
            rid = self.next_run; self.next_run += 1; self.put_runs_for(C, [run_api(rid, C, V.ts(t))])
        return C

    def pins(self):
        return {f: H(open(os.path.join(self.ev, f), 'rb').read()) for f in os.listdir(self.ev)}

    def store(self, online=False):
        return V.Evidence(self.ev, online=online, pins=self.pins(), pins_src={'test': True})

    def collect(self, start='2026-10-14', today='2026-10-16', now='2026-10-16T12:00:00Z', store=None):
        cfg = dict(V.SPEC, start=start, v2_manifest_sha256=self.msha)
        return V.collect(self.g, 'astra-ledger', 'main', cfg, today, V.P(now), store or self.store())


def batch(**kw):
    with tempfile.TemporaryDirectory() as td:
        X = Fx(td); lc, rc = X.lock('2026-10-14', [('ADI', SNAP, REAL['v'])], **kw); g = X.g
        head = [json.loads(l) for l in (g.show('astra-ledger', 'marks.jsonl') or b'').decode().splitlines() if l.strip()]
        bw, _ = V.check_receipt(rc, '2026-10-14', X.store())
        bw2, per, _ = V.check_batch(g, 'astra-ledger', '2026-10-14', rc, head, X.msha, g.show('astra-ledger', 'batches/2026-10-14.json'))
        return bw + bw2, per


bw, per = batch(); ok('clean_batch_accepted', bw == [] and per[REAL['id']] == [], (bw, per))
bw, _ = batch(run_head='0' * 40); ok('receipt_for_other_commit_rejected', 'receipt_head_sha' in bw, bw)                                          # v0.7.3 反例 1
bw, per = batch(pending_marks=[]); ok('mark_not_in_pending_rejected', 'id_sets_differ' in bw and 'counts_differ' in bw, bw)                      # v0.7.3 反例 2
bw, per = batch(row_patch={'type': 'idx', 'style': 'c', 'kind': '回' if REAL['kind'] == '底' else '底', 'p': 0.99})
ok('field_changes_rejected', {'field_type', 'field_style', 'field_kind', 'type_style_rule', 'verdict_p'} <= set(per[REAL['id']]), per)           # v0.7.3 反例 3
bw, per = batch(dup_row=True); ok('duplicate_rows_rejected', 'duplicate_id_in_locked' in bw, bw)                                                 # v0.7.3 反例 4
bw, per = batch(verdict_patch={'why': 'changed later'}); ok('verdict_text_mismatch_rejected', 'verdict_fields' in per[REAL['id']], per)

# 快照被換成「最後一根不是買點」(指紋跟著改,只剩買點核對擋得住)
with tempfile.TemporaryDirectory() as td:
    X = Fx(td); bad = [list(b) for b in SNAP]; lo7 = min(b[4] for b in bad[-7:-1]); c = round((lo7 + bad[-2][2]) / 2, 3)   # 收盤不是 7 天最低、也沒突破昨高
    bad[-1][1:5] = [c, max(c, bad[-1][2]), min(c, bad[-1][3]), c]
    assert (len(bad) - 1) not in dict(V.AT.buy_points(V.AD.sw_series(bad)))
    d = '2026-10-14'; pm = [{'id': REAL['id'], 'sym': 'ADI', 'kind': REAL['kind'], 'type': 'stock', 'style': 'b', 'displayed_buy': True, 'bars_sha256': bsha(bad)}]
    pend = json.dumps(X.pending_header(d, 1, pm)).encode(); verd = json.dumps({'asof': d, 'model': 'claude-opus-5-5', 'marks': [{'id': REAL['id'], 'v': 'agree', 'p': 0.6, 'why': 't'}]}).encode()
    WR(td, f'pending/{d}.json', pend); WR(td, f'verdicts/{d}.json', verd); WR(td, f'snap/{d}/ADI.json.gz', gz('ADI', d, bad))
    row = {'id': REAL['id'], 'date': d, 'sym': 'ADI', 'kind': REAL['kind'], 'type': 'stock', 'style': 'b', 'displayed_buy': True, 'v': 'agree', 'p': 0.6, 'why': 't',
           'model': 'claude-opus-5-5', 'protocol': 'v2', 'test': False, 'pending_sha256': H(pend), 'verdicts_sha256': H(verd), 'bars_sha256': bsha(bad), 'engine_manifest_sha256': X.msha}
    WR(td, 'marks.jsonl', (json.dumps(row) + '\n').encode())
    WR(td, f'batches/{d}.json', json.dumps({'asof': d, 'status': 'locked', 'n': 1, 'n_agree': 1, 'verdicts_sha256': H(verd)}).encode()); lc = COMMIT(td, 'lock bad snapshot')
    head = [row]; bw2, per2, _ = V.check_batch(X.g, 'astra-ledger', d, {'lock_commit': lc}, head, X.msha, X.g.show('astra-ledger', f'batches/{d}.json'))
    ok('snapshot_not_buy_point_rejected', 'snapshot_not_this_buy_point' in per2[REAL['id']] and 'snapshot_sha' not in per2[REAL['id']], per2)

# ---- 3. 整批驗收與零訊號(Astra v0.7.4 附錄四 §3)
with tempfile.TemporaryDirectory() as td:                                                                                                       # 3.2:單列錯 → 整批不收
    X = Fx(td); X.lock('2026-10-14', [('ADI', SNAP, 'agree')], row_patch={'style': 'c', 'type': 'idx'})
    pub, closed, missing, cal, cov = X.collect()
    bd = pub['batch_coverage']['by_date']['2026-10-14']
    ok('row_error_rejects_whole_batch', pub['batch_coverage']['ok'] == 0 and pub['batch_coverage']['seen'] == 1 and not bd['accepted'] and pub['counts']['eligible'] == 0
       and pub['counts']['rejected'] == 1 and {'field_type', 'type_style_rule'} <= set(bd['reasons']), {'coverage': pub['batch_coverage'], 'counts': pub['counts']})
with tempfile.TemporaryDirectory() as td:                                                                                                       # 3.1:鎖定之後改成 no_signals
    X = Fx(td); X.lock('2026-10-14', [('ADI', SNAP, 'agree')])
    before = X.collect()[0]
    p = os.path.join(td, 'batches/2026-10-14.json'); b = json.loads(open(p).read()); b.update(status='no_signals', n=0); open(p, 'w').write(json.dumps(b)); COMMIT(td, 'relabel no_signals')
    after = X.collect()[0]; bd = after['batch_coverage']['by_date']['2026-10-14']
    ok('no_signals_cannot_hide_locked_mark', before['counts']['eligible'] == 1 and after['counts']['marks_in_window'] == 1 and after['counts']['eligible'] == 0
       and after['batch_coverage']['ok'] == 0 and 'no_signals_but_marks_exist' in bd['reasons'], {'before': before['counts'], 'after': after['counts'], 'reasons': bd['reasons']})
with tempfile.TemporaryDirectory() as td:                                                                                                       # 真的零訊號日
    X = Fx(td); C = X.no_signals('2026-10-15')
    pub = X.collect(start='2026-10-15', today='2026-10-16', now='2026-10-16T14:00:00Z')[0]; bd = pub['batch_coverage']['by_date']['2026-10-15']
    ok('genuine_no_signals_accepted', bd['accepted'] and pub['batch_coverage']['ok'] == 1 and bd['no_signals_evidence']['prep_commit'] == C, bd)
for name, kw, want in (('no_signals_without_receipt_rejected', {'receipt': None}, 'no_signals_receipt_evidence_missing'),
                       ('no_signals_late_receipt_rejected', {'receipt': 'late'}, 'no_signals_late_remote'),
                       ('no_signals_nonempty_pending_rejected', {'pending_patch': {'n': 1, 'marks': [{'id': '2026-10-15:ADI'}]}}, 'no_signals_pending_not_empty')):
    with tempfile.TemporaryDirectory() as td:
        X = Fx(td); X.no_signals('2026-10-15', **kw)
        bd = X.collect(start='2026-10-15', today='2026-10-16', now='2026-10-16T14:00:00Z')[0]['batch_coverage']['by_date']['2026-10-15']
        ok(name, not bd['accepted'] and want in bd['reasons'], bd['reasons'])
with tempfile.TemporaryDirectory() as td:                                                                                                       # SPY 那天其實是買點
    X = Fx(td); spy14 = snap_of('2026-10-14', 'SPY'); X.no_signals('2026-10-14', spy=spy14, qqq=snap_of('2026-10-14', 'QQQ'))
    bd = X.collect(start='2026-10-14', today='2026-10-15', now='2026-10-15T14:00:00Z')[0]['batch_coverage']['by_date']['2026-10-14']
    ok('no_signals_but_spy_buy_point_rejected', not bd['accepted'] and 'no_signals_but_SPY_buy_point' in bd['reasons'], bd['reasons'])
with tempfile.TemporaryDirectory() as td:                                                                                                       # 宣告零訊號之後 pending 被改
    X = Fx(td); X.no_signals('2026-10-15'); p = os.path.join(td, 'pending/2026-10-15.json'); j = json.load(open(p)); j['note'] = 'edited'; open(p, 'w').write(json.dumps(j)); COMMIT(td, 'edit pending')
    bd = X.collect(start='2026-10-15', today='2026-10-16', now='2026-10-16T14:00:00Z')[0]['batch_coverage']['by_date']['2026-10-15']
    ok('no_signals_pending_changed_rejected', not bd['accepted'] and 'no_signals_pending_changed' in bd['reasons'], bd['reasons'])

# ---- 4. 收件證據(Astra v0.7.4 附錄四 §5)
FAKE = tempfile.mkdtemp(prefix='fakegh_'); DB = os.path.join(FAKE, 'db.json')
open(os.path.join(FAKE, 'gh'), 'w').write('#!/usr/bin/env python3\nimport json, sys, re\ndb = json.load(open(%r))\np = sys.argv[2]\n'
    'm = re.fullmatch(r"repos/[^/]+/[^/]+/actions/runs/(\\d+)", p)\nif m:\n    r = db["runs"].get(m.group(1))\n    if r is None: sys.stderr.write("404"); sys.exit(1)\n'
    '    print(json.dumps(r)); sys.exit(0)\nm = re.search(r"head_sha=([0-9a-f]{40})", p)\nif m:\n    print(json.dumps({"workflow_runs": [r for r in db["runs"].values() if r["head_sha"] == m.group(1)]})); sys.exit(0)\n'
    'sys.stderr.write("unknown"); sys.exit(1)\n' % DB)
os.chmod(os.path.join(FAKE, 'gh'), 0o755); os.environ['PATH'] = FAKE + os.pathsep + os.environ['PATH']
def fake_db(*runs):
    json.dump({'runs': {str(r['id']): dict(r, repository={'full_name': r['repository']}, status='completed', conclusion='success') for r in runs}}, open(DB, 'w'))
with tempfile.TemporaryDirectory() as td:
    X = Fx(td); lc, rc = X.lock('2026-10-14', [('ADI', SNAP, 'agree')]); api = run_api(rc['run_id'], lc, rc['remote_received_utc']); fake_db(api)
    w, _ = V.check_receipt(rc, '2026-10-14', V.Evidence(X.ev, online=True)); ok('online_matches_cache_accepted', w == [], w)
    cp = os.path.join(X.ev, f"run-{rc['run_id']}.json"); d0 = json.load(open(cp))
    bad = dict(d0, api=dict(d0['api'], head_sha='a' * 40), api_subset_sha256='wrong', source='not a GitHub response'); json.dump(bad, open(cp, 'w'))
    w, _ = V.check_receipt(dict(rc, lock_commit='a' * 40), '2026-10-14', V.Evidence(X.ev, online=True))
    ok('online_rejects_modified_cache', w == ['receipt_evidence_cache_corrupt'], w)                                                               # Astra 附錄四 §5 的構造
    forged = dict(d0, api=dict(d0['api'], head_sha='a' * 40)); forged['api_subset_sha256'] = H(json.dumps(forged['api'], sort_keys=True).encode()); json.dump(forged, open(cp, 'w'))
    w, _ = V.check_receipt(dict(rc, lock_commit='a' * 40), '2026-10-14', V.Evidence(X.ev, online=True))
    ok('online_rejects_self_consistent_forged_cache', w == ['receipt_evidence_cache_differs_from_api'], w)
    json.dump(d0, open(cp, 'w'))
    w, _ = V.check_receipt(rc, '2026-10-14', V.Evidence(X.ev, online=False)); ok('offline_unpinned_rejected', w == ['receipt_evidence_not_pinned'], w)
    pins = X.pins(); w, _ = V.check_receipt(rc, '2026-10-14', V.Evidence(X.ev, online=False, pins=pins)); ok('offline_pinned_accepted', w == [], w)
    json.dump(forged, open(cp, 'w')); w, _ = V.check_receipt(rc, '2026-10-14', V.Evidence(X.ev, online=False, pins=pins)); ok('offline_pin_mismatch_rejected', w == ['receipt_evidence_pin_mismatch'], w)
    fake_db(); json.dump(d0, open(cp, 'w'))
    w, _ = V.check_receipt(rc, '2026-10-14', V.Evidence(X.ev, online=True)); ok('online_api_failure_rejects_in_dry_run', w == ['receipt_api_error'], w)
    try:
        V.check_receipt(rc, '2026-10-14', V.Evidence(X.ev, online=True, strict=True)); ok('formal_api_failure_stops', False)
    except SystemExit as e: ok('formal_api_failure_stops', '不寫判定' in str(e), str(e)[:80])
# Astra v0.7.5 §3.2:API 好好的、只有本機快取壞 → 正式模式要停(不是「證據不合格」);試跑照舊列原因;修復 = 隔離 + 用新查到的原件重建 + 記錄
with tempfile.TemporaryDirectory() as td:
    X = Fx(td); lc, rc = X.lock('2026-10-14', [('ADI', SNAP, 'agree')]); api = run_api(rc['run_id'], lc, rc['remote_received_utc']); fake_db(api)
    name = f"run-{rc['run_id']}.json"; cp = os.path.join(X.ev, name); d0 = json.load(open(cp)); open(cp, 'w').write('{local cache damaged')
    try:
        V.check_receipt(rc, '2026-10-14', V.Evidence(X.ev, online=True, strict=True)); ok('formal_corrupt_cache_stops', False)
    except SystemExit as e: ok('formal_corrupt_cache_stops', 'repair-evidence' in str(e) and '不寫判定' in str(e) and 'evidence_cache_corrupt' in str(e), str(e)[:90])
    w, _ = V.check_receipt(rc, '2026-10-14', V.Evidence(X.ev, online=True)); ok('dry_run_corrupt_cache_still_listed', w == ['receipt_evidence_cache_corrupt'], w)
    forged = dict(d0, api=dict(d0['api'], created_at='2026-10-15T01:00:00Z')); forged['api_subset_sha256'] = H(json.dumps(forged['api'], sort_keys=True).encode()); json.dump(forged, open(cp, 'w'))
    try:
        V.check_receipt(rc, '2026-10-14', V.Evidence(X.ev, online=True, strict=True)); ok('formal_cache_differs_stops', False)
    except SystemExit as e: ok('formal_cache_differs_stops', 'evidence_cache_differs_from_api' in str(e), str(e)[:90])
    bad_b = open(cp, 'rb').read(); rep = V.repair_evidence(X.ev, name)
    qf = os.path.join(X.ev, rep['quarantined_as']); logl = V.repairs_log(X.ev)
    w, _ = V.check_receipt(rc, '2026-10-14', V.Evidence(X.ev, online=True, strict=True))
    ok('repair_quarantines_rebuilds_and_logs', rep['status'] == 'repaired' and rep['reason'] == 'evidence_cache_differs_from_api' and open(qf, 'rb').read() == bad_b
       and len(logl) == 1 and logl[0]['old_sha256'] == H(bad_b) and json.load(open(cp))['api'] == api and w == [], {k: rep[k] for k in ('reason', 'quarantined_as', 'new_sha256')})
    ok('repair_noop_when_cache_ok', V.repair_evidence(X.ev, name)['status'] == 'no_repair_needed' and len(V.repairs_log(X.ev)) == 1)
    fake_db()
    try:
        V.repair_evidence(X.ev, name); ok('repair_refuses_without_api', False)
    except SystemExit as e: ok('repair_refuses_without_api', '不修' in str(e), str(e)[:60])
    st_ = V.Evidence(os.path.join(td, 'ev_empty'), online=True); runs, src = V.runs_for_commit(st_, 'b' * 40)
    ok('empty_run_list_not_cached', runs == [] and src == 'online' and not os.path.exists(os.path.join(td, 'ev_empty', f"runs-for-{'b' * 40}.json")))

# ---- 5. 引擎從 git 物件載入
with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as fake:
    X = Fx(td)
    open(os.path.join(fake, 'astra_trades.py'), 'w').write(ENG['scripts/astra_trades.py'].decode() + '\ndef ret(O, e, x, cost=0.0):\n    return 0.123456789\n')
    sys.path.insert(0, fake); sys.modules.pop('astra_trades', None)
    prov = V.load_engine(X.g, X.mc, X.man['files'])
    sys.path.remove(fake)
    ok('engine_loaded_from_git_not_local', V.AT.ret([100, 100, 89], 1, 2, 0.0) != 0.123456789 and prov['scripts/astra_trades.py']['loaded_from'].startswith('git:'), prov)
    try:
        bad = dict(X.man['files']); bad['scripts/astra_trades.py'] = '0' * 64; V.load_engine(X.g, X.mc, bad); ok('engine_hash_mismatch_stops', False)
    except SystemExit as e: ok('engine_hash_mismatch_stops', True, str(e))
    V.load_engine(X.g, X.mc, X.man['files'])
    try:
        V.engine_changes_on_main(X.g, 'no-such-ref', X.mc); ok('history_query_failure_stops', False)
    except SystemExit as e: ok('history_query_failure_stops', True, str(e)[:60])
    ok('no_engine_change_after_freeze', V.engine_changes_on_main(X.g, 'main', X.mc) == [])

# ---- 6. 出場重播(真實快照 + 自己做的之後 K 線:第 2 根收盤跌破 8% → 停損)
i = len(SNAP) - 1; o1 = SNAP[i][4]
fwd = [['2026-10-15', o1, o1 * 1.01, o1 * .99, o1, 1], ['2026-10-16', o1, o1, o1 * .88, o1 * .90, 1], ['2026-10-19', o1 * .89, o1 * .9, o1 * .87, o1 * .88, 1]]
B = SNAP + fwd; O = [x[1] for x in B]
rec = {'status': 'closed', 'entry': '2026-10-15', 'exit': '2026-10-19', 'exit_why': '停損', 'ret': V.AT.ret(O, i + 1, i + 3, .001), 'bars_used': B[i - 1:],
       'entry_open': O[i + 1], 'exit_open': O[i + 3], 'closed_utc': '2026-10-20T00:30:00Z'}
m = dict(REAL)
st, r, note = V.replay(m, rec, SNAP, V.SPEC); ok('replay_reproduces_within_tolerance', st == 'closed' and abs(r - rec['ret']) < 1e-15 and note == '', (st, r, note))
ok('replay_wrong_return_unreproducible', V.replay(m, dict(rec, ret=0.123456789), SNAP, V.SPEC)[0] == 'unreproducible')
ok('replay_wrong_reason_unreproducible', V.replay(m, dict(rec, exit_why='頂'), SNAP, V.SPEC)[0] == 'unreproducible')
ok('missing_bars_unreproducible', V.replay(m, dict(rec, bars_used=B[i - 1:i + 2]), SNAP, V.SPEC)[0] == 'unreproducible')
wk = [['2026-10-17'] + fwd[0][1:], ['2026-10-18'] + fwd[1][1:], ['2026-10-19'] + fwd[2][1:]]
st6, _, n6 = V.replay(m, dict(rec, bars_used=SNAP[i - 1:] + wk, entry='2026-10-17'), SNAP, V.SPEC); ok('weekend_bars_rejected', st6 == 'unreproducible', n6)
ok('gap_in_window_rejected', V.replay(m, dict(rec, bars_used=SNAP[i - 1:] + [fwd[0], fwd[2]]), SNAP, V.SPEC)[0] == 'unreproducible')
st7, _, n7 = V.replay(m, dict(rec, closed_utc='2026-10-14T21:00:00Z'), SNAP, V.SPEC); ok('recorded_before_available_rejected', st7 == 'unreproducible', n7)
ok('late_close_flagged', V.replay(m, dict(rec, closed_utc='2026-11-05T00:00:00Z'), SNAP, V.SPEC)[2] == 'late_close')
# 半日市的出場紀錄(Astra v0.7.5 附錄四的構造:11-25 進場、收盤跌破停損 → 11-27 開盤出場;11-27 13:00 收盤,14:00 記錄)
snapE = [list(b) for b in SNAP]; dE = dt.date(2026, 11, 24); dsE = []
while len(dsE) < len(snapE):
    if dE.weekday() < 5: dsE.append(dE.isoformat())
    dE -= dt.timedelta(days=1)
for b_, d_ in zip(snapE, reversed(dsE)): b_[0] = d_
oE = snapE[-1][4]; BE = snapE + [['2026-11-25', oE, oE, oE * .88, oE * .90, 1], ['2026-11-27', oE * .89, oE * .90, oE * .87, oE * .88, 1]]; iE = len(snapE) - 1
recE = dict(status='closed', entry='2026-11-25', exit='2026-11-27', exit_why='停損', ret=V.AT.ret([b_[1] for b_ in BE], iE + 1, iE + 2, .001), bars_used=BE[iE - 1:], closed_utc='2026-11-27T19:00:00Z')
mE = {'date': snapE[-1][0], 'style': 'b'}
D3.AD, D3.AT = V.AD, V.AT
eA, eB, eC = V.replay(mE, recE, snapE, V.SPEC), V.replay(mE, dict(recE, closed_utc='2026-11-27T17:59:00Z'), snapE, V.SPEC), D3.replay(mE, recE, snapE, D3.SPEC)
ok('early_close_exit_recorded_after_1300_accepted', eA[0] == 'closed' and eB[0] == 'unreproducible' and '記錄時間早於' in eB[2] and eC[0] == 'unreproducible',
   {'new_14:00': eA[:1], 'new_12:59': eB[:1], 'draft3_14:00': eC[:1] + eC[2:]})
ok('entry_open_mismatch_unreproducible', V.replay(m, dict(rec, entry_open=O[i + 1] + 0.01), SNAP, V.SPEC)[0] == 'unreproducible')
# 尺度(Astra v0.7.4 附錄四 §4)
sc = [[b[0]] + [V.AD.rp(x * 0.99) for x in b[1:5]] + [b[5]] for b in SNAP[i - 1:]] + fwd
st8, r8, n8 = V.replay(m, dict(rec, bars_used=sc), SNAP, V.SPEC)
ok('consistent_rescale_reconciled', st8 == 'closed' and n8.startswith('rescaled f=') and abs(float(n8.split('f=')[1].split('(')[0]) - 0.99) < 2e-5, (st8, n8))
c1 = json.loads(json.dumps(rec)); c1['bars_used'][0][1:5] = [x * 2 for x in c1['bars_used'][0][1:5]]
s1, _, w1 = V.replay(m, c1, SNAP, V.SPEC); ok('inconsistent_overlap_rejected', s1 == 'unreproducible' and '共同比例' in w1, w1)                    # 4.1 反例 1
c2 = json.loads(json.dumps(rec)); c2['bars_used'][1][4] = V.AD.rp(c2['bars_used'][1][4] * .99)
s2, _, w2 = V.replay(m, c2, SNAP, V.SPEC); ok('single_close_change_rejected', s2 == 'unreproducible' and ('共同比例' in w2 or '欄位不合理' in w2), w2)                    # 4.1 反例 2
c3 = json.loads(json.dumps(rec)); hi_, lo_, cl_ = c3['bars_used'][1][2], c3['bars_used'][1][3], c3['bars_used'][1][4]
c3['bars_used'][1][4] = V.AD.rp(cl_ - 0.4 * (cl_ - lo_)); assert V.valid_bar(c3['bars_used'][1]) and c3['bars_used'][1][4] != cl_                  # 收盤改了但 K 線仍合理
s3_, _, w3 = V.replay(m, c3, SNAP, V.SPEC); ok('single_close_change_caught_by_scale_check', s3_ == 'unreproducible' and '共同比例' in w3, w3)
L = legacy(); L.AD, L.AT = V.AD, V.AT
ok('legacy_draft2_accepted_both_overlap_counterexamples', L.replay(m, c1, SNAP, L.SPEC)[0] == 'closed' and L.replay(m, c2, SNAP, L.SPEC)[0] == 'closed')
# 4.2:整段 × 0.4 後再四捨五入會把原買點變成不是買點 → 新版不重新選樣
ts_ = [list(b) for b in TSNAP]; ts_[-2][2] = round(ts_[-1][4] - .001, 3); j = len(ts_) - 1
assert j in dict(V.AT.buy_points(V.AD.sw_series(ts_)))
scaled = [[b[0]] + [V.AD.rp(x * .4) for x in b[1:5]] + [b[5]] for b in ts_]
assert j not in dict(V.AT.buy_points(V.AD.sw_series(scaled)))
to = scaled[-1][4]; tf = [['2026-10-15', to, to * 1.01, to * .99, to, 1], ['2026-10-16', to, to, to * .88, to * .9, 1], ['2026-10-19', to * .89, to * .9, to * .87, to * .88, 1]]
BL = scaled + tf; WL = V.AD.sw_series(BL); OL = [b[1] for b in BL]; dL, whyL = V.AT.exit_of(WL, OL, j, V.AT.STY['b'])          # 帳本會在「新尺度」上算出場
trec = {'status': 'closed', 'entry': BL[j + 1][0], 'exit': BL[dL + 1][0], 'exit_why': whyL, 'ret': V.AT.ret(OL, j + 1, dL + 1, .001), 'bars_used': BL[j - 1:dL + 2],
        'entry_open': OL[j + 1], 'exit_open': OL[dL + 1], 'closed_utc': '2026-10-20T00:30:00Z'}
tm = dict(next(json.loads(l) for l in real_show('origin/astra-ledger', 'marks.jsonl').decode().splitlines() if json.loads(l)['id'] == '2026-10-14:T'))
tr = V.replay(tm, trec, ts_, V.SPEC); lr = L.replay(tm, trec, ts_, L.SPEC)
ok('frozen_buy_point_not_reselected_after_rescale', tr[0] == 'closed' and tr[2].startswith('rescaled f=') and lr[0] == 'unreproducible' and '不是買點' in lr[2], {'new': tr, 'draft2': lr[:1] + lr[2:]})

# ---- 7. 統計(正式估計量,2,000 次)— Astra v0.7.4 附錄三的反例
cal = [f'D{k:03d}' for k in range(120)]
def astra_example(s):
    rows = []
    for k, d in enumerate(cal):
        if k % 2 == 0: rows += [(d, 'stock', f'A{q}', 'agree', .005) for q in range(30)] + [(d, 'stock', f'B{q}', 'disagree', -.005) for q in range(30)]
        else: rows += [(d, 'stock', f'C{k}', 'agree', -s), (d, 'stock', f'E{k}', 'disagree', s)]
    return rows
ce = astra_example(.006)
old = L.decide(ce, [], cal, dict(L.SPEC))
ok('draft2_counterexample_reproduced', old['decision'] == 'PASS' and old['go_live_candidate'] and abs(old['excluded_missing']['h1_lb_pp'] - 0.1841978051) < 1e-9
   and abs(old['excluded_missing']['h1_pp'] + 0.1) < 1e-12, {'h1_pp': old['excluded_missing']['h1_pp'], 'h1_lb_pp': old['excluded_missing']['h1_lb_pp']})
new = V.decide(ce, [], cal, dict(V.SPEC, h2_mode='none')); ex = new['excluded_missing']
ok('counterexample_now_no_pass_all_modes', set(new['decision_by_h2_mode'].values()) == {'NO_PASS'} and ex['h1_lb_pp'] < 0 and ex['h1_methods']['M2']['lb_pp'] < 0
   and abs(ex['h1_methods']['M1']['median_pp'] - ex['h1_pp']) < 0.01 and ex['draws_effective'] == 2000,
   {'h1_pp': ex['h1_pp'], 'M1': ex['h1_methods']['M1'], 'M2_lb': ex['h1_methods']['M2']['lb_pp'], 'decision': new['decision_by_h2_mode']})
mult, U = V.draw_weights(cal, 180, V.SPEC)
ok('weights_positive_and_dates_unbiased', bool((U > 0).all()) and abs(mult.mean() - 1) < 1e-12 and float(np.abs(mult.mean(0) - 1).max()) < 0.12
   and abs(float(mult[:, :5].mean()) - float(mult[:, 50:70].mean())) < 0.06, {'U_min': float(U.min()), 'date_mean_max_dev': float(np.abs(mult.mean(0) - 1).max()),
                                                                                'edge_mean': float(mult[:, :5].mean()), 'middle_mean': float(mult[:, 50:70].mean())})
cal = V.sessions('2026-10-19', V.add_sessions('2026-10-19', 120)); cfg = dict(V.SPEC, h2_mode='agree_vs_disagree_lb')
def rows_(n_days, ag, dg, ra, rd, syms=80, typ='stock'):
    out = []
    for t in range(n_days):
        for k in range(ag): out.append((cal[t], typ, f'S{(t * 7 + k) % syms}', 'agree', ra(t, k)))
        for k in range(dg): out.append((cal[t], typ, f'S{(t * 11 + k + 40) % syms}', 'disagree', rd(t, k)))
    return out
base = rows_(100, 2, 2, lambda t, k: .001, lambda t, k: -.001)
miss1 = [(cal[3], 'stock', 'S5', 'agree')]
a = V.decide(base, miss1, cal, cfg)
ok('missing_agree_uses_minus_100pct', a['decision'] == 'NO_PASS' and a['excluded_missing']['H1'] and not a['agree_missing_at_minus_100pct']['H1'] and a['stress_q05_q95']['H1'],
   {'excl_lb': a['excluded_missing']['h1_lb_pp'], 'minus100_h1': a['agree_missing_at_minus_100pct']['h1_pp'], 'stress_h1': a['stress_q05_q95']['h1_pp']})
fp = a['flip_points']['agree']; ok('flip_point_reported', fp is not None and abs(V.h1_point(base + [miss1[0] + (fp,)])) < 1e-9 and -1 < fp < 0, fp)
b = V.decide(base, [(cal[3], 'stock', 'S6', 'disagree')], cal, cfg)
ok('missing_disagree_is_insufficient', b['decision'] == 'INSUFFICIENT' and not b['gates']['no_missing_disagree'])
allwin = rows_(100, 2, 2, lambda t, k: .03 + .001 * ((t + k) % 3), lambda t, k: .01 + .001 * ((t + k) % 3))
c1 = V.decide(allwin, [], cal, cfg)
ok('h1_without_win_gap_fails_h2', c1['decision'] == 'NO_PASS' and c1['excluded_missing']['H1'] and c1['decision_by_h2_mode']['none'] == 'PASS',
   {'h1_pp': c1['excluded_missing']['h1_pp'], 'win_a': c1['excluded_missing']['win_agree_pct'], 'win_d': c1['excluded_missing']['win_disagree_pct']})
one = [(cal[0], 'stock', f'S{q}', 'agree' if q < 100 else 'disagree', .01 if q < 100 else -.01) for q in range(200)] + [(cal[1], 'stock', f'S{q}', 'agree', .01) for q in range(200, 300)]
ok('one_paired_date_insufficient', V.decide(one, [], cal, cfg)['decision'] == 'INSUFFICIENT')
strong = rows_(100, 2, 2, lambda t, k: .02 + .001 * ((t * 7 + k) % 5 - 2), lambda t, k: -.01 + .001 * ((t * 3 + k) % 5 - 2))
d1 = V.decide(strong, [], cal, cfg); ok('strong_effect_passes', d1['decision'] == 'PASS' and d1['go_live_candidate'], {k: d1['excluded_missing'][k] for k in ('h1_pp', 'h1_lb_pp', 'win_gap_ad_lb_pp')})
ok('low_batch_coverage_insufficient', V.decide(strong, [], cal, cfg, coverage=0.85)['decision'] == 'INSUFFICIENT')
ok('goog_googl_one_issuer', len({V.issuer(s) for s in ('GOOG', 'GOOGL', 'AAPL')}) == 2)
e = V.stats(strong, cal, cfg); lhs = e['win_agree_pct'] - e['win_all_pct']; rhs = (1 - e['agree_share']) * (e['win_agree_pct'] - e['win_disagree_pct'])
ok('h2_identity', abs(lhs - rhs) < 1e-9, (lhs, rhs))
import math as _m   # 下面 t 分位數的對照值 = scipy 1.18.1 t.ppf(0.975, df)
ok('t_quantile_matches_tables', all(abs(V.t_quantile(0.975, d) - q) < 1e-8 for d, q in ((1, 12.706204736174694), (5, 2.5705818356363146), (23, 2.0686576104190486), (120, 1.9799304050824402), (10 ** 6, 1.959966356814107))),
   {d: V.t_quantile(0.975, d) for d in (1, 5, 23, 120)})
hm = V.stats(strong, cal, dict(V.SPEC))['h1_methods']
ok('c1_c3_intervals_reported', all(k in hm for k in ('M1', 'M2', 'C1', 'C3')) and hm['C1']['df'] == min(len(cal) // 5, 80) - 1
   and abs(hm['C1']['lb_pp'] - (V.stats(strong, cal, dict(V.SPEC))['h1_pp'] - hm['C1']['t975'] * hm['C1']['se_pp'])) < 1e-9 and set(hm['C3']['var_components_pp2']) == {'date_blocks', 'issuers', 'intersection'},
   {m: {k: hm[m].get(k) for k in ('lb_pp', 'ub_pp', 'se_pp', 'df')} for m in ('M1', 'C1', 'C3')})
ok('undecided_h2_reports_all_modes', V.decide(strong, [], cal, dict(V.SPEC))['decision'] is None and set(V.decide(strong, [], cal, dict(V.SPEC))['decision_by_h2_mode']) == set(V.H2_MODES))

# ---- 8. 唯一一次與正式入口(完整正式流程另見 v3_fullflow.py)
with tempfile.TemporaryDirectory() as td:
    subprocess.run(['git', 'init', '-q', td], check=True)
    lp = os.path.join(td, V.LOOK_DIR, 'EXP-TEST.json'); os.makedirs(os.path.dirname(lp)); open(lp, 'w').write('{}'); COMMIT(td, 'look'); os.remove(lp)
    ok('look_registry_blocks_even_if_file_deleted', V.look_exists(td, lp))
    out2 = subprocess.run([sys.executable, '-I', os.path.join(HERE, 'v3_verify.py'), 'analyze', '--repo', td, '--dry-run', '--out', os.path.dirname(lp)], capture_output=True, text=True)
    ok('dry_run_cannot_write_registry', out2.returncode != 0 and '不能寫進正式' in (out2.stderr + out2.stdout), (out2.stderr + out2.stdout).strip()[-60:])
run = lambda *a: subprocess.run([sys.executable, '-I', os.path.join(HERE, 'v3_verify.py'), *a], capture_output=True, text=True)
with tempfile.TemporaryDirectory() as td:                       # 沒有凍結 manifest 的 repo(有本機 bare origin;正式模式一開始就以遠端為準)
    w0 = os.path.join(td, 'w'); org0 = os.path.join(td, 'o.git'); subprocess.run(['git', 'init', '-q', '--bare', org0], check=True); subprocess.run(['git', 'init', '-q', '-b', 'main', w0], check=True)
    WR(w0, 'README', b'x'); COMMIT(w0, 'm'); GIT(w0, 'checkout', '-q', '-b', 'astra-ledger'); WR(w0, 'L', b'x'); COMMIT(w0, 'l')
    GIT(w0, 'remote', 'add', 'origin', org0); GIT(w0, 'push', '-q', 'origin', 'main', 'astra-ledger')
    o3 = run('analyze', '--formal', '--repo', w0); ok('formal_mode_needs_frozen_manifest', o3.returncode != 0 and 'v3_manifest' in (o3.stderr + o3.stdout), (o3.stderr + o3.stdout).strip()[-80:])
o4 = run('analyze', '--formal', '--repo', REPO, '--today', '2027-12-31'); ok('formal_mode_rejects_overrides', o4.returncode != 0 and '不接受任何覆寫' in (o4.stderr + o4.stdout))
o5 = run('status', '--repo', REPO); ok('needs_dry_run_or_formal', o5.returncode != 0 and '--dry-run' in (o5.stderr + o5.stdout))
mf = V.make_manifest('2026-11-02', 250, 'none', '3faf68b7' + '0' * 56, open(os.path.join(HERE, 'v3_verify.py'), 'rb').read(), 1.0)
ok('manifest_fixes_id_paths_calendar', mf['experiment_id'] == 'LV3-20261102-S250-C1-L5-none' and mf['look_path'].endswith(mf['experiment_id'] + '.json')
   and mf['end'] == V.add_sessions('2026-11-02', 250) and mf['calendar_sha256'] == V.calendar_fingerprint() and mf['spec']['h2_mode'] == 'none', {k: mf[k] for k in ('experiment_id', 'end', 'look_path')})
try:
    V.make_manifest('2026-11-02', 180, 'none', 'f' * 64, b'x', 1.0); ok('manifest_rejects_unlisted_choices', False)
except SystemExit: ok('manifest_rejects_unlisted_choices', True)
ok('manifest_records_resolve_by', mf['resolve_by'] == V.add_sessions(mf['end'], 52))
try:
    V.make_manifest('2028-06-01', 250, 'none', 'f' * 64, b'x', 1.0); ok('manifest_rejects_start_beyond_calendar', False)
except SystemExit as e: ok('manifest_rejects_start_beyond_calendar', '日曆只到' in str(e), str(e)[:60])

# ---- 9. 半日市的凍結錨點(Astra v0.7.5 §3.1:起日 2026-11-27 13:00 收盤,錨點 14:00 才收到 → 草案 3 照收)
VB = open(os.path.join(HERE, 'v3_verify.py'), 'rb').read(); VPATH = os.path.join(HERE, 'v3_verify.py')
def freeze_fx(td, start):
    X = Fx(td); GIT(td, 'checkout', '-q', 'main')
    man = V.make_manifest(start, 120, 'none', X.msha, VB, 1.0, 'session-close probe'); mb = (json.dumps(man, ensure_ascii=False, indent=1) + '\n').encode()
    WR(td, V.MANIFEST_PATH, mb); WR(td, V.VERIFIER_PATH, VB); F = COMMIT(td, 'freeze')
    GIT(td, 'checkout', '-q', 'astra-ledger'); WR(td, man['anchor_path'], json.dumps(V.anchor_json(mb, F)).encode()); A = COMMIT(td, 'anchor')
    def check(t):
        X.put_runs_for(A, [run_api(999, A, t)])
        try: V.formal_checks(X.g, 'main', 'astra-ledger', X.store(), VB); return 'accepted'
        except SystemExit as e: return str(e)[:60]
    return check
for name, start, good, bad in (('anchor_deadline_uses_early_close', '2026-11-27', ['2026-11-27T17:59:00Z'], ['2026-11-27T18:00:00Z', '2026-11-27T19:00:00Z']),
                               ('anchor_deadline_normal_day', '2026-11-30', ['2026-11-30T20:59:00Z'], ['2026-11-30T21:00:00Z']),
                               ('anchor_deadline_dst_day', '2026-10-30', ['2026-10-30T19:59:00Z'], ['2026-10-30T20:00:00Z'])):
    with tempfile.TemporaryDirectory() as td:
        chk = freeze_fx(td, start); r = {t: chk(t) for t in good + bad}
        ok(name, all(r[t] == 'accepted' for t in good) and all('不早於起日' in r[t] for t in bad), r)

# ---- 10. 結案截止(收案期最後一天之後第 51 個交易日收盤)— 判定和「哪一天跑」無關
with tempfile.TemporaryDirectory() as td:
    X = Fx(td); X.lock('2026-10-14', [('ADI', SNAP, REAL['v'])])
    def with_rec(closed_utc, now):
        WR(td, 'scores.json', json.dumps({'marks': {REAL['id']: dict(rec, closed_utc=closed_utc)}}).encode()); COMMIT(td, 'scores ' + closed_utc)
        return X.collect(start='2026-10-14', today=V.P(now).astimezone(V.ET).date().isoformat(), now=now)
    p1, c1, m1, *_ = with_rec('2026-10-20T00:30:00Z', '2027-08-02T22:00:00Z')
    p2, c2, m2, *_ = with_rec('2027-07-30T00:00:00Z', '2027-08-02T22:00:00Z')
    p3, c3, m3, *_ = with_rec('2026-10-20T00:30:00Z', '2026-10-19T12:00:00Z')
    ok('result_after_cutoff_counts_as_missing', len(c1) == 1 and not m1 and not c2 and len(m2) == 1 and 'closed_after_cutoff' in p2['flags'][REAL['id']]
       and p2['cohort']['resolve_by'] == V.add_sessions(p2['cohort']['end'], 52), {'cut': p2['cohort']['resolve_by_close_utc'], 'flag': p2['flags'].get(REAL['id'])})
    ok('result_later_than_now_not_yet_closed', not c3 and not m3 and p3['counts']['pending'] == 1, p3['flags'])

# ---- 11. 開跑登記 + 決定性重播(Astra v0.7.5 §3.2、§3.3;本機 bare repo 當 origin,hook = 假的 ledger-receipt 與 push 被拒)
HK = tempfile.mkdtemp(prefix='v3hook_'); CLK = os.path.join(HK, 'clock'); NOREC = os.path.join(HK, 'no_receipt'); REJ = os.path.join(HK, 'reject_')
POST = (f'#!/usr/bin/env python3\nimport json, os, sys\nif os.path.exists({NOREC!r}): sys.exit(0)\ndb = json.load(open({DB!r})); now = open({CLK!r}).read().strip()\n'
        f'for line in sys.stdin:\n    old, new, ref = line.split()\n    if ref == "refs/heads/astra-ledger" and set(new) != {{"0"}}:\n        rid = 950000000 + len(db["runs"])\n'
        f'        db["runs"][str(rid)] = {{"id": rid, "name": "ledger-receipt", "path": {V.RECEIPT_WF!r}, "event": "push", "head_branch": "astra-ledger", "head_sha": new,'
        f' "created_at": now, "repository": {{"full_name": {V.OWNER_REPO!r}}}, "status": "completed", "conclusion": "success"}}\njson.dump(db, open({DB!r}, "w"))\n')
PRE = (f'#!/usr/bin/env python3\nimport os, sys\nfor line in sys.stdin:\n    old, new, ref = line.split()\n'
       f'    if os.path.exists({REJ!r} + ref.split("/")[-1]): sys.stderr.write("rejected by test hook"); sys.exit(1)\n')
def remote_fx(td):
    X = Fx(os.path.join(td, 'w')); w = X.td; start = '2026-10-14'
    GIT(w, 'checkout', '-q', 'main'); man = V.make_manifest(start, 120, 'none', X.msha, VB, 1.0, 'remote fixture'); mb = (json.dumps(man, ensure_ascii=False, indent=1) + '\n').encode()
    WR(w, V.MANIFEST_PATH, mb); WR(w, V.VERIFIER_PATH, VB); F = COMMIT(w, 'freeze')
    GIT(w, 'checkout', '-q', 'astra-ledger'); WR(w, man['anchor_path'], json.dumps(V.anchor_json(mb, F)).encode()); A = COMMIT(w, 'anchor')
    lc, rc = X.lock(start, [('ADI', SNAP, 'agree')])
    fake_db(run_api(rc['run_id'], lc, rc['remote_received_utc']), run_api(999, A, '2026-10-13T12:00:00Z'))
    org = os.path.join(td, 'origin.git'); subprocess.run(['git', 'init', '-q', '--bare', '-b', 'main', org], check=True)
    for n_, s_ in (('post-receive', POST), ('pre-receive', PRE)):
        p_ = os.path.join(org, 'hooks', n_); open(p_, 'w').write(s_); os.chmod(p_, 0o755)
    open(CLK, 'w').write('2026-10-16T06:00:00Z'); GIT(w, 'remote', 'add', 'origin', org); GIT(w, 'push', '-q', 'origin', 'main', 'astra-ledger')   # 截止前收件
    open(CLK, 'w').write('2027-08-02T22:05:00Z')                                                                  # 之後的 push(登記等)= 截止後
    return X, man, rc, org
def remote_state(repo, exp, look_path):
    g = V.Git(repo); rm, rl = V.fetch_remote(g, 'origin')
    return {'main': rm, 'ledger': rl, 'registration': g.touching(rl, V.registration_path(exp)), 'look': g.touching(rm, look_path)}
def must_stop(fn, want):
    try:
        fn(); return 'DID NOT STOP'
    except SystemExit as e:
        return str(e) if want in str(e) else 'WRONG STOP: ' + str(e)[:120]
def push_edit(org, td, branch, path, edit):
    c = os.path.join(td, 'edit-' + branch); shutil.rmtree(c, ignore_errors=True); subprocess.run(['git', 'clone', '-q', '-b', branch, org, c], check=True)
    p_ = os.path.join(c, path); open(p_, 'wb').write(edit(open(p_, 'rb').read())); COMMIT(c, 'edit ' + path); GIT(c, 'push', '-q', 'origin', branch)
old_clock, old_sleep = V.clock, V.time.sleep
V.clock = lambda: V.P('2027-08-02T22:00:00Z')
try:
    with tempfile.TemporaryDirectory() as td:          # A:API 正常、本機快取壞 → 停(沒有登記、沒有判定)→ 修復 → 一份判定;之後怎麼重跑都是同一份
        X, man, rc, org = remote_fx(td); exp, lpath = man['experiment_id'], man['look_path']; ev = os.path.join(td, 'ev'); os.makedirs(ev)
        name = f"run-{rc['run_id']}.json"; open(os.path.join(ev, name), 'w').write('{local cache damaged')
        msg = must_stop(lambda: V.formal_run(X.td, evdir=ev, me_path=VPATH), 'repair-evidence'); s0 = remote_state(X.td, exp, lpath)
        ok('formal_corrupt_cache_stops_before_registration', not msg.startswith(('DID', 'WRONG')) and s0['registration'] == [] and s0['look'] == [], {'stop': msg[:70], 'state': s0})
        rep = V.repair_evidence(ev, name)
        look, info = V.formal_run(X.td, evdir=ev, me_path=VPATH); s1 = remote_state(X.td, exp, lpath)
        ok('repaired_cache_then_one_persisted_look', rep['status'] == 'repaired' and info['mode'] == 'FIRST' and info['status'] == 'PERSISTED' and look['status']['counts']['eligible'] == 1
           and look['status']['batch_coverage']['by_date']['2026-10-14']['accepted'] and look['decision'] == 'INSUFFICIENT' and len(s1['registration']) == 1 and len(s1['look']) == 1
           and look['registration']['record']['evidence_repairs'][0]['name'] == name and look['analysis_time_utc'] == '2027-06-21T20:00:00Z',
           {'info': info, 'eligible': look['status']['counts']['eligible'], 'decision': look['decision']})
        shutil.rmtree(ev); look2, info2 = V.formal_run(X.td, evdir=os.path.join(td, 'ev2'), me_path=VPATH); s2 = remote_state(X.td, exp, lpath)
        ok('rerun_after_deleting_local_files_replays_identical', info2['mode'] == 'REPLAY' and info2['status'] == 'ALREADY_PERSISTED_IDENTICAL' and info2['look_sha256'] == info['look_sha256']
           and (s2['main'], s2['ledger']) == (s1['main'], s1['ledger']), info2)
        cl = os.path.join(td, 'clone'); subprocess.run(['git', 'clone', '-q', org, cl], check=True)
        look3, info3 = V.formal_run(cl, evdir=os.path.join(td, 'ev3'), me_path=VPATH)
        ok('other_checkout_replays_identical', info3['status'] == 'ALREADY_PERSISTED_IDENTICAL' and info3['look_sha256'] == info['look_sha256'], info3)
        push_edit(org, td, 'astra-ledger', 'scores.json', lambda b: b.replace(b'{"marks":{}}', b'{"marks":{},"note":"after registration"}'))
        look4, info4 = V.formal_run(X.td, evdir=os.path.join(td, 'ev2'), me_path=VPATH); s4 = remote_state(X.td, exp, lpath)
        L0 = look['registration']['record']['ledger_view_commit']
        ok('new_ledger_data_after_registration_ignored', info4['look_sha256'] == info['look_sha256'] and look4['status']['refs']['ledger'] == L0 and s4['ledger'] != L0, {'L0': L0[:10], 'head': s4['ledger'][:10]})
        push_edit(org, td, 'main', lpath, lambda b: b.replace(b'"decision": "INSUFFICIENT"', b'"decision": "PASS"', 1))
        msg = must_stop(lambda: V.formal_run(X.td, evdir=os.path.join(td, 'ev2'), me_path=VPATH), '不同')
        ok('tampered_remote_look_stops', not msg.startswith(('DID', 'WRONG')), msg[:80])
    V.time.sleep = lambda s: None
    with tempfile.TemporaryDirectory() as td:          # B:登記沒送出 / 送出但還沒收件 / 判定存不進去 → 停;之後重跑 = 照登記重播 → 保存
        X, man, rc, org = remote_fx(td); exp, lpath = man['experiment_id'], man['look_path']; ev = os.path.join(td, 'ev')
        open(REJ + 'astra-ledger', 'w').close(); msg = must_stop(lambda: V.formal_run(X.td, evdir=ev, me_path=VPATH), '開跑登記沒有送到遠端'); os.remove(REJ + 'astra-ledger')
        s0 = remote_state(X.td, exp, lpath); ok('ledger_push_rejected_no_registration', not msg.startswith(('DID', 'WRONG')) and s0['registration'] == [] and s0['look'] == [], msg[:70])
        open(NOREC, 'w').close(); msg = must_stop(lambda: V.formal_run(X.td, evdir=ev, me_path=VPATH, wait_receipt_s=0.2), '還查不到'); os.remove(NOREC)
        s1 = remote_state(X.td, exp, lpath); ok('registration_without_receipt_stops_no_look', not msg.startswith(('DID', 'WRONG')) and len(s1['registration']) == 1 and s1['look'] == [], msg[:70])
        db = json.load(open(DB)); R_reg = s1['registration'][0]
        db['runs']['960000000'] = dict(run_api(960000000, R_reg, '2027-08-02T22:06:00Z'), repository={'full_name': V.OWNER_REPO}); json.dump(db, open(DB, 'w'))
        open(REJ + 'main', 'w').close(); msg = must_stop(lambda: V.formal_run(X.td, evdir=ev, me_path=VPATH), '未持久完成'); os.remove(REJ + 'main')
        s2 = remote_state(X.td, exp, lpath); ok('look_push_rejected_not_persisted', not msg.startswith(('DID', 'WRONG')) and s2['registration'] == [R_reg] and s2['look'] == [], msg[:70])
        look, info = V.formal_run(X.td, evdir=ev, me_path=VPATH); s3 = remote_state(X.td, exp, lpath)
        ok('replay_after_failed_save_persists', info['mode'] == 'REPLAY' and info['status'] == 'PERSISTED' and len(s3['look']) == 1 and look['registration']['remote_received_utc'] == '2027-08-02T22:06:00Z', info)
        push_edit(org, td, 'astra-ledger', V.registration_path(exp), lambda b: b.replace(b'"schema"', b'"note": "edited", "schema"', 1))
        msg = must_stop(lambda: V.formal_run(X.td, evdir=ev, me_path=VPATH), '開跑登記被改過'); ok('tampered_registration_stops', not msg.startswith(('DID', 'WRONG')), msg[:60])
finally:
    V.clock, V.time.sleep = old_clock, old_sleep

# ---- 12. 結案截止的時間反例(Astra v0.7.6 §3):① 截止日早上就判缺漏 ② 截止前算好、截止後才上傳;另驗試跑同語義、收件 run ID
def draft4():
    b = real_show('c72f2f7', 'research/ledger_v3_draft_2026-10-16/v3_verify.py'); assert H(b) == 'e957328e058296d0984ad5f9894e53ac32a94855cad34ac16ecc93f80d43a413'
    p_ = os.path.join(tempfile.mkdtemp(prefix='v3d4_'), 'v3_verify_draft4.py'); open(p_, 'wb').write(b)
    sp_ = importlib.util.spec_from_file_location('v3_verify_draft4', p_); m_ = importlib.util.module_from_spec(sp_); sp_.loader.exec_module(m_); return m_
D4 = draft4()
def cfg_cut(target, msha):          # 收案 1 天(2026-10-14),把截止日調到 target(第 k 個交易日)
    k = len(V.sessions('2026-10-14', target))
    return dict(V.SPEC, start='2026-10-14', cohort_sessions=1, horizon_sessions=k - 11, unresolved_after=10, v2_manifest_sha256=msha)
for name, target, close in (('missing_waits_for_close_half_day', '2026-11-27', '2026-11-27T18:00:00Z'), ('missing_waits_for_close_normal_day', '2026-11-30', '2026-11-30T21:00:00Z')):
    with tempfile.TemporaryDirectory() as td:
        X = Fx(td); X.lock('2026-10-14', [('ADI', SNAP, 'disagree')]); cfg = cfg_cut(target, X.msha); res = {}
        for label, t in (('morning', target + 'T14:00:00Z'), ('one_second_before', V.ts(V.P(close) - dt.timedelta(seconds=1))), ('at_close', close)):
            pub, cl, mi, *_ = V.collect(X.g, 'astra-ledger', 'main', cfg, target, V.P(t), X.store())
            res[label] = (pub['status'], len(cl), len(mi), pub['counts']['pending'])
        po, clo, mio, *_ = D4.collect(X.g, 'astra-ledger', 'main', cfg, target, V.P(target + 'T14:00:00Z'), X.store())
        res['draft4_morning'] = (po['status'], len(clo), len(mio), po['counts']['pending'])
        ok(name, pub['cohort']['resolve_by'] == target and res['morning'] == res['one_second_before'] == ('MATURING', 0, 0, 1) and res['at_close'] == ('READY', 0, 1, 0)
           and res['draft4_morning'] == ('READY', 0, 1, 0), res)
with tempfile.TemporaryDirectory() as td:          # 截止視圖:截止前 1 秒算好、截止後 2 秒才收件 → 不算;任何更晚的 head 選出同一個視圖;準時收件 → 算
    X = Fx(td); lc, rc = X.lock('2026-10-14', [('ADI', SNAP, REAL['v'])]); H0 = GIT(td, 'rev-parse', 'HEAD')
    cut = V.close_utc(V.add_sessions(V.add_sessions('2026-10-14', 120), 52))
    WR(td, 'scores.json', json.dumps({'marks': {REAL['id']: dict(rec, closed_utc=V.ts(cut - dt.timedelta(seconds=1)))}}).encode()); S1 = COMMIT(td, 'score: closed 1 s before cutoff')
    fake_db(run_api(rc['run_id'], lc, rc['remote_received_utc']), run_api(9000, H0, '2026-10-15T06:00:00Z'), run_api(9001, S1, V.ts(cut + dt.timedelta(seconds=2))))
    def classify(view, evd):
        cfg = dict(V.SPEC, start='2026-10-14', v2_manifest_sha256=X.msha)
        pub, cl, mi, *_ = V.collect(X.g, view, 'main', cfg, cut.astimezone(V.ET).date().isoformat(), cut, V.Evidence(os.path.join(td, evd), online=True))
        return pub['status'], [k_[2] for k_ in cl], [k_[2] for k_ in mi]
    v1 = V.cutoff_view(X.g, S1, cut, V.Evidence(os.path.join(td, 'e1'), online=True)); c1 = classify(v1[0], 'e2')
    WR(td, 'notes.txt', b'later'); S2 = COMMIT(td, 'later commit')
    def add_run(i, head, t):
        db = json.load(open(DB)); db['runs'][str(i)] = dict(run_api(i, head, t), repository={'full_name': V.OWNER_REPO}, status='completed', conclusion='success'); json.dump(db, open(DB, 'w'))
    add_run(9002, S2, '2027-07-21T05:00:00Z'); v2 = V.cutoff_view(X.g, S2, cut, V.Evidence(os.path.join(td, 'e3'), online=True))
    ok('late_upload_excluded_even_with_old_local_time', v1 == (H0, '2026-10-15T06:00:00Z') and c1 == ('READY', [], ['ADI']), {'view': v1, 'class': c1})
    ok('same_cutoff_view_from_later_head', v2 == v1 and classify(v2[0], 'e4') == c1, {'v2': v2})
    cfgD = dict(V.SPEC, start='2026-10-14', v2_manifest_sha256=X.msha)        # 試跑和正式同一個截止語義(草案 5 補)
    def dry(t, analyze, evd):
        return V.dry_collect(X.g, S2, 'main', cfgD, t.astimezone(V.ET).date().isoformat(), t, V.Evidence(os.path.join(td, evd), online=True), analyze)
    pd_, cld, mid, *_ = dry(cut + dt.timedelta(hours=25), True, 'd1')
    ok('dry_run_after_settle_uses_cutoff_view', pd_['cutoff_view'] == {'commit': H0, 'received_utc': '2026-10-15T06:00:00Z', 'receipt_run_id': 9000}
       and pd_['status'] == 'READY' and [k_[2] for k_ in cld] == [] and [k_[2] for k_ in mid] == ['ADI'], pd_['cutoff_view'])
    pw, clw, miw, *_ = dry(cut + dt.timedelta(hours=1), False, 'd2'); msg = must_stop(lambda: dry(cut + dt.timedelta(hours=1), True, 'd3'), '還沒定案')
    ok('dry_run_within_settle_window_counts_only', not msg.startswith(('DID', 'WRONG')) and 'cutoff_view' not in pw and '只供參考' in pw.get('note', '') and len(clw) == 1,
       {'analyze_stop': msg[:50], 'status_closed_by_local_time': len(clw), 'note': pw.get('note', '')[:36]})
    pe, cle, mie, *_ = V.collect(X.g, S1, 'main', cfgD, cut.astimezone(V.ET).date().isoformat(), cut - dt.timedelta(seconds=1), V.Evidence(os.path.join(td, 'd4'), online=True))
    ok('early_ready_labeled_info_only', pe['status'] == 'READY' and len(cle) == 1 and '提早資訊' in pe.get('note', '') and pe['cohort']['formal_earliest_utc'] == V.ts(cut + dt.timedelta(hours=24)),
       {'status': pe['status'], 'note': pe.get('note', '')[:30], 'formal_earliest_utc': pe['cohort']['formal_earliest_utc']})
    good_db = open(DB).read(); open(DB, 'w').write('{broken')          # 選截止視圖時 GitHub API 查詢失敗(假 gh 讀不到資料 → 非 0 結束)→ 停,不當缺漏
    m1 = must_stop(lambda: V.dry_collect(X.g, S2, 'main', cfgD, '2027-06-23', cut + dt.timedelta(hours=25), V.Evidence(os.path.join(td, 'd5'), online=True), True), '查不到')
    m2 = must_stop(lambda: V.cutoff_view(X.g, S2, cut, V.Evidence(os.path.join(td, 'd6'), online=True, strict=True)), 'GitHub API 查詢失敗')
    open(DB, 'w').write(good_db)
    ok('cutoff_view_api_failure_stops_not_missing', not m1.startswith(('DID', 'WRONG')) and not m2.startswith(('DID', 'WRONG')), {'dry_run': m1[:60], 'formal': m2[:60]})
    # §3.2 反例在草案 4 原碼上:同一份資料(截止前 1 秒的本機時間、截止後 2 秒才到 GitHub),截止 + 25 小時判 → 草案 4 照收、草案 5 不算
    p4, cl4, mi4, *_ = D4.collect(X.g, S2, 'main', cfgD, '2027-06-22', cut + dt.timedelta(hours=25), V.Evidence(os.path.join(td, 'd7'), online=True))
    ok('draft4_counts_late_upload_draft5_does_not', [k_[2] for k_ in cl4] == ['ADI'] and not mi4 and not cld and [k_[2] for k_ in mid] == ['ADI'],
       {'draft4_latest_ledger': {'closed': [k_[2] for k_ in cl4], 'missing': [k_[2] for k_ in mi4]}, 'draft5_cutoff_view': {'closed': [k_[2] for k_ in cld], 'missing': [k_[2] for k_ in mid]}})
    add_run(9001, S1, V.ts(cut - dt.timedelta(minutes=15))); v3 = V.cutoff_view(X.g, S2, cut, V.Evidence(os.path.join(td, 'e5'), online=True))
    ok('on_time_upload_included', v3[0] == S1 and classify(v3[0], 'e6') == ('READY', ['ADI'], []), {'v3': v3})
old_clock = V.clock
try:                                               # 正式入口:截止 + 24 小時前不能登記;截止後才上傳的結果不算、準時的算(和登記時間無關)
    with tempfile.TemporaryDirectory() as td:
        X, man, rc, org = remote_fx(td); V.clock = lambda: V.P('2027-06-22T19:00:00Z')
        msg = must_stop(lambda: V.formal_run(X.td, evdir=os.path.join(td, 'ev'), me_path=VPATH), '還不能判定'); s0 = remote_state(X.td, man['experiment_id'], man['look_path'])
        ok('formal_refuses_before_cutoff_settle', not msg.startswith(('DID', 'WRONG')) and s0['registration'] == [] and s0['look'] == [], msg[:70])
    out = {}
    for label, t_push in (('late', '2027-06-21T20:00:02Z'), ('on_time', '2027-06-21T19:45:00Z')):
        with tempfile.TemporaryDirectory() as td:
            X, man, rc, org = remote_fx(td); open(CLK, 'w').write(t_push)
            body = json.dumps({'marks': {REAL['id']: dict(rec, closed_utc='2027-06-21T19:59:59Z')}}).encode()
            push_edit(org, td, 'astra-ledger', 'scores.json', lambda b: body); open(CLK, 'w').write('2027-08-02T22:05:00Z')
            V.clock = lambda: V.P('2027-08-02T22:00:00Z'); look, info = V.formal_run(X.td, evdir=os.path.join(td, 'ev'), me_path=VPATH)
            rg = look['registration']['record']; run_ = json.load(open(DB))['runs'].get(str(rg['ledger_view_receipt_run_id'])) or {}
            st_ = look['status']; out[label] = {'closed': st_['counts']['closed_reproducible'], 'missing': st_['counts']['missing_or_unreproducible'],
                                                 'view_received': rg['ledger_view_received_utc'], 'status': info['status'], 'view_run_id': rg['ledger_view_receipt_run_id'],
                                                 'run_matches': run_.get('head_sha') == rg['ledger_view_commit'] and run_.get('created_at') == rg['ledger_view_received_utc']}
            if label == 'on_time':          # 登記之後 GitHub 那邊的收件證據變了(同一 commit、同一時間多一筆 run)→ 重播停
                add_run(1, rg['ledger_view_commit'], rg['ledger_view_received_utc'])
                out['receipt_changed_stop'] = must_stop(lambda: V.formal_run(X.td, evdir=os.path.join(td, 'ev_new'), me_path=VPATH), '截止視圖')
    ok('formal_excludes_result_received_after_cutoff', out['late']['closed'] == 0 and out['late']['missing'] == 1 and out['late']['view_received'] == '2026-10-16T06:00:00Z', out['late'])
    ok('formal_includes_result_received_before_cutoff', out['on_time']['closed'] == 1 and out['on_time']['missing'] == 0 and out['on_time']['view_received'] == '2027-06-21T19:45:00Z', out['on_time'])
    ok('registration_records_view_receipt_run_id', out['late']['run_matches'] and out['on_time']['run_matches'], {k: out[k]['view_run_id'] for k in ('late', 'on_time')})
    ok('changed_view_receipt_after_registration_stops', not out['receipt_changed_stop'].startswith(('DID', 'WRONG')), out['receipt_changed_stop'][:70])
finally:
    V.clock = old_clock

json.dump({'tests': len(R), 'all_pass': True, 'verifier_sha256': H(open(os.path.join(HERE, 'v3_verify.py'), 'rb').read()), 'results': R},
          open(os.path.join(HERE, 'v3_tests_result.json'), 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps({'tests': len(R), 'all_pass': True}, ensure_ascii=False))
