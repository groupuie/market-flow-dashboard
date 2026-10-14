"""Compare published output snapshots; never infer bar changes from file hashes alone."""
import json, hashlib, statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / 'astra-exits-20261013'
NEW = HERE / 'claude-source/research/astra_v0.5.0_2026-10-13'
def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def key(x): return x['symbol'], x['period'], x['policy']
def main():
    a, b = read(OLD/'data/manifest.json'), read(NEW/'claude_rerun/data_manifest.json')
    aa = {key(x):x for x in read(OLD/'evidence/accounts.json')}
    bb = {key(x):x for x in read(NEW/'claude_rerun/accounts.json')}
    assert aa.keys() == bb.keys()
    exact = ['experiment.py', 'data_tools.py', 'test_experiment.py', 'test_data_tools.py', 'audit_results.py', 'universe_266.txt']
    files = [{'file':f,'original':sha(OLD/f),'claude':sha(NEW/f),'equal':sha(OLD/f)==sha(NEW/f)} for f in exact]
    oldmd = OLD/'delivery/v0.5.0_2026-10-13_23-20-32_減碼出場研究.md'
    if not oldmd.exists(): oldmd=Path.home()/'Downloads'/oldmd.name
    files.append({'file':oldmd.name,'original':sha(oldmd),'claude':sha(NEW/oldmd.name),'equal':sha(oldmd)==sha(NEW/oldmd.name)})
    names = sorted(a['symbols'])
    assert names == sorted(b['symbols'])
    manifest = {'originalCreated':a['createdAt'],'claudeCreated':b['createdAt'],
        'symbols':len(names),'calendarEqual':a['calendarSha256']==b['calendarSha256'],
        'adjustedFileHashesEqual':sum(a['symbols'][s]['adjustedSha256']==b['symbols'][s]['adjustedSha256'] for s in names),
        'rawFileHashesEqual':sum(a['symbols'][s]['rawSha256']==b['symbols'][s]['rawSha256'] for s in names),
        'barCountDifferences':[{'symbol':s,'original':a['symbols'][s]['qa']['usableBars'],'claude':b['symbols'][s]['qa']['usableBars']} for s in names if a['symbols'][s]['qa']['usableBars']!=b['symbols'][s]['qa']['usableBars']],
        'warning':'Adjusted objects contain provenance; unequal complete-file digests do not prove unequal economic bars. Claude bars not available in this checkout.'}
    central = {}
    for p in ['B0','R1','E1','C50']:
        for label,d in [('original',aa),('claude',bb)]:
            xs=sorted([x for x in d.values() if x['period']=='B' and x['policy']==p and 'ALL' in x['groups']], key=lambda x:(x['mdd'],x['symbol']))
            n=len(xs)
            central[label+'_'+p]={'n':n,'median':statistics.median(x['mdd'] for x in xs),'central':[{'rank':i+1,'symbol':xs[i]['symbol'],'mdd':xs[i]['mdd']} for i in [n//2-1,n//2]],'neighbors':[{'rank':i+1,'symbol':xs[i]['symbol'],'mdd':xs[i]['mdd']} for i in range(n//2-4,n//2+4)]}
    differences=[]
    for k in sorted(aa):
        x,y=aa[k],bb[k]
        differences.append({'symbol':k[0],'period':k[1],'policy':k[2], 'originalMDD':x['mdd'],'claudeMDD':y['mdd'],'deltaMDD':y['mdd']-x['mdd'],'originalReturn':x['return'],'claudeReturn':y['return'],'deltaReturn':y['return']-x['return'],'originalCampaigns':x['campaigns'],'claudeCampaigns':y['campaigns'],'originalTransactions':x['transactions'],'claudeTransactions':y['transactions']})
    out={'status':'PUBLISHED_SNAPSHOT_COMPARISON_ONLY','files':files,'manifest':manifest,'central':central,'accountRows':len(aa),'accountDifferences':differences,
         'topMDDChangesB0B':sorted([x for x in differences if x['period']=='B' and x['policy']=='B0'],key=lambda x:abs(x['deltaMDD']),reverse=True)[:15],
         'mddChangedOver01pp':sum(abs(x['deltaMDD'])>.001 for x in differences),
         'returnChangedOver1pp':sum(abs(x['deltaReturn'])>.01 for x in differences)}
    (HERE/'snapshot-comparison.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:out[k] for k in ['files','manifest','central','topMDDChangesB0B','mddChangedOver01pp','returnChangedOver1pp']},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
