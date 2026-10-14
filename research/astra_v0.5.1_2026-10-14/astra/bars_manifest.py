"""Economic OHLCV digests without download metadata; stdlib-only Python 3."""
import argparse, csv, hashlib, io, json, math
from pathlib import Path

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def normalize(bars):
    out=[]
    for bar in bars:
        if len(bar)!=6: raise ValueError('Expected [date,open,high,low,close,volume]')
        d,*v=bar
        if not isinstance(d,str) or len(d)!=10: raise ValueError('Invalid date')
        prices=[float(x) for x in v[:4]]
        if any(not math.isfinite(x) or x<=0 for x in prices): raise ValueError('Invalid price')
        volume=float(v[4])
        if not math.isfinite(volume) or volume<0 or not volume.is_integer(): raise ValueError('Invalid volume')
        out.append([d]+[x.hex() for x in prices]+[int(volume)])
    if any(out[i][0]>=out[i+1][0] for i in range(len(out)-1)): raise ValueError('Dates not strictly ascending')
    return out

def bar_hash(bars): return digest(normalize(bars))

def build(data_dir, verify=True, selected=None):
    manifest=json.loads((data_dir/'manifest.json').read_text())
    symbols={}
    for symbol,m in sorted(manifest['symbols'].items()):
        if selected and symbol not in selected: continue
        p=data_dir/m['adjustedFile']; blob=p.read_bytes()
        actual=hashlib.sha256(blob).hexdigest()
        if verify and actual!=m['adjustedSha256']: raise ValueError('File mismatch: '+symbol)
        x=json.loads(blob); bars=x['bars']
        if x['symbol']!=symbol: raise ValueError('Wrong symbol')
        symbols[symbol]={'bars':len(bars),'first':bars[0][0] if bars else None,'last':bars[-1][0] if bars else None,
                         'barsSha256':bar_hash(bars),'adjustedFileSha256':actual}
    cal=json.loads((data_dir/manifest['calendarFile']).read_text())
    return {'schema':'astra-economic-bars-v1','serialization':'JSON compact ASCII rows: date, float.hex OHLC, integer volume; metadata excluded',
            'manifestSha256':hashlib.sha256((data_dir/'manifest.json').read_bytes()).hexdigest(),
            'createdAt':manifest['createdAt'],'calendarDatesSha256':digest(cal['dates']),
            'calendarSessions':len(cal['dates']),'symbols':symbols}

def self_test():
    bars=[['2020-01-02',10,12,9,11,100]]
    a={'bars':bars,'retrievedAt':'a'}; b={'bars':bars,'retrievedAt':'b'}
    assert bar_hash(a['bars'])==bar_hash(b['bars'])
    assert bar_hash(bars)==bar_hash([['2020-01-02',10.0,12.,9.,11.,100.]])
    assert bar_hash(bars)!=bar_hash([['2020-01-02',10,12,9,11.00001,100]])
    assert bar_hash(bars)!=bar_hash([['2020-01-02',10,12,9,11,101]])
    try: normalize(bars+bars)
    except ValueError: pass
    else: raise AssertionError('Duplicate date accepted')
    return {'tests':5,'status':'PASS'}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-dir',type=Path)
    ap.add_argument('--output',type=Path)
    ap.add_argument('--expect',type=Path,help='Astra original economic-bars.json to compare')
    ap.add_argument('--symbols',help='Optional comma-separated symbols')
    ap.add_argument('--self-test',action='store_true')
    args=ap.parse_args()
    if args.self_test: print(json.dumps(self_test())); return
    if args.data_dir is None or args.output is None: ap.error('--data-dir and --output required')
    out=build(args.data_dir, selected=set(args.symbols.split(',')) if args.symbols else None)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    s=io.StringIO(newline=''); w=csv.writer(s,lineterminator='\n')
    w.writerow(['symbol','bars','first','last','barsSha256','adjustedFileSha256'])
    for symbol,row in out['symbols'].items(): w.writerow([symbol]+[row[k] for k in ['bars','first','last','barsSha256','adjustedFileSha256']])
    args.output.with_suffix('.csv').write_text(s.getvalue())
    print(json.dumps({'symbols':len(out['symbols']),'calendarSessions':out['calendarSessions'],'output':str(args.output)}))
    if args.expect:
        expected=json.loads(args.expect.read_text()); e=expected['symbols']; a=out['symbols']
        common=sorted(a.keys()&e.keys())
        comparison={'common':len(common),'onlyActual':sorted(a.keys()-e.keys()),'onlyExpected':sorted(e.keys()-a.keys()),
                    'calendarDatesEqual':out['calendarDatesSha256']==expected['calendarDatesSha256'],
                    'barsEqual':[s for s in common if a[s]['barsSha256']==e[s]['barsSha256']],
                    'barsDifferent':[s for s in common if a[s]['barsSha256']!=e[s]['barsSha256']],
                    'warning':'A difference is exact floating-value inequality, not a material-change diagnosis. Compare dates/values and trade events next.'}
        args.output.with_name(args.output.stem+'-comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
        print(json.dumps({k:v for k,v in comparison.items() if k not in ['barsEqual','warning']}))

if __name__=='__main__': main()
