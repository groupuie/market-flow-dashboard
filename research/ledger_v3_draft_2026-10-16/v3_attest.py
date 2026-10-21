#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪 盤感測試 v3:長期收件證據 PoC(Claude 2026-10-21;回應 Astra v0.7.7 §四、§五)— 隔離測試分支,不是正式流程

政策 甲1(Astra v0.7.7 §4.3):收件時間 = **經核驗的 Sigstore 簽證時間 t_signed**(不是 GitHub run 的 created_at,也不是本機時間)
  - 每次 push 到被保全的分支 → 事先釘住的 workflow 對那次 push 的確切 commit 做收件清單(manifest)並簽章(GitHub OIDC + Sigstore)
    → manifest 原位元組 + 完整 bundle 存進證據分支,一個 commit 只新增一筆;manifest 記上一個證據 commit(evidence_parent)→ 一條鏈
  - 驗證完全離線:不用 GitHub API、不用本機快取;只用證據分支的檔、事先釘住的信任根(sigstore/root-signing 的版本,
    不是 workflow 自己存的那份)、事先釘住版本的 gh(sigstore-go);gh 在沒有網路的命名空間(unshare -rn)裡跑
  - gh 通過之後,再自己逐項核對:被簽的 subject = manifest 位元組、predicate = manifest、憑證(直接解析 Fulcio 擴充欄位,不靠 gh 的輸出)
    的 repo 名稱 / 數字 ID / 分支 / commit / workflow / 觸發事件 / run ID / 執行環境、workflow 檔內容 = 釘住的位元組、
    tlog 時間 = gh 核驗過的時間
  - 封存(seal):截止 C 的結果要在封存期限 D(政策:C + 24 小時,不是 GitHub 的保證)前封定 →
    封定的證據 = 鏈上「第一筆簽證時間晚於 D 的紀錄」之前的全部紀錄;還沒有這一筆 → 停(不能判定)
    → 第一次分析哪天做、之後才補進來的證據,都不改變封定的集合
  - 證據缺失、改過一個 byte、身分不符、鏈接錯、時間不遞增、信任根互相矛盾 → 停(Stop),不當成缺漏交易
