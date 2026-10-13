"""Fixed-policy paired exit research. No orders, credentials, or website writes."""
from __future__ import annotations
import argparse, bisect, csv, gzip, hashlib, json, math, random, statistics, subprocess
from collections import defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
POLICIES = ('B0', 'R1', 'E1', 'C50')
PERIODS = {'A': ('2010-01-01', '2017-12-31'), 'B': ('2018-01-01', '2026-07-31')}
BLOCKS = (20, 60, 126)


def quantile(x, p):
    if not x: return None
    y = sorted(x); pos = (len(y)-1)*p; lo = int(pos); hi = min(lo+1, len(y)-1)
    return y[lo]*(hi-pos)+y[hi]*(pos-lo) if hi != lo else y[lo]


def drawdown(nav):
    peak = nav[0]; dd = 0.
    for v in nav:
        peak = max(peak, v)
        dd = max(dd, 1-v/peak)
    return dd


def atr14(B):
    a = [None]*len(B); tr = []
    for i, b in enumerate(B):
        prev = B[i-1][4] if i else b[4]
        tr.append(max(b[2]-b[3], abs(b[2]-prev), abs(b[3]-prev)))
        if i == 13: a[i] = sum(tr[:14])/14
        elif i > 13: a[i] = (a[i-1]*13+tr[i])/14
    return a


def episode(B, t, tops, atr0, policy, cost=0.):
    """All indices local to gap-free bars. events are SELL fractions of initial shares."""
    if policy not in POLICIES: raise ValueError('unknown policy')
    if t < 0 or t+64 >= len(B): raise ValueError('incomplete common forward window')
    if not math.isfinite(atr0) or atr0 <= 0: raise ValueError('invalid frozen ATR')
    if not 0 <= cost < .1: raise ValueError('invalid cost')
    e, end = t+1, t+64
    for b in B[max(0,t-10):end+1]:
        if any(not isinstance(x,(int,float)) or not math.isfinite(x) or x<=0 for x in b[1:5]):
            raise ValueError('invalid OHLC')
        tol=1e-12*max(b[1:5])
        if b[2]+tol < max(b[1],b[3],b[4]) or b[3]-tol > min(b[1],b[2],b[4]):
            raise ValueError('inconsistent OHLC')
    top = next((j for j in range(t+1,t+41) if j in tops), None)
    x = top+1 if top is not None else t+41
    entry = B[e][1]; events = []; triggered = False
    if policy in ('B0','C50'):
        events = [(x,1.,'first_top' if top is not None else 'time40')]
    elif policy == 'R1':
        high_close = -math.inf; qualified = False
        for j in range(e,x):
            high_close = max(high_close,B[j][4])
            qualified = qualified or high_close >= entry+2*atr0
            if qualified and B[j][4] <= high_close-atr0 and j+1 < x:
                events.append((j+1,.5,'profit_giveback')); triggered = True; break
        events.append((x,.5 if triggered else 1.,'first_top' if top is not None else 'time40'))
    elif policy == 'E1':
        if top is None: events = [(x,1.,'time40')]
        else:
            events.append((x,.5,'first_top_half')); triggered = True
            tail = end; why = 'time63'
            for j in range(x,end):
                if B[j][4] < min(b[4] for b in B[j-10:j]):
                    tail = j+1; why = 'prior10_close_low'; break
            events.append((tail,.5,why))
    allocation = .5 if policy == 'C50' else 1.
    shares0 = allocation/(entry*(1+cost)); shares = shares0; cash = 1-allocation
    nav = [1.]; exp = []; hold = 0; turnover = shares0*entry
    emap = defaultdict(list)
    for j,f,why in events: emap[j].append((f,why))
    for j in range(e,end+1):
        for f,why in emap[j]:
            q = shares0*f; value = q*B[j][1]; cash += value*(1-cost); shares -= q; turnover += value
        if shares < -1e-10: raise AssertionError('oversold')
        shares = max(shares,0.)
        mark = B[j][1] if j == end else B[j][4]
        value = cash+shares*mark; nav.append(value)
        if j < end:
            exp.append(shares*mark/value if value else 0.)
            hold += int(shares > 1e-12)
    if abs(shares) > 1e-9: raise AssertionError('unclosed episode')
    return {'return': nav[-1]-1, 'nav': nav, 'events': events, 'mdd': drawdown(nav),
            'giveback': 1-nav[-1]/max(nav), 'exposure': statistics.mean(exp),
            'hold':hold, 'turnover':turnover, 'triggered':triggered, 'transactions':1+len(events)}


