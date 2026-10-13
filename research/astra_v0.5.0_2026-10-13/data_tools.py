#!/usr/bin/env python3
"""Read-only public Yahoo daily data + pinned Astra signals; no exit scoring.

Adjusted bars are [date,open,high,low,close,volume], unrounded. OHLC all
use adjclose/raw close; volume is the provider's unmodified reported volume.
No missing OHLC, duplicate day, or missing adjustment is silently repaired.
"""
from __future__ import annotations
import argparse
import ast
import concurrent.futures
import datetime as dt
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
DEFAULT_DATA = HERE / 'data'
VENDOR = HERE / 'vendor'
COMMIT = '1dbaddfcb1e75f772e550faa191a3ca9ea5834c8'
SOURCE_SHA256 = '506e35f1485b96bfc4795a1a339379b769d905d4fdaccbb27d33a9d331560e0a'
UNIVERSE_FILE = HERE / 'universe_266.txt'
UNIVERSE_SHA256 = 'd26a73138dcff3f33180fd0c69fd8435a0d8a54ee04940738bb6fc754349dfb8'
GROUPS_FILE = VENDOR / 'research/swing_tune_2026-10-12/groups.json'
GROUPS_SHA256 = '8ed69d47dc7e3f0893ef3d9bfb7873c266f72f1c48f98d61190e1f76c9ecef09'
ET = ZoneInfo('America/New_York')
SCHEMA = 'astra-exit-daily-v1'
_SYM = re.compile(r'[A-Z][A-Z0-9.-]{0,9}\Z')
_SW = None


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_checked(path, expected):
    raw = Path(path).read_bytes()
    if sha(raw) != expected:
        raise ValueError(f'pinned source hash mismatch: {path}')
    return raw


def symbol_name(symbol):
    if not isinstance(symbol, str) or not _SYM.fullmatch(symbol):
        raise ValueError('invalid symbol')
    return symbol


def load_groups():
    text = read_checked(UNIVERSE_FILE, UNIVERSE_SHA256).decode('utf-8')
    all_ = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith('#')]
    if len(all_) != 266 or len(set(all_)) != 266:
        raise ValueError('frozen universe must have 266 unique equities')
    for s in all_:
        symbol_name(s)
    g = json.loads(read_checked(GROUPS_FILE, GROUPS_SHA256))
    return {'ALL': sorted(all_), 'IDX': list(g['IDX']),
            'MAG7': sorted(set(g['MAG7']) & set(all_)),
            'NDX': sorted(set(g['NDX']) & set(all_))}


def signal_source():
    """Load only sw_series AST from verified source; never execute vendor main."""
    global _SW
    if _SW is None:
        path = VENDOR / 'scripts/astra_data.py'
        tree = ast.parse(read_checked(path, SOURCE_SHA256), filename=str(path))
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('sw_series', 'js_round')]
        if len(nodes) != 2:
            raise ValueError('ambiguous source function')
        ns = {'math': math, 'COOL': 5}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), ns)
        _SW = ns['sw_series']
    return _SW


def signals(bars, mode='research'):
    """Same frozen formula. Default: full unrounded history, unlike site input.

    website_snapshot means explicitly reproduce the last 1250 rounded bars,
    returning indices relative to that slice; it is NOT a rolling backtest.
    """
    if mode == 'research':
        b = bars
    elif mode == 'website_snapshot':
        b = [[x[0], *(round(v, 3 if v >= 1 else 5) for v in x[1:5]), x[5]] for x in bars[-1250:]]
    else:
        raise ValueError('unknown signal mode')
    return signal_source()(b)


def completed_cutoff(asof, now=None):
    request_date = dt.date.fromisoformat(asof)
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError('now must be timezone aware')
    et = now.astimezone(ET)
    completed = et.date() if et.time() >= dt.time(16, 15) else et.date() - dt.timedelta(days=1)
    return min(request_date, completed).isoformat()


def _valid(v, positive=True):
    return (not isinstance(v, bool) and isinstance(v, (int, float))
            and math.isfinite(v) and (v > 0 if positive else v >= 0))


