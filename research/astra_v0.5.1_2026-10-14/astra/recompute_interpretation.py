"""Read-only reaggregation of frozen v0.5 output; no market simulation or download."""
from pathlib import Path
from datetime import datetime, timezone
import csv, gzip, hashlib, itertools, json, math, statistics
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'astra-exits-20261013'
RESULT=OLD/'evidence/results.json'
CSV=OLD/'evidence/episodes.csv.gz'
report=json.loads(RESULT.read_text())
POLICIES=('B0','R1','E1','C50')
sets={p:{s:{k:[] for k in POLICIES} for s in ('all','r1_executed','r1_not_executed')} for p in ('A','B')}
identical={'untriggeredPairs':0,'maxAbsReturnDifference':0.,'maxAbsMddDifference':0.}
rows_seen=0; source_symbols=set()
with gzip.open(CSV,'rt',encoding='utf-8',newline='') as f:
    rd=csv.DictReader(f)
    for key, grp in itertools.groupby(rd,lambda r:(r['symbol'],r['date'],r['cost'])):
        raw=list(grp); rows_seen+=len(raw)
        if key[2]!='0.0' or key[0] in ('SPY','QQQ'): continue
        assert len(raw)==4 and {r['policy'] for r in raw}==set(POLICIES), key
        source_symbols.add(key[0]); p=raw[0]['period']
        rows={r['policy']:{'return':float(r['return']),'mdd':float(r['mdd']),
              'exposure':float(r['exposure']),'triggered':r['triggered']=='True'} for r in raw}
        trigger=rows['R1']['triggered']; subgroup='r1_executed' if trigger else 'r1_not_executed'
        for k in POLICIES:
            sets[p]['all'][k].append(rows[k]); sets[p][subgroup][k].append(rows[k])
        if not trigger:
            identical['untriggeredPairs']+=1
            for src,dst in [('return','maxAbsReturnDifference'),('mdd','maxAbsMddDifference')]:
                identical[dst]=max(identical[dst],abs(rows['R1'][src]-rows['B0'][src]))
def mean(xs): return math.fsum(xs)/len(xs) if xs else None
def summary(rows):
    returns=[x['return'] for x in rows]
    return {'n':len(rows),'wins':sum(x>0 for x in returns),'positiveReturnFraction':mean([int(x>0) for x in returns]),
            'meanReturn':mean(returns),'medianReturn':statistics.median(returns) if returns else None,
            'meanEpisodeMdd':mean([x['mdd'] for x in rows]),'meanExposure':mean([x['exposure'] for x in rows])}
def pair(base, other):
    dr=mean([b['return']-a['return'] for a,b in zip(base,other)])
    lessdd=mean([a['mdd']-b['mdd'] for a,b in zip(base,other)])
    return {'n':len(base),'deltaMeanReturn':dr,'meanDrawdownReduction':lessdd,
            'lessDrawdownPerLostReturn':lessdd/(-dr) if dr<0 and lessdd>0 else None,
            'addedReturnPerAddedDrawdown':dr/(-lessdd) if dr>0 and lessdd<0 else None}
res={}; discrepancies=[]
for p in ('A','B'):
    res[p]={}
    for subset,pols in sets[p].items():
        sums={k:summary(v) for k,v in pols.items()}
        pairs={k:pair(pols['B0'],pols[k]) for k in POLICIES if k!='B0'}
        b=sums['B0']; level=b['meanReturn']/b['meanEpisodeMdd']
        incr=pairs['E1']['addedReturnPerAddedDrawdown']
        res[p][subset]={'policies':sums,'pairedVsB0':pairs,'baselineMeanReturnDividedByMeanMdd':level,
                       'e1IncrementalRatioDividedByB0LevelRatio_NOT_EXPOSURE_COUNTERFACTUAL':incr/level if incr is not None else None}
    alln=res[p]['all']['policies']['B0']['n']; tn=res[p]['r1_executed']['policies']['B0']['n']
    res[p]['r1ExecutedCount']=tn;res[p]['allCount']=alln;res[p]['r1ExecutedFraction']=tn/alln
    res[p]['conditionalDeltaIdentity']={k:{'all':res[p]['all']['pairedVsB0']['R1'][k],
                  'triggerFractionTimesConditional':tn/alln*res[p]['r1_executed']['pairedVsB0']['R1'][k]}
                  for k in ('deltaMeanReturn','meanDrawdownReduction')}
    for k in POLICIES:
        old=report['episode_summary'][f'ALL|{p}|0.0|{k}'];new=res[p]['all']['policies'][k]
        assert old['n']==new['n']
        for oldkey,newkey in [('mean','meanReturn'),('median','medianReturn'),('mdd','meanEpisodeMdd'),('win','positiveReturnFraction'),('exposure','meanExposure')]:
            diff=abs(old[oldkey]-new[newkey]);discrepancies.append(diff)
            assert diff<1e-12,(p,k,oldkey,diff)
