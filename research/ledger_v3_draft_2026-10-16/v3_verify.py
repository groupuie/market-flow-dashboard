#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪 盤感測試 v3 草案(2026-10-16,Claude;**未凍結、還沒開始**)— 回應 Astra v0.7.2 附錄五

做法:每天的收集照舊(scripts/astra_ledger.py v2 的 prep / lock / score、prompt_v2.md、268 檔名單、排程都不改),
v3 是在上面加一層「更嚴的收案 + 唯一一次分析」,全部從 git 物件讀(不寫 astra-ledger 分支、不碰排程):
  - 收案:只收「遠端收件已驗證、在截止前、鎖定 commit 內容逐一對得上指紋、提示詞 / PROTOCOL / 名單 / 引擎指紋不變、模型 = 凍結的模型」的買點
  - 收案期:固定日曆 120 個交易日(零買點、失敗、沒跑的日子都算),不看筆數提早截止
  - 結果:v2 帳上的出場,必須能用「判讀時的快照 + bars_used」以凍結的程式逐位重播;重播不出來 = 不可重現
  - 判定前的門檻:已結束 ≥ 300、同意 / 不同意各 ≥ 60、有配對的日期 ≥ 80、缺漏 + 不可重現 ≤ 3%
  - H1:同日同類格子平均差;下界 = min(日期 5 日區塊重抽下界, 股票 Poisson 重抽下界) > 0(sim2_cluster.py:這樣假陽性約 2–4%;只用日期區塊約 4–9%)
  - 缺漏的最壞情境:缺的同意 = 全體已結束報酬的第 5 百分位、缺的不同意 = 第 95 百分位;排除與最壞兩種都要成立
  - H2:同意勝率 − 全部勝率 ≥ 10 個百分點(排除與最壞都要成立)
  - H3(只為「只亮同意」上線提案):同意組本身扣成本平均的下界 > 0
用法:
  python3 v3_verify.py status  --repo <clone> [--ledger-ref origin/astra-ledger] [--main-ref origin/main] [--start YYYY-MM-DD] [--today YYYY-MM-DD]
  python3 v3_verify.py analyze --repo <clone> --out <資料夾> ...   (只在 READY 時做一次;out/v3_look.json 已存在就不再做)