def decode_chart(raw, symbol, start, cutoff):
    symbol_name(symbol)
    j = json.loads(raw)
    chart = j.get('chart', {})
    if chart.get('error') or not isinstance(chart.get('result'), list) or len(chart['result']) != 1:
        raise ValueError('missing/failed Yahoo chart result')
    r = chart['result'][0]
    meta = r.get('meta', {})
    if meta.get('symbol') != symbol:
        raise ValueError('Yahoo response symbol mismatch (aliases are not silently accepted)')
    tz = ZoneInfo(meta['exchangeTimezoneName'])
    timestamps = r.get('timestamp')
    if not isinstance(timestamps, list) or not timestamps:
        raise ValueError('empty timestamps')
    indicators = r.get('indicators', {})
    qs, acs = indicators.get('quote'), indicators.get('adjclose')
    if not isinstance(qs, list) or len(qs) != 1 or not isinstance(acs, list) or len(acs) != 1:
        raise ValueError('missing/ambiguous OHLC or adjusted close schema')
    quote, adj = qs[0], acs[0].get('adjclose')
    arrays = {k: quote.get(k) for k in ('open', 'high', 'low', 'close', 'volume')}
    arrays['adjclose'] = adj
    if any(not isinstance(v, list) or len(v) != len(timestamps) for v in arrays.values()):
        raise ValueError('unequal or absent daily arrays')
    bars, factors, bad, excluded = [], [], [], []
    seen = set()
    for i, stamp in enumerate(timestamps):
        if not isinstance(stamp, int) or isinstance(stamp, bool):
            raise ValueError('non-integer timestamp')
        date = dt.datetime.fromtimestamp(stamp, tz).date().isoformat()
        if date in seen:
            raise ValueError(f'duplicate daily date {date}')
        seen.add(date)
        if date < start or date > cutoff:
            excluded.append(date)
            continue
        o, h, l, c, v, ac = (arrays[k][i] for k in ('open','high','low','close','volume','adjclose'))
        issues = []
        if not all(_valid(x) for x in (o,h,l,c,ac)):
            issues.append('missing_nonpositive_or_nonfinite_price')
        if not _valid(v, positive=False) or (isinstance(v, (int,float)) and v != int(v)):
            issues.append('missing_negative_or_noninteger_volume')
        if not issues and (h < max(o,c,l) or l > min(o,c,h)):
            issues.append('inconsistent_ohlc')
        if issues:
            bad.append({'date': date, 'issues': issues})
            continue
        factor = ac / c
        adjusted = [o*factor,h*factor,l*factor,ac]
        if not all(_valid(x) for x in adjusted) or not _valid(factor):
            bad.append({'date':date,'issues':['invalid_adjustment_factor']})
            continue
        bars.append([date, *adjusted, int(v)])
        factors.append([date, factor])
    if any(a[0] >= b[0] for a,b in zip(bars, bars[1:])):
        raise ValueError('non-increasing daily dates')
    if not bars:
        raise ValueError('no usable bars through cutoff')
    return {'schema':SCHEMA,'symbol':symbol,'requestedStart':start,'completedCutoff':cutoff,
            'bars':bars,'adjustmentFactors':factors,'events':r.get('events',{}),
            'providerMetadata':meta,'adjustment':'Yahoo adjclose/close applied to all OHLC; provider volume unchanged',
            'adjustmentVerified':False,'pointInTimeAdjustmentVerified':False,
            'barSemantics':'daily aggregate; open is not a guaranteed executable tick',
            'qa':{'invalidBars':bad,'excludedOutsideCompletedRange':excluded,
                  'reportedBars':len(timestamps),'usableBars':len(bars),
                  'firstDate':bars[0][0],'lastDate':bars[-1][0]},
            'retrospective':True}


