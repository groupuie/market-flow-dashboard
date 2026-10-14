#!/usr/bin/env python3
"""Alpha Vantage 帶時間戳記的原始快照(只用 Python 標準函式庫)。

用途(2026-10-14 起):驗證 Astra v0.5.2 提出的「共識 EPS 是不是當時就看得到」。
  - 每天存 EARNINGS_CALENDAR(未來 3 個月所有排定財報 + 當天共識 EPS)
  - 每天存固定 4 檔的 EARNINGS_ESTIMATES(觀察「N 天前」欄位與舊季度會不會被改)
  - 剩下的額度抓 EARNINGS:先抓剛公布財報的研究名單股票,再慢慢回補 266 檔

規則:
  - 回應原封不動存檔(位元組不改),另存 .meta.json:功能、參數(不含金鑰)、抓取時間、HTTP 狀態、大小、SHA-256
  - 舊檔永不覆蓋;同一功能同一代號每次都是新檔
  - 金鑰只從環境變數 ALPHAVANTAGE_API_KEY 讀;任何檔案、log、網址紀錄都不含金鑰
  - 碰到額度用完 / 錯誤訊息:記在 logs/,不當資料存,並停止這一輪
  - 沒有金鑰:印一行說明後正常結束(排程不會報錯)

用法:
  python3 scripts/av_snapshot.py --mode evening      # 行事曆 + 4 檔預估 + EARNINGS 佇列
  python3 scripts/av_snapshot.py --mode morning      # 只存行事曆(開盤前)
  python3 scripts/av_snapshot.py --self-test         # 不連網的自我測試
"""
import argparse, csv, datetime as dt, hashlib, io, json, os, sys, time, urllib.parse, urllib.request

VERSION = '2026-10-14.1'
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
BASE = 'https://www.alphavantage.co/query'
PANEL = ['NVDA', 'MSFT', 'TSLA', 'AAOI']          # 每天都存 EARNINGS_ESTIMATES 的固定 4 檔
EVENING_BUDGET = 19                                # 晚上這一輪最多幾次查詢(早上 1 次 → 一天 20 次,留 5 次給臨時查詢)
SLEEP = 15                                         # 每次查詢間隔秒數(保守)
REPORTED_LOOKBACK_DAYS = 10                        # 公布後幾天內還沒抓 EARNINGS 的,優先抓


def utcnow():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def stamp(t):
    return t.strftime('%Y-%m-%dT%H%M%SZ')


def redact(params):
    return {k: v for k, v in params.items() if k.lower() != 'apikey'}


def classify(function, body):
    """回傳 (ok, reason)。只把真正的資料當資料;額度或錯誤訊息一律不收。"""
    head = body[:2048].lstrip()
    if function == 'EARNINGS_CALENDAR':
        first = head.split(b'\n', 1)[0].strip().lower()
        if first.startswith(b'symbol,name,reportdate'):
            rows = [x for x in body.splitlines()[1:] if x.strip()]
            return (True, 'csv') if rows else (False, 'calendar_empty')
        try:
            obj = json.loads(body)
            for k in ('Information', 'Note', 'Error Message'):
                if isinstance(obj, dict) and k in obj:
                    return False, f'{k}:{str(obj[k])[:200]}'
        except Exception:
            pass
        return False, 'calendar_not_csv:' + head[:200].decode('utf-8', 'replace')
    try:
        obj = json.loads(body)
    except Exception:
        return False, 'not_json'
    if isinstance(obj, dict):
        for k in ('Information', 'Note', 'Error Message'):
            if k in obj:
                return False, f'{k}:{str(obj[k])[:200]}'
        if function == 'EARNINGS' and 'quarterlyEarnings' not in obj:
            return False, 'missing_quarterlyEarnings'
        if function == 'EARNINGS_ESTIMATES' and 'estimates' not in obj:
            return False, 'missing_estimates'
        return True, 'json'
    return False, 'unexpected_json_type'


def fetch(function, params, key, opener=None):
    q = {'function': function, **params, 'apikey': key}          # 和官方範例網址同順序
    url = BASE + '?' + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={'User-Agent': 'market-flow-private/' + VERSION})
    op = opener or urllib.request.urlopen
    with op(req, timeout=60) as r:
        body = r.read(50_000_001)
        hdr = {k: r.headers.get(k) for k in ('Date', 'Content-Type', 'Last-Modified', 'ETag') if r.headers.get(k)}
        return r.status, hdr, body