def summarize(rows):
    if not rows: return {'n':0}
    ret = [r['return'] for r in rows]; wins=[x for x in ret if x>0]; losses=[x for x in ret if x<0]
    return {'n':len(ret),'win':len(wins)/len(ret),'zero':sum(x==0 for x in ret)/len(ret),
            'mean_win':statistics.mean(wins) if wins else None,'mean_loss':statistics.mean(losses) if losses else None,
            'mean':statistics.mean(ret),'median':statistics.median(ret),'p05':quantile(ret,.05),'p95':quantile(ret,.95),
            **{k:statistics.mean(r[k] for r in rows) for k in ('mdd','giveback','exposure','hold','turnover','transactions','triggered')}}


def paired_bootstrap(daily, blocks=BLOCKS, draws=2000):
    """daily: [(n,sum_delta_dd,sum_delta_return)] INCLUDING zero-count calendar days."""
    out={}; n=len(daily)
    for L in blocks:
        if n < L: out[str(L)]={'valid':0,'error':'short_calendar'}; continue
        rng=random.Random(20261013)
        pref=[[0.] for _ in range(3)]
        for row in daily:
            for k in range(3): pref[k].append(pref[k][-1]+row[k])
        samples=[[],[]]
        for _ in range(draws):
            count=0; dd=rr=0.; remain=n
            while remain:
                start=rng.randrange(n-L+1); length=min(L,remain); stop=start+length
                count += pref[0][stop]-pref[0][start]
                dd += pref[1][stop]-pref[1][start]; rr += pref[2][stop]-pref[2][start]
                remain -= length
            if count: samples[0].append(dd/count); samples[1].append(rr/count)
        out[str(L)]={'valid':len(samples[0]),'dd90':[quantile(samples[0],.05),quantile(samples[0],.95)],
                     'return90':[quantile(samples[1],.05),quantile(samples[1],.95)]}
    return out


def longest_gap_free_segments(B, cal):
    ci={d:i for i,d in enumerate(cal)}; segments=[]; part=[]; previous=None
    for b in B:
        if b[0] not in ci: continue
        i=ci[b[0]]
        if previous is not None and i!=previous+1:
            if part: segments.append(part)
            part=[]
        part.append(b); previous=i
    if part: segments.append(part)
    return segments


def ledger(B, selected, trades, start_index, end_index, policy):
    """Nonoverlapping preselected windows; identical entry indices across policies."""
    value=1.; series=[1.]; exposure_sum=0.; transactions=0; turnover=0.; campaign=0
    sm={t:trades[(t,policy)] for t in selected}; cursor=start_index
    for t in selected:
        e=t+1; end=t+64
        while cursor < e:
            series.append(value); cursor += 1
        r=sm[t]; initial=value
        # daily closes e..end-1; final cash is marked on end day too.
        for v in r['nav'][1:-1]: series.append(initial*v)
        value=initial*r['nav'][-1]; series.append(value); cursor=end+1
        exposure_sum += r['exposure']*63
        transactions += r['transactions']; turnover += initial*r['turnover']; campaign+=1
    while cursor <= end_index: series.append(value); cursor+=1
    years=(date.fromisoformat(B[end_index][0])-date.fromisoformat(B[start_index][0])).days/365.25
    cagr=value**(1/years)-1 if years>0 and value>0 else None; dd=drawdown(series)
    return {'return':value-1,'cagr':cagr,'mdd':dd,'calmar':cagr/dd if dd and cagr is not None else None,
            'exposure':exposure_sum/(end_index-start_index+1),'transactions':transactions,'turnover':turnover,
            'campaigns':campaign,'start':B[start_index][0],'end':B[end_index][0],'days':end_index-start_index+1,
            'curve':series}


