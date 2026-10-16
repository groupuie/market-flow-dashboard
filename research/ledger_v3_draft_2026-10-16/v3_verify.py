#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪 盤感測試 v3 草案 3(2026-10-17,Claude;**未凍結、還沒開始**)— 回應 Astra v0.7.4
草案 2(git a654145)→ 草案 3:
  統計(Astra v0.7.4 §3.1、附錄三)
  - H1 重抽保住「固定的格子目標」:發行人權重從 Poisson(1)(有 37% 是 0,稀疏格子會整格消失、分母跟著變)改成 Exp(1)
    (平均 1、變異 1、永遠 > 0)→ 原本有配對的格子在每一次重抽都還在,格子之間的權重只由日期決定;
    日期從「移動區塊」改成「環狀區塊」(每一天被抽到次數的期望值都剛好 = 1,頭尾不再吃虧)
  - 同一組權重另算 M2(發行人方向一階展開:中心恰好 = 點估計)當對照;正式用 M1 或 M2、區塊長度 L,由事先寫好的校準規則決定(sim4_calibrate.py)
  - H2 三種模式一次算完(decision_by_h2_mode);正式模式只用 manifest 裡使用者選的那一種
  工程(Astra v0.7.4 §5、附錄四)
  - 零訊號批次:找到宣告零訊號的 prep commit;pending 真的是空的、指紋對;沒有判讀檔、沒有鎖定列;之後沒被改;
    GitHub 在截止前收到這個 commit(ledger-receipt run);SPY / QQQ 快照用凍結引擎重算也不是買點 → 才算合格
  - 整批驗收:批次層級 + 每一列 + 跨批 ID + 模型 + 引擎,任何一項不符 → 整批不收;只有整批合格才算覆蓋;拒收筆數與原因逐日列出
  - 收件證據:online 一定重新問 GitHub,已存的檔要和 API 一樣(不一樣 → 不收);離線只接受「指紋寫在 git 裡的釘選表」的檔(--pins REF:PATH)
  - 尺度:重疊的兩根 K 線全部 8 個價格(開高低收)求共同比例的可行區間(含四捨五入半格);沒有共同比例 → 無法重現;
    換尺度之後不再四捨五入;進場以鎖定時為準 — 買點只在原快照(原尺度)上用凍結引擎核對,不因後來重新還原而重新選樣
  - 正式模式:讀 git 裡的 research/ledger_v3/v3_manifest.json(只被一個 commit 寫過)、核對本程式指紋與固定規格、官方日曆、
    astra-ledger 上的凍結錨點(GitHub 收件時間要早於起日收盤)、實驗 ID;唯一一次判定用「不存在才建立」寫入 looks/<實驗 ID>.json;
    GitHub API 查不到 → 停、不寫判定(不會把查詢失敗當成資料缺漏用掉唯一一次)
用法:
  python3 -I v3_verify.py status  --dry-run --start YYYY-MM-DD --manifest-sha <v2 manifest SHA> [--repo R] [--evidence DIR] [--offline --pins REF:PATH]
  python3 -I v3_verify.py analyze --dry-run ... --out <試跑資料夾>
  python3 -I v3_verify.py analyze --formal [--repo R]                      (凍結之後才能用)
  python3 -I v3_verify.py pin --evidence DIR                               (把證據檔的指紋寫成 PINS.json,之後 commit)
  python3 -I v3_verify.py make-manifest --start ... --cohort-sessions ... --h2-mode ... --v2-manifest-sha ... --min-effect-pp ...