def save(function, symbol, ext, body, meta, t):
    rel_dir = os.path.join('raw', function, symbol)
    os.makedirs(os.path.join(ROOT, rel_dir), exist_ok=True)
    base = f'{function}_{symbol}_{stamp(t)}'
    rel = os.path.join(rel_dir, base + '.' + ext)
    path = os.path.join(ROOT, rel)
    if os.path.exists(path):
        raise RuntimeError('refuse to overwrite ' + rel)
    with open(path, 'xb') as f:
        f.write(body)
    meta = dict(meta, file=rel, bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
    with open(path + '.meta.json', 'x', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    os.makedirs(os.path.join(ROOT, 'manifest'), exist_ok=True)
    with open(os.path.join(ROOT, 'manifest', t.strftime('%Y-%m') + '.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps(meta, ensure_ascii=False, sort_keys=True) + '\n')
    return rel


def log(t, rec):
    os.makedirs(os.path.join(ROOT, 'logs'), exist_ok=True)
    with open(os.path.join(ROOT, 'logs', t.strftime('%Y-%m') + '.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps(dict(rec, at=t.isoformat()), ensure_ascii=False, sort_keys=True) + '\n')


def load_universe():
    p = os.path.join(ROOT, 'config', 'universe_266.txt')
    return [s.strip() for s in open(p, encoding='utf-8') if s.strip() and not s.lstrip().startswith('#')]


def load_state():
    p = os.path.join(ROOT, 'state', 'earnings_fetched.json')
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}


def save_state(st):
    os.makedirs(os.path.join(ROOT, 'state'), exist_ok=True)
    p = os.path.join(ROOT, 'state', 'earnings_fetched.json')
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(st, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, p)


def recent_reporters(today, universe):
    """從所有已存的行事曆快照,找出研究名單裡「排定公布日已過、在回看天數內」的股票與日期。"""
    d = os.path.join(ROOT, 'raw', 'EARNINGS_CALENDAR', 'ALL')
    seen = {}
    if not os.path.isdir(d):
        return seen
    U = set(universe)
    lo = (today - dt.timedelta(days=REPORTED_LOOKBACK_DAYS)).isoformat()
    for name in sorted(os.listdir(d)):
        if not name.endswith('.csv'):
            continue
        for r in csv.DictReader(io.StringIO(open(os.path.join(d, name), encoding='utf-8', newline='').read())):
            s, rd = r.get('symbol'), r.get('reportDate') or ''
            if s in U and lo <= rd < today.isoformat():
                seen[s] = max(seen.get(s, ''), rd)
    return seen


def after_report(ts, rd):
    """這次抓取是否在公布之後:隔天以後,或同一天 21:00 UTC 以後(美東收盤後)。"""
    return ts[:10] > rd or (ts[:10] == rd and ts[11:16] >= '21:00')


def plan_earnings(today, universe, state, n):
    """EARNINGS 佇列:①剛公布、公布後還沒抓 ②從沒抓過(回補) ③公布後只抓過一次、已滿 21 天(看舊資料會不會被改)。"""
    rep = recent_reporters(today, universe)
    first = [s for s, rd in sorted(rep.items(), key=lambda x: x[1])
             if not any(after_report(ts, rd) for ts in state.get(s, []))]
    rest = [s for s in universe if s not in state and s not in first]
    cutoff = (today - dt.timedelta(days=21)).isoformat()
    recheck = [s for s in universe if s not in first and s not in rest and len(state.get(s, [])) == 1
               and state[s][0][:10] <= cutoff]
    return (first + rest + recheck)[:n], first


def run(mode, key, opener=None, sleep=SLEEP):
    t0 = utcnow()
    universe = load_universe()
    state = load_state()
    jobs = [('EARNINGS_CALENDAR', 'ALL', {'horizon': '3month'}, 'csv')]
    if mode == 'evening':
        jobs += [('EARNINGS_ESTIMATES', s, {'symbol': s}, 'json') for s in PANEL]
        left = EVENING_BUDGET - len(jobs)
        todo, priority = plan_earnings(t0.date(), universe, state, max(0, left))
        jobs += [('EARNINGS', s, {'symbol': s}, 'json') for s in todo]
    done, stopped = [], None
    for i, (fn, sym, params, ext) in enumerate(jobs):
        if i:
            time.sleep(sleep)
        t = utcnow()
        try:
            status, hdr, body = fetch(fn, params, key, opener)
        except Exception as e:
            log(t, {'function': fn, 'symbol': sym, 'params': redact(params), 'error': type(e).__name__ + ': ' + str(e)[:200]})
            stopped = 'network_error'
            break
        ok, why = classify(fn, body)
        if not ok:
            log(t, {'function': fn, 'symbol': sym, 'params': redact(params), 'http': status, 'rejected': why,
                    'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()})
            stopped = why
            break
        meta = {'function': fn, 'symbol': sym, 'params': redact(params), 'fetched_at_utc': t.isoformat(),
                'http_status': status, 'response_headers': hdr, 'source': 'alphavantage.co/query (direct API)',
                'script_version': VERSION, 'mode': mode}
        rel = save(fn, sym, ext, body, meta, t)
        if fn == 'EARNINGS':
            state.setdefault(sym, []).append(t.isoformat())
        done.append(rel)
    save_state(state)
    summary = {'mode': mode, 'started_utc': t0.isoformat(), 'saved': len(done), 'planned': len(jobs), 'stopped': stopped}
    log(utcnow(), {'run_summary': summary})
    print(json.dumps(summary, ensure_ascii=False))
    return summary


def self_test():
    import tempfile, shutil
    global ROOT
    old = ROOT
    tmp = tempfile.mkdtemp()
    try:
        ROOT = tmp
        os.makedirs(os.path.join(tmp, 'config'))
        open(os.path.join(tmp, 'config', 'universe_266.txt'), 'w').write('# test\nAAA\nBBB\nCCC\n')
        assert redact({'symbol': 'X', 'apikey': 'SECRET'}) == {'symbol': 'X'}
        assert classify('EARNINGS', b'{"Information": "rate limit"}')[0] is False
        assert classify('EARNINGS', b'{"symbol":"X","quarterlyEarnings":[]}')[0] is True
        assert classify('EARNINGS_CALENDAR', b'symbol,name,reportDate,fiscalDateEnding,estimate,currency,timeOfTheDay\r\nAAA,A,2026-10-20,2026-09-30,1,USD,post-market\r\n')[0] is True
        assert classify('EARNINGS_CALENDAR', b'{"Information":"x"}')[0] is False

        class R:
            def __init__(self, body): self.body, self.status, self.headers = body, 200, {'Date': 'x', 'Content-Type': 'y'}
            def read(self, n): return self.body
            def __enter__(self): return self
            def __exit__(self, *a): return False
        calls = []

        def fake(req, timeout=60):
            u = req.full_url
            assert 'apikey=SECRETKEY123' in u
            calls.append(u)
            q = urllib.parse.parse_qs(urllib.parse.urlparse(u).query)
            fn = q['function'][0]
            if fn == 'EARNINGS_CALENDAR':
                return R(b'symbol,name,reportDate,fiscalDateEnding,estimate,currency,timeOfTheDay\r\nBBB,B,2000-01-01,1999-12-31,1,USD,post-market\r\n')
            if fn == 'EARNINGS_ESTIMATES':
                return R(b'{"symbol":"P","estimates":[]}')
            return R(b'{"symbol":"S","quarterlyEarnings":[]}')
        s = run('evening', 'SECRETKEY123', opener=fake, sleep=0)
        assert s['saved'] == 1 + len(PANEL) + 3 and s['stopped'] is None, s
        # 不會把金鑰寫進任何檔案
        for dp, _, fs in os.walk(tmp):
            for f in fs:
                assert b'SECRETKEY123' not in open(os.path.join(dp, f), 'rb').read(), f
        st = load_state()
        assert sorted(st) == ['AAA', 'BBB', 'CCC'], st
        # 額度用完 → 停止、不收資料
        def limited(req, timeout=60):
            return R(b'{"Information": "We have detected your API key ... 25 requests per day"}')
        s2 = run('morning', 'SECRETKEY123', opener=limited, sleep=0)
        assert s2['saved'] == 0 and s2['stopped'].startswith('Information'), s2
        print(json.dumps({'self_test': 'PASS', 'calls': len(calls)}))
    finally:
        ROOT = old
        shutil.rmtree(tmp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['evening', 'morning'], default='evening')
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args()
    if a.self_test:
        self_test()
        return
    key = os.environ.get('ALPHAVANTAGE_API_KEY', '').strip()
    if not key:
        print('ALPHAVANTAGE_API_KEY not set — skipped (nothing fetched)')
        return
    run(a.mode, key)


if __name__ == '__main__':
    main()
