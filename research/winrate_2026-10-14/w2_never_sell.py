# "Never sell at a loss": same entry (RSI2<10 & close>SMA200, next open), exit next open after close >= entry*(1+tp); forced exit after maxh bars.
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
def lev2(c):
    # synthetic 2x daily-rebalanced series from closes (no fees/financing) - approximation of QLD/SSO
    y=[c[0]]
    for i in range(1,len(c)): y.append(y[-1]*(1+2*(c[i]/c[i-1]-1)))
    return y
def run(s, tp, maxh=250, start='2005-01-01', end='2026-09-30', cost=0.001, two_x=False):
    b=bars(s); d=[x[0] for x in b]; o=[x[1] for x in b]; c=[x[4] for x in b]
    r=rsi2(c); tr=[]; i=200
    if two_x:
        y=lev2(c)
        # open of 2x approx: scale by overnight move of underlying x2
        yo=[y[0]]+[y[k-1]*(1+2*(o[k]/c[k-1]-1)) for k in range(1,len(c))]
    while i < len(b)-2:
        if d[i] < start or d[i] > end: i+=1; continue
        if r[i] is not None and r[i] < 10 and c[i] > sma(c,200,i):
            e=i+1; P=(yo if two_x else o); C=(y if two_x else c)
            px=P[e]; j=e
            while j < len(b)-1 and j-e < maxh and not (C[j] >= px*(1+tp)): j+=1
            if j >= len(b)-1: break
            ex=P[j+1]; ret=(ex*(1-cost))/(px*(1+cost))-1
            mae=min(C[e:j+1])/px-1
            tr.append((d[e], ret, j+1-e, mae)); i=j+1
        else: i+=1
    return tr
def summ(tr):
    rs=[t[1] for t in tr]; w=[x for x in rs if x>0]; l=[x for x in rs if x<=0]
    hs=sorted(t[2] for t in tr)
    return dict(n=len(rs), win=round(100*len(w)/len(rs),1), avg_win=round(100*st.mean(w),2) if w else None,
        avg_loss=round(100*st.mean(l),2) if l else None, ev=round(100*st.mean(rs),2), worst=round(100*min(rs),1),
        worst_mae=round(100*min(t[3] for t in tr),1), hold_med=hs[len(hs)//2], hold_p90=hs[int(.9*len(hs))], hold_max=hs[-1],
        stuck_over_60=sum(1 for t in tr if t[2]>60))
out={}
for s in ['SPY','QQQ']:
    for tp in (0.02,0.05):
        out[f'{s}_tp{int(tp*100)}']=summ(run(s,tp))
        out[f'{s}_2x_tp{int(tp*100)}']=summ(run(s,tp,two_x=True))
u=[f[:-5] for f in os.listdir(f'{D}/adjusted') if f.endswith('.json')]
allt=[]
for s in u:
    try: allt+=run(s,0.05)
    except Exception: pass
out['ALL_STOCKS_tp5']=summ(allt)
print(json.dumps(out, ensure_ascii=False, indent=1))