用法:python3 -I v3_attest.py <證據分支的 git 目錄> <ref> <被保全分支的 git 目錄>(列出整條鏈的核驗結果)
"""
import base64, datetime as dt, hashlib, json, os, re, subprocess, sys, tempfile
from cryptography import x509

HERE = os.path.dirname(os.path.abspath(__file__))
TRUSTED_ROOT = os.path.join(HERE, 'attest_poc', 'trusted_root.public-good.sigstore-root-signing-f138b50.json')
TRUSTED_ROOT_SHA256 = '6494e21ea73fa7ee769f85f57d5a3e6a08725eae1e38c755fc3517c9e6bc0b66'   # sigstore/root-signing f138b503 targets/trusted_root.json
GH_VERSION = 'gh version 2.89.0 (2026-03-26)'
POLICY_POC = {'repository': 'groupuie/market-flow-dashboard', 'repository_id': '1305425368', 'ref': 'refs/heads/attest-poc', 'event': 'push',
              'workflow_path': '.github/workflows/attest-poc.yml',
              'workflow_sha256': 'c81e71fa319aa739d9a91abe0bed8c930df4d2840e36c8d47229546bb3f93d91',
              'predicate_type': 'https://github.com/groupuie/market-flow-dashboard/attest-poc/receipt/v1',
              'issuer': 'https://token.actions.githubusercontent.com', 'manifest_schema': 'ledger-attest-manifest-1'}
FULCIO = {'1.3.6.1.4.1.57264.1.8': 'issuer', '1.3.6.1.4.1.57264.1.9': 'buildSignerURI', '1.3.6.1.4.1.57264.1.10': 'buildSignerDigest',
          '1.3.6.1.4.1.57264.1.11': 'runnerEnvironment', '1.3.6.1.4.1.57264.1.12': 'sourceRepositoryURI',
          '1.3.6.1.4.1.57264.1.13': 'sourceRepositoryDigest', '1.3.6.1.4.1.57264.1.14': 'sourceRepositoryRef',
          '1.3.6.1.4.1.57264.1.15': 'sourceRepositoryIdentifier', '1.3.6.1.4.1.57264.1.20': 'buildTrigger',
          '1.3.6.1.4.1.57264.1.21': 'runInvocationURI'}
UTC = dt.timezone.utc


class Stop(Exception):
    """證據缺失 / 矛盾 / 不符 → 停(流程故障或證據不成立;不當成研究缺漏)"""


def sha(b): return hashlib.sha256(b).hexdigest()
def P(s): return dt.datetime.fromisoformat(str(s).replace('Z', '+00:00')).astimezone(UTC)
def ts(t): return t.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')


def git(repo, *a, binary=False):
    r = subprocess.run(['git', '-C', repo, *a], capture_output=True)
    if r.returncode != 0: raise Stop(f'git {" ".join(a[:3])} 失敗:{r.stderr.decode()[:160]}')
    return r.stdout if binary else r.stdout.decode().strip()


def is_ancestor(repo, a, b):
    return subprocess.run(['git', '-C', repo, 'merge-base', '--is-ancestor', a, b], capture_output=True).returncode == 0


def der_utf8(b):
    """Fulcio v2 擴充欄位的值 = DER UTF8String(tag 0x0c)"""
    if len(b) < 2 or b[0] != 0x0c: raise Stop('憑證擴充欄位格式不對')
    n, o = b[1], 2
    if n & 0x80: k = n & 0x7f; n, o = int.from_bytes(b[2:2 + k], 'big'), 2 + k
    return b[o:o + n].decode()


def cert_fields(bundle):
    """不靠 gh:直接解析 bundle 裡的 Fulcio 憑證,取出身分欄位(和 gh 的輸出互相核對)"""
    der = base64.b64decode(bundle['verificationMaterial']['certificate']['rawBytes'])
    out = {}
    for e in x509.load_der_x509_certificate(der).extensions:
        k = FULCIO.get(e.oid.dotted_string)
        if k: out[k] = der_utf8(e.value.value)
    return out


def trusted_root_jsonl():
    b = open(TRUSTED_ROOT, 'rb').read()
    if sha(b) != TRUSTED_ROOT_SHA256: raise Stop('釘住的信任根檔案指紋不對')
    p = os.path.join(tempfile.mkdtemp(prefix='v3tr_'), 'trusted_root.jsonl')
    open(p, 'w').write(json.dumps(json.loads(b), separators=(',', ':')) + '\n')
    return p


def gh_verify(mpath, bpath, head, pol, root_jsonl, offline=True):
    """官方 CLI(sigstore-go)完整核驗:憑證鏈 / 身分 / 簽章 / 透明紀錄 / 時間;不能連網(unshare -rn)、沒有快取(新的設定目錄)"""
    v = subprocess.run(['gh', '--version'], capture_output=True, text=True).stdout.splitlines()[:1]
    if v != [GH_VERSION]: raise Stop(f'gh 版本不是釘住的 {GH_VERSION}:{v}')
    cmd = ['gh', 'attestation', 'verify', mpath, '--bundle', bpath, '--custom-trusted-root', root_jsonl, '-R', pol['repository'],
           '--signer-workflow', f"{pol['repository']}/{pol['workflow_path']}", '--source-ref', pol['ref'], '--source-digest', head,
           '--signer-digest', head, '--cert-oidc-issuer', pol['issuer'], '--deny-self-hosted-runners',
           '--predicate-type', pol['predicate_type'], '--format', 'json']
    env = dict(os.environ, GH_CONFIG_DIR=tempfile.mkdtemp(prefix='v3gh_'), XDG_CACHE_HOME=tempfile.mkdtemp(prefix='v3cache_'), GH_TOKEN='offline-no-token')
    r = subprocess.run((['unshare', '-rn'] if offline else []) + cmd, capture_output=True, text=True, env=env)
    if r.returncode != 0: raise Stop(f'Sigstore 核驗不通過:{(r.stderr or r.stdout).strip()[:400]}')
    return json.loads(r.stdout)


def verify_record(mbytes, bbytes, mname, pol=POLICY_POC, ledger=None, root_jsonl=None, offline=True):
    """一筆收件證據 → 核驗過的紀錄 {head, t, ...};任何一項不符 → Stop"""
    m_ = re.fullmatch(r'(\d{6})_([0-9a-f]{40})\.manifest\.json', mname)
    if not m_: raise Stop(f'manifest 檔名不對:{mname}')
    head = m_.group(2)
    try: m, b = json.loads(mbytes), json.loads(bbytes)
    except ValueError: raise Stop('manifest 或 bundle 不是 JSON')
    # 1. 自己先查(不做密碼學,只為了講清楚是哪裡不對;真正的核驗在第 2 步):簽住的內容、類型、身分、有沒有時間證據
    try: st0 = json.loads(base64.b64decode(b['dsseEnvelope']['payload']))
    except Exception: raise Stop('bundle 裡沒有可讀的簽章內容(DSSE)')
    if st0.get('subject') != [{'name': mname, 'digest': {'sha256': sha(mbytes)}}]: raise Stop('manifest 和簽住的 subject(檔名 / 指紋)不同 → 改過或不是這一份')
    if st0.get('predicateType') != pol['predicate_type']: raise Stop('predicate 類型不是釘住的')
    vm = b.get('verificationMaterial') or {}
    if not (vm.get('tlogEntries') or (vm.get('timestampVerificationData') or {}).get('rfc3161Timestamps')): raise Stop('bundle 沒有時間證據(透明紀錄 / 時間戳記)')
    cf = cert_fields(b)
    want_c = {'issuer': pol['issuer'], 'sourceRepositoryURI': f"https://github.com/{pol['repository']}", 'sourceRepositoryIdentifier': pol['repository_id'],
              'sourceRepositoryRef': pol['ref'], 'sourceRepositoryDigest': head, 'buildTrigger': pol['event'],
              'buildSignerURI': f"https://github.com/{pol['repository']}/{pol['workflow_path']}@{pol['ref']}", 'buildSignerDigest': head,
              'runnerEnvironment': 'github-hosted',
              'runInvocationURI': f"https://github.com/{pol['repository']}/actions/runs/{m.get('run_id')}/attempts/{m.get('run_attempt')}"}
    bad = [k for k, v in want_c.items() if cf.get(k) != v]
    if bad: raise Stop(f'憑證身分欄位不符:{bad}')
    # 2. 官方 CLI 完整核驗(憑證鏈、簽章、透明紀錄、時間;身分也再由 gh 檢查一次)
    d = tempfile.mkdtemp(prefix='v3att_'); mp, bp = os.path.join(d, mname), os.path.join(d, 'bundle.json')
    open(mp, 'wb').write(mbytes); open(bp, 'wb').write(bbytes)
    out = gh_verify(mp, bp, head, pol, root_jsonl or trusted_root_jsonl(), offline)
    if len(out) != 1: raise Stop('核驗結果不是剛好一筆')
    # 3. 核驗之後再對一次:gh 讀到的內容 = 自己讀到的;manifest 欄位;workflow 位元組;時間
    vr = out[0]['verificationResult']; st = vr['statement']
    if st.get('subject') != st0['subject'] or st.get('predicate') != m: raise Stop('gh 核驗的內容和 manifest 不同')
    want_m = {'schema': pol['manifest_schema'], 'repository': pol['repository'], 'repository_id': pol['repository_id'], 'ref': pol['ref'],
              'event': pol['event'], 'head_sha': head, 'workflow_ref': f"{pol['repository']}/{pol['workflow_path']}@{pol['ref']}", 'seq': int(m_.group(1))}
    bad = [k for k, v in want_m.items() if m.get(k) != v]
    if bad: raise Stop(f'manifest 欄位不符:{bad}')
    gc = vr['signature']['certificate']
    if any(gc.get(k) != v for k, v in want_c.items()): raise Stop('gh 讀到的憑證身分和直接解析的不同')
    if ledger is not None:
        wf = git(ledger, 'show', f"{head}:{pol['workflow_path']}", binary=True)
        if sha(wf) != pol['workflow_sha256']: raise Stop('簽章的 workflow 不是釘住的版本')
    tl = [t for t in vr.get('verifiedTimestamps') or []]
    if not tl: raise Stop('沒有經核驗的時間證據')
    t = max(P(x['timestamp']) for x in tl)                       # 多個可信時間 → 取最晚(偏嚴)
    it = [int(e['integratedTime']) for e in b['verificationMaterial'].get('tlogEntries') or [] if e.get('integratedTime')]
    if any(x['type'] == 'Tlog' for x in tl) and not any(abs(P(x['timestamp']).timestamp() - i) < 1 for x in tl for i in it):
        raise Stop('bundle 的 tlog 時間和核驗過的時間對不上')
    return {'head': head, 'seq': m['seq'], 't': t, 'time_evidence': [{'type': x['type'], 'uri': x['uri'], 'utc': ts(P(x['timestamp']))} for x in tl],
            'before': m['before_sha'], 'evidence_parent': m['evidence_parent'], 'run': f"{m['run_id']}/{m['run_attempt']}",
            'manifest_sha256': sha(mbytes), 'bundle_sha256': sha(bbytes)}


def trust_snapshot_consistent(snap_bytes):
    """workflow 存的信任根快照(不採信)要和釘住的版本一致:釘住版本的 Rekor 金鑰與 Fulcio 根憑證都要在快照裡;不一致 = 來源矛盾 → 停"""
    pin = json.load(open(TRUSTED_ROOT)); lines = [json.loads(l) for l in snap_bytes.decode().splitlines() if l.strip()]
    keys = {t['logId']['keyId'] for r in lines for t in r.get('tlogs', [])}
    cas = {c['certChain']['certificates'][-1]['rawBytes'] for r in lines for c in r.get('certificateAuthorities', [])}
    if not {t['logId']['keyId'] for t in pin['tlogs']} <= keys or not {c['certChain']['certificates'][-1]['rawBytes'] for c in pin['certificateAuthorities']} <= cas:
        raise Stop('workflow 存的信任根快照和釘住的 sigstore 信任根不一致 → 來源矛盾')


def load_chain(ev, ref, pol=POLICY_POC, ledger=None, verify=None, offline=True):
    """證據分支 → 依序核驗過的紀錄;規則:每個證據 commit 只「新增」一筆 manifest + bundle(可另加 trust/ 快照),
    序號連續、manifest 的 evidence_parent = 這個 commit 的上一個 commit、簽證時間嚴格遞增;不是 merge"""
    if verify is None:                                  # 預設 = 真的 Sigstore 核驗(測試可以換成假的,只測鏈的規則)
        root = trusted_root_jsonl()
        verify = lambda mb, bb, mn: verify_record(mb, bb, mn, pol, ledger, root, offline)
    commits = git(ev, 'rev-list', '--first-parent', '--reverse', ref).split()
    if not commits: raise Stop('證據分支是空的')
    if git(ev, 'ls-tree', '-r', '--name-only', commits[0]).split() != ['README.md']: raise Stop('證據分支的起點不是只有說明檔')
    recs = []
    for i, c in enumerate(commits[1:], 1):
        parents = git(ev, 'rev-list', '--parents', '-n', '1', c).split()[1:]
        if parents != [commits[i - 1]]: raise Stop(f'證據 commit {c[:10]} 不是接在上一個證據 commit 後面(或是 merge)')
        rows = [l.split('\t') for l in git(ev, 'diff-tree', '--no-commit-id', '--name-status', '-r', commits[i - 1], c).splitlines()]
        if any(r_[0] != 'A' for r_ in rows): raise Stop(f'證據 commit {c[:10]} 改了或刪了既有的檔(只能新增)')
        added = [r_[1] for r_ in rows]; att = sorted(p for p in added if p.startswith('att/')); other = [p for p in added if not p.startswith(('att/', 'trust/'))]
        mn = [p for p in att if p.endswith('.manifest.json')]
        if other or len(att) != 2 or len(mn) != 1: raise Stop(f'證據 commit {c[:10]} 不是剛好新增一筆 manifest + bundle')
        name = mn[0][4:]; seq = int(name[:6])
        if att != sorted([mn[0], 'att/' + name.replace('.manifest.json', '.bundle.json')]) or seq != i: raise Stop(f'證據 commit {c[:10]} 的序號或檔名不對')
        for p in added:
            if p.startswith('trust/'): trust_snapshot_consistent(git(ev, 'show', f'{c}:{p}', binary=True))
        rec = verify(git(ev, 'show', f'{c}:{mn[0]}', binary=True), git(ev, 'show', f"{c}:att/{name.replace('.manifest.json', '.bundle.json')}", binary=True), name)
        if rec['evidence_parent'] != commits[i - 1]: raise Stop(f'第 {seq} 筆簽住的上一個證據 commit 和實際的不同 → 鏈被改過或晚補')
        if recs and rec['t'] <= recs[-1]['t']: raise Stop(f'第 {seq} 筆的簽證時間沒有晚於上一筆 → 矛盾')
        recs.append(dict(rec, evidence_commit=c))
    return recs


def seal(recs, D):
    """封存期限 D:封定的證據 = 第一筆簽證時間晚於 D 的紀錄之前的全部;那一筆 = 封存證明。還沒有 → 停"""
    for k, r in enumerate(recs):
        if r['t'] > D: return recs[:k], r
    raise Stop(f'證據鏈還沒有 {ts(D)} 之後的紀錄(封存證明)→ 還不能判定')


def received_by(ledger, x, recs):
    """被保全分支的 commit x 最晚什麼時候已在 GitHub:所有「head 是 x 或 x 的後代」的紀錄裡,簽證時間最早的那筆(一起 push 的中間 commit 也算到)"""
    hits = [r for r in recs if r['head'] == x or is_ancestor(ledger, x, r['head'])]
    return min(hits, key=lambda r: r['t']) if hits else None


def view_at(ledger, head, C, recs):
    """截止視圖(甲1):沿第一父鏈往回,第一個「自己有紀錄、簽證時間 ≤ C」的 commit"""
    own = {r['head']: r for r in recs if r['t'] <= C}
    for c in git(ledger, 'rev-list', '--first-parent', head).split():
        if c in own: return c, own[c]
    raise Stop('截止前沒有任何收件證據')


if __name__ == '__main__':
    ev, ref, led = sys.argv[1:4]
    for r in load_chain(ev, ref, ledger=led):
        print(json.dumps(dict(r, t=ts(r['t'])), ensure_ascii=False))
