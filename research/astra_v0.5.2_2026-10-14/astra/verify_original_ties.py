"""Read-only replay of Claude v1.8's six dates against Astra's frozen snapshot.

No downloads, no new universe, no overwrite of the original experiment.
Usage: python3 verify_original_ties.py --study ../astra-exits-20261013 --output tie-audit.json
"""
import argparse
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
from zoneinfo import ZoneInfo

CASES = [
    ('ADI','2018-11-09','top',False),
    ('ADI','2018-11-12','top',True),
    ('ADI','2018-12-11','bot',False),
    ('PWR','2018-10-18','top',False),
    ('PWR','2021-11-05','bot',False),
    ('PWR','2021-11-08','bot',True),
]
EXPECTED_CALENDAR = '99be666ac4b579dae46f7e8b882f0eaac5b760beae83018a89832a5bdfaa0607'
EXPECTED_MANIFEST = 'a5cfada0b67deec9de6cf9a467c517e991609ff621ad3169dde5340256a56bf8'
EXPECTED_FREEZE = '3ef884394b836c39f43bbef7ebd16aa7900a541fb9c7fcdd5fecb6f16c254fe6'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def rounded(bars):
    # Match the pinned Python publisher's rp(), NOT Math.round or Decimal half-up.
    return [[b[0], *[round(x, 3) if abs(x) >= 1 else round(x, 5) for x in b[1:5]], b[5]] for b in bars]