def _atomic(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_bytes(raw)
    temp.replace(path)


def write_json(path, obj):
    _atomic(path, json.dumps(obj,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf-8'))


def fetch_chart(symbol, start, end):
    symbol_name(symbol)
    period1 = int(dt.datetime.combine(dt.date.fromisoformat(start),dt.time(),dt.timezone.utc).timestamp())
    period2 = int(dt.datetime.combine(dt.date.fromisoformat(end)+dt.timedelta(days=1),dt.time(),dt.timezone.utc).timestamp())
    params = urllib.parse.urlencode({'period1':period1,'period2':period2,'interval':'1d','events':'div,split','includeAdjustedClose':'true'})
    errors = []
    for attempt in range(4):
        host = 'query1.finance.yahoo.com' if attempt % 2 == 0 else 'query2.finance.yahoo.com'
        url = f'https://{host}/v8/finance/chart/{urllib.parse.quote(symbol)}?{params}'
        try:
            req = urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req,timeout=45) as response:
                raw = response.read(20_000_001)
            if len(raw)>20_000_000:
                raise ValueError('daily response exceeds 20MB limit')
            return raw, url
        except Exception as exc:
            errors.append(type(exc).__name__+': '+str(exc)[:160])
            if attempt < 3:
                time.sleep(1.5*(attempt+1))
    raise RuntimeError('; '.join(errors))


def download_symbol(symbol, start, cutoff, data_dir=DEFAULT_DATA, refresh=False):
    data_dir = Path(data_dir)
    symbol_name(symbol)
    target = data_dir / 'adjusted' / (symbol+'.json')
    if target.exists() and not refresh:
        old = json.loads(target.read_text())
        if old.get('requestedStart') == start and old.get('completedCutoff') == cutoff:
            rawpath = data_dir / old['provenance']['rawFile']
            compressed = rawpath.read_bytes()
            if sha(compressed) != old['provenance']['rawGzipSha256'] or sha(gzip.decompress(compressed)) != old['provenance']['rawSha256']:
                raise ValueError('cached raw hash mismatch')
            return old
        raise ValueError('cached date range differs: use a different --data-dir or explicit --refresh')
    raw, url = fetch_chart(symbol,start,cutoff)
    obj = decode_chart(raw,symbol,start,cutoff)
    rawrel = f'raw/{symbol}.json.gz'
    compressed = gzip.compress(raw,mtime=0)
    _atomic(data_dir / rawrel,compressed)
    obj['provenance'] = {'rawFile':rawrel,'rawSha256':sha(raw),'rawGzipSha256':sha(compressed),
                         'url':url,'retrievedAt':dt.datetime.now(dt.timezone.utc).isoformat(),
                         'strategySourceCommit':COMMIT,'strategySourceSha256':SOURCE_SHA256,
                         'universeSha256':UNIVERSE_SHA256}
    write_json(target,obj)
    return obj


def calendar_diagnostics(obj, calendar):
    dates = {b[0] for b in obj['bars']}
    calendar_set = set(calendar)
    first,last = obj['qa']['firstDate'],obj['qa']['lastDate']
    missing = [d for d in calendar if first<=d<=last and d not in dates]
    return {'missingInsideObservedRange':missing,
            'providerDatesOutsideSPY':[d for d in sorted(dates) if d not in calendar_set],
            'spySessionsBeforeFirstBar':sum(d<first for d in calendar),
            'spySessionsAfterLastBar':sum(d>last for d in calendar),
            'leadingAbsenceNotImputed':True,
            'calendarIsProxyNotOfficialExchangeCalendar':True}


def load_symbol(symbol, data_dir=DEFAULT_DATA, require_clean=True):
    """Return unrounded adjusted B. Strict default rejects known bad/gap series."""
    symbol_name(symbol)
    data_dir = Path(data_dir)
    path = data_dir/'adjusted'/(symbol+'.json')
    raw = path.read_bytes()
    obj = json.loads(raw)
    if obj.get('schema') != SCHEMA or obj.get('symbol') != symbol:
        raise ValueError('wrong stored symbol/schema')
    manifest = data_dir/'manifest.json'
    if not manifest.exists():
        raise ValueError('missing completed data manifest')
    m = json.loads(manifest.read_text())
    entry = m['symbols'].get(symbol)
    if not entry or entry.get('adjustedSha256') != sha(raw):
        raise ValueError('adjusted file not in manifest or hash mismatch')
    if require_clean:
        q=entry['calendarQA']
        if obj['qa']['invalidBars'] or q['missingInsideObservedRange'] or q['providerDatesOutsideSPY']:
            raise ValueError(f'{symbol}: invalid bars/calendar gaps; inspect manifest, never silently compress sessions')
    return obj['bars']


def download(symbols, start, asof, data_dir=DEFAULT_DATA, workers=4, refresh=False):
    data_dir=Path(data_dir)
    cutoff=completed_cutoff(asof)
    objects,failures={},{}
    symbols=sorted(set(symbols)|{'SPY'})
    for s in symbols:
        symbol_name(s)
    def job(s):
        try:
            return s,download_symbol(s,start,cutoff,data_dir,refresh),None
        except Exception as exc:
            return s,None,type(exc).__name__+': '+str(exc)[:400]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        for i,(s,obj,err) in enumerate(ex.map(job,symbols),1):
            if err:
                failures[s]=err
            else:
                objects[s]=obj
            print(json.dumps({'progress':i,'of':len(symbols),'symbol':s,'bars':len(obj['bars']) if obj else 0,'error':err}),flush=True)
    if 'SPY' not in objects:
        write_json(data_dir/'failed-download.json',{'failures':failures})
        raise ValueError('SPY unavailable: no calendar can be constructed')
    calendar=[b[0] for b in objects['SPY']['bars']]
    if objects['SPY']['qa']['invalidBars']:
        raise ValueError('SPY invalid bars: proxy calendar incomplete')
    calobj={'source':'Yahoo SPY observed valid daily bars','officialExchangeCalendar':False,
            'dates':calendar,'start':start,'completedCutoff':cutoff,
            'rawSPYSha256':objects['SPY']['provenance']['rawSha256']}
    write_json(data_dir/'calendar.json',calobj)
    entries={}
    for s,obj in sorted(objects.items()):
        p=data_dir/'adjusted'/(s+'.json')
        entries[s]={'adjustedFile':str(p.relative_to(data_dir)),'adjustedSha256':sha(p.read_bytes()),
                    'rawSha256':obj['provenance']['rawSha256'],'qa':obj['qa'],
                    'calendarQA':calendar_diagnostics(obj,calendar)}
    manifest={'schema':SCHEMA,'requestedAsOf':asof,'completedCutoff':cutoff,'start':start,
              'createdAt':dt.datetime.now(dt.timezone.utc).isoformat(),'requestedSymbols':symbols,
              'groups':load_groups(),'universeSha256':UNIVERSE_SHA256,'groupSourceSha256':GROUPS_SHA256,
              'sourceCommit':COMMIT,'signalSourceSha256':SOURCE_SHA256,
              'calendarFile':'calendar.json','calendarSha256':sha((data_dir/'calendar.json').read_bytes()),
              'symbols':entries,'failures':failures,'allRequestedDownloaded':not failures,
              'researchReady':False,'performanceRun':False,
              'limitations':['current-survivor universe; not point-in-time membership',
                             'current vendor adjustments; corporate actions not independently verified',
                             'SPY bars proxy for sessions, not authoritative exchange calendar',
                             'no gap or OHLC imputation; strict loader rejects invalid/gapped symbols',
                             'Yahoo endpoint public without key; no service/coverage guarantee']}
    write_json(data_dir/'manifest.json',manifest)
    print(json.dumps({'manifest':str(data_dir/'manifest.json'),'success':len(objects),'failed':len(failures),'completedCutoff':cutoff}),flush=True)
    return manifest


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest='command',required=True)
    p=sub.add_parser('download')
    p.add_argument('--workers',type=int,default=4)
    p.add_argument('--start',default='2004-01-01')
    p.add_argument('--asof',default='2026-10-13')
    p.add_argument('--data-dir',type=Path,default=DEFAULT_DATA)
    p.add_argument('--symbols',nargs='+',help='bounded probe; omitted=frozen 266 equities plus SPY/QQQ')
    p.add_argument('--refresh',action='store_true',help='explicitly replace data in this output directory')
    a=ap.parse_args()
    if not 1<=a.workers<=8:
        ap.error('workers must be 1..8')
    if a.start>a.asof:
        ap.error('start must precede asof')
    g=load_groups()
    download(a.symbols or g['ALL']+g['IDX'],a.start,a.asof,a.data_dir,a.workers,a.refresh)

if __name__=='__main__':
    main()
