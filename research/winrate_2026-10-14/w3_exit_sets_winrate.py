# Win rate is set mostly by exit distances: compare "any day" entries vs RSI2 pullback entries, same +tp / -sl exits.
import json, sys, os, statistics as st
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
def sma(c,n,i): return sum(c[i-n+1:i+1])/n
def trade(o,c,e,tp,sl,maxh,cost=0.001):
    px=o[e]; j=e
    while j < len(c)-1 and j-e < maxh and not (c[j] >= px*(1+tp) or c[j] <= px*(1-sl)): j+=1
    if j >= len(c)-1: return None
    return (o[j+1]*(1-cost))/(px*(1+cost))-1, j+1-e
def run(syms, tp, sl, maxh=120, start='2005-01-01', end='2026-06-30'):
    anyd=[]; sig=[]
    for s in syms:
        b=bars(s); d=[x[0] for x in b]; o=[x[1] for x in b]; c=[x[4] for x in b]; r=rsi2(c)
        for i in range(200, len(b)-2):
            if d[i] < start or d[i] > end: continue
            t=trade(o,c,i+1,tp,sl,maxh)
            if t is None: continue
            anyd.append(t)
            if r[i] is not None and r[i] < 10 and c[i] > sma(c,200,i): sig.append(t)
    def sm(tr):
        rs=[t[0] for t in tr]; return dict(n=len(rs), win=round(100*sum(1 for x in rs if x>0)/len(rs),1), ev=round(100*st.mean(rs),2), hold=round(st.mean(t[1] for t in tr),1))
    return dict(any_day=sm(anyd), rsi2_signal=sm(sig), theory_win_no_skill=round(100*sl/(tp+sl),1))
out={}
out['QQQ_+2/-8']=run(['QQQ'],0.02,0.08)
out['SPY_+2/-8']=run(['SPY'],0.02,0.08)
out['QQQ_+5/-5']=run(['QQQ'],0.05,0.05)
u=[f[:-5] for f in os.listdir(f'{D}/adjusted') if f.endswith('.json')]
out['266_+5/-15']=run(u,0.05,0.15)
out['266_+10/-10']=run(u,0.10,0.10)
print(json.dumps(out, ensure_ascii=False, indent=1))
