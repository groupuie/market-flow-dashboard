# High-win-rate demo: "pullback in uptrend, sell first bounce" (Connors-style RSI2), daily bars, next-open execution.
import json, sys, os, statistics as st
D = sys.argv[1]
def bars(s):
    return json.load(open(f'{D}/adjusted/{s}.json'))['bars']
def rsi2(c):
    out=[None]*len(c); g=l=None
    for i in range(1,len(c)):
        ch=c[i]-c[i-1]; up=max(ch,0); dn=max(-ch,0)
        if i<2: g=up if g is None else g; l=dn if l is None else l; continue
        if i==2: g=(g+up)/2; l=(l+dn)/2
        else: g=(g*1+up)/2; l=(l*1+dn)/2
        out[i]=100 if l==0 else 100-100/(1+g/l)
    return out
def sma(c,n,i): return sum(c[i-n+1:i+1])/n if i>=n-1 else None
def run(s, start='2005-01-01', end='2026-09-30', cost=0.001):
    b=bars(s); d=[x[0] for x in b]; o=[x[1] for x in b]; c=[x[4] for x in b]
    r=rsi2(c); tr=[]; i=200
    while i < len(b)-2:
        if d[i] < start or d[i] > end: i+=1; continue
        s200=sma(c,200,i)
        if r[i] is not None and r[i] < 10 and c[i] > s200:
            e=i+1; px=o[e]; j=e
            while j < len(b)-1 and not (c[j] > sma(c,5,j)): j+=1
            if j >= len(b)-1: break
            ex=o[j+1]; ret=(ex*(1-cost))/(px*(1+cost))-1
            mae=min(c[e:j+1])/px-1
            tr.append((d[e], ret, j+1-e, mae)); i=j+1
        else: i+=1
    return tr
def summ(tr):
    if not tr: return {}
    rs=[t[1] for t in tr]; w=[x for x in rs if x>0]; l=[x for x in rs if x<=0]
    return dict(n=len(rs), win=round(100*len(w)/len(rs),1), avg_win=round(100*st.mean(w),2) if w else None,
                avg_loss=round(100*st.mean(l),2) if l else None, ev=round(100*st.mean(rs),2),
                worst=round(100*min(rs),2), worst_mae=round(100*min(t[3] for t in tr),2),
                hold=round(st.mean(t[2] for t in tr),1), per_year=round(len(rs)/21.75,1))
res={}
for s in ['SPY','QQQ']:
    tr=run(s); res[s]=summ(tr)
    worst=sorted(tr,key=lambda t:t[1])[:3]; res[s]['worst3']=[(t[0],round(100*t[1],1),t[2]) for t in worst]
    # by period
    res[s]['2005-2017']=summ([t for t in tr if t[0]<'2018'])
    res[s]['2018-2026']=summ([t for t in tr if t[0]>='2018'])
    # 2x approx: daily-compounded 2x of underlying over the holding window (no fees/financing)
# individual stocks for contrast
u=[f[:-5] for f in os.listdir(f'{D}/adjusted') if f.endswith('.json')]
allt=[]
for s in u:
    try: allt+=run(s)
    except Exception as ex: pass
res['ALL_STOCKS']=summ(allt); res['ALL_STOCKS']['worst3']=[(round(100*t[1],1)) for t in sorted(allt,key=lambda t:t[1])[:3]]
print(json.dumps(res, ensure_ascii=False, indent=1))
