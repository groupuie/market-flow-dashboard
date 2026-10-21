#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3 收件證據 PoC 的測試(Claude 2026-10-21;Astra v0.7.7 §4、§五、附錄三 §6 的驗收清單)
真的 Sigstore 證據:attest_poc/attest_poc.gitbundle(GitHub 上 attest-poc / attest-poc-evidence 兩個隔離測試分支的原 git 物件,3 次真的簽章)
→ 每次都從 bundle 重新 clone 到空資料夾(沒有本機快取)、gh 在沒有網路的命名空間跑、不用 GitHub API
鏈的規則另用假的核驗函式 + 真的 git 操作測(晚補、改檔、時間倒退、分析拖晚)
用法:python3 -I v3_attest_tests.py → v3_attest_result.json"""
import copy, datetime as dt, hashlib, json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import v3_attest as A

R = []
def ok(name, cond, proof=None):
    R.append({'name': name, 'pass': bool(cond), 'proof': proof}); print(('PASS ' if cond else 'FAIL ') + name, flush=True)
    if not cond: raise SystemExit(f'FAIL {name}: {proof}')
def stops(fn, want=''):
    try: fn(); return 'DID NOT STOP'
    except A.Stop as e: return str(e) if want in str(e) else 'WRONG STOP: ' + str(e)[:120]
def good(msg): return not msg.startswith(('DID', 'WRONG'))
S = lambda x: dt.timedelta(seconds=x)

# ---- 真的證據:從 git bundle 重新 clone(空資料夾、沒有快取)
TD = tempfile.mkdtemp(prefix='v3attest_'); G = os.path.join(TD, 'poc.git')
subprocess.run(['git', 'clone', '-q', '--mirror', os.path.join(HERE, 'attest_poc', 'attest_poc.gitbundle'), G], check=True)
EV = 'refs/heads/attest-poc-evidence'; P4 = A.git(G, 'rev-parse', 'refs/heads/attest-poc')
P1, P2, P3 = A.git(G, 'rev-list', '--reverse', P4).split()[:3]
recs = A.load_chain(G, EV, ledger=G)
T1, T2, T3 = (r['t'] for r in recs)
ok('offline_chain_verifies_all_three', [r['head'] for r in recs] == [P1, P3, P4] and T1 < T2 < T3 and all(r['time_evidence'][0]['type'] == 'Tlog' for r in recs),
   {'records': [{'seq': r['seq'], 'head': r['head'][:10], 't': A.ts(r['t']), 'run': r['run'], 'time': r['time_evidence']} for r in recs],
    'setup': '從 git bundle 重新 clone;gh 新的設定與快取資料夾、假 token;unshare -rn(沒有網路);不用 GitHub API'})
net = subprocess.run(['unshare', '-rn', 'python3', '-c', "import socket; socket.create_connection(('140.82.112.3', 443), timeout=5)"], capture_output=True, text=True)
ok('sandbox_has_no_network', net.returncode != 0, (net.stderr.strip().splitlines() or ['?'])[-1][:100])

# ---- 拒收:每一項都要停(用第 1 筆的原位元組)
c1 = recs[0]['evidence_commit']; mn = f'000001_{P1}.manifest.json'
MB = A.git(G, 'show', f'{c1}:att/{mn}', binary=True); BB = A.git(G, 'show', f"{c1}:att/{mn.replace('.manifest.json', '.bundle.json')}", binary=True)
def rec_with(pol_change=None, mb=MB, bb=BB, name=mn, root=None):
    pol = dict(A.POLICY_POC, **(pol_change or {})); return lambda: A.verify_record(mb, bb, name, pol, G, root)
ok('original_record_verifies', A.verify_record(MB, BB, mn, A.POLICY_POC, G)['t'] == T1, A.ts(T1))
ROOT = A.trusted_root_jsonl()
def gh_only(pol_change=None, mb=MB, bb=BB, name=mn, root=None):          # 只跑密碼學那一層(官方 CLI),看它自己會不會拒收
    d_ = tempfile.mkdtemp(prefix='v3gh1_'); mp, bp = os.path.join(d_, name), os.path.join(d_, 'b.json'); open(mp, 'wb').write(mb); open(bp, 'wb').write(bb)
    return lambda: A.gh_verify(mp, bp, name[7:47], dict(A.POLICY_POC, **(pol_change or {})), root or ROOT)
def both(tname, want, **kw):                                            # 兩層都要拒收;want = 我們自己那層的原因
    m1 = stops(rec_with(**kw), want); m2 = stops(gh_only(**kw), 'Sigstore 核驗不通過'); ok(tname, good(m1) and good(m2), {'ours': m1[:110], 'gh': m2[:160]})
both('wrong_repo_rejected', '憑證身分欄位不符', pol_change={'repository': 'groupuie/other-repo'})
both('wrong_workflow_rejected', '憑證身分欄位不符', pol_change={'workflow_path': '.github/workflows/ledger-receipt.yml'})
both('wrong_branch_rejected', '憑證身分欄位不符', pol_change={'ref': 'refs/heads/astra-ledger'})
both('wrong_predicate_type_rejected', 'predicate 類型', pol_change={'predicate_type': 'https://example.com/other/v1'})
both('wrong_commit_rejected', 'subject', name=f'000001_{P2}.manifest.json')
i = MB.index(b'"tree_sha":"') + 12; mb2 = MB[:i] + (b'0' if MB[i:i + 1] != b'0' else b'1') + MB[i + 1:]
both('manifest_one_byte_changed_rejected', '改過', mb=mb2)
b0 = json.loads(BB); b0['verificationMaterial']['tlogEntries'] = []
both('missing_time_evidence_rejected', '沒有時間證據', bb=json.dumps(b0).encode())
m_ = stops(rec_with({'repository_id': '1305425369'}), 'sourceRepositoryIdentifier'); ok('wrong_repo_id_rejected', good(m_), {'ours': m_[:110], 'gh': 'gh 沒有數字 repo ID 的選項 → 只有我們這層會擋(憑證欄位 1.3.6.1.4.1.57264.1.15)'})
m_ = stops(rec_with({'workflow_sha256': '0' * 64}), '釘住'); ok('unpinned_workflow_bytes_rejected', good(m_), m_[:110])
b1 = json.loads(BB); s0 = b1['dsseEnvelope']['signatures'][0]['sig']; k = len(s0) // 2
b1['dsseEnvelope']['signatures'][0]['sig'] = s0[:k] + ('A' if s0[k] != 'A' else 'B') + s0[k + 1:]
m_ = stops(rec_with(bb=json.dumps(b1).encode()), 'Sigstore 核驗不通過')
ok('bundle_signature_one_byte_changed_rejected', good(m_), {'msg': m_[:110], 'note': '簽章只有密碼學那層能驗;同樣設定的原檔通過(original_record_verifies),差別只在這 1 個字元'})
tr = json.load(open(A.TRUSTED_ROOT)); tr['tlogs'] = [t for t in tr['tlogs'] if t['baseUrl'] != 'https://rekor.sigstore.dev']
p_ = os.path.join(TD, 'wrong_root.jsonl'); open(p_, 'w').write(json.dumps(tr) + '\n')
m_ = stops(rec_with(root=p_), 'Sigstore 核驗不通過'); ok('wrong_trust_root_rejected', good(m_), {'msg': m_[:110], 'note': '信任根拿掉 rekor.sigstore.dev 的金鑰 → 透明紀錄驗不過'})
snap = A.git(G, 'show', f"{c1}:{[p for p in A.git(G, 'ls-tree', '-r', '--name-only', c1).split() if p.startswith('trust/')][0]}", binary=True)
A.trust_snapshot_consistent(snap)
bad_snap = b'\n'.join(json.dumps(dict(json.loads(l), tlogs=[])).encode() for l in snap.splitlines() if l.strip())
m_ = stops(lambda: A.trust_snapshot_consistent(bad_snap), '矛盾'); ok('runner_trust_snapshot_checked_against_pinned_root', good(m_), m_[:80])

# ---- 甲1 的時間規則(真的簽證時間;截止前後 1 秒)
ok('view_boundary_one_second', A.view_at(G, P4, T1, recs)[0] == P1 and good(stops(lambda: A.view_at(G, P4, T1 - S(1), recs), '截止前')), {'C=T1': 'P1 收', 'C=T1-1s': '停(截止前沒有收件證據)'})
lock = lambda x, deadline: (A.received_by(G, x, recs) or {'t': None})['t'] is not None and A.received_by(G, x, recs)['t'] < deadline   # 批次 / 錨點:要早於截止
ok('deadline_boundary_one_second', lock(P1, T1 + S(1)) and not lock(P1, T1), {'deadline=T1+1s': '準時', 'deadline=T1': '晚了(簽證時間不早於截止)'})
ok('intermediate_commit_covered_by_push_head', A.received_by(G, P2, recs)['head'] == P3 and A.received_by(G, P2, recs)['t'] == T2 and A.received_by(G, P1, recs)['t'] == T1,
   {'P2(中間 commit)': f'由第 2 筆(head {P3[:10]})證明,{A.ts(T2)}'})
ok('signed_after_cutoff_not_backfilled', A.view_at(G, P4, T2 - S(1), recs)[0] == P1 and A.received_by(G, P3, recs)['t'] > T2 - S(1),
   {'C=T2-1s': '截止視圖退回 P1;P3 的內容不算準時(簽證晚於截止,不回填)'})
# ---- 封存:第一筆晚於 D 的紀錄封定之前的全部
s_a = A.seal(recs, T1 + S(1)); s_b = A.seal(recs, T2 + S(1))
ok('seal_fixed_by_first_record_after_D', [r['seq'] for r in s_a[0]] == [1] and s_a[1]['seq'] == 2 and [r['seq'] for r in s_b[0]] == [1, 2] and s_b[1]['seq'] == 3
   and good(stops(lambda: A.seal(recs, T3), '封存證明')), {'D 在第 1、2 筆之間': '封定 [1],封存證明 = 第 2 筆', 'D 在第 2、3 筆之間': '封定 [1, 2],封存證明 = 第 3 筆', 'D ≥ 第 3 筆': '停'})
# ---- 五個地方同一套證據(真的鏈;C、D 縮成秒,正式是 C + 24 小時)
C = T2 + S(20); D = C + S(20); sealed, proof = A.seal(recs, D)
five = {'anchor(P1,截止 T1+60s)': lock(P1, T1 + S(60)), 'lock(P3,截止 T2+60s)': A.received_by(G, P3, sealed)['t'] < T2 + S(60),
        'no_signals_prep(P2,截止 T2+60s,一起 push)': A.received_by(G, P2, sealed)['t'] < T2 + S(60),
        'cutoff_view(C)': A.view_at(G, P4, C, sealed)[0] == P3, 'registration(P4,D 之後)': proof['head'] == P4 and proof['t'] > D}
ok('five_places_same_evidence', all(five.values()), five)

# ---- 鏈的規則(假的核驗函式 + 真的 git):晚補、改檔、時間倒退、分析拖晚
BASE = dt.datetime(2027, 6, 21, 20, 0, tzinfo=A.UTC)
def fake(mb, bb, mn):
    m = json.loads(mb); return {'head': mn[7:47], 'seq': m['seq'], 't': BASE + S(m['fake_t']), 'evidence_parent': m['evidence_parent'], 'before': '0' * 40, 'run': 'x', 'time_evidence': []}
def synth(times):
    d = tempfile.mkdtemp(prefix='v3chain_'); g = lambda *a: subprocess.run(['git', '-C', d, '-c', 'user.name=t', '-c', 'user.email=t@t', *a], check=True, capture_output=True)
    subprocess.run(['git', 'init', '-q', '-b', 'ev', d], check=True); open(os.path.join(d, 'README.md'), 'w').write('x'); g('add', '-A'); g('commit', '-qm', 'root')
    for i, t in enumerate(times, 1): add(d, i, t)
    return d
def add(d, i, t, parent=None, head=None):
    g = lambda *a: subprocess.run(['git', '-C', d, '-c', 'user.name=t', '-c', 'user.email=t@t', *a], check=True, capture_output=True, text=True).stdout.strip()
    head = head or hashlib.sha1(f'h{i}'.encode()).hexdigest(); os.makedirs(os.path.join(d, 'att'), exist_ok=True)
    open(os.path.join(d, 'att', f'{i:06d}_{head}.manifest.json'), 'w').write(json.dumps({'seq': i, 'fake_t': t, 'evidence_parent': parent or g('rev-parse', 'HEAD')}))
    open(os.path.join(d, 'att', f'{i:06d}_{head}.bundle.json'), 'w').write('{}'); g('add', '-A'); g('commit', '-qm', f'r{i}'); return g('rev-parse', 'HEAD')
d = synth([10, 20, 30]); early = A.load_chain(d, 'ev', verify=fake); e_ref = A.git(d, 'rev-parse', 'ev')
add(d, 4, 40); add(d, 5, 50); late = A.load_chain(d, 'ev', verify=fake); Dx = BASE + S(25)
ok('delayed_first_analysis_same_sealed_set', [r['seq'] for r in A.seal(early, Dx)[0]] == [r['seq'] for r in A.seal(late, Dx)[0]] == [1, 2] and A.seal(early, Dx)[1]['seq'] == A.seal(late, Dx)[1]['seq'] == 3,
   {'第一次分析(鏈只到第 3 筆)': '封定 [1, 2]', '拖晚分析(鏈到第 5 筆)': '封定 [1, 2](同一個)'})
d2 = synth([10, 20, 30]); first = A.git(d2, 'rev-list', '--reverse', 'ev').split()[1]; add(d2, 4, 15, parent=first)      # 晚補:舊時間的證據接到鏈尾,簽住的上一個 commit 對不上
m_ = stops(lambda: A.load_chain(d2, 'ev', verify=fake), '晚補'); ok('late_archived_evidence_rejected', good(m_), m_[:90])
d3 = synth([10, 20]); p = os.path.join(d3, 'att', sorted(os.listdir(os.path.join(d3, 'att')))[0]); open(p, 'a').write(' ')
subprocess.run(['git', '-C', d3, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qam', 'edit'], check=True)
m_ = stops(lambda: A.load_chain(d3, 'ev', verify=fake), '只能新增'); ok('modified_or_deleted_evidence_rejected', good(m_), m_[:90])
d4 = synth([10, 30, 20]); m_ = stops(lambda: A.load_chain(d4, 'ev', verify=fake), '矛盾'); ok('time_not_increasing_rejected', good(m_), m_[:90])
d5 = synth([10]); subprocess.run(['git', '-C', d5, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-q', '--allow-empty', '-m', 'junk'], check=True)
m_ = stops(lambda: A.load_chain(d5, 'ev', verify=fake), '剛好新增一筆'); ok('commit_without_exactly_one_record_rejected', good(m_), m_[:90])

json.dump({'tests': len(R), 'all_pass': all(r['pass'] for r in R), 'attest_module_sha256': A.sha(open(os.path.join(HERE, 'v3_attest.py'), 'rb').read()),
           'gitbundle_sha256': A.sha(open(os.path.join(HERE, 'attest_poc', 'attest_poc.gitbundle'), 'rb').read()), 'gh': A.GH_VERSION, 'results': R},
          open(os.path.join(HERE, 'v3_attest_result.json'), 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps({'tests': len(R), 'all_pass': all(r['pass'] for r in R)}))