"""
import argparse, datetime as dt, gzip, hashlib, json, math, os, re, subprocess, sys, tempfile
from collections import Counter
from zoneinfo import ZoneInfo
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); REPO0 = os.path.abspath(os.path.join(HERE, '..', '..'))
ET = ZoneInfo('America/New_York')
VERSION = 'v3-draft3'
OWNER_REPO = 'groupuie/market-flow-dashboard'; LEDGER_BRANCH = 'astra-ledger'; RECEIPT_WF = '.github/workflows/ledger-receipt.yml'
ENGINE_FILES = ('scripts/astra_ledger.py', 'scripts/astra_trades.py', 'scripts/astra_data.py')
IDX = ('SPY', 'QQQ')
ISSUER = {'GOOG': 'GOOGL'}            # 268 檔名單裡同一家公司的兩種股別(只有這一組)
H2_MODES = ('gap_vs_all_10pp', 'agree_vs_disagree_lb', 'none')
DECISION_KEYS = ('cohort_sessions', 'h2_mode')                      # 使用者在凍結時決定、寫進 manifest
ALLOWED = {'cohort_sessions': (120, 250), 'h2_mode': H2_MODES}
SPEC = {'cohort_sessions': 120, 'horizon_sessions': 41, 'unresolved_after': 10, 'model': 'claude-opus-5-5',
        'min_closed': 300, 'min_agree': 60, 'min_disagree': 60, 'min_paired_dates': 80, 'min_issuers_per_label': 30,
        'min_batch_coverage': 0.90, 'date_block': 5, 'date_scheme': 'circular', 'issuer_weight': 'exp1', 'h1_method': 'C1',   # C1 / L=5:sim5 第二輪照事先規則選出
        'draws': 2000, 'seed': 20261016, 'cost': 0.001, 'late_close_sessions': 5, 'tol': 1e-12, 'agree_missing_value': -1.0,
        'h2_mode': None,                      # 待使用者決定(gap_vs_all_10pp / agree_vs_disagree_lb / none);試跑三種都列
        'win_gap_pp': 10.0, 'stress_q': (5, 95)}
HOLIDAYS = {'2026-01-01', '2026-01-19', '2026-02-16', '2026-04-03', '2026-05-25', '2026-06-19', '2026-07-03', '2026-09-07', '2026-11-26', '2026-12-25',
            '2027-01-01', '2027-01-18', '2027-02-15', '2027-03-26', '2027-05-31', '2027-06-18', '2027-07-05', '2027-09-06', '2027-11-25', '2027-12-24',
            '2028-01-17', '2028-02-21', '2028-04-14', '2028-05-29', '2028-06-19', '2028-07-04', '2028-09-04', '2028-11-23', '2028-12-25'}
CAL_END = '2028-12-29'
MANIFEST_PATH = 'research/ledger_v3/v3_manifest.json'; VERIFIER_PATH = 'research/ledger_v3/v3_verify.py'; LOOK_DIR = 'research/ledger_v3/looks'
ANCHOR_DIR = 'v3_freeze'              # astra-ledger 分支上的凍結錨點(它的 ledger-receipt run = GitHub 收到凍結內容的時間)
IMMUTABLE_RUN_KEYS = ('id', 'name', 'path', 'event', 'head_branch', 'head_sha', 'created_at', 'repository')
sha = lambda b: hashlib.sha256(b).hexdigest()
AD = AT = None                            # 由 load_engine() 從 git 物件載入


def clock():
    """正式模式唯一的時間來源(命令列不能改;只有測試在程式內換掉)"""
    return dt.datetime.now(dt.timezone.utc)


def ts(x):
    return x.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


# ---------------------------------------------------------------- 日曆
def is_session(d):
    if isinstance(d, str): d = dt.date.fromisoformat(d)
    if d.isoformat() > CAL_END: raise SystemExit(f'日曆只到 {CAL_END}:{d} 超出範圍 → 先補官方休市表(新版本)')
    return d.weekday() < 5 and d.isoformat() not in HOLIDAYS


def next_session(d):
    d = (dt.date.fromisoformat(d) if isinstance(d, str) else d) + dt.timedelta(days=1)
    while not is_session(d): d += dt.timedelta(days=1)
    return d


def deadline_utc(asof):
    n = next_session(asof)
    return dt.datetime(n.year, n.month, n.day, 9, 30, tzinfo=ET).astimezone(dt.timezone.utc)


def close_utc(d):
    d = dt.date.fromisoformat(d)
    return dt.datetime(d.year, d.month, d.day, 16, 0, tzinfo=ET).astimezone(dt.timezone.utc)


def sessions(a, b):
    out = []; d = dt.date.fromisoformat(a); e = dt.date.fromisoformat(b)
    while d <= e:
        if is_session(d): out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def add_sessions(a, k):
    d = dt.date.fromisoformat(a)
    if not is_session(d): raise SystemExit(f'{a} 不是交易日')
    for _ in range(k - 1): d = next_session(d)
    return d.isoformat()


def calendar_fingerprint():
    return sha(json.dumps({'holidays': sorted(HOLIDAYS), 'cal_end': CAL_END}, sort_keys=True).encode())


def P(x):
    return dt.datetime.fromisoformat(str(x).replace('Z', '+00:00'))


# ---------------------------------------------------------------- git(失敗就停)
class Git:
    def __init__(self, repo): self.repo = repo
    def run(self, *a):
        r = subprocess.run(['git', '-C', self.repo, *a], capture_output=True)
        if r.returncode != 0: raise SystemExit(f'git 失敗 → 停:git {" ".join(a)}\n{r.stderr.decode()[:300]}')
        return r.stdout
    def show(self, ref, path):
        r = subprocess.run(['git', '-C', self.repo, 'show', f'{ref}:{path}'], capture_output=True)
        return r.stdout if r.returncode == 0 else None
    def ls(self, ref, path):
        return [x for x in self.run('ls-tree', '--name-only', ref, path.rstrip('/') + '/').decode().split('\n') if x]
    def verify(self, ref):
        return self.run('rev-parse', '--verify', ref + '^{commit}').decode().strip()
    def is_ancestor(self, a, b):
        return subprocess.run(['git', '-C', self.repo, 'merge-base', '--is-ancestor', a, b], capture_output=True).returncode == 0
    def touching(self, ref, path):
        """碰過 path 的 commit(新 → 舊)"""
        return self.run('log', '--format=%H', ref, '--', path).decode().split()


def load_engine(g, commit, want):
    """從 commit 的 git 物件取出 astra_data / astra_trades,核對 SHA-256 = manifest,再從隔離資料夾載入;回傳實際執行的來源"""
    global AD, AT
    tmp = tempfile.mkdtemp(prefix='v3eng_'); prov = {}
    for p in ('scripts/astra_data.py', 'scripts/astra_trades.py'):
        b = g.show(commit, p)
        if b is None: raise SystemExit(f'引擎檔在 {commit} 不存在:{p} → 停')
        if sha(b) != want.get(p): raise SystemExit(f'引擎指紋和凍結的不同:{p} → 停')
        open(os.path.join(tmp, os.path.basename(p)), 'wb').write(b)
    for m in ('astra_data', 'astra_trades'): sys.modules.pop(m, None)
    sys.path.insert(0, tmp)
    try:
        import astra_data as ad, astra_trades as at
    finally:
        sys.path.remove(tmp)
    for p, mod in (('scripts/astra_data.py', ad), ('scripts/astra_trades.py', at)):
        f = os.path.abspath(mod.__file__)
        if os.path.dirname(f) != tmp or sha(open(f, 'rb').read()) != want[p]: raise SystemExit(f'實際載入的 {p} 不是凍結版 → 停')
        prov[p] = {'loaded_from': f'git:{commit}:{p}', 'executed_file_sha256': sha(open(f, 'rb').read())}
    AD, AT = ad, at
    return prov


# ---------------------------------------------------------------- GitHub 收件證據
class APIError(Exception):
    pass


def gh_api(path):
    try:
        r = subprocess.run(['gh', 'api', path], capture_output=True, text=True, timeout=60)
    except Exception as e:
        raise APIError(str(e)[:200])
    if r.returncode != 0: raise APIError(r.stderr[:200])
    return json.loads(r.stdout)


def run_subset(a):
    return {k: ((a.get('repository') or {}).get('full_name') if k == 'repository' else a.get(k)) for k in IMMUTABLE_RUN_KEYS}


def canon(x):
    if isinstance(x, list): return sorted((canon(v) for v in x), key=lambda v: json.dumps(v, sort_keys=True))
    if isinstance(x, dict) and 'head_sha' in x: return {k: x.get(k) for k in IMMUTABLE_RUN_KEYS}
    return x


class Evidence:
    """online:一定重新問 GitHub;已存的檔要完整(內部雜湊對、來源字串對)而且和 API 一樣,否則不收;沒有就存一份
    pinned(離線):只用已存的檔,檔案位元組的 SHA-256 要等於釘選表(從 git 物件讀,--pins REF:PATH);沒釘住 → 不收
    strict(正式模式):API 查詢失敗 → 停(不把基礎設施失敗當成證據不合格)"""
    def __init__(self, evdir, online, pins=None, pins_src=None, strict=False):
        self.dir, self.online, self.pins, self.pins_src, self.strict, self.used = evdir, online, pins or {}, pins_src, strict, {}

    @staticmethod
    def _intact(rec, source):
        return isinstance(rec, dict) and rec.get('source') == source and rec.get('api_subset_sha256') == sha(json.dumps(rec.get('api'), sort_keys=True).encode())

    def get(self, name, source, fetch):
        p = os.path.join(self.dir, name)
        if self.online:
            try:
                fresh = fetch()
            except APIError as e:
                if self.strict: raise SystemExit(f'GitHub API 查詢失敗({name})→ 停,不寫判定;之後再跑:{e}')
                return None, 'api_error'
            if os.path.exists(p):
                try: rec = json.load(open(p, encoding='utf-8'))
                except Exception: return None, 'evidence_cache_corrupt'
                if not self._intact(rec, source): return None, 'evidence_cache_corrupt'
                if canon(rec['api']) != canon(fresh): return None, 'evidence_cache_differs_from_api'
            else:
                rec = {'schema': 'v3-evidence-2', 'fetched_utc': ts(clock()), 'source': source, 'api': fresh,
                       'api_subset_sha256': sha(json.dumps(fresh, sort_keys=True).encode())}
                os.makedirs(self.dir, exist_ok=True)
                with open(p, 'w', encoding='utf-8') as fh: json.dump(rec, fh, indent=1, sort_keys=True)
            self.used[name] = sha(open(p, 'rb').read())
            return fresh, 'online'
        if not os.path.exists(p): return None, 'evidence_missing'
        b = open(p, 'rb').read()
        if name not in self.pins: return None, 'evidence_not_pinned'
        if sha(b) != self.pins[name]: return None, 'evidence_pin_mismatch'
        rec = json.loads(b)
        if not self._intact(rec, source): return None, 'evidence_cache_corrupt'
        self.used[name] = self.pins[name]
        return rec['api'], 'pinned'


def get_run(store, run_id):
    path = f'repos/{OWNER_REPO}/actions/runs/{int(run_id)}'
    return store.get(f'run-{int(run_id)}.json', 'GET ' + path, lambda: run_subset(gh_api(path)))


def runs_for_commit(store, commit):
    if not re.fullmatch(r'[0-9a-f]{40}', str(commit)): return None, 'bad_commit_id'
    path = f'repos/{OWNER_REPO}/actions/runs?branch={LEDGER_BRANCH}&event=push&head_sha={commit}&per_page=100'
    return store.get(f'runs-for-{commit}.json', 'GET ' + path,
                     lambda: sorted((run_subset(r) for r in (gh_api(path).get('workflow_runs') or [])), key=lambda x: x['id']))


def good_receipts(runs, commit):
    return [r for r in (runs or []) if r.get('repository') == OWNER_REPO and r.get('event') == 'push' and r.get('head_branch') == LEDGER_BRANCH
            and r.get('path') == RECEIPT_WF and r.get('head_sha') == commit and r.get('created_at')]


def load_pins(g, spec):
    """--pins REF:PATH → (釘選表, 來源);從 git 物件讀,不讀工作區"""
    if not spec: return {}, None
    ref, _, path = spec.partition(':')
    b = g.show(g.verify(ref), path)
    if b is None: raise SystemExit(f'釘選表不存在:{spec} → 停')
    j = json.loads(b)
    return dict(j.get('files') or {}), {'ref': g.verify(ref), 'path': path, 'sha256': sha(b)}


def check_receipt(rc, asof, store):
    """鎖定批次的遠端回條:回傳 (原因, run)"""
    if not rc or not rc.get('run_id') or not rc.get('lock_commit'): return ['no_receipt'], None
    run, src = get_run(store, rc['run_id'])
    if run is None: return ['receipt_' + src], None
    why = []
    if run.get('id') != rc['run_id']: why.append('receipt_run_id')
    if run.get('repository') != OWNER_REPO: why.append('receipt_repo')
    if run.get('event') != 'push': why.append('receipt_event')
    if run.get('head_branch') != LEDGER_BRANCH: why.append('receipt_branch')
    if run.get('path') != RECEIPT_WF: why.append('receipt_workflow')
    if run.get('head_sha') != rc['lock_commit']: why.append('receipt_head_sha')
    if not run.get('created_at') or P(run['created_at']) >= deadline_utc(asof): why.append('late_remote')
    if rc.get('remote_received_utc') != run.get('created_at'): why.append('receipt_time_differs_from_api')
    return why, run


# ---------------------------------------------------------------- 批次驗收
def n_universe(b):
    return len([s for s in (b or b'').decode().splitlines() if s.strip() and not s.startswith('#')])


def snapshot_bars(g, ref, asof, sym):
    sb = g.show(ref, f'snap/{asof}/{sym}.json.gz')
    if not sb: return None, 'no_snapshot'
    try: sj = json.loads(gzip.decompress(sb))
    except Exception: return None, 'snapshot_unreadable'
    bars = sj.get('bars') or []
    if sj.get('sym') != sym or sj.get('asof') != asof or not bars or bars[-1][0] != asof: return None, 'snapshot_header'
    ds = [b[0] for b in bars]
    if ds != sorted(set(ds)): return None, 'snapshot_dates'
    if not (30 <= len(bars) <= AD.KEEP): return None, 'snapshot_length'
    return bars, ''


def check_batch(g, lref, asof, rc, head_rows, frozen_manifest_sha, head_batch_bytes):
    """鎖定批次:回傳 (批次層級原因, {id: 列原因}, {id: 快照 K 線});呼叫的人把兩層原因合併,任何一項 → 整批不收"""
    lc = rc['lock_commit']; bw = []; per = {}; snaps = {}
    if not re.fullmatch(r'[0-9a-f]{40}', str(lc)) or not g.is_ancestor(lc, lref): return ['lock_commit_not_on_ledger_branch'], {}, {}
    pb, vb, mb, fb, bb = (g.show(lc, f'pending/{asof}.json'), g.show(lc, f'verdicts/{asof}.json'), g.show(lc, 'marks.jsonl'),
                          g.show(lc, 'engine_manifest.json'), g.show(lc, f'batches/{asof}.json'))
    if not (pb and vb and mb and fb and bb): return ['lock_commit_missing_files'], {}, {}
    pen, ver, man, bat = json.loads(pb), json.loads(vb), json.loads(fb), json.loads(bb)
    if frozen_manifest_sha and sha(fb) != frozen_manifest_sha: bw.append('manifest_changed')
    for k, p, hk in (('prompt', 'prompt_v2.md', 'prompt_sha256'), ('protocol', 'PROTOCOL.md', 'protocol_sha256'), ('universe', 'universe.txt', 'universe_sha256')):
        if sha(g.show(lc, p) or b'') != man.get(hk): bw.append(f'{k}_sha')
    if pen.get('asof') != asof or ver.get('asof') != asof or pen.get('protocol') != 'v2' or pen.get('test'): bw.append('batch_header')
    if pen.get('engine_manifest_sha256') != sha(fb) or pen.get('universe_sha256') != man.get('universe_sha256') or pen.get('n_universe') != n_universe(g.show(lc, 'universe.txt')):
        bw.append('pending_header_fingerprints')
    lrows = [json.loads(l) for l in mb.decode().splitlines() if l.strip()]; lrows = [r for r in lrows if r.get('date') == asof]
    pm, vm = pen.get('marks') or [], ver.get('marks') or []
    for name, lst in (('pending', [m.get('id') for m in pm]), ('verdicts', [m.get('id') for m in vm]), ('locked', [r.get('id') for r in lrows])):
        if len(lst) != len(set(lst)): bw.append(f'duplicate_id_in_{name}')
    P_, V_, L_ = {m['id']: m for m in pm}, {m['id']: m for m in vm}, {r['id']: r for r in lrows}
    if not (set(P_) == set(V_) == set(L_)): bw.append('id_sets_differ')
    if pen.get('n') != len(pm) or len(pm) != len(lrows): bw.append('counts_differ')
    if list(head_rows) != lrows: bw.append('head_rows_differ_from_lock')
    if bat.get('asof') != asof or bat.get('status') != 'locked' or bat.get('verdicts_sha256') != sha(vb) or bat.get('test'): bw.append('lock_batch_record')
    if bat.get('n') != len(lrows) or bat.get('n_agree') != sum(r.get('v') == 'agree' for r in lrows): bw.append('lock_batch_counts')
    if head_batch_bytes != bb: bw.append('batch_changed_after_lock')
    for i, r in L_.items():
        w = []; p = P_.get(i) or {}; v = V_.get(i) or {}
        sym = r.get('sym'); typ = 'idx' if sym in IDX else 'stock'; sty = 'c' if typ == 'idx' else 'b'
        if i != f'{asof}:{sym}' or r.get('date') != asof: w.append('id_or_date')
        for f in ('sym', 'kind', 'type', 'style', 'displayed_buy', 'bars_sha256'):
            if r.get(f) != p.get(f): w.append(f'field_{f}')
        if r.get('type') != typ or r.get('style') != sty: w.append('type_style_rule')
        if r.get('v') not in ('agree', 'disagree'): w.append('verdict_value')
        if r.get('v') != v.get('v') or r.get('why') != str(v.get('why', ''))[:300]: w.append('verdict_fields')
        if (r.get('p') is None) != (v.get('p') is None) or (r.get('p') is not None and abs(float(r['p']) - float(v['p'])) > 1e-12): w.append('verdict_p')
        if r.get('model') != ver.get('model'): w.append('verdict_model')
        if r.get('pending_sha256') != sha(pb) or r.get('verdicts_sha256') != sha(vb) or r.get('engine_manifest_sha256') != sha(fb): w.append('row_hashes')
        if r.get('protocol') != 'v2' or r.get('test'): w.append('row_protocol')
        bars, why = snapshot_bars(g, lc, asof, sym) if sym else (None, 'no_sym')
        if bars is None: w.append(why)
        else:
            if sha(json.dumps(bars, separators=(',', ':')).encode()) != r.get('bars_sha256'): w.append('snapshot_sha')
            # 買點只在原快照(原尺度)上用凍結引擎核對 — 鎖定的進場資格不因之後重新還原而改變
            W = AD.sw_series(bars); j = len(bars) - 1; kinds = dict(AT.buy_points(W))
            if kinds.get(j) != r.get('kind'): w.append('snapshot_not_this_buy_point')
            else:
                T = AT.trades(W, [b[1] for b in bars], AT.style_of(sym))
                if bool(T and T[-1]['i'] == j) != bool(r.get('displayed_buy')): w.append('displayed_buy_recomputed_differs')
            snaps[i] = bars
        per[i] = w
    return bw, per, snaps


def check_no_signals(g, lref, asof, head_rows, frozen_manifest_sha, store):
    """零訊號批次要有不可變的證據:回傳 (原因, 證據)"""
    why = ['no_signals_but_marks_exist'] if head_rows else []; ev = {}
    bpath = f'batches/{asof}.json'
    commits = g.touching(lref, bpath)
    if not commits: return why + ['no_signals_batch_not_in_history'], ev
    C = commits[0]; ev['prep_commit'] = C           # 最後一次改批次檔的 commit = 宣告零訊號的 prep
    bb = g.show(C, bpath); b = json.loads(bb) if bb else {}
    if b.get('status') != 'no_signals' or b.get('asof') != asof or b.get('n') != 0 or b.get('test'): why.append('no_signals_batch_record')
    pb, fb, ub = g.show(C, f'pending/{asof}.json'), g.show(C, 'engine_manifest.json'), g.show(C, 'universe.txt')
    if not (pb and fb and ub): return why + ['no_signals_prep_files_missing'], ev
    pen, man = json.loads(pb), json.loads(fb); nu = n_universe(ub)
    if sha(pb) != b.get('pending_sha256'): why.append('no_signals_pending_sha')
    if pen.get('asof') != asof or pen.get('protocol') != 'v2' or pen.get('test') or pen.get('n') != 0 or pen.get('marks') != []: why.append('no_signals_pending_not_empty')
    if frozen_manifest_sha and sha(fb) != frozen_manifest_sha: why.append('manifest_changed')
    if pen.get('engine_manifest_sha256') != sha(fb) or pen.get('universe_sha256') != man.get('universe_sha256') or sha(ub) != man.get('universe_sha256') or pen.get('n_universe') != nu:
        why.append('no_signals_pending_fingerprints')
    if not isinstance(pen.get('n_fresh'), int) or pen['n_fresh'] < 0.9 * nu: why.append('no_signals_low_data_coverage')
    if g.show(lref, f'pending/{asof}.json') != pb: why.append('no_signals_pending_changed')
    if g.show(C, f'verdicts/{asof}.json') is not None or g.show(lref, f'verdicts/{asof}.json') is not None: why.append('no_signals_has_verdicts')
    if any(json.loads(l).get('date') == asof for l in (g.show(C, 'marks.jsonl') or b'').decode().splitlines() if l.strip()): why.append('no_signals_marks_at_prep')
    for s in IDX:                                   # SPY / QQQ 的快照每天都存:凍結引擎重算,最後一根不能是買點
        bars, w = snapshot_bars(g, C, asof, s)
        if bars is None: why.append(f'no_signals_{s}_{w}')
        elif (len(bars) - 1) in dict(AT.buy_points(AD.sw_series(bars))): why.append(f'no_signals_but_{s}_buy_point')
    runs, src = runs_for_commit(store, C)
    if runs is None: why.append('no_signals_receipt_' + src)
    else:
        good = good_receipts(runs, C)
        if not good: why.append('no_signals_no_receipt')
        else:
            t = min(r['created_at'] for r in good); ev['remote_received_utc'] = t
            if P(t) >= deadline_utc(asof): why.append('no_signals_late_remote')
    return why, ev


def engine_changes_on_main(g, main_ref, since):
    g.verify(main_ref); g.verify(since)
    if not g.is_ancestor(since, main_ref): raise SystemExit(f'{since} 不是 {main_ref} 的祖先 → 停')
    return g.run('log', '--format=%H', f'{since}..{main_ref}', '--', *ENGINE_FILES).decode().split()


# ---------------------------------------------------------------- 出場重播
def valid_bar(b):
    try:
        o, h, l, c = float(b[1]), float(b[2]), float(b[3]), float(b[4])
        return min(o, h, l, c) > 0 and l <= min(o, c) + 1e-9 and h >= max(o, c) - 1e-9
    except Exception:
        return False


def half_unit(x):
    """凍結資料的四捨五入(astra_data.rp):≥ 1 元 3 位、< 1 元 5 位 → 真值在 ± 半格內"""
    return 0.0005 if abs(x) >= 1 else 0.000005


def scale_factor(snap, ov):
    """快照和 bars_used 重疊的 K 線,全部開高低收 → 共同比例 f 的可行區間;回傳 ((f, lo, hi, 個數), 說明)"""
    S = {b[0]: b for b in snap}; lo, hi, n = 0.0, math.inf, 0; su = ss = 0.0
    for b in ov:
        s = S.get(b[0])
        if s is None: return None, f'bars_used 的 {b[0]} 不在快照裡'
        for k in (1, 2, 3, 4):
            sv, uv = float(s[k]), float(b[k])
            if not (sv > 0 and uv > 0): return None, '重疊的價格不是正數'
            es, eu = half_unit(sv) * (1 + 1e-9), half_unit(uv) * (1 + 1e-9)
            lo = max(lo, (uv - eu) / (sv + es)); hi = min(hi, (uv + eu) / (sv - es)); n += 1; su += uv; ss += sv
    if n == 0: return None, '沒有重疊的 K 線'
    if lo > hi: return None, f'重疊的 {n} 個價格找不到共同比例(可行區間 {lo:.8f} > {hi:.8f})→ 不是同一組資料換尺度'
    f = 1.0 if lo <= 1.0 <= hi else min(max(su / ss, lo), hi)
    return (f, lo, hi, n), ''


def replay(m, rec, snap, cfg):
    """回傳 (狀態, 扣成本報酬, 說明);狀態 = closed / unreproducible / open / no_data / missing
    研究定義:鎖定的買點(原快照、原尺度)+ 結案時存的 bars_used;歷史換到 bars_used 的尺度(不再四捨五入)後,用凍結的賣法重播,
    要和帳上的出場日、原因、報酬(容忍度內)一樣"""
    if not rec: return 'missing', None, ''
    if rec.get('status') != 'closed': return rec.get('status', 'missing'), None, ''
    bu = [list(b) for b in (rec.get('bars_used') or [])]
    ds = [b[0] for b in bu]
    if not bu or ds != sorted(set(ds)): return 'unreproducible', None, 'bars_used 是空的、日期重複或沒排序'
    ov = [b for b in bu if b[0] <= m['date']]; fwd = [b for b in bu if b[0] > m['date']]
    if [b[0] for b in ov] != [b[0] for b in snap[-2:]]: return 'unreproducible', None, 'bars_used 和快照重疊的不是「訊號前一天 + 訊號日」'
    if not fwd: return 'unreproducible', None, '沒有之後的 K 線'
    exp = next_session(m['date']).isoformat()
    for b in fwd:
        if b[0] != exp: return 'unreproducible', None, f'之後的 K 線不是官方交易日或有缺日:{b[0]}(應為 {exp})'
        exp = next_session(b[0]).isoformat()
    for b in bu:
        if not valid_bar(b): return 'unreproducible', None, f'K 線欄位不合理:{b[0]}'
    sf, why = scale_factor(snap, ov)
    if sf is None: return 'unreproducible', None, why
    f, flo, fhi, npx = sf
    S = [list(b) for b in snap] if f == 1.0 else [[b[0]] + [float(x) * f for x in b[1:5]] + [b[5]] for b in snap]   # 換尺度不再四捨五入
    B = S + fwd; i = len(S) - 1
    W = AD.sw_series(B)
    if W['D'][i] != m['date']: return 'unreproducible', None, '接起來之後訊號日對不上'
    O = [b[1] for b in B]
    d, xw = AT.exit_of(W, O, i, AT.STY[m['style']])
    if d is None or d + 1 >= len(B): return 'unreproducible', None, 'bars_used 不夠重播出場'
    r = AT.ret(O, i + 1, d + 1, cfg['cost'])
    ok = (W['D'][i + 1] == rec.get('entry') and W['D'][d + 1] == rec.get('exit') and xw == rec.get('exit_why')
          and r is not None and rec.get('ret') is not None and abs(r - rec['ret']) < cfg['tol']
          and rec.get('entry_open', O[i + 1]) == O[i + 1] and rec.get('exit_open', O[d + 1]) == O[d + 1])
    if not ok: return 'unreproducible', None, f'重播 {W["D"][d + 1]} {xw} {r} ≠ 帳上 {rec.get("exit")} {rec.get("exit_why")} {rec.get("ret")}'
    if not rec.get('closed_utc') or P(rec['closed_utc']) < close_utc(rec['exit']):
        return 'unreproducible', None, '記錄時間早於出場那根 K 線收盤(不可能當時就有)'
    note = '' if f == 1.0 else f'rescaled f={f:.8f}(可行區間 {flo:.8f}–{fhi:.8f},{npx} 個重疊價格)'
    lag = len(sessions(rec['exit'], P(rec['closed_utc']).astimezone(ET).date().isoformat())) - 1
    if lag > cfg['late_close_sessions']: note = (note + ' late_close').strip()
    return 'closed', r, note


# ---------------------------------------------------------------- 統計(正式估計量;模擬也呼叫這裡)
def _betacf(a, b, x):
    """不完全 Beta 的連分式(Lentz)"""
    tiny = 1e-300; qab, qap, qam = a + b, a + 1, a - 1; c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > tiny else tiny); h = d
    for m in range(1, 400):
        m2 = 2 * m; aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > tiny else tiny); c = 1 + aa / c; c = c if abs(c) > tiny else tiny; h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > tiny else tiny); c = 1 + aa / c; c = c if abs(c) > tiny else tiny; de = d * c; h *= de
        if abs(de - 1) < 1e-15: break
    return h


def t_cdf(t, df):
    x = df / (df + t * t); a, b = df / 2.0, 0.5
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    ib = math.exp(lbt) * _betacf(a, b, x) / a if x < (a + 1) / (a + b + 2) else 1 - math.exp(lbt) * _betacf(b, a, 1 - x) / b
    return 1 - 0.5 * ib if t > 0 else 0.5 * ib


def t_quantile(p, df):
    """Student-t 的 p 分位數(p > 0.5;二分法,誤差 < 1e-12)"""
    lo, hi = 0.0, 100.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if t_cdf(mid, df) < p: lo = mid
        else: hi = mid
    return (lo + hi) / 2


def issuer(s):
    return ISSUER.get(s, s)


def draw_weights(cal, n_issuers, cfg, salt=0):
    """日期:收案日曆上的環狀區塊(長度 date_block)→ 每天的倍數 mult(D, T),每一天的期望值都 = 1
    發行人:Exp(1)(平均 1、變異 1、永遠 > 0)→ U(D, 發行人數)"""
    if cfg.get('date_scheme', 'circular') != 'circular' or cfg.get('issuer_weight', 'exp1') != 'exp1': raise SystemExit('草案 3 只支援環狀日期區塊 × Exp(1) 發行人權重')
    D = cfg['draws']; T = len(cal); b = max(1, min(int(cfg['date_block']), T)); nb = -(-T // b)
    rng = np.random.default_rng(cfg['seed'] + salt)
    st = rng.integers(0, T, size=(D, nb))
    pick = ((st[:, :, None] + np.arange(b)[None, None, :]) % T).reshape(D, -1)[:, :T]
    mult = np.zeros((D, T))
    for k in range(D): mult[k] = np.bincount(pick[k], minlength=T)
    U = rng.exponential(1.0, size=(D, n_issuers))
    return mult, U


def stats(rows, cal, cfg, salt=0):
    """rows: (date, type, sym, v, ret);格子 = (日期, 類型 stock / idx)
    H1 = 原資料裡兩邊都有的格子內「同意平均 − 不同意平均」,再對格子等權平均(固定的格子集合;重抽時格子不會消失)
    重抽:每筆權重 = 日期倍數 × 發行人 Exp(1);M1 = 格內照權重重算;M2 = 發行人方向一階展開(中心 = 點估計)
    H2 乙(agree_vs_disagree_lb)與 H3 是「每筆事件加權」的勝率差 / 同意組平均,和 H1 的格子等權不同"""
    n = len(rows); cal_idx = {d: k for k, d in enumerate(cal)}
    key = np.array([cal_idx[r[0]] * 2 + (1 if r[1] == 'idx' else 0) for r in rows])
    order = np.argsort(key, kind='stable'); rows = [rows[k] for k in order]; key = key[order]
    iss = [issuer(r[2]) for r in rows]; ui = sorted(set(iss)); ii = {s: k for k, s in enumerate(ui)}
    si = np.array([ii[s] for s in iss]); di = key // 2
    a = np.array([r[3] == 'agree' for r in rows], float); ret = np.array([r[4] for r in rows], float); win = (ret > 0).astype(float)
    starts = np.flatnonzero(np.r_[True, key[1:] != key[:-1]]); sizes = np.diff(np.r_[starts, n]); cdate = key[starts] // 2
    na = np.add.reduceat(a, starts); nd = np.add.reduceat(1 - a, starts); pr = (na > 0) & (nd > 0)
    abar = np.divide(np.add.reduceat(ret * a, starts), na, out=np.zeros_like(na), where=na > 0)
    dbar = np.divide(np.add.reduceat(ret * (1 - a), starts), nd, out=np.zeros_like(nd), where=nd > 0)
    dc = abar - dbar; K = int(pr.sum())
    mult, U = draw_weights(cal, len(ui), cfg, salt)
    Uo = U[:, si]; mk = mult[:, cdate[pr]]; den = mk.sum(1)
    with np.errstate(invalid='ignore', divide='ignore'):
        SA = np.add.reduceat(Uo * (ret * a), starts, axis=1)[:, pr]; NA = np.add.reduceat(Uo * a, starts, axis=1)[:, pr]
        SD = np.add.reduceat(Uo * (ret * (1 - a)), starts, axis=1)[:, pr]; ND = np.add.reduceat(Uo * (1 - a), starts, axis=1)[:, pr]
        h1_m1 = np.where(den > 0, (mk * (SA / NA - SD / ND)).sum(1) / den, np.nan)
        oc = np.repeat(np.arange(len(starts)), sizes)
        psi = np.where(a == 1, (ret - abar[oc]) / np.maximum(na[oc], 1), -(ret - dbar[oc]) / np.maximum(nd[oc], 1)) * pr[oc]
        X2 = dc[pr][None, :] + np.add.reduceat((Uo - 1.0) * psi, starts, axis=1)[:, pr]
        h1_m2 = np.where(den > 0, (mk * X2).sum(1) / den, np.nan)
        Wf = mult[:, di] * Uo; wa = (Wf * a).sum(1); wd = (Wf * (1 - a)).sum(1)
        win_a = (Wf * (a * win)).sum(1) / wa; win_d = (Wf * ((1 - a) * win)).sum(1) / wd; mean_a = (Wf * (ret * a)).sum(1) / wa
    enough = lambda v: (~np.isnan(v)).sum() > 0.9 * cfg['draws']
    pct = lambda v, p: float(np.percentile(v[~np.isnan(v)], p)) if enough(v) else None
    def summ(v):
        w = v[~np.isnan(v)]
        if not enough(v): return {'lb_pp': None, 'ub_pp': None, 'median_pp': None, 'mean_pp': None, 'sd_pp': None, 'valid_draws': int(w.size)}
        return {'lb_pp': 100 * pct(v, 2.5), 'ub_pp': 100 * pct(v, 97.5), 'median_pp': 100 * float(np.median(w)), 'mean_pp': 100 * float(w.mean()),
                'sd_pp': 100 * float(w.std(ddof=1)), 'valid_draws': int(w.size)}
    meth = {'M1': summ(h1_m1), 'M2': summ(h1_m2)}
    # C1 / C3(草案 3 第二輪候選):區間 = 點估計 ± t(0.975, df) × 標準誤;df = min(日期區塊數, 發行人數) − 1(有效獨立單位不多時的小樣本修正)
    #   C1 的標準誤 = M1 重抽的標準差;C3 = 兩向群集變異數(日期區塊 + 發行人 − 區塊×發行人交集;Cameron, Gelbach & Miller 2011、Thompson 2011),
    #   把「每筆自己的雜訊」只算一次(M1 的乘積權重會算到約三次 → 偏寬)
    T = len(cal); Lb = max(1, min(int(cfg['date_block']), T)); df = max(1, min(max(1, T // Lb), len(ui)) - 1); tq = t_quantile(0.975, df)
    with np.errstate(invalid='ignore', divide='ignore'):
        h1_date = np.where(den > 0, (mk * dc[pr][None, :]).sum(1) / den, np.nan)
        h1_iss = (SA / NA - SD / ND).mean(1) if K else np.full(cfg['draws'], np.nan)
        cl = (di // Lb) * len(ui) + si; _, cli = np.unique(cl, return_inverse=True)
        Vw = np.random.default_rng(cfg['seed'] + salt + 7919).exponential(1.0, size=(cfg['draws'], int(cli.max()) + 1 if n else 1))[:, cli]
        h1_int = (np.add.reduceat(Vw * (ret * a), starts, axis=1)[:, pr] / np.add.reduceat(Vw * a, starts, axis=1)[:, pr]
                  - np.add.reduceat(Vw * (ret * (1 - a)), starts, axis=1)[:, pr] / np.add.reduceat(Vw * (1 - a), starts, axis=1)[:, pr]).mean(1) if K else np.full(cfg['draws'], np.nan)
    def nvar(v):
        w = v[~np.isnan(v)]; return float(w.var(ddof=1)) if w.size > 1 else float('nan')
    vd, vi, vx = nvar(h1_date), nvar(h1_iss), nvar(h1_int); vc = vd + vi - vx; fb = not (vc > 0)
    se3 = math.sqrt(max(vd, vi) if fb else vc) if K and not math.isnan(vd) else None
    se1 = (meth['M1']['sd_pp'] / 100) if meth['M1']['sd_pp'] is not None else None
    h1v = float(dc[pr].mean()) if K else None
    for name, se in (('C1', se1), ('C3', se3)):
        ok_ = h1v is not None and se is not None and enough(h1_m1)
        meth[name] = {'lb_pp': 100 * (h1v - tq * se) if ok_ else None, 'ub_pp': 100 * (h1v + tq * se) if ok_ else None, 'se_pp': 100 * se if ok_ else None,
                      'median_pp': meth['M1']['median_pp'], 'mean_pp': meth['M1']['mean_pp'], 'sd_pp': meth['M1']['sd_pp'],
                      'valid_draws': meth['M1']['valid_draws'], 'df': df, 't975': tq}
    meth['C3'].update(var_components_pp2={'date_blocks': 1e4 * vd, 'issuers': 1e4 * vi, 'intersection': 1e4 * vx}, negative_two_way_fallback=bool(fb))
    use = meth[cfg['h1_method']]
    cnt = Counter(iss); g_ad = pct(win_a - win_d, 2.5); g_ma = pct(mean_a, 2.5)
    out = {'h1_pp': 100 * float(dc[pr].mean()) if K else None, 'h1_lb_pp': use['lb_pp'], 'h1_ub_pp': use['ub_pp'], 'h1_method': cfg['h1_method'],
           'h1_methods': meth, 'paired_dates': int(len(set(cdate[pr].tolist()))), 'cells_paired': K, 'draws_effective': use['valid_draws'],
           'win_agree_pct': 100 * float(win[a == 1].mean()) if (a == 1).any() else None, 'win_disagree_pct': 100 * float(win[a == 0].mean()) if (a == 0).any() else None,
           'win_all_pct': 100 * float(win.mean()) if n else None, 'win_gap_ad_lb_pp': None if g_ad is None else 100 * g_ad,
           'agree_mean_pp': 100 * float(ret[a == 1].mean()) if (a == 1).any() else None, 'agree_mean_lb_pp': None if g_ma is None else 100 * g_ma,
           'issuers_agree': len({iss[k] for k in range(n) if a[k] == 1}), 'issuers_disagree': len({iss[k] for k in range(n) if a[k] == 0}),
           'top_issuer_share_pct': 100 * max(cnt.values() or [0]) / max(1, n), 'agree_share': float(a.mean()) if n else 0.0}
    out['H1'] = out['h1_lb_pp'] is not None and out['h1_lb_pp'] > 0
    out['H2_by_mode'] = {'gap_vs_all_10pp': out['win_agree_pct'] is not None and out['win_all_pct'] is not None and out['win_agree_pct'] - out['win_all_pct'] >= cfg['win_gap_pp'],
                         'agree_vs_disagree_lb': out['win_gap_ad_lb_pp'] is not None and out['win_gap_ad_lb_pp'] > 0, 'none': True}
    out['H3'] = out['agree_mean_lb_pp'] is not None and out['agree_mean_lb_pp'] > 0
    return out


def h1_point(rows):
    """H1 點估計(不重抽):同日同類格子內同意 − 不同意,再對格子等權平均"""
    cells = {}
    for r in rows: cells.setdefault((r[0], r[1]), {'agree': [], 'disagree': []})[r[3]].append(r[4])
    d = [np.mean(c['agree']) - np.mean(c['disagree']) for c in cells.values() if c['agree'] and c['disagree']]
    return float(np.mean(d)) if d else None


def flip_value(closed, missing, side):
    """把缺的 side(agree / disagree)都填同一個值 x,H1 點估計剛好變 0 的 x(在 −100% ~ +500% 之間找;找不到 = None)"""
    other = [m + (0.0,) for m in missing if m[3] != side]
    f = lambda x: h1_point(closed + other + [m + (x,) for m in missing if m[3] == side])
    lo, hi = -1.0, 5.0; flo, fhi = f(lo), f(hi)
    if flo is None or fhi is None or flo * fhi > 0: return None
    for _ in range(60):
        mid = (lo + hi) / 2; fm = f(mid)
        if (fm > 0) == (flo > 0): lo, flo = mid, fm
        else: hi = mid
    return (lo + hi) / 2


def decide(closed, missing, cal, cfg, coverage=1.0):
    """closed: (date,type,sym,v,ret);missing: (date,type,sym,v)。缺的不同意沒有有限上界 → 資訊不足;缺的同意 = −100%
    三種 H2 一次判;cfg['h2_mode'] 有值時 decision = 那一種"""
    n = len(closed) + len(missing); na = sum(r[3] == 'agree' for r in closed); nd = len(closed) - na
    ex = stats(closed, cal, cfg) if closed else {}
    gates = {'closed': len(closed) >= cfg['min_closed'], 'agree': na >= cfg['min_agree'], 'disagree': nd >= cfg['min_disagree'],
             'paired_dates': ex.get('paired_dates', 0) >= cfg['min_paired_dates'],
             'issuers': min(ex.get('issuers_agree', 0), ex.get('issuers_disagree', 0)) >= cfg['min_issuers_per_label'],
             'batch_coverage': coverage >= cfg['min_batch_coverage'], 'no_missing_disagree': not any(m[3] == 'disagree' for m in missing),
             'draws_effective': ex.get('draws_effective', 0) >= 0.9 * cfg['draws']}
    imp = stats(closed + [m + (cfg['agree_missing_value'],) for m in missing], cal, cfg) if missing and gates['no_missing_disagree'] else ex
    by, live = {}, {}
    for mode in H2_MODES:
        if not all(gates.values()): d = 'INSUFFICIENT'
        elif ex['H1'] and imp['H1'] and ex['H2_by_mode'][mode] and imp['H2_by_mode'][mode]: d = 'PASS'
        else: d = 'NO_PASS'
        by[mode] = d; live[mode] = bool(d == 'PASS' and ex.get('H3') and imp.get('H3'))
    mode = cfg.get('h2_mode')
    res = {'decision': by[mode] if mode else None, 'decision_by_h2_mode': by, 'h2_mode': mode, 'gates': gates, 'n_eligible': n, 'n_closed': len(closed),
           'n_missing': len(missing), 'agree': na, 'disagree': nd, 'coverage': coverage, 'excluded_missing': ex,
           'agree_missing_at_minus_100pct': imp if missing else None,
           'go_live_candidate': live[mode] if mode else None, 'go_live_candidate_by_h2_mode': live,
           'go_live_note': 'PASS 且 H3(排除缺漏、缺的同意填 −100% 兩版)都過 = 上線候選;還要另做持倉路徑重播,不是已可上線'}
    if missing and closed:   # 只當壓力情境(不是最壞界)
        q = np.percentile([r[4] for r in closed], cfg['stress_q'])
        st = stats(closed + [m + (float(q[0] if m[3] == 'agree' else q[1]),) for m in missing], cal, cfg)
        res['stress_q05_q95'] = {k: st[k] for k in ('h1_pp', 'h1_lb_pp', 'H1', 'H2_by_mode')}
        res['flip_points'] = {s_: flip_value(closed, missing, s_) for s_ in ('agree', 'disagree') if any(m[3] == s_ for m in missing)}
    return res


# ---------------------------------------------------------------- 收案與重播(試跑、正式共用)
def collect(g, lref, mref, cfg, today, now, store):
    fb = g.show(lref, 'engine_manifest.json')
    if not fb or sha(fb) != cfg['v2_manifest_sha256']: raise SystemExit('ledger 的 engine_manifest.json 和給定的 SHA 不同 → 停')
    man = json.loads(fb)
    prov = load_engine(g, man['main_commit'], man['files'])
    eng_changes = engine_changes_on_main(g, mref, man['main_commit'])
    marks = [json.loads(l) for l in (g.show(lref, 'marks.jsonl') or b'').decode().splitlines() if l.strip()]
    idc = Counter(m.get('id') for m in marks); dup = {i for i, c in idc.items() if c > 1}
    rc, rc_conflict = {}, set()
    for p in g.ls(lref, 'receipts'):
        j = json.loads(g.show(lref, p))
        if j.get('asof') in rc or p != f"receipts/{j.get('asof')}.json": rc_conflict.add(j.get('asof'))
        rc[j.get('asof')] = j
    batches, bbytes, bconflict = {}, {}, set()
    for p in g.ls(lref, 'batches'):
        bb = g.show(lref, p); b = json.loads(bb)
        if p != f"batches/{b.get('asof')}.json": bconflict.add(b.get('asof'))
        batches[b.get('asof')] = b; bbytes[b.get('asof')] = bb
    sc = json.loads(g.show(lref, 'scores.json') or b'{"marks":{}}')
    end = add_sessions(cfg['start'], cfg['cohort_sessions']); cal = sessions(cfg['start'], end)
    seen = [d for d in cal if d <= min(today, end) and (deadline_utc(d) < now or (batches.get(d) or {}).get('status') in ('locked', 'no_signals'))]
    reasons, rows, cov_ok, snaps_all, by_date = Counter(), [], 0, {}, {}
    for d in seen:
        b = batches.get(d); st = (b or {}).get('status'); head_rows = [m for m in marks if m.get('date') == d and not m.get('test')]
        bw, per, snaps, ev = [], {}, {}, {}
        if d in bconflict: bw.append('batch_file_name_conflict')
        if st == 'no_signals':
            w, ev = check_no_signals(g, lref, d, head_rows, cfg['v2_manifest_sha256'], store); bw += w
        elif st == 'locked':
            r = rc.get(d)
            if d in rc_conflict: bw.append('receipt_file_conflict')
            w, _ = check_receipt(r, d, store) if r else (['no_receipt'], None); bw += w
            if r and r.get('lock_commit'):
                w2, per, snaps = check_batch(g, lref, d, r, head_rows, cfg['v2_manifest_sha256'], bbytes.get(d)); bw += w2
            if b.get('n') != len(head_rows): bw.append('batch_n_differs')
            if eng_changes: bw.append('engine_changed_on_main_after_freeze')
            for m in head_rows:
                per.setdefault(m['id'], ['not_in_lock_commit'])
                if m['id'] in dup: per[m['id']].append('duplicate_id_across_ledger')
                if m.get('model') != cfg['model']: per[m['id']].append('model')
        else:
            bw.append(f'batch_status_{st or "missing"}')
        errs = sorted(set(bw) | {w for ws in per.values() for w in ws})
        accepted = not errs
        cov_ok += int(accepted)
        by_date[d] = {'status': st or 'no_batch', 'accepted': accepted, 'reasons': errs, 'events': len(head_rows),
                      'rejected_events': 0 if accepted else len(head_rows), **({'no_signals_evidence': ev} if ev else {})}
        for m in head_rows:
            w = [] if accepted else errs
            rows.append((m, w)); snaps_all[m['id']] = snaps.get(m['id'])
            for k in w: reasons[k] += 1
    elig = [(m, w) for m, w in rows if not w]
    n_after = len(sessions(end, today)) - 1 if today >= end else -1
    closed, missing, flags = [], [], {}
    for m, _ in elig:
        stt, r, note = replay(m, (sc.get('marks') or {}).get(m['id']), snaps_all[m['id']], cfg)
        if note: flags[m['id']] = note
        key = (m['date'], m['type'], m['sym'], m['v'])
        if stt == 'closed': closed.append(key + (r,))
        elif stt == 'unreproducible' or n_after >= cfg['horizon_sessions'] + cfg['unresolved_after']: missing.append(key)
        if stt == 'unreproducible': flags[m['id']] = 'unreproducible: ' + note
    pending = len(elig) - len(closed) - len(missing)
    status = 'COLLECTING' if today <= end else ('MATURING' if (n_after < cfg['horizon_sessions'] or pending) else 'READY')
    pub = {'version': VERSION, 'cohort': {'start': cfg['start'], 'end': end, 'sessions': len(cal), 'today': today, 'sessions_seen': len(seen)},
           'status': status, 'batch_coverage': {'ok': cov_ok, 'seen': len(seen), 'rate': cov_ok / max(1, len(seen)), 'by_date': by_date},
           'counts': {'marks_in_window': len(rows), 'eligible': len(elig), 'rejected': len(rows) - len(elig), 'closed_reproducible': len(closed),
                      'missing_or_unreproducible': len(missing), 'pending': pending, 'not_eligible_reasons': dict(reasons),
                      'agree_eligible': sum(m['v'] == 'agree' for m, _ in elig)},
           'flags': flags, 'engine_provenance': prov, 'engine_changes_on_main_after_freeze': eng_changes,
           'refs': {'ledger': lref, 'main': mref}, 'evidence_used': dict(sorted(store.used.items())),
           'evidence_mode': 'online' if store.online else {'pinned': store.pins_src},
           'spec': {k: (list(v) if isinstance(v, tuple) else v) for k, v in sorted(cfg.items())}}
    return pub, closed, missing, cal, cov_ok / max(1, len(seen))


# ---------------------------------------------------------------- 正式模式
def spec_json(spec):
    return {k: (list(v) if isinstance(v, tuple) else v) for k, v in spec.items()}


def experiment_id(start, cfg):
    return f"LV3-{start.replace('-', '')}-S{cfg['cohort_sessions']}-{cfg['h1_method']}-L{cfg['date_block']}-{cfg['h2_mode']}"


def make_manifest(start, cohort_sessions, h2_mode, v2_manifest_sha, verifier_bytes, min_effect_pp, note=''):
    if h2_mode not in ALLOWED['h2_mode'] or cohort_sessions not in ALLOWED['cohort_sessions']: raise SystemExit('H2 / 收案長度不在允許的選項裡')
    if not re.fullmatch(r'[0-9a-f]{64}', v2_manifest_sha): raise SystemExit('v2 manifest SHA 格式不對')
    cfg = dict(SPEC, cohort_sessions=cohort_sessions, h2_mode=h2_mode); end = add_sessions(start, cohort_sessions); exp = experiment_id(start, cfg)
    return {'schema': 'ledger-v3-manifest-1', 'experiment_id': exp, 'owner_repo': OWNER_REPO, 'ledger_branch': LEDGER_BRANCH,
            'verifier_path': VERIFIER_PATH, 'verifier_sha256': sha(verifier_bytes), 'verifier_version': VERSION, 'spec': spec_json(cfg),
            'start': start, 'end': end, 'calendar_sha256': calendar_fingerprint(), 'cohort_sessions_sha256': sha('\n'.join(sessions(start, end)).encode()),
            'v2_engine_manifest_sha256': v2_manifest_sha, 'min_effect_pp': min_effect_pp, 'look_path': f'{LOOK_DIR}/{exp}.json',
            'anchor_path': f'{ANCHOR_DIR}/{exp}.json', 'note': note}


def anchor_json(manifest_bytes, freeze_commit):
    m = json.loads(manifest_bytes)
    return {'schema': 'ledger-v3-anchor-1', 'experiment_id': m['experiment_id'], 'manifest_sha256': sha(manifest_bytes), 'main_freeze_commit': freeze_commit}


def look_exists(repo, path):
    if os.path.exists(path): return True
    rel = os.path.relpath(path, repo)
    r = subprocess.run(['git', '-C', repo, 'log', '--all', '--format=%H', '--', rel], capture_output=True, text=True)
    if r.returncode != 0: raise SystemExit('查不到 look 登記的 git 歷史 → 停')
    return bool(r.stdout.strip())


def formal_checks(g, mref, lref, store, me_bytes):
    """正式模式開跑前的全部核對;回傳 (manifest, manifest bytes, 凍結 commit, 凍結公開時間, cfg)"""
    mb = g.show(mref, MANIFEST_PATH)
    if mb is None: raise SystemExit('還沒有凍結的 research/ledger_v3/v3_manifest.json → 正式模式不能跑;試跑請加 --dry-run')
    wt = os.path.join(g.repo, MANIFEST_PATH)
    if os.path.exists(wt) and open(wt, 'rb').read() != mb: raise SystemExit('工作區的 manifest 和 git 裡的不同 → 停')
    touched = g.touching(mref, MANIFEST_PATH)
    if len(touched) != 1: raise SystemExit(f'manifest 被 {len(touched)} 個 commit 改過(凍結後不能改)→ 停')
    F = touched[0]; man = json.loads(mb)
    if man.get('schema') != 'ledger-v3-manifest-1' or man.get('owner_repo') != OWNER_REPO or man.get('ledger_branch') != LEDGER_BRANCH: raise SystemExit('manifest 格式 / repo 不對 → 停')
    if sha(me_bytes) != man.get('verifier_sha256'): raise SystemExit('正在執行的程式不是凍結的驗證程式(指紋不同)→ 停')
    if g.show(mref, man['verifier_path']) != me_bytes or g.show(F, man['verifier_path']) != me_bytes: raise SystemExit('git 裡的驗證程式和正在執行的不同 → 停')
    if g.run('log', '--format=%H', f'{F}..{mref}', '--', man['verifier_path']).decode().split(): raise SystemExit('凍結之後驗證程式被改過 → 停')
    want = {k: v for k, v in spec_json(SPEC).items() if k not in DECISION_KEYS}
    got = man.get('spec') or {}
    if {k: got.get(k) for k in want} != want or set(got) != set(want) | set(DECISION_KEYS): raise SystemExit('manifest 的固定規格和程式不同 → 停')
    for k in DECISION_KEYS:
        if got.get(k) not in ALLOWED[k]: raise SystemExit(f'manifest 的 {k} 不在允許的選項裡 → 停')
    cfg = dict(SPEC); cfg.update({k: got[k] for k in DECISION_KEYS})
    if man.get('calendar_sha256') != calendar_fingerprint(): raise SystemExit('官方日曆和凍結時不同 → 停')
    end = add_sessions(man['start'], cfg['cohort_sessions'])
    if end != man.get('end') or sha('\n'.join(sessions(man['start'], end)).encode()) != man.get('cohort_sessions_sha256'): raise SystemExit('收案日曆和凍結時不同 → 停')
    exp = experiment_id(man['start'], cfg)
    if man.get('experiment_id') != exp or man.get('look_path') != f'{LOOK_DIR}/{exp}.json' or man.get('anchor_path') != f'{ANCHOR_DIR}/{exp}.json': raise SystemExit('實驗 ID / 固定位置不對 → 停')
    ap = man['anchor_path']; at_ = g.touching(lref, ap)
    if len(at_) != 1: raise SystemExit('astra-ledger 上沒有凍結錨點、或錨點被改過 → 停')
    A = at_[0]; aj = json.loads(g.show(A, ap) or b'{}')
    if aj != anchor_json(mb, F): raise SystemExit('凍結錨點的內容和 manifest / 凍結 commit 對不上 → 停')
    runs, src = runs_for_commit(store, A)
    good = good_receipts(runs, A) if runs is not None else []
    if not good: raise SystemExit(f'凍結錨點沒有 GitHub 收件紀錄({src})→ 停')
    t = min(r['created_at'] for r in good)
    if P(t) >= close_utc(man['start']): raise SystemExit(f'凍結錨點 GitHub 收件 {t} 不早於起日 {man["start"]} 收盤 → 停')
    cfg.update(start=man['start'], v2_manifest_sha256=man['v2_engine_manifest_sha256'])
    return man, mb, F, {'anchor_commit': A, 'remote_received_utc': t}, cfg


def formal_run(repo, ledger_ref='origin/astra-ledger', main_ref='origin/main', evdir=None, me_path=None):
    g = Git(repo); mref = g.verify(main_ref); lref = g.verify(ledger_ref)
    me = open(me_path or os.path.abspath(__file__), 'rb').read()
    store = Evidence(evdir or os.path.join(repo, 'research', 'ledger_v3', 'evidence'), online=True, strict=True)
    man, mb, F, anchor, cfg = formal_checks(g, mref, lref, store, me)
    lp = os.path.join(repo, man['look_path'])
    if look_exists(repo, lp): raise SystemExit('這個實驗已經做過唯一一次判定 → 不再做')
    now = clock(); today = now.astimezone(ET).date().isoformat()
    pub, closed, missing, cal, cov = collect(g, lref, mref, cfg, today, now, store)
    if pub['status'] != 'READY': raise SystemExit(f'狀態是 {pub["status"]},還不能判定(沒有寫任何判定)')
    res = decide(closed, missing, cal, cfg, cov)
    look = {'schema': 'ledger-v3-look-1', 'mode': 'FORMAL', 'experiment_id': man['experiment_id'], 'decision': res['decision'],
            'go_live_candidate': res['go_live_candidate'], 'result': res, 'status': pub, 'manifest_sha256': sha(mb), 'freeze_commit': F,
            'freeze_anchor': anchor, 'verifier_sha256': sha(me), 'inputs_sha256': sha(json.dumps([closed, missing], sort_keys=True).encode()),
            'performed_utc': ts(now)}
    os.makedirs(os.path.dirname(lp), exist_ok=True)
    try:
        fd = os.open(lp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)       # 已經有檔 → 失敗,不覆蓋
    except FileExistsError:
        raise SystemExit('looks 檔已經存在 → 不覆蓋、不再做')
    with os.fdopen(fd, 'w', encoding='utf-8') as fh: json.dump(look, fh, ensure_ascii=False, indent=1, sort_keys=True, default=str)
    return look, lp


# ---------------------------------------------------------------- 命令列
def dry_cfg(A):
    if not (A.start and A.manifest_sha): raise SystemExit('--dry-run 要給 --start 和 --manifest-sha')
    cfg = dict(SPEC); cfg.update(start=A.start, v2_manifest_sha256=A.manifest_sha)
    for k in ('h2_mode', 'date_block', 'cohort_sessions', 'h1_method'):
        if getattr(A, k, None) is not None: cfg[k] = getattr(A, k)
    return cfg


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('cmd', choices=['status', 'analyze', 'pin', 'make-manifest'])
    ap.add_argument('--repo', default=REPO0); ap.add_argument('--ledger-ref', default='origin/astra-ledger'); ap.add_argument('--main-ref', default='origin/main')
    ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--formal', action='store_true')
    ap.add_argument('--start'); ap.add_argument('--today'); ap.add_argument('--now'); ap.add_argument('--manifest-sha')
    ap.add_argument('--evidence'); ap.add_argument('--offline', action='store_true'); ap.add_argument('--pins'); ap.add_argument('--out')
    ap.add_argument('--h2-mode', dest='h2_mode', choices=list(H2_MODES)); ap.add_argument('--date-block', dest='date_block', type=int)
    ap.add_argument('--cohort-sessions', dest='cohort_sessions', type=int); ap.add_argument('--h1-method', dest='h1_method', choices=['M1', 'M2', 'C1', 'C3'])
    ap.add_argument('--v2-manifest-sha'); ap.add_argument('--min-effect-pp', type=float); ap.add_argument('--note', default='')
    A = ap.parse_args()
    if A.cmd == 'pin':
        d = A.evidence or os.path.join(HERE, 'evidence')
        files = {f: sha(open(os.path.join(d, f), 'rb').read()) for f in sorted(os.listdir(d)) if f.endswith('.json') and f != 'PINS.json'}
        json.dump({'schema': 'v3-evidence-pins-1', 'files': files}, open(os.path.join(d, 'PINS.json'), 'w'), indent=1, sort_keys=True); print(len(files), 'pinned'); return
    if A.cmd == 'make-manifest':
        vb = open(os.path.abspath(__file__), 'rb').read()
        print(json.dumps(make_manifest(A.start, A.cohort_sessions, A.h2_mode, A.v2_manifest_sha, vb, A.min_effect_pp, A.note), ensure_ascii=False, indent=1)); return
    if A.formal:
        if A.dry_run or A.offline or A.today or A.now or A.start or A.h2_mode or A.date_block or A.cohort_sessions or A.h1_method or A.out:
            raise SystemExit('正式模式不接受任何覆寫參數(時間、規格、離線、輸出位置都由凍結的 manifest 決定)')
        if A.cmd != 'analyze': raise SystemExit('正式模式只有 analyze')
        look, lp = formal_run(A.repo, A.ledger_ref, A.main_ref, A.evidence)
        print(look['decision'], lp, '\n→ 請把這個檔 commit + push(git 歷史裡有了就不能再做)'); return
    if not A.dry_run: raise SystemExit('沒有 --formal 就要 --dry-run(試跑)')
    if A.cmd == 'analyze' and (not A.out or os.path.abspath(A.out).startswith(os.path.join(os.path.abspath(A.repo), 'research', 'ledger_v3', 'looks'))):
        raise SystemExit('試跑要 --out,而且不能寫進正式 looks 位置')
    cfg = dry_cfg(A); g = Git(A.repo); lref = g.verify(A.ledger_ref); mref = g.verify(A.main_ref)
    pins, psrc = load_pins(g, A.pins) if A.offline else ({}, None)
    store = Evidence(A.evidence or os.path.join(HERE, 'evidence'), online=not A.offline, pins=pins, pins_src=psrc)
    now = P(A.now) if A.now else clock(); today = A.today or now.astimezone(ET).date().isoformat()
    pub, closed, missing, cal, cov = collect(g, lref, mref, cfg, today, now, store)
    pub['mode'] = 'DRY_RUN(試跑,不是正式結果)'
    if A.cmd == 'status':
        print(json.dumps(pub, ensure_ascii=False, indent=1)); return     # 判定前只有筆數與原因,不顯示勝率
    if pub['status'] != 'READY': raise SystemExit(f'狀態是 {pub["status"]},還不能判定')
    res = decide(closed, missing, cal, cfg, cov); res.update(status=pub, performed_utc=ts(clock()))
    os.makedirs(A.out, exist_ok=True); json.dump(res, open(os.path.join(A.out, 'v3_look_DRYRUN.json'), 'w'), ensure_ascii=False, indent=1, default=str)
    print(res['decision_by_h2_mode'])


if __name__ == '__main__':
    main()