def run(study):
    study = Path(study).resolve()
    if sha((study/'freeze.json').read_bytes()) != EXPECTED_FREEZE:
        raise ValueError('This is not the pinned original freeze.json')
    if sha((study/'data/manifest.json').read_bytes()) != EXPECTED_MANIFEST:
        raise ValueError('This is not the pinned original data snapshot')
    freeze = json.loads((study/'freeze.json').read_text())
    for name, expected in freeze['files'].items():
        if sha((study/name).read_bytes()) != expected:
            raise ValueError('Frozen source mismatch: '+name)
    data_tools = load_module('frozen_dt', study/'data_tools.py')
    experiment = load_module('frozen_ex', study/'experiment.py')
    data = study/'data'
    manifest = json.loads((data/'manifest.json').read_text())
    calbytes = (data/manifest['calendarFile']).read_bytes()
    assert sha(calbytes) == manifest['calendarSha256']
    calendar = json.loads(calbytes)['dates']
    calhash = sha(json.dumps(calendar,ensure_ascii=True,separators=(',',':'),allow_nan=False).encode())
    assert calhash == EXPECTED_CALENDAR
    original_accounts = json.loads((study/'evidence/accounts.json').read_text())
    rows, sources, account_results, changes = [], {}, [], {}
    for symbol in ('ADI','PWR'):
        entry = manifest['symbols'][symbol]
        blob = (data/entry['adjustedFile']).read_bytes()
        assert sha(blob) == entry['adjustedSha256']
        obj = json.loads(blob)
        rawzip = (data/obj['provenance']['rawFile']).read_bytes()
        raw = gzip.decompress(rawzip)
        assert sha(raw) == entry['rawSha256']
        assert sha(rawzip) == obj['provenance']['rawGzipSha256']
        yahoo = json.loads(raw)['chart']['result'][0]
        quote = yahoo['indicators']['quote'][0]
        zone = ZoneInfo(yahoo['meta']['exchangeTimezoneName'])
        rd = {dt.datetime.fromtimestamp(t,zone).date().isoformat():i for i,t in enumerate(yahoo['timestamp'])}
        bars = obj['bars']; rb = rounded(bars)
        dates = [b[0] for b in bars]; idx = {d:i for i,d in enumerate(dates)}
        assert dates == calendar  # These two complete histories need no gap approximation.
        un = data_tools.signals(bars)
        ro = data_tools.signal_source()(rb)
        sources[symbol] = {'adjustedSha256':sha(blob),'rawSha256':sha(raw),'bars':len(bars)}
        changes[symbol] = {kind:{'onlyUnrounded':[dates[i] for i in sorted(set(un[kind])-set(ro[kind]))],
                                'onlyRounded':[dates[i] for i in sorted(set(ro[kind])-set(un[kind]))]}
                           for kind in ('bot','top','b2')}
        for sym, day, kind, expected in CASES:
            if sym != symbol: continue
            i = idx[day]; j = rd[day]; k = rd[dates[i-1]]
            column = 2 if kind=='bot' else 3
            raw_column = 'high' if kind=='bot' else 'low'
            close, previous = quote['close'][j], quote[raw_column][k]
            a, b = bars[i][4], bars[i-1][column]
            ra, rbv = rb[i][4], rb[i-1][column]
            fired = i in un[kind]
            rows.append({'symbol':symbol,'date':day,'kind':kind,'expectedUnroundedSignal':expected,
                         'actualUnroundedSignal':fired,'actualRoundedSignal':i in ro[kind],
                         'matchesClaudePrediction':fired == expected,
                         'rawClose':close,'rawPreviousLevel':previous,
                         'rawPricesEqual':close == previous,
                         'adjustedClose':a,'adjustedPreviousLevel':b,'adjustedDifference':a-b,
                         'adjustedCloseHex':a.hex(),'adjustedPreviousHex':b.hex(),
                         'roundedClose':ra,'roundedPreviousLevel':rbv,
                         'strictPriceConditionUnrounded':a>b if kind=='bot' else a<b,
                         'strictPriceConditionRounded':ra>rbv if kind=='bot' else ra<rbv})
        atr = experiment.atr14(bars)
        start = next(i for i,b in enumerate(bars) if b[0]>='2018-01-01')
        last_t = max(i for i,b in enumerate(bars) if b[0]<='2026-07-31' and i+64<len(bars))
        end = last_t+64
        for mode,sig in [('unrounded',un),('publisher_rounded_signals',ro)]:
            buys = sorted(set(sig['bot'])|set(sig['b2']))
            candidates = [t for t in buys if t>=199 and '2018-01-01'<=bars[t][0]<='2026-07-31' and t+64<len(bars)]
            selected = []; unlocked = -1
            for t in candidates:
                if t>=unlocked:
                    selected.append(t); unlocked=t+64
            trades = {(t,'B0'):experiment.episode(bars,t,set(sig['top']),atr[t],'B0',0.) for t in selected}
            account = experiment.ledger(bars,selected,trades,start,end,'B0')
            account.pop('curve')
            original = next(a for a in original_accounts if (a['symbol'],a['period'],a['policy'])==(symbol,'B','B0'))
            differences = {k:account[k]-original[k] for k in ('mdd','return','cagr','calmar')}
            if mode=='unrounded':
                assert all(abs(v)<1e-12 for v in differences.values())
            account_results.append({'symbol':symbol,'mode':mode,'period':'B','policy':'B0',**account,
                                    'deltaVsOriginal':differences,'selectedSignalDates':[bars[t][0] for t in selected]})
    assert all(r['matchesClaudePrediction'] for r in rows)
    return {'status':'PASS_SIX_DATES_AND_ORIGINAL_ACCOUNT_REPLAY',
            'scope':'Six claimed signal dates and two frozen B0 accounts only; not a new E1 validation.',
            'createdAt':dt.datetime.now(dt.timezone.utc).isoformat(),
            'sourceFrozenCommit':freeze['commit'],'dataCreatedAt':manifest['createdAt'],
            'manifestSha256':sha((data/'manifest.json').read_bytes()),
            'calendarDatesSha256':calhash,'calendarSessions':len(calendar),
            'calendarMatchesClaude':True,'sourceHashes':sources,'cases':rows,
            'signalChangesFullHistory':changes,'accounts':account_results}

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--study',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    result=run(args.study)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ('status','calendarDatesSha256','cases','accounts')},ensure_ascii=False,indent=2))
