# Selectivity: buy index only after deep drawdowns (fresh RSI2 dip), fixed 20-bar hold, non-overlapping. Compare with any day.
import json, sys, statistics as st
D = sys.argv[1]
def bars(s): return json.load(open(f'{D}/adjusted/{s}.json'))['bars']
def rsi2(c):
    out=[None]*len(c); g=l=None
    for i in range(1,len(c)):
        ch=c[i]-c[i-1]; up=max(ch,0); dn=max(-ch,0)
        if i<2: g=up; l=dn; continue
        g=(g+up)/2; l=(l+dn)/2
        out[i]=100 if l==0 else 100-100/(1+g/l)
    return out
def run(s, ddmin, H=20, start='2005-01-01', end='2026-08-31', cost=0.001):
    b=bars(s); d=[x[0] for x in b]; o=[x[1] for x in b]; c=[x[4] for x in b]; r=rsi2(c)
    tr=[]; i=252
    while i < len(b)-H-2:
        if d[i] < start or d[i] > end: i+=1; continue
        hi=max(c[i-251:i+1]); dd=1-c[i]/hi
        cond = (ddmin is None) or (dd >= ddmin and r[i] is not None and r[i] < 10)
        if cond:
            e=i+1; x=e+H
            ret=(o[x]*(1-cost))/(o[e]*(1+cost))-1
            mae=min(c[e:x])/o[e]-1
            tr.append((d[e],ret,mae)); i=x
        else: i+=1
    rs=[t[1] for t in tr]
    return dict(n=len(rs), win=round(100*sum(1 for v in rs if v>0)/len(rs),1), avg=round(100*st.mean(rs),2),
                worst=round(100*min(rs),1), worst_dip=round(100*min(t[2] for t in tr),1),
                years=sorted(set(t[0][:4] for t in tr)) if ddmin else None)
out={}
for s in ['QQQ','SPY']:
    out[s]={ 'any_day(每20天一筆)':run(s,None) }
    for dd in (0.10,0.15,0.20,0.25):
        out[s][f'離一年高點跌>={int(dd*100)}%且短線超賣']=run(s,dd)
print(json.dumps(out, ensure_ascii=False, indent=1))