def dd(nav):
    peak=nav[0];m=0.
    for x in nav:peak=max(peak,x);m=max(m,1-x/peak)
    return m
nav=[1.,1.2,1.08];w=2.;lever=[1+w*(x-1) for x in nav]
output={
 'createdAtUtc':datetime.now(timezone.utc).isoformat(),
 'scope':'Read-only reaggregation of existing frozen v0.5 episodes, not a new strategy backtest or new-stock test.',
 'sourceVersion':report['version'],'ALLDefinition':'All existing study stocks; SPY and QQQ excluded. No outcome-based symbol filter.',
 'primaryCostPerFill':0.0,'units':'Returns and MDD are decimals. Multiply differences by 100 for percentage points. Ratios are dimensionless.',
 'sourceFiles':{str(p.relative_to(HERE.parent.parent)):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in [CSV,RESULT,OLD/'experiment.py',OLD/'protocol.md']},
 'csvRowsRead':rows_seen,'ALLUniqueSymbolsWithEligibleRows':len(source_symbols),
 'summaryComparisons':len(discrepancies),'maxAbsSummaryDifference':max(discrepancies),
 'untriggeredEqualityCheck':identical,
 'formulas':{
  'deltaReturn':'mean(policy_return - B0_return)',
  'drawdownReduction':'mean(B0_episode_mdd - policy_episode_mdd)',
  'R1_or_C50_lessDrawdownPerLostReturn':'drawdownReduction / (-deltaReturn), when both are positive',
  'E1_addedReturnPerAddedDrawdown':'mean(E1_return - B0_return) / mean(E1_episode_mdd - B0_episode_mdd)',
  'B0_levelRatio':'mean(B0_return) / mean(B0_episode_mdd); not marginal exposure efficiency',
  'reportedNearFourArithmetic':'E1_addedReturnPerAddedDrawdown / B0_levelRatio; a ratio of unlike descriptive quantities, NOT an exposure counterfactual',
  'conditionalIdentity':'All-case R1 difference = P(executed R1) * conditional mean difference, because non-executed R1 equals B0',
  'exposureNav':'V_w(t) = 1 + w * (V_1(t) - 1), idealized financing-free static scaling with fixed initial equity',
  'exposureDrawdownGivenPeakAndTrough':'DD_w = w*(P-T)/(1+w*(P-1)); generally not w*DD_1',
  'trueRange':'max(high-low, abs(high-previousClose), abs(low-previousClose))',
  'wilderAtr14':'First 14 true ranges arithmetic mean; thereafter ATR_t=(13*ATR_(t-1)+TR_t)/14; signal-day ATR frozen for R1'
 },
 'periods':res,
 'mddNonlinearityCounterexample':{'baselineNav':nav,'exposureMultiple':w,'scaledNav':lever,
      'baselineMdd':dd(nav),'actualScaledMdd':dd(lever),'invalidLinearGuess':w*dd(nav)},
 'predeclaredMainResult':{'votes':report['votes'],'numericalCriteriaPassed':report['numerical_criteria_passed']},
 'limits':['Triggered R1 cohort is selected using post-entry outcomes; valid for mechanism description, not an entry-time identifiable sample.',
           'No confidence intervals for newly described ratios. Correlated overlapping episodes are not independent trials.',
           'Same-data independent reproduction validates arithmetic/implementation consistency, not a new market edge.',
           'Episode mean MDD is neither account MDD nor portfolio MDD; mean return / mean episode MDD is not Calmar.',
           'No actual increased-exposure B0 policy was simulated; financing/margin/position constraints are not modeled here.']
}
p=HERE/'interpretation_formulas.json'
with p.open('x',encoding='utf-8') as f:json.dump(output,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
print(json.dumps({'summaryComparisons':len(discrepancies),'maxAbsSummaryDifference':max(discrepancies),'periods':res,'counterexample':output['mddNonlinearityCounterexample']},ensure_ascii=False,indent=2))