def check_freeze():
    f=HERE/'freeze.json'
    if not f.exists(): raise RuntimeError('freeze.json required before market performance')
    snap=json.loads(f.read_text())
    for name,want in snap['files'].items():
        if hashlib.sha256((HERE/name).read_bytes()).hexdigest()!=want: raise RuntimeError('frozen file changed: '+name)
    return snap


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--data-dir',type=Path,default=HERE/'data'); args=parser.parse_args()
    freeze=check_freeze()
    import data_tools as dt
    groups=dt.load_groups(); syms=sorted(set(groups['ALL'])|set(groups['IDX']))
    cal=[b[0] for b in dt.load_symbol('SPY',data_dir=args.data_dir)]
    cal=[d for d in cal if d<='2026-10-12']; ci={d:i for i,d in enumerate(cal)}
    acc=defaultdict(list); paired=defaultdict(list); ledger_rows=[]; excluded=[]; coverage={}; flat=[]; curve_rows=[]
    for si,sym in enumerate(syms):
        print(f'{si+1}/{len(syms)} {sym}',flush=True)
        try: raw=dt.load_symbol(sym,data_dir=args.data_dir,require_clean=False)
        except Exception as exc:
            coverage[sym]={'error':str(exc)}; continue
        member=[g for g,ss in groups.items() if g in ('IDX','MAG7','NDX','ALL') and sym in ss]
        segments=longest_gap_free_segments(raw,cal); cov=defaultdict(int); all_candidates=[]
        for segno,B in enumerate(segments):
            if len(B)<201: continue
            sig=dt.signals(B); buys=sorted(set(sig['bot'])|set(sig['b2'])); tops=set(sig['top']); atr=atr14(B)
            segment_trades={}; segment_candidates=[]
            for t in buys:
                day=B[t][0]; period=next((p for p,(lo,hi) in PERIODS.items() if lo<=day<=hi),None)
                if not period: continue
                cov['signal_candidates']+=1
                if t<199: cov['insufficient_warmup']+=1; continue
                if t+64>=len(B):
                    cov['incomplete_or_gap_window']+=1
                    excluded.append({'symbol':sym,'date':day,'reason':'incomplete_or_gap_window'}); continue
                if atr[t] is None or atr[t]<=0: cov['invalid_atr']+=1; continue
                cov['paired_windows']+=1; segment_candidates.append(t); results={}
                for cost in (0.,.001):
                    for pol in POLICIES:
                        r=episode(B,t,tops,atr[t],pol,cost); results[(cost,pol)]=r
                        row={k:v for k,v in r.items() if k not in ('nav','events')}
                        row.update(symbol=sym,date=day,period=period,policy=pol,cost=cost,entry_date=B[t+1][0],end_date=B[t+64][0],
                                   events=json.dumps([(B[j][0],f,why) for j,f,why in r['events']],separators=(',',':')))
                        flat.append(row)
                        for g in member: acc[(g,period,cost,pol)].append(row)
                        if not cost: segment_trades[(t,pol)]=r
                    base=results[(cost,'B0')]
                    for pol in ('R1','E1','C50'):
                        r=results[(cost,pol)]; pair=(day,base['mdd']-r['mdd'],r['return']-base['return'],sym)
                        for g in member: paired[(g,period,cost,pol)].append(pair)
            # Account diagnosis: availability decided from raw calendar, never outcomes.
            dates=[b[0] for b in B]; idx={d:i for i,d in enumerate(dates)}
            for period,(lo,hi) in PERIODS.items():
                period_days=[d for d in cal if lo<=d<=hi and ci[d]+64<len(cal)]
                if not period_days: continue
                start_day=next(d for d in cal if d>=lo); stop_day=cal[ci[period_days[-1]]+64]
                if start_day not in idx or stop_day not in idx or idx[start_day]<199: continue
                selected=[]; previous_end=-1
                for t in segment_candidates:
                    if lo<=B[t][0]<=hi and t>=previous_end:
                        selected.append(t); previous_end=t+64
                for pol in POLICIES:
                    r=ledger(B,selected,segment_trades,idx[start_day],idx[stop_day],pol)
                    series=r.pop('curve')
                    ledger_rows.append(dict(symbol=sym,period=period,policy=pol,groups=member,**r))
                    if sym in ('SPY','QQQ','AAPL','NVDA'):
                        curve_rows.append(dict(symbol=sym,period=period,policy=pol,curve=series,start=start_day,end=stop_day))
        eligibility={}; raw_dates={b[0] for b in raw}
        for period,(lo,hi) in PERIODS.items():
            ok=any(r['symbol']==sym and r['period']==period and r['policy']=='B0' for r in ledger_rows)
            start_day=next(d for d in cal if d>=lo)
            tail=[d for d in cal if lo<=d<=hi and ci[d]+64<len(cal)]
            stop_day=cal[ci[tail[-1]]+64]
            reason=('eligible' if ok else 'missing_period_start' if start_day not in raw_dates else
                    'missing_common_end' if stop_day not in raw_dates else
                    'gap_or_insufficient_200_bar_warmup')
            eligibility[period]={'eligible':ok,'reason':reason,'start':start_day,'end':stop_day}
        coverage[sym]=dict(cov,source_bars=len(raw),continuous_segments=len(segments),account_eligibility=eligibility)
    outdir=HERE/'evidence'; outdir.mkdir(exist_ok=True)
    with gzip.open(outdir/'episodes.csv.gz','wt',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(flat[0])); w.writeheader(); w.writerows(flat)
    (outdir/'coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2))
    (outdir/'excluded-windows.json').write_text(json.dumps(excluded,indent=2))
    (outdir/'accounts.json').write_text(json.dumps(ledger_rows,indent=2))
    (outdir/'account-curves.json').write_text(json.dumps(curve_rows,separators=(',',':')))
    sums={'|'.join(map(str,k)):summarize(v) for k,v in acc.items()}; tests={}; votes=defaultdict(int)
    daily_out=[]
    for key,rows in paired.items():
        g,period,cost,pol=key; label='|'.join(map(str,key)); lo,hi=PERIODS[period]
        daily=defaultdict(lambda:[0,0.,0.])
        for d,dd,rr,sym in rows:
            daily[d][0]+=1; daily[d][1]+=dd; daily[d][2]+=rr
        dates=[d for d in cal if lo<=d<=hi and ci[d]+64<len(cal)]
        for d in dates: daily_out.append({'group':g,'period':period,'cost':cost,'policy':pol,'date':d,'n':daily[d][0],'sum_dd':daily[d][1],'sum_return':daily[d][2]})
        s={'n':len(rows),'delta_dd':statistics.mean(r[1] for r in rows),'delta_return':statistics.mean(r[2] for r in rows)}
        if not cost and pol=='R1':
            s['bootstrap']=paired_bootstrap([daily[d] for d in dates])
            checks={'enough':len(rows)>=(30 if g=='IDX' else 50),'dd_effect':s['delta_dd']>=.01,
                    'dd_ci':all(s['bootstrap'][str(L)]['valid']==2000 and s['bootstrap'][str(L)]['dd90'][0]>0 for L in (20,60)),
                    'return_noninferior':all(s['bootstrap'][str(L)]['valid']==2000 and s['bootstrap'][str(L)]['return90'][0]>-.005 for L in (20,60))}
            s['checks']=checks;s['passed']=all(checks.values());votes[period]+=int(s['passed'])
            rr=[x for x in rows if x[3] not in ('SNDK','WOLF','NBIS')]
            s['identity_exclusion_sensitivity']={'n':len(rr),'delta_dd':statistics.mean(x[1] for x in rr),'delta_return':statistics.mean(x[2] for x in rr)} if rr else None
        tests[label]=s
    with gzip.open(outdir/'paired-dates.csv.gz','wt',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(daily_out[0]));w.writeheader();w.writerows(daily_out)
    account_summary={}
    for g in ('IDX','MAG7','NDX','ALL'):
        for p in PERIODS:
            for pol in POLICIES:
                rr=[r for r in ledger_rows if g in r['groups'] and p==r['period'] and pol==r['policy']]
                account_summary[f'{g}|{p}|{pol}']={'n_stocks':len(rr),**{k:statistics.median(r[k] for r in rr if r[k] is not None) if any(r[k] is not None for r in rr) else None for k in ('return','cagr','mdd','calmar','exposure','transactions','campaigns')}}
    data_manifest=args.data_dir/'manifest.json'
    result={'version':'0.5.0','freeze':freeze,'source_commit':'1dbaddfcb1e75f772e550faa191a3ca9ea5834c8',
            'data_manifest_sha256':hashlib.sha256(data_manifest.read_bytes()).hexdigest() if data_manifest.exists() else None,
            'calendar_last':cal[-1],'mature_signal_last':cal[-65],'groups':{g:len(v) for g,v in groups.items()},
            'episode_summary':sums,'paired_tests':tests,'votes':dict(votes),'numerical_criteria_passed':all(votes[p]>=3 for p in PERIODS),
            'account_summary':account_summary,'status':'EXPLORATORY_CURRENT_UNIVERSE_HISTORICAL_COMPARISON'}
    (outdir/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    print(json.dumps({'votes':dict(votes),'numeric_pass':result['numerical_criteria_passed'],'mature_signal_last':result['mature_signal_last']},ensure_ascii=False),flush=True)


if __name__=='__main__': main()
