# Claude(2026-10-14,只描述):Astra 底/回(B0 賣法)每筆期望值、賺賠比,對比「任意日買、抱一樣久」的基準
#   資料:research/astra_v0.5.0_2026-10-13/claude_rerun/results.json + episodes.csv.gz(Claude 10/13 重跑)+ /home/claude/work/astra_v050_data
#   用法:python3 -I x1_expectancy_vs_baseline.py  → x1_result.json
import json, gzip, csv, os, collections, numpy as np
HERE=os.path.dirname(os.path.abspath(__file__)); R0=os.path.join(HERE,'..','astra_v0.5.0_2026-10-13')
R=json.load(open(os.path.join(R0,'claude_rerun/results.json')))['episode_summary']
out={'policies':{},'baseline':{},'byYear':{}}
for k,e in R.items():
    g,p,c,pol=k.split('|')
    if g not in('ALL','IDX','MAG7','NDX') or pol not in('B0','E1'): continue
    w=e['win']; out['policies'][k]={'win':w,'meanWin':e['mean_win'],'meanLoss':e['mean_loss'],'payoff':e['mean_win']/abs(e['mean_loss']),
        'expectancy':w*e['mean_win']+(1-w)*e['mean_loss'],'median':e['median'],'p05':e['p05'],'p95':e['p95'],'hold':e['hold'],'n':e['n']}
D='/home/claude/work/astra_v050_data'; m=json.load(open(f'{D}/manifest.json'))['symbols']
G=json.load(open(os.path.join(R0,'vendor/research/swing_tune_2026-10-12/groups.json')))
uni=[s.strip() for s in open(os.path.join(R0,'universe_266.txt')) if s.strip() and not s.startswith('#')]
GS={'ALL':set(uni),'IDX':{'SPY','QQQ'},'MAG7':set(G['MAG7'])&set(uni),'NDX':set(G['NDX'])&set(uni)}
PER={'A':('2010-01-01','2017-12-31'),'B':('2018-01-01','2026-07-31')}
acc={(g,p,h):[] for g in GS for p in PER for h in(20,41)}
for s in sorted(set().union(*GS.values())):
    b=json.load(open(f"{D}/{m[s]['adjustedFile']}"))['bars']; O=np.array([x[1] for x in b]); Dt=[x[0] for x in b]
    for p,(a,z) in PER.items():
        i=np.array([i for i,d in enumerate(Dt) if a<=d<=z and i>=199 and i+41<len(O)],dtype=int)
        if not len(i): continue
        for g,mem in GS.items():
            if s in mem:
                for h in(20,41): acc[(g,p,h)].append(O[i+h]/O[i+1]-1)
for (g,p,h),v in acc.items():
    x=np.concatenate(v); out['baseline'][f'{g}|{p}|hold{h-1}']={'mean':float(x.mean()),'win':float((x>0).mean()),'n':int(len(x))}
yr=collections.defaultdict(list)
with gzip.open(os.path.join(R0,'claude_rerun/episodes.csv.gz'),'rt') as f:
    for r in csv.DictReader(f):
        if r['policy']=='B0' and r['cost']=='0.0' and r['symbol'] not in('SPY','QQQ'): yr[r['date'][:4]].append(float(r['return']))
out['byYear']={y:{'mean':float(np.mean(v)),'win':float(np.mean(np.array(v)>0)),'n':len(v)} for y,v in sorted(yr.items())}
json.dump(out,open(os.path.join(HERE,'x1_result.json'),'w'),indent=1)
for g in GS:
    for p in PER:
        e=out['policies'][f'{g}|{p}|0.0|B0']; b=out['baseline'][f'{g}|{p}|hold19']
        print(f"{g:4s} {p} B0 期望值 {100*e['expectancy']:+.2f}% 勝 {100*e['win']:.1f}% 賺賠比 {e['payoff']:.2f} | 基準抱19根 {100*b['mean']:+.2f}% 勝 {100*b['win']:.1f}% | 超額 {100*(e['expectancy']-b['mean']):+.2f} 點")
