"""Descriptive audit of already-seen 266 names. Never evaluates the 345-name holdout."""
from __future__ import annotations
import argparse, bisect, collections, datetime, hashlib, importlib.util, json
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
LO, HI, COST, BLOCK, DRAWS, SEED = '2021-03-17', '2026-07-31', .001, 126, 2000, 20261014
ORIGINAL_MANIFEST = 'e8e8e1451ed23f7cb091820c536d16467a6362111020a6b953882176507f2c3f'   # Claude 診斷:改成 Claude 10/13 快照的 manifest(不是 Astra 原件)
ORIGINAL_FREEZE = '3ef884394b836c39f43bbef7ebd16aa7900a541fb9c7fcdd5fecb6f16c254fe6'
REGIME_HASH = '5c61b600aa6a711345e499f30cecbd8e86ecef312aa838d81002137dfec79f6b'
X2_HASH = '43fa126f116b33fccf6a7d05b8eac352b1a7a47e85675967085f943b62423924'

def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def net(r, c=COST): return (1+r)*(1-c)/(1+c)-1
def stats(x):
    a=np.asarray(x,dtype=float); w=a[a>0]; l=a[a<0]
    if not len(a): return {'n':0}
    return {'n':len(a),'mean':float(a.mean()),'win':float(np.mean(a>0)),
            'meanWin':float(w.mean()) if len(w) else None,
            'meanLoss':float(l.mean()) if len(l) else None,
            'payoff':float(w.mean()/-l.mean()) if len(w) and len(l) else None,
            'median':float(np.median(a)),'p05':float(np.quantile(a,.05)),
            'expectedShortfall05':float(a[a<=np.quantile(a,.05)].mean())}

def estimates(total):
    # count/sum pairs; the entire calendar, including zero-count days, is sampled.
    ns,sb,nb,bb,nd,sd,nw,sw,nbd,sbd=total
    return [sb/ns-bb/nb if ns and nb else np.nan,
            sd/nd if nd else np.nan,sw/nw if nw else np.nan,sbd/nbd if nbd else np.nan]

def bootstrap(daily, draws=DRAWS, block=BLOCK, seed=SEED):
    a=np.asarray(daily,dtype=float); n=len(a)
    if n<block: raise ValueError('calendar shorter than block')
    pref=np.vstack([np.zeros(a.shape[1]),np.cumsum(a,axis=0)])
    rng=np.random.default_rng(seed); samples=[]
    for _ in range(draws):
        total=np.zeros(a.shape[1]); remain=n
        while remain:
            length=min(block,remain); start=int(rng.integers(0,n-block+1))
            total+=pref[start+length]-pref[start]; remain-=length
        samples.append(estimates(total))
    samples=np.asarray(samples)
    names=['legacy_pooled_b0_minus_fixed19_all','fixed19_same_date_non_signal_date_equal',
           'fixed19_same_date_non_signal_signal_weighted','same_b0_rule_same_date_non_signal_date_equal']
    point=estimates(a.sum(axis=0)); out={}
    for j,name in enumerate(names):
        v=samples[:,j];v=v[np.isfinite(v)]
        out[name]={'mean':float(point[j]),'ci95':np.quantile(v,[.025,.975]).tolist() if len(v) else None,'validDraws':len(v)}
    return out

def self_test():
    assert abs((net(.05)-net(.03))-(.05-.03)*(1-COST)/(1+COST))<1e-14
    assert net(.05)-net(.03)>0
    assert net(1.3/1.1-1)-net(1.3/1.1-1)==0
    # Two dates: one trade +10%, nine trades -2%. Date and trade weights differ.
    assert abs(np.mean([.10,-.02])-.04)<1e-14
    assert abs((.10+9*(-.02))/10-(-.008))<1e-14
    days=np.zeros((252,10));days[10]=[1,.04,2,.04,1,.02,1,.02,1,.02]
    b=bootstrap(days,draws=100,block=126)
    assert b['fixed19_same_date_non_signal_date_equal']['validDraws']<100
    assert all(abs(v-.02)<1e-14 for v in b['fixed19_same_date_non_signal_date_equal']['ci95'])
    # A positive unlevered two-day return becomes negative under daily 2x resetting.
    base=(1+.10)*(1-.09)-1; lever=(1+2*.10)*(1-2*.09)-1
    assert base>0 and lever<0 and abs(lever-2*base)>.01
    return {'symmetric_cost':'PASS','identical_trade':'PASS','date_weights':'PASS',
            'calendar_zero_days':'PASS','daily_leverage':'PASS','base_example':base,'leveraged_example':lever}

