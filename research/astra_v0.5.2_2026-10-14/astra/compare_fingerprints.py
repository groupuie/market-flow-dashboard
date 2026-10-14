"""Compare saved economic manifests. Missing calendar evidence means unknown."""
import argparse
import json
from pathlib import Path

def compare(actual, expected):
    a,e=actual['symbols'],expected['symbols']
    common=sorted(a.keys()&e.keys())
    ac,ec=actual.get('calendarDatesSha256'),expected.get('calendarDatesSha256')
    status='not_provided' if not ac or not ec else ('equal' if ac==ec else 'different')
    return {
        'common':len(common),
        'onlyActual':sorted(a.keys()-e.keys()),'onlyExpected':sorted(e.keys()-a.keys()),
        'equalEconomicHashes':sum(a[s]['barsSha256']==e[s]['barsSha256'] for s in common),
        'unequalEconomicHashes':sum(a[s]['barsSha256']!=e[s]['barsSha256'] for s in common),
        'differentLengthsDates':[s for s in common if any(a[s][k]!=e[s][k] for k in ('bars','first','last'))],
        'calendarComparison':status,
        'calendarDatesEqual':None if status=='not_provided' else status=='equal',
        'warning':'Unequal hashes do not identify the cause or size of price changes.'}

def self_test():
    a={'symbols':{},'calendarDatesSha256':'aaa'}
    assert compare(a,{'symbols':{}})['calendarDatesEqual'] is None
    assert compare(a,a)['calendarDatesEqual'] is True
    assert compare(a,{'symbols':{},'calendarDatesSha256':'bbb'})['calendarDatesEqual'] is False
    return {'status':'PASS','tests':3}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--actual',type=Path);p.add_argument('--expected',type=Path)
    p.add_argument('--output',type=Path);p.add_argument('--self-test',action='store_true')
    args=p.parse_args()
    if args.self_test: print(json.dumps(self_test()))
    else:
        if not all((args.actual,args.expected,args.output)): p.error('actual, expected and output required')
        result=compare(json.loads(args.actual.read_text()),json.loads(args.expected.read_text()))
        args.output.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
