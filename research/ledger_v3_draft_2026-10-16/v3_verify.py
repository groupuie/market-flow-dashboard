#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪 盤感測試 v3 草案 2(2026-10-16 晚,Claude;**未凍結、還沒開始**)— 回應 Astra v0.7.3 附錄四、五

和草案 1 的差別:
  - 引擎(astra_data / astra_trades)從「凍結 commit 的 git 物件」取出、核對 SHA-256 後才載入;結果寫明實際執行的來源與指紋
  - 遠端回條:向 GitHub API 讀 run 原件(repo / run ID / event / branch / workflow / head SHA / 建立時間),原件存進 evidence/;
    ledger 自己寫的 verified 欄位不再當證據
  - 以「批次」為單位驗收:pending / verdicts / 鎖定列三者 ID 集合一模一樣、不可重複;每筆欄位逐一對上(含 type / style 規則);
    快照內部 sym / asof / 最後日期;HEAD 的列和鎖定 commit 的列完全相同;跨批次 ID 唯一
  - 出場重播:之後的 K 線必須是官方交易日、一天都不少、第一根 = 下一個交易日;記錄時間必須晚於出場那根收盤;
    快照和 bars_used 的尺度不同(配息 / 分割重新還原)時先對齊;「在指定容忍度內重現」(報酬差 < 1e-12)
  - git 查詢失敗就停(不再把失敗當成「沒有改過」)
  - H1 / H2 / H3 的區間改用「日期區塊 × 發行人」同時重抽(雙軸權重,Owen & Eckles 2012 的方向);GOOG / GOOGL 算同一家
  - 缺漏:缺的「同意」用 −100%(做多 1 倍的真正下界);缺的「不同意」沒有有限上界 → 資訊不足;q05 / q95 只當壓力情境
  - 唯一一次判定綁在實驗 ID 與固定位置(research/ledger_v3/looks/<實驗 ID>.json,工作區或 git 歷史有就不再做)
  - 正式模式只讀凍結的 research/ledger_v3/v3_manifest.json(現在還沒有 → 正式模式會停);試跑一定要 --dry-run,輸出標明不是正式結果
用法:
  python3 -I v3_verify.py status  --dry-run --start YYYY-MM-DD --manifest-sha <v2 manifest SHA> [--repo <clone>] [--evidence <資料夾>] [--offline]
  python3 -I v3_verify.py analyze --dry-run ... --out <試跑資料夾>