"""
import argparse, datetime as dt, gzip, hashlib, json, os, subprocess, sys
from zoneinfo import ZoneInfo
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); REPO0 = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO0, 'scripts'))
import astra_data as AD, astra_trades as AT

ET = ZoneInfo('America/New_York')
VERSION = 'v3-draft'
ENGINE_FILES = ('scripts/astra_ledger.py', 'scripts/astra_trades.py', 'scripts/astra_data.py')
# 凍結時才填 start / v2_manifest_sha256;草案階段用 --start 試跑
V3 = {'start': None, 'v2_manifest_sha256': None, 'model': 'claude-opus-5-5',
      'cohort_sessions': 120, 'horizon_sessions': 41, 'unresolved_after': 10,
      'min_closed': 300, 'min_agree': 60, 'min_disagree': 60, 'min_paired_dates': 80, 'max_missing_frac': 0.03,
      'date_block': 5, 'draws': 2000, 'seed': 20261016, 'win_gap_pp': 10.0, 'cost': 0.001, 'late_close_sessions': 5,
      'worst_q': (5, 95)}
# NYSE 官方休市(NYSE Group 2025-12-23 公告的 2026 / 2027 / 2028;半日照常是交易日)
HOLIDAYS = {'2026-01-01', '2026-01-19', '2026-02-16', '2026-04-03', '2026-05-25', '2026-06-19', '2026-07-03', '2026-09-07', '2026-11-26', '2026-12-25',
            '2027-01-01', '2027-01-18', '2027-02-15', '2027-03-26', '2027-05-31', '2027-06-18', '2027-07-05', '2027-09-06', '2027-11-25', '2027-12-24',
            '2028-01-17', '2028-02-21', '2028-04-14', '2028-05-29', '2028-06-19', '2028-07-04', '2028-09-04', '2028-11-23', '2028-12-25'}
CAL_END = '2028-12-29'


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


def sessions(a, b):
    """a ~ b(含)之間的交易日"""
    out = []; d = dt.date.fromisoformat(a); e = dt.date.fromisoformat(b)
    while d <= e:
        if is_session(d): out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def add_sessions(a, k):
    """a 是第 1 個交易日 → 第 k 個交易日"""
    d = dt.date.fromisoformat(a)
    if not is_session(d): raise SystemExit(f'{a} 不是交易日')
    n = 1
    while n < k:
        d = next_session(d); n += 1
    return d.isoformat()


def P(x):
    return dt.datetime.fromisoformat(str(x).replace('Z', '+00:00'))


# ---------------------------------------------------------------- git 物件
class Git:
    def __init__(self, repo): self.repo = repo
    def run(self, *a, check=True):
        r = subprocess.run(['git', '-C', self.repo, *a], capture_output=True)
        if check and r.returncode != 0: raise RuntimeError(r.stderr.decode()[:300])
        return r.stdout
    def show(self, ref, path):
        r = subprocess.run(['git', '-C', self.repo, 'show', f'{ref}:{path}'], capture_output=True)
        return r.stdout if r.returncode == 0 else None
    def ls(self, ref, path):
        r = subprocess.run(['git', '-C', self.repo, 'ls-tree', '--name-only', ref, path.rstrip('/') + '/'], capture_output=True, text=True)
        return [x for x in r.stdout.split('\n') if x] if r.returncode == 0 else []


H = lambda b: hashlib.sha256(b).hexdigest()


def load_ledger(g, ref):
    raw = g.show(ref, 'marks.jsonl') or b''
    marks = [json.loads(l) for l in raw.decode().splitlines() if l.strip()]
    rc = {}
    for p in g.ls(ref, 'receipts'):
        r = json.loads(g.show(ref, p)); rc[r['asof']] = r
    sc = json.loads(g.show(ref, 'scores.json') or b'{"marks":{}}')
    man_b = g.show(ref, 'engine_manifest.json')
    return marks, rc, sc, man_b


# ---------------------------------------------------------------- 收案資格(每一筆)
def eligibility(g, m, rc, cfg, cache, flags=None):
    why = []; flags = {} if flags is None else flags
    if m.get('test'): why.append('test')
    if not is_session(m['date']): why.append('not_a_session')
    if m.get('protocol') != 'v2': why.append('protocol')
    if cfg['start'] and m['date'] < cfg['start']: why.append('before_v3_start')
    if m.get('model') != cfg['model']: why.append('model')
    r = rc.get(m['date'])
    dl = deadline_utc(m['date'])
    if not r or not r.get('verified') or not r.get('run_id') or not r.get('remote_received_utc') or not r.get('lock_commit'):
        why.append('no_verified_receipt')
    else:
        if P(r['remote_received_utc']) >= dl: why.append('late_remote')
        if r.get('deadline_utc') and P(r['deadline_utc']) != dl: flags[m['id']] = 'v2 截止和官方日曆不同(判定用官方日曆)'   # 只記錄,不排除
        lc = r['lock_commit']
        if lc not in cache:   # 同一個 lock commit 只核一次
            c = {}
            vb = g.show(lc, f'verdicts/{m["date"]}.json'); pb = g.show(lc, f'pending/{m["date"]}.json')
            mb = g.show(lc, 'marks.jsonl'); fb = g.show(lc, 'engine_manifest.json')
            c['verdicts_sha'] = H(vb) if vb else None; c['pending_sha'] = H(pb) if pb else None; c['manifest_sha'] = H(fb) if fb else None
            c['marks_at_lock'] = {json.loads(l)['id']: json.loads(l) for l in (mb or b'').decode().splitlines() if l.strip()}
            c['verdicts'] = {x['id']: x for x in (json.loads(vb).get('marks') or [])} if vb else {}
            c['verdict_model'] = json.loads(vb).get('model') if vb else None
            man = json.loads(fb) if fb else {}
            c['frozen_ok'] = {k: (H(g.show(lc, p) or b'') == man.get(hk)) for k, p, hk in
                              (('prompt', 'prompt_v2.md', 'prompt_sha256'), ('protocol', 'PROTOCOL.md', 'protocol_sha256'), ('universe', 'universe.txt', 'universe_sha256'))}
            c['engine_files'] = man.get('files') or {}
            cache[lc] = c
        c = cache[lc]
        if c['verdicts_sha'] != m.get('verdicts_sha256'): why.append('verdicts_sha')
        if c['pending_sha'] != m.get('pending_sha256'): why.append('pending_sha')
        if c['manifest_sha'] != m.get('engine_manifest_sha256'): why.append('manifest_sha_vs_mark')
        if cfg['v2_manifest_sha256'] and c['manifest_sha'] != cfg['v2_manifest_sha256']: why.append('manifest_changed')
        for k, ok in c['frozen_ok'].items():
            if not ok: why.append(f'{k}_sha')
        if c['marks_at_lock'].get(m['id']) != m: why.append('mark_row_differs_at_lock')
        v = c['verdicts'].get(m['id'])
        if not v or v.get('v') != m.get('v'): why.append('verdict_differs')
        if c['verdict_model'] != m.get('model'): why.append('verdict_model_differs')
        sb = g.show(lc, f'snap/{m["date"]}/{m["sym"]}.json.gz')
        if not sb: why.append('no_snapshot')
        else:
            bars = json.loads(gzip.decompress(sb))['bars']
            if H(json.dumps(bars, separators=(',', ':')).encode()) != m.get('bars_sha256'): why.append('snapshot_sha')
            cache[('snap', m['id'])] = bars
    return why


def engine_changes_on_main(g, main_ref, since_commit):
    """凍結之後 main 上改過三支引擎的 commit(有 → 之後的買點不收)"""
    if not since_commit: return []
    out = g.run('log', '--format=%H%x09%cI', f'{since_commit}..{main_ref}', '--', *ENGINE_FILES, check=False).decode().strip()
    return [x.split('\t') for x in out.split('\n') if x]


# ---------------------------------------------------------------- 結果(重播)
def replay(m, rec, snap_bars, cfg):
    """v2 帳上的出場 → 用快照(≤ 訊號日)+ bars_used(> 訊號日)重播;回傳 (狀態, 報酬, 說明)"""
    if not rec or rec.get('status') != 'closed': return (rec or {}).get('status', 'missing'), None, ''
    fwd = [b for b in (rec.get('bars_used') or []) if b[0] > m['date']]
    B = [list(b) for b in snap_bars] + [list(b) for b in fwd]
    D = [b[0] for b in B]
    if any(D[k] >= D[k + 1] for k in range(len(D) - 1)): return 'unreproducible', None, '日期不是遞增'
    W = AD.sw_series(B); i = len(snap_bars) - 1
    if W['D'][i] != m['date'] or i not in dict(AT.buy_points(W)): return 'unreproducible', None, '快照重算不是買點'
    O = [b[1] for b in B]
    d, why = AT.exit_of(W, O, i, AT.STY[m['style']])
    if d is None or d + 1 >= len(B): return 'unreproducible', None, 'bars_used 不夠重播出場'
    r = AT.ret(O, i + 1, d + 1, cfg['cost'])
    same = (W['D'][i + 1] == rec.get('entry') and W['D'][d + 1] == rec.get('exit') and why == rec.get('exit_why')
            and r is not None and rec.get('ret') is not None and abs(r - rec['ret']) < 1e-12)
    if not same: return 'unreproducible', None, f'重播 {W["D"][d + 1]} {why} {r} ≠ 帳上 {rec.get("exit")} {rec.get("exit_why")} {rec.get("ret")}'
    late = len(sessions(rec['exit'], P(rec['closed_utc']).astimezone(ET).date().isoformat())) - 1 > cfg['late_close_sessions'] if rec.get('closed_utc') else True
    return 'closed', r, ('late_close' if late else '')


# ---------------------------------------------------------------- 統計
def cells_of(rows, w=None):
    """rows: (date, type, sym, v, ret);w: 每筆權重 (D, n) → 每個 (date,type) 的格內差 (D, K)"""
    keys = sorted({(r[0], r[1]) for r in rows}); ki = {k: j for j, k in enumerate(keys)}
    n = len(rows); K = len(keys)
    M = np.zeros((n, K)); M[np.arange(n), [ki[(r[0], r[1])] for r in rows]] = 1.0
    a = np.array([r[3] == 'agree' for r in rows], float); ret = np.array([r[4] for r in rows])
    W = np.ones((1, n)) if w is None else w
    Sa = (W * ret * a) @ M; Na = (W * a) @ M; Sd = (W * ret * (1 - a)) @ M; Nd = (W * (1 - a)) @ M
    with np.errstate(invalid='ignore', divide='ignore'):
        X = np.where((Na > 0) & (Nd > 0), Sa / Na - Sd / Nd, np.nan)
    return keys, X


def h1_point(rows):
    keys, X = cells_of(rows); x = X[0]
    return float(np.nanmean(x)) if (~np.isnan(x)).any() else None, sorted({keys[j][0] for j in range(len(keys)) if not np.isnan(x[j])})


def lb_date_block(rows, cal, cfg, stat='h1'):
    """完整收案日曆上的 5 日移動區塊重抽(沒有格子的日子也在);stat='h1' 格子平均差 / 'agree_mean' 同意組平均"""
    idx = {d: k for k, d in enumerate(cal)}; T = len(cal)
    s = np.zeros(T); c = np.zeros(T)
    if stat == 'h1':
        keys, X = cells_of(rows); x = X[0]
        for j, (d, _) in enumerate(keys):
            if not np.isnan(x[j]): s[idx[d]] += x[j]; c[idx[d]] += 1
    else:
        for r in rows:
            if r[3] == 'agree': s[idx[r[0]]] += r[4]; c[idx[r[0]]] += 1
    rng = np.random.default_rng(cfg['seed']); b = cfg['date_block']
    nb = int(np.ceil(T / b)); starts = np.arange(0, T - b + 1)
    st_ = rng.choice(starts, size=(cfg['draws'], nb)); pick = (st_[:, :, None] + np.arange(b)[None, None, :]).reshape(cfg['draws'], -1)[:, :T]
    num = s[pick].sum(1); den = c[pick].sum(1); v = num[den > 0] / den[den > 0]
    return float(np.percentile(v, 2.5)) if len(v) else None


def lb_stock(rows, cfg, stat='h1'):
    syms = sorted({r[2] for r in rows}); si = {s: k for k, s in enumerate(syms)}
    rng = np.random.default_rng(cfg['seed'] + 1)
    Wst = rng.poisson(1.0, size=(cfg['draws'], len(syms))).astype(float)[:, [si[r[2]] for r in rows]]
    if stat == 'h1':
        _, X = cells_of(rows, Wst); v = np.nanmean(X, axis=1)
    else:
        a = np.array([r[3] == 'agree' for r in rows], float); ret = np.array([r[4] for r in rows])
        with np.errstate(invalid='ignore', divide='ignore'):
            v = (Wst * a * ret).sum(1) / (Wst * a).sum(1)
    v = v[~np.isnan(v)]
    return float(np.percentile(v, 2.5)) if len(v) else None


def evaluate(rows, cal, cfg):
    h1, pdates = h1_point(rows)
    l_d = lb_date_block(rows, cal, cfg); l_s = lb_stock(rows, cfg)
    lb = None if (l_d is None or l_s is None) else min(l_d, l_s)
    win_ag = np.mean([r[4] > 0 for r in rows if r[3] == 'agree']) * 100 if any(r[3] == 'agree' for r in rows) else None
    win_all = np.mean([r[4] > 0 for r in rows]) * 100 if rows else None
    a_mean = float(np.mean([r[4] for r in rows if r[3] == 'agree'])) if win_ag is not None else None
    a_l = [lb_date_block(rows, cal, cfg, 'agree_mean'), lb_stock(rows, cfg, 'agree_mean')] if win_ag is not None else [None]
    a_lb = None if any(x is None for x in a_l) else min(a_l)
    return {'h1_pp': None if h1 is None else 100 * h1, 'h1_lb_date5_pp': None if l_d is None else 100 * l_d, 'h1_lb_stock_pp': None if l_s is None else 100 * l_s,
            'h1_lb_min_pp': None if lb is None else 100 * lb, 'H1': bool(lb is not None and lb > 0), 'paired_dates': len(pdates),
            'win_agree_pct': win_ag, 'win_all_pct': win_all, 'H2': bool(win_ag is not None and win_ag - win_all >= cfg['win_gap_pp']),
            'agree_mean_pp': None if a_mean is None else 100 * a_mean, 'agree_mean_lb_pp': None if a_lb is None else 100 * a_lb, 'H3': bool(a_lb is not None and a_lb > 0)}


def analyze(closed, missing, cal, cfg):
    """closed: (date,type,sym,v,ret);missing: (date,type,sym,v) → 唯一一次判定"""
    n = len(closed) + len(missing); na = sum(r[3] == 'agree' for r in closed); nd = len(closed) - na
    ex = evaluate(closed, cal, cfg)
    rets = np.array([r[4] for r in closed]) if closed else np.array([0.0])
    q_lo, q_hi = np.percentile(rets, cfg['worst_q'][0]), np.percentile(rets, cfg['worst_q'][1])
    worst = closed + [(d, t, s, v, float(q_lo if v == 'agree' else q_hi)) for d, t, s, v in missing]
    wc = evaluate(worst, cal, cfg)
    gates = {'closed': len(closed) >= cfg['min_closed'], 'agree': na >= cfg['min_agree'], 'disagree': nd >= cfg['min_disagree'],
             'paired_dates': ex['paired_dates'] >= cfg['min_paired_dates'], 'missing_frac': (len(missing) / max(1, n)) <= cfg['max_missing_frac']}
    if not all(gates.values()): decision = 'INSUFFICIENT'
    elif ex['H1'] and wc['H1'] and ex['H2'] and wc['H2']: decision = 'PASS'
    else: decision = 'NO_PASS'
    return {'decision': decision, 'gates': gates, 'n_eligible': n, 'n_closed': len(closed), 'n_missing': len(missing), 'agree': na, 'disagree': nd,
            'excluded_missing': ex, 'worst_case_missing': wc, 'worst_case_imputation': {'agree_missing_ret': float(q_lo), 'disagree_missing_ret': float(q_hi)},
            'go_live_candidate': bool(decision == 'PASS' and ex['H3'] and wc['H3']),
            'note': 'PASS = 盤感有判斷力(H1 且 H2,排除與最壞都成立);go_live_candidate 另外要 H3,而且還要用固定判讀重播「只亮同意」的持倉路徑,再由使用者決定'}


# ---------------------------------------------------------------- 主流程
def build(A):
    g = Git(A.repo); cfg = dict(V3)
    if A.start: cfg['start'] = A.start
    if not cfg['start']: raise SystemExit('草案還沒有 start:試跑請給 --start')
    marks, rc, sc, man_b = load_ledger(g, A.ledger_ref)
    if A.manifest_sha: cfg['v2_manifest_sha256'] = A.manifest_sha
    end = add_sessions(cfg['start'], cfg['cohort_sessions'])
    today = A.today or dt.datetime.now(ET).date().isoformat()
    cal = sessions(cfg['start'], end)
    man = json.loads(man_b) if man_b else {}
    eng = engine_changes_on_main(g, A.main_ref, man.get('main_commit'))
    cut_eng = min((x[1][:10] for x in eng), default=None)
    cache = {}; rows = []; flags = {}
    for m in marks:
        if m.get('test') or m['date'] < cfg['start'] or m['date'] > end: continue
        why = eligibility(g, m, rc, cfg, cache, flags)
        if cut_eng and m['date'] >= cut_eng: why.append('engine_changed_on_main')
        rows.append((m, why))
    elig = [(m, w) for m, w in rows if not w]
    n_after = len(sessions(end, today)) - 1 if today >= end else -1
    out_closed, out_missing = [], []
    for m, _ in elig:
        rec = (sc.get('marks') or {}).get(m['id'])
        snap = cache.get(('snap', m['id']))
        stt, r, note = replay(m, rec, snap, cfg)
        if note: flags[m['id']] = note
        key = (m['date'], m.get('type', 'stock'), m['sym'], m['v'])
        if stt == 'closed': out_closed.append(key + (r,))
        elif stt == 'unreproducible' or n_after >= cfg['horizon_sessions'] + cfg['unresolved_after']: out_missing.append(key)
    pending = len(elig) - len(out_closed) - len(out_missing)
    if today <= end: status = 'COLLECTING'
    elif n_after < cfg['horizon_sessions'] or pending: status = 'MATURING'
    else: status = 'READY'
    reasons = {}
    for _, w in rows:
        for k in w: reasons[k] = reasons.get(k, 0) + 1
    return {'version': VERSION, 'cohort': {'start': cfg['start'], 'end': end, 'sessions': len(cal), 'today': today, 'sessions_after_end': max(0, n_after)},
            'status': status, 'counts': {'marks_in_window': len(rows), 'eligible': len(elig), 'closed_reproducible': len(out_closed), 'missing_or_unreproducible': len(out_missing),
                                          'pending': pending, 'not_eligible_reasons': reasons},
            'engine_changes_on_main_after_freeze': eng, 'flags': flags, '_closed': out_closed, '_missing': out_missing, '_cal': cal, '_cfg': cfg}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('cmd', choices=['status', 'analyze'])
    ap.add_argument('--repo', default=REPO0); ap.add_argument('--ledger-ref', default='origin/astra-ledger'); ap.add_argument('--main-ref', default='origin/main')
    ap.add_argument('--start'); ap.add_argument('--today'); ap.add_argument('--manifest-sha'); ap.add_argument('--out')
    A = ap.parse_args()
    if A.cmd == 'analyze':
        if not A.out: raise SystemExit('analyze 要 --out')
        lp = os.path.join(A.out, 'v3_look.json')
        if os.path.exists(lp): print('已經做過唯一一次判定 → 不再做:', lp); return   # 唯一一次:做過就不再算
    S = build(A)
    pub = {k: v for k, v in S.items() if not k.startswith('_')}
    if A.cmd == 'status':
        print(json.dumps(pub, ensure_ascii=False, indent=1)); return   # 判定前只有筆數,不顯示勝率
    if S['status'] != 'READY': raise SystemExit(f'狀態是 {S["status"]},還不能判定')
    res = analyze(S['_closed'], S['_missing'], S['_cal'], S['_cfg'])
    res.update(look_id=1, performed_utc=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), status=pub)
    os.makedirs(A.out, exist_ok=True); json.dump(res, open(lp, 'w'), ensure_ascii=False, indent=1); print(json.dumps(res['decision']))


if __name__ == '__main__':
    main()