def main(study, output):
    study=Path(study).resolve();output=Path(output);output.mkdir(parents=True,exist_ok=True)
    manifest_path=study/'data/manifest.json'
    if digest(manifest_path)!=ORIGINAL_MANIFEST: raise ValueError('not the original Astra data manifest')
    if digest(study/'freeze.json')!=ORIGINAL_FREEZE: raise ValueError('not the original code freeze')
    freeze=json.loads((study/'freeze.json').read_text())
    for file,sha in freeze['files'].items():
        if digest(study/file)!=sha: raise ValueError('frozen code changed: '+file)
    spec=importlib.util.spec_from_file_location('audit_data_tools',study/'data_tools.py')
    dt=importlib.util.module_from_spec(spec);spec.loader.exec_module(dt)
    manifest=json.loads(manifest_path.read_text()); universe=dt.load_groups()['ALL']
    regime_path=HERE/'source-audit/source/research/expectancy_2026-10-14/regime_2026-10-14.json'
    if digest(regime_path)!=REGIME_HASH: raise ValueError('regime snapshot changed')
    if digest(regime_path.parent/'x2_result.json')!=X2_HASH: raise ValueError('official x2 result changed')
    reg=json.loads(regime_path.read_text());sc=dict(zip(reg['d'],reg['sc']))
    cal=json.loads((study/'data/calendar.json').read_text())
    if isinstance(cal,dict): cal=cal.get('dates',cal.get('calendar'))
    # Use frozen SPY to avoid ambiguity in a calendar object's metadata shape.
    if digest(study/'data/adjusted/SPY.json')!=manifest['symbols']['SPY']['adjustedSha256']: raise ValueError('SPY hash mismatch')
    spy=json.loads((study/'data/adjusted/SPY.json').read_text())['bars']
    cal=[r[0] for r in spy]; ci={d:i for i,d in enumerate(cal)}
    dates=[d for d in cal if LO<=d<=HI and d in sc]
    assert len(dates)==len(set(dates))
    records=collections.defaultdict(list);legacy_signal=collections.defaultdict(list);legacy_base=collections.defaultdict(list)
    inputs={};gaps=[]
    for pos,s in enumerate(universe):
        p=study/'data'/manifest['symbols'][s]['adjustedFile']
        if digest(p)!=manifest['symbols'][s]['adjustedSha256']: raise ValueError('bar hash mismatch '+s)
        bars=json.loads(p.read_text())['bars'];inputs[s]=digest(p)
        rounded=[[b[0],*(round(v,3 if abs(v)>=1 else 5) for v in b[1:5]),b[5]] for b in bars]
        sig=dt.signals(rounded);buy=set(sig['bot'])|set(sig['b2']);tops=sorted(sig['top'])
        op=np.asarray([b[1] for b in bars]);n=len(bars)
        for t in range(n):
            d=bars[t][0]
            if not LO<=d<=HI or d not in sc: continue
            if t>=199 and t+20<n: legacy_base[d].append(float(op[t+20]/op[t+1]-1))
            if t+41>=n: continue
            topi=bisect.bisect_right(tops,t)
            top=tops[topi] if topi<len(tops) and tops[topi]<=t+40 else None
            x=top+1 if top is not None else t+41
            b0=float(op[x]/op[t+1]-1);fixed=float(op[t+20]/op[t+1]-1)
            if t in buy: legacy_signal[d].append(b0)
            if t<199: continue
            if any(ci.get(bars[j][0],-999)-ci.get(bars[j-1][0],-999)!=1 for j in range(t+1,t+42)):
                gaps.append([s,d]);continue
            records[d].append((s,t in buy,net(fixed),net(b0),x-(t+1)))
        if (pos+1)%50==0: print('Validated',pos+1,'of',len(universe),flush=True)
    results={};daily_rows=[];same_identity_max=0.
    for state in ('strong','other'):
        is_state=lambda d:(sc[d]>=2)==(state=='strong')
        selected_days=[d for d in dates if is_state(d)]
        oldsig=[v for d in selected_days for v in legacy_signal[d]]
        oldbase=[v for d in selected_days for v in legacy_base[d]]
        daily=[];fixed_all=[];same_day_all_diffs=[];holds=[];excluded_dates=[]
        for d in dates:
            if not is_state(d): daily.append([0.]*10);continue
            ls,lb=legacy_signal[d],legacy_base[d]
            row=[len(ls),sum(net(v) for v in ls),len(lb),sum(net(v) for v in lb),0,0.,0,0.,0,0.]
            ss=[r for r in records[d] if r[1]];cc=[r for r in records[d] if not r[1]]
            if ss and cc:
                fd=float(np.mean([r[2] for r in ss])-np.mean([r[2] for r in cc]))
                bd=float(np.mean([r[3] for r in ss])-np.mean([r[3] for r in cc]))
                row[4:]=[1,fd,len(ss),len(ss)*fd,1,bd]
                fixed_all.extend(r[2] for r in ss);holds.extend(r[4] for r in ss)
                same_day_all_diffs.append(float(np.mean([r[2] for r in ss])-np.mean([r[2] for r in records[d]])))
                for r in ss: same_identity_max=max(same_identity_max,abs(r[3]-r[3]))
            else: excluded_dates.append(d)
            daily.append(row);daily_rows.append({'date':d,'state':state,'ns':len(ss),'nc':len(cc),'aggregate':row})
        strong_segments=0;prev=False
        for d in dates:
            yes=is_state(d)
            if yes and not prev:strong_segments+=1
            prev=yes
        results[state]={'dates':len(selected_days),'contiguousRuns':strong_segments,
            'byYear':dict(collections.Counter(d[:4] for d in selected_days)),
            'legacyGrossSignalB0':stats(oldsig),'legacyGrossBaselineFixed19':stats(oldbase),
            'legacyNetSignalB0':stats([net(v) for v in oldsig]),'legacyNetBaselineFixed19':stats([net(v) for v in oldbase]),
            'netFixed19Signal':stats(fixed_all),'pairedDateCount':len(same_day_all_diffs),
            'excludedPairDates':excluded_dates,'meanB0HoldIntervals':float(np.mean(holds)) if holds else None,
            'fixed19_same_date_all_date_equal':float(np.mean(same_day_all_diffs)) if same_day_all_diffs else None,
            'bootstrap':bootstrap(daily)}
    official=json.loads((regime_path.parent/'x2_result.json').read_text())
    comparison={}
    for state,label in [('strong','強'),('other','其他')]:
        ours=results[state]
        comparison[state]={k:{'nDifference':ours[key]['n']-official[k][label]['n'],
                               'meanDifference':ours[key]['mean']-official[k][label]['mean']}
                            for k,key in [('signal','legacyGrossSignalB0'),('baseline','legacyGrossBaselineFixed19')]}
    result={'createdAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'status':'POST_HOC_OLD_UNIVERSE_DESCRIPTIVE_NOT_A_PASS_TEST','period':[LO,HI],
      'manifestSha256':digest(manifest_path),'regimeSha256':digest(regime_path),'universeN':len(universe),
      'calendarN':len(dates),'costPerSide':COST,'fixedOpenIntervals':19,
      'bootstrap':{'block':BLOCK,'draws':DRAWS,'seed':SEED,'rng':'numpy.default_rng','interval':.95,'zeroDaysRetained':True,'multipleTestingAdjusted':False},
      'gapExclusions':gaps,'identicalTradeAlgebraExampleMaxDifference':same_identity_max,
      'identicalTradeCheckScope':'Algebraic identity only, not an independent market replay.',
      'officialSnapshotComparison':comparison,'results':results,'tests':self_test(),
      'limitations':['Retrospective current universe and regime.','Existing 266 names and states already inspected.',
        'Neither intervals nor positive estimates are evidence of independently confirmed alpha.',
        'No 345-name performance calculated.','Date-matched groups are not sector/beta matched.',
        'B0 same-rule control still permits different holding lengths; it is a descriptive policy comparison.',
        'Two thousand resamples do not create new independent panic episodes.']}
    (output/'audit-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    (output/'daily-aggregates.json').write_text(json.dumps(daily_rows,separators=(',',':'))+'\n')
    (output/'input-bars-sha256.json').write_text(json.dumps(inputs,indent=2)+'\n')
    print(json.dumps({'comparison':comparison,'estimates':{s:results[s]['bootstrap'] for s in results}},ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--self-test',action='store_true');p.add_argument('--study',type=Path,default=HERE.parent/'astra-exits-20261013');p.add_argument('--output',type=Path,default=HERE/'audit-output');a=p.parse_args()
    if a.self_test: print(json.dumps(self_test()))
    else: main(a.study,a.output)