"""
import argparse, datetime as dt, gzip, hashlib, json, math, os, subprocess, sys, tempfile
from zoneinfo import ZoneInfo
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); REPO0 = os.path.abspath(os.path.join(HERE, '..', '..'))
ET = ZoneInfo('America/New_York')
VERSION = 'v3-draft2'
OWNER_REPO = 'groupuie/market-flow-dashboard'; LEDGER_BRANCH = 'astra-ledger'; RECEIPT_WF = '.github/workflows/ledger-receipt.yml'
ENGINE_FILES = ('scripts/astra_ledger.py', 'scripts/astra_trades.py', 'scripts/astra_data.py')
IDX = ('SPY', 'QQQ')
ISSUER = {'GOOG': 'GOOGL'}            # 268 檔名單裡同一家公司的兩種股別(只有這一組)
SPEC = {'cohort_sessions': 120, 'horizon_sessions': 41, 'unresolved_after': 10, 'model': 'claude-opus-5-5',
        'min_closed': 300, 'min_agree': 60, 'min_disagree': 60, 'min_paired_dates': 80, 'min_issuers_per_label': 30,
        'min_batch_coverage': 0.90, 'date_block': 10, 'draws': 2000, 'seed': 20261016, 'cost': 0.001,
        'late_close_sessions': 5, 'tol': 1e-12, 'agree_missing_value': -1.0,
        'h2_mode': 'agree_vs_disagree_lb',      # 待使用者決定:gap_vs_all_10pp(v2 原樣)/ agree_vs_disagree_lb / none
        'win_gap_pp': 10.0, 'stress_q': (5, 95)}
HOLIDAYS = {'2026-01-01', '2026-01-19', '2026-02-16', '2026-04-03', '2026-05-25', '2026-06-19', '2026-07-03', '2026-09-07', '2026-11-26', '2026-12-25',
            '2027-01-01', '2027-01-18', '2027-02-15', '2027-03-26', '2027-05-31', '2027-06-18', '2027-07-05', '2027-09-06', '2027-11-25', '2027-12-24',
            '2028-01-17', '2028-02-21', '2028-04-14', '2028-05-29', '2028-06-19', '2028-07-04', '2028-09-04', '2028-11-23', '2028-12-25'}
CAL_END = '2028-12-29'
sha = lambda b: hashlib.sha256(b).hexdigest()
AD = AT = None                            # 由 load_engine() 從 git 物件載入


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
        return subprocess.run(['git', '-C', self.repo, 'merge-base', '--is-ancestor', a, b]).returncode == 0


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


# ---------------------------------------------------------------- 遠端回條(GitHub API 原件)
def fetch_run(run_id, evdir, online):
    p = os.path.join(evdir, f'run-{run_id}.json')
    if os.path.exists(p): return json.load(open(p))['api'], 'cache'
    if not online: return None, 'missing'
    r = subprocess.run(['gh', 'api', f'repos/{OWNER_REPO}/actions/runs/{run_id}'], capture_output=True, text=True, timeout=60)
    if r.returncode != 0: return None, 'api_error'
    a = json.loads(r.stdout)
    keep = {k: a.get(k) for k in ('id', 'name', 'path', 'event', 'head_branch', 'head_sha', 'created_at', 'run_started_at', 'status', 'conclusion', 'html_url')}
    keep['repository'] = (a.get('repository') or {}).get('full_name')
    os.makedirs(evdir, exist_ok=True)
    json.dump({'fetched_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'source': f'GET repos/{OWNER_REPO}/actions/runs/{run_id}',
               'api': keep, 'api_subset_sha256': sha(json.dumps(keep, sort_keys=True).encode())}, open(p, 'w'), indent=1)
    return keep, 'fetched'


def check_receipt(rc, asof, evdir, online):
    why = []
    if not rc or not rc.get('run_id') or not rc.get('lock_commit'): return ['no_receipt']
    run, src = fetch_run(rc['run_id'], evdir, online)
    if run is None: return ['receipt_unverifiable_' + src]
    if run.get('id') != rc['run_id']: why.append('receipt_run_id')
    if run.get('repository') != OWNER_REPO: why.append('receipt_repo')
    if run.get('event') != 'push': why.append('receipt_event')
    if run.get('head_branch') != LEDGER_BRANCH: why.append('receipt_branch')
    if run.get('path') != RECEIPT_WF: why.append('receipt_workflow')
    if run.get('head_sha') != rc['lock_commit']: why.append('receipt_head_sha')
    if not run.get('created_at') or P(run['created_at']) >= deadline_utc(asof): why.append('late_remote')
    if rc.get('remote_received_utc') != run.get('created_at'): why.append('receipt_time_differs_from_api')
    return why


# ---------------------------------------------------------------- 批次驗收(整批一起)
def check_batch(g, asof, rc, head_rows, frozen_manifest_sha):
    """回傳 (整批的原因清單, {id: 原因清單}, {id: 快照 K 線})"""
    lc = rc['lock_commit']; bw = []; per = {}; snaps = {}
    pb, vb, mb, fb = g.show(lc, f'pending/{asof}.json'), g.show(lc, f'verdicts/{asof}.json'), g.show(lc, 'marks.jsonl'), g.show(lc, 'engine_manifest.json')
    if not (pb and vb and mb and fb): return ['lock_commit_missing_files'], {}, {}
    pen, ver, man = json.loads(pb), json.loads(vb), json.loads(fb)
    if frozen_manifest_sha and sha(fb) != frozen_manifest_sha: bw.append('manifest_changed')
    for k, p, hk in (('prompt', 'prompt_v2.md', 'prompt_sha256'), ('protocol', 'PROTOCOL.md', 'protocol_sha256'), ('universe', 'universe.txt', 'universe_sha256')):
        if sha(g.show(lc, p) or b'') != man.get(hk): bw.append(f'{k}_sha')
    if pen.get('asof') != asof or ver.get('asof') != asof or pen.get('protocol') != 'v2' or pen.get('test'): bw.append('batch_header')
    lrows = [json.loads(l) for l in mb.decode().splitlines() if l.strip()]; lrows = [r for r in lrows if r.get('date') == asof]
    pm, vm = pen.get('marks') or [], ver.get('marks') or []
    for name, lst in (('pending', [m.get('id') for m in pm]), ('verdicts', [m.get('id') for m in vm]), ('locked', [r.get('id') for r in lrows])):
        if len(lst) != len(set(lst)): bw.append(f'duplicate_id_in_{name}')
    P_, V_, L_ = {m['id']: m for m in pm}, {m['id']: m for m in vm}, {r['id']: r for r in lrows}
    if not (set(P_) == set(V_) == set(L_)): bw.append('id_sets_differ')
    if pen.get('n') != len(pm) or len(pm) != len(lrows): bw.append('counts_differ')
    if [r for r in head_rows] != lrows: bw.append('head_rows_differ_from_lock')
    for i, r in L_.items():
        w = []; p = P_.get(i) or {}; v = V_.get(i) or {}
        sym = r.get('sym'); typ = 'idx' if sym in IDX else 'stock'; sty = 'c' if typ == 'idx' else 'b'
        if i != f'{asof}:{sym}' or r.get('date') != asof: w.append('id_or_date')
        for f in ('sym', 'kind', 'type', 'style', 'displayed_buy', 'bars_sha256'):
            if r.get(f) != p.get(f): w.append(f'field_{f}')
        if r.get('type') != typ or r.get('style') != sty: w.append('type_style_rule')
        if r.get('v') != v.get('v') or r.get('why') != str(v.get('why', ''))[:300]: w.append('verdict_fields')
        if (r.get('p') is None) != (v.get('p') is None) or (r.get('p') is not None and abs(float(r['p']) - float(v['p'])) > 1e-12): w.append('verdict_p')
        if r.get('model') != ver.get('model'): w.append('verdict_model')
        if r.get('pending_sha256') != sha(pb) or r.get('verdicts_sha256') != sha(vb) or r.get('engine_manifest_sha256') != sha(fb): w.append('row_hashes')
        if r.get('protocol') != 'v2' or r.get('test'): w.append('row_protocol')
        sb = g.show(lc, f'snap/{asof}/{sym}.json.gz')
        if not sb: w.append('no_snapshot')
        else:
            sj = json.loads(gzip.decompress(sb)); bars = sj.get('bars') or []
            if sj.get('sym') != sym or sj.get('asof') != asof or not bars or bars[-1][0] != asof: w.append('snapshot_header')
            if sha(json.dumps(bars, separators=(',', ':')).encode()) != r.get('bars_sha256'): w.append('snapshot_sha')
            snaps[i] = bars
        per[i] = w
    return bw, per, snaps


def engine_changes_on_main(g, main_ref, since):
    g.verify(main_ref); g.verify(since)
    if not g.is_ancestor(since, main_ref): raise SystemExit(f'{since} 不是 {main_ref} 的祖先 → 停')
    out = g.run('log', '--format=%H', f'{since}..{main_ref}', '--', *ENGINE_FILES).decode().split()
    return out


# ---------------------------------------------------------------- 出場重播
def valid_bar(b):
    try:
        o, h, l, c = float(b[1]), float(b[2]), float(b[3]), float(b[4])
        return min(o, h, l, c) > 0 and l <= min(o, c) + 1e-9 and h >= max(o, c) - 1e-9
    except Exception:
        return False


def replay(m, rec, snap, cfg):
    """回傳 (狀態, 扣成本報酬, 說明);狀態 = closed / unreproducible / open / no_data / missing"""
    if not rec: return 'missing', None, ''
    if rec.get('status') != 'closed': return rec.get('status', 'missing'), None, ''
    bu = [list(b) for b in (rec.get('bars_used') or [])]
    fwd = [b for b in bu if b[0] > m['date']]
    if not fwd: return 'unreproducible', None, '沒有之後的 K 線'
    # 交易日曆:第一根 = 下一個交易日,之後一天都不少
    exp = next_session(m['date']).isoformat()
    for b in fwd:
        if b[0] != exp: return 'unreproducible', None, f'之後的 K 線不是官方交易日或有缺日:{b[0]}(應為 {exp})'
        if not valid_bar(b): return 'unreproducible', None, f'K 線欄位不合理:{b[0]}'
        exp = next_session(b[0]).isoformat()
    # 尺度對齊:bars_used 裡訊號日那根的收盤 ≠ 快照 → 快照整段乘同一個比例(資料商配息 / 分割重新還原)
    same_day = [b for b in bu if b[0] == m['date']]
    S = [list(b) for b in snap]; note = ''
    if same_day and abs(same_day[0][4] / S[-1][4] - 1) > 1e-9:
        f = same_day[0][4] / S[-1][4]; S = [[b[0]] + [AD.rp(x * f) for x in b[1:5]] + [b[5]] for b in S]; note = 'rescaled'
    B = S + fwd; i = len(S) - 1
    W = AD.sw_series(B)
    if W['D'][i] != m['date'] or i not in dict(AT.buy_points(W)): return 'unreproducible', None, '快照重算不是買點'
    O = [b[1] for b in B]
    d, why = AT.exit_of(W, O, i, AT.STY[m['style']])
    if d is None or d + 1 >= len(B): return 'unreproducible', None, 'bars_used 不夠重播出場'
    r = AT.ret(O, i + 1, d + 1, cfg['cost'])
    ok = (W['D'][i + 1] == rec.get('entry') and W['D'][d + 1] == rec.get('exit') and why == rec.get('exit_why')
          and r is not None and rec.get('ret') is not None and abs(r - rec['ret']) < cfg['tol'])
    if not ok: return 'unreproducible', None, f'重播 {W["D"][d + 1]} {why} {r} ≠ 帳上 {rec.get("exit")} {rec.get("exit_why")} {rec.get("ret")}'
    if not rec.get('closed_utc') or P(rec['closed_utc']) < close_utc(rec['exit']):
        return 'unreproducible', None, '記錄時間早於出場那根 K 線收盤(不可能當時就有)'
    lag = len(sessions(rec['exit'], P(rec['closed_utc']).astimezone(ET).date().isoformat())) - 1
    if lag > cfg['late_close_sessions']: note = (note + ' late_close').strip()
    return 'closed', r, note


# ---------------------------------------------------------------- 統計(正式估計量;模擬也呼叫這裡)
def issuer(s):
    return ISSUER.get(s, s)


def twoway_weights(dates, iss, cal, cfg, salt=0):
    """日期:完整收案日曆上的移動區塊(長度 date_block)→ 每天被抽到幾次;發行人:Poisson(1);每筆權重 = 兩者相乘"""
    D = cfg['draws']; T = len(cal); b = min(cfg['date_block'], T); idx = {d: k for k, d in enumerate(cal)}
    rng = np.random.default_rng(cfg['seed'] + salt)
    nb = int(math.ceil(T / b)); starts = np.arange(0, T - b + 1)
    pick = (rng.choice(starts, size=(D, nb))[:, :, None] + np.arange(b)[None, None, :]).reshape(D, -1)[:, :T]
    mult = np.zeros((D, T)); np.add.at(mult, (np.repeat(np.arange(D), T), pick.ravel()), 1.0)
    ui = sorted(set(iss)); ii = {s: k for k, s in enumerate(ui)}
    Wi = rng.poisson(1.0, size=(D, len(ui))).astype(float)
    di = np.array([idx[d] for d in dates]); si_ = np.array([ii[s] for s in iss])
    return mult[:, di] * Wi[:, si_], mult, di


def stats(rows, cal, cfg, salt=0):
    """rows: (date, type, sym, v, ret);回傳點估計與雙軸重抽下界(H1 格子平均差、勝率差、同意組平均)
    格子 = (日期, 類型 stock / idx);H1 = 兩邊都有的格子內「同意平均 − 不同意平均」再對格子等權平均(不是每筆交易等權)"""
    n = len(rows); cal_idx = {d: k for k, d in enumerate(cal)}
    keyc = np.array([cal_idx[r[0]] * 2 + (1 if r[1] == 'idx' else 0) for r in rows])
    order = np.argsort(keyc, kind='stable'); rows = [rows[k] for k in order]; keyc = keyc[order]
    dates = [r[0] for r in rows]; iss = [issuer(r[2]) for r in rows]
    a = np.array([r[3] == 'agree' for r in rows], float); ret = np.array([r[4] for r in rows], float); win = (ret > 0).astype(float)
    starts = np.flatnonzero(np.r_[True, keyc[1:] != keyc[:-1]]); kd = keyc[starts] // 2      # 每個格子的開頭、所屬日期
    ra, rd, ad = ret * a, ret * (1 - a), 1 - a
    def cells(w):
        Sa = np.add.reduceat(w * ra, starts, axis=1); Na = np.add.reduceat(w * a, starts, axis=1)
        Sd = np.add.reduceat(w * rd, starts, axis=1); Nd = np.add.reduceat(w * ad, starts, axis=1)
        with np.errstate(invalid='ignore', divide='ignore'):
            return np.where((Na > 0) & (Nd > 0), Sa / Na - Sd / Nd, np.nan)
    x0 = cells(np.ones((1, n)))[0]; valid0 = ~np.isnan(x0)
    W, mult, di = twoway_weights(dates, iss, cal, cfg, salt)
    X = cells(W)                                                     # (D, K):發行人權重下的格內差;日期權重另外乘在格子上
    mk = mult[:, kd]                                                 # 每個格子(= 那一天)被抽到幾次
    ok = ~np.isnan(X) & (mk > 0)
    with np.errstate(invalid='ignore', divide='ignore'):
        h1 = np.where(ok.any(1), np.where(ok, X * mk, 0).sum(1) / np.where(ok, mk, 0).sum(1), np.nan)
        wa = (W * a).sum(1); wd = (W * ad).sum(1)
        win_a = (W * (a * win)).sum(1) / wa; win_d = (W * (ad * win)).sum(1) / wd; mean_a = (W * ra).sum(1) / wa
    from collections import Counter
    cnt = Counter(iss)
    lb = lambda v: float(np.percentile(v[~np.isnan(v)], 2.5)) if (~np.isnan(v)).sum() > 0.9 * cfg['draws'] else None
    out = {'h1_pp': 100 * float(np.nanmean(x0)) if valid0.any() else None, 'h1_lb_pp': None if lb(h1) is None else 100 * lb(h1),
           'paired_dates': int(len(set(kd[valid0].tolist()))), 'cells_valid': int(valid0.sum()),
           'draws_effective': int((~np.isnan(h1)).sum()), 'cell_survival_mean': float((ok.sum(1) / max(1, valid0.sum())).mean()),
           'win_agree_pct': 100 * float(win[a == 1].mean()) if (a == 1).any() else None, 'win_disagree_pct': 100 * float(win[a == 0].mean()) if (a == 0).any() else None,
           'win_all_pct': 100 * float(win.mean()) if n else None,
           'win_gap_ad_lb_pp': None if lb(win_a - win_d) is None else 100 * lb(win_a - win_d),
           'agree_mean_pp': 100 * float(ret[a == 1].mean()) if (a == 1).any() else None, 'agree_mean_lb_pp': None if lb(mean_a) is None else 100 * lb(mean_a),
           'issuers_agree': len({iss[k] for k in range(n) if a[k] == 1}), 'issuers_disagree': len({iss[k] for k in range(n) if a[k] == 0}),
           'top_issuer_share_pct': 100 * max(cnt.values() or [0]) / max(1, n), 'agree_share': float(a.mean()) if n else 0.0}
    out['H1'] = out['h1_lb_pp'] is not None and out['h1_lb_pp'] > 0
    if cfg['h2_mode'] == 'gap_vs_all_10pp': out['H2'] = out['win_agree_pct'] is not None and out['win_agree_pct'] - out['win_all_pct'] >= cfg['win_gap_pp']
    elif cfg['h2_mode'] == 'agree_vs_disagree_lb': out['H2'] = out['win_gap_ad_lb_pp'] is not None and out['win_gap_ad_lb_pp'] > 0
    else: out['H2'] = True
    out['H3'] = out['agree_mean_lb_pp'] is not None and out['agree_mean_lb_pp'] > 0
    return out


def decide(closed, missing, cal, cfg, coverage=1.0):
    """closed: (date,type,sym,v,ret);missing: (date,type,sym,v)。正式規則:缺的不同意沒有有限上界 → 資訊不足;缺的同意 = −100%"""
    n = len(closed) + len(missing); na = sum(r[3] == 'agree' for r in closed); nd = len(closed) - na
    ex = stats(closed, cal, cfg) if closed else {}
    gates = {'closed': len(closed) >= cfg['min_closed'], 'agree': na >= cfg['min_agree'], 'disagree': nd >= cfg['min_disagree'],
             'paired_dates': ex.get('paired_dates', 0) >= cfg['min_paired_dates'],
             'issuers': min(ex.get('issuers_agree', 0), ex.get('issuers_disagree', 0)) >= cfg['min_issuers_per_label'],
             'batch_coverage': coverage >= cfg['min_batch_coverage'], 'no_missing_disagree': not any(m[3] == 'disagree' for m in missing),
             'draws_effective': ex.get('draws_effective', 0) >= 0.9 * cfg['draws']}
    imp = stats(closed + [m + (cfg['agree_missing_value'],) for m in missing], cal, cfg) if missing and gates['no_missing_disagree'] else ex
    if not all(gates.values()): decision = 'INSUFFICIENT'
    elif ex['H1'] and imp['H1'] and ex['H2'] and imp['H2']: decision = 'PASS'
    else: decision = 'NO_PASS'
    res = {'decision': decision, 'gates': gates, 'n_eligible': n, 'n_closed': len(closed), 'n_missing': len(missing), 'agree': na, 'disagree': nd,
           'coverage': coverage, 'excluded_missing': ex, 'agree_missing_at_minus_100pct': imp if missing else None, 'h2_mode': cfg['h2_mode'],
           'go_live_candidate': bool(decision == 'PASS' and ex['H3'] and imp['H3'])}
    if missing and closed:   # 只當壓力情境(不是最壞界)
        q = np.percentile([r[4] for r in closed], cfg['stress_q'])
        st = stats(closed + [m + (float(q[0] if m[3] == 'agree' else q[1]),) for m in missing], cal, cfg)
        res['stress_q05_q95'] = {k: st[k] for k in ('h1_pp', 'h1_lb_pp', 'H1', 'H2')}
    return res


# ---------------------------------------------------------------- 主流程
def build(A):
    cfg = dict(SPEC); dry = A.dry_run
    if not dry:
        mp = os.path.join(A.repo, 'research', 'ledger_v3', 'v3_manifest.json')
        if not os.path.exists(mp): raise SystemExit('還沒有凍結的 v3_manifest.json → 正式模式不能跑;試跑請加 --dry-run')
        raise SystemExit('正式模式要在凍結時一起實作(讀 manifest、核對本程式指紋);草案階段只能 --dry-run')
    if not (A.start and A.manifest_sha): raise SystemExit('--dry-run 要給 --start 和 --manifest-sha')
    cfg.update(start=A.start, v2_manifest_sha256=A.manifest_sha)
    for k in ('h2_mode', 'date_block'):
        if getattr(A, k, None) is not None: cfg[k] = getattr(A, k)
    g = Git(A.repo); lref = g.verify(A.ledger_ref); mref = g.verify(A.main_ref)
    fb = g.show(lref, 'engine_manifest.json')
    if not fb or sha(fb) != cfg['v2_manifest_sha256']: raise SystemExit('ledger 的 engine_manifest.json 和給定的 SHA 不同 → 停')
    man = json.loads(fb)
    prov = load_engine(g, man['main_commit'], man['files'])
    eng_changes = engine_changes_on_main(g, mref, man['main_commit'])
    raw = (g.show(lref, 'marks.jsonl') or b'').decode()
    marks = [json.loads(l) for l in raw.splitlines() if l.strip()]
    ids = [m['id'] for m in marks]; dup = {i for i in ids if ids.count(i) > 1}
    rc = {json.loads(g.show(lref, p))['asof']: json.loads(g.show(lref, p)) for p in g.ls(lref, 'receipts')}
    batches = {}
    for p in g.ls(lref, 'batches'):
        b = json.loads(g.show(lref, p)); batches[b['asof']] = b
    sc = json.loads(g.show(lref, 'scores.json') or b'{"marks":{}}')
    end = add_sessions(cfg['start'], cfg['cohort_sessions'])
    today = A.today or dt.datetime.now(ET).date().isoformat()
    cal = sessions(cfg['start'], end)
    now = P(A.now) if getattr(A, 'now', None) else dt.datetime.now(dt.timezone.utc)
    seen = [d for d in cal if d <= min(today, end) and (deadline_utc(d) < now or (batches.get(d) or {}).get('status') in ('locked', 'no_signals'))]   # 截止已過、或已經完成的批次
    evdir = A.evidence or os.path.join(HERE, 'evidence')
    reasons, rows, cov_ok, snaps_all, batch_rep = {}, [], 0, {}, {}
    for d in seen:
        b = batches.get(d); st_ = (b or {}).get('status')
        if st_ == 'no_signals': cov_ok += 1; continue
        if st_ != 'locked': batch_rep[d] = st_ or 'no_batch'; continue
        r = rc.get(d); head_rows = [m for m in marks if m['date'] == d and not m.get('test')]
        bw = check_receipt(r, d, evdir, not A.offline) if r else ['no_receipt']
        per, snaps = {}, {}
        if r and r.get('lock_commit'):
            bw2, per, snaps = check_batch(g, d, r, head_rows, cfg['v2_manifest_sha256']); bw += bw2
        if b.get('n') != len(head_rows): bw.append('batch_n_differs')
        if not bw: cov_ok += 1
        batch_rep[d] = bw or 'ok'
        for m in head_rows:
            w = list(bw) + per.get(m['id'], ['not_in_lock_commit'])
            if m['id'] in dup: w.append('duplicate_id_across_ledger')
            if m.get('model') != cfg['model']: w.append('model')
            if eng_changes: w.append('engine_changed_on_main_after_freeze')
            rows.append((m, w)); snaps_all[m['id']] = snaps.get(m['id'])
            for k in w: reasons[k] = reasons.get(k, 0) + 1
    elig = [(m, w) for m, w in rows if not w]
    n_after = len(sessions(end, today)) - 1 if today >= end else -1
    closed, missing, flags = [], [], {}
    for m, _ in elig:
        stt, r, note = replay(m, (sc.get('marks') or {}).get(m['id']), snaps_all[m['id']], cfg)
        if note: flags[m['id']] = note
        key = (m['date'], m['type'], m['sym'], m['v'])
        if stt == 'closed': closed.append(key + (r,))
        elif stt == 'unreproducible' or n_after >= cfg['horizon_sessions'] + cfg['unresolved_after']: missing.append(key)
    pending = len(elig) - len(closed) - len(missing)
    status = 'COLLECTING' if today <= end else ('MATURING' if (n_after < cfg['horizon_sessions'] or pending) else 'READY')
    pub = {'mode': 'DRY_RUN(試跑,不是正式結果)', 'version': VERSION, 'cohort': {'start': cfg['start'], 'end': end, 'sessions': len(cal), 'today': today, 'sessions_seen': len(seen)},
           'status': status, 'batch_coverage': {'ok': cov_ok, 'seen': len(seen), 'by_date': batch_rep},
           'counts': {'marks_in_window': len(rows), 'eligible': len(elig), 'closed_reproducible': len(closed), 'missing_or_unreproducible': len(missing), 'pending': pending,
                      'not_eligible_reasons': reasons, 'agree_eligible': sum(m['v'] == 'agree' for m, _ in elig)},
           'flags': flags, 'engine_provenance': prov, 'engine_changes_on_main_after_freeze': eng_changes,
           'refs': {'ledger': lref, 'main': mref}, 'spec': {k: cfg[k] for k in sorted(cfg)}}
    return pub, closed, missing, cal, cfg, (cov_ok / max(1, len(seen)))


def look_path(repo, exp_id):
    return os.path.join(repo, 'research', 'ledger_v3', 'looks', f'{exp_id}.json')


def look_exists(repo, path):
    if os.path.exists(path): return True
    rel = os.path.relpath(path, repo)
    r = subprocess.run(['git', '-C', repo, 'log', '--all', '--format=%H', '--', rel], capture_output=True, text=True)
    if r.returncode != 0: raise SystemExit('查不到 look 登記的 git 歷史 → 停')
    return bool(r.stdout.strip())


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('cmd', choices=['status', 'analyze'])
    ap.add_argument('--repo', default=REPO0); ap.add_argument('--ledger-ref', default='origin/astra-ledger'); ap.add_argument('--main-ref', default='origin/main')
    ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--start'); ap.add_argument('--today'); ap.add_argument('--now'); ap.add_argument('--manifest-sha')
    ap.add_argument('--evidence'); ap.add_argument('--offline', action='store_true'); ap.add_argument('--out'); ap.add_argument('--experiment-id')
    ap.add_argument('--h2-mode', dest='h2_mode', choices=['gap_vs_all_10pp', 'agree_vs_disagree_lb', 'none']); ap.add_argument('--date-block', dest='date_block', type=int)
    A = ap.parse_args()
    if A.cmd == 'analyze':
        exp = A.experiment_id or ('DRYRUN' if A.dry_run else None)
        if not exp: raise SystemExit('analyze 要實驗 ID')
        if not A.dry_run and look_exists(A.repo, look_path(A.repo, exp)): print('這個實驗已經做過唯一一次判定 → 不再做'); return
        if A.dry_run and (not A.out or os.path.abspath(A.out).startswith(os.path.join(os.path.abspath(A.repo), 'research', 'ledger_v3', 'looks'))):
            raise SystemExit('試跑要 --out,而且不能寫進正式 looks 位置')
    pub, closed, missing, cal, cfg, cov = build(A)
    if A.cmd == 'status':
        print(json.dumps(pub, ensure_ascii=False, indent=1)); return     # 判定前只有筆數與原因,不顯示勝率
    if pub['status'] != 'READY': raise SystemExit(f'狀態是 {pub["status"]},還不能判定')
    res = decide(closed, missing, cal, cfg, cov); res.update(status=pub, performed_utc=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
    os.makedirs(A.out, exist_ok=True); json.dump(res, open(os.path.join(A.out, 'v3_look_DRYRUN.json'), 'w'), ensure_ascii=False, indent=1); print(res['decision'])


if __name__ == '__main__':
    main()
