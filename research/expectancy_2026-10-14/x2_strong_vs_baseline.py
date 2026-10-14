# Claude(2026-10-14,只描述):Astra 底/回在「強」日 vs 其他日的期望值,各自對比同一天隨便買的基準
#   訊號:vendor 釘住的 sw_series(照網站先四捨五入);賣法 B0(第一個頂隔天開盤,40 根內沒頂則 t+41 開盤);成本 0
#   強 = regime_2026-10-14.json 的 sc ≥ 2(網站現行定義;資料 2021-03-17 起)
#   基準:同一檔股票、每個交易日各一筆、抱 19 根(t+1 開盤 → t+20 開盤);分「強日」與「其他日」
import json, os, importlib.util, numpy as np
HERE=os.path.dirname(os.path.abspath(__file__)); R0=os.path.join(HERE,'..','astra_v0.5.0_2026-10-13')
spec=importlib.util.spec_from_file_location('ad',os.path.join(R0,'vendor/scripts/astra_data.py')); ad=importlib.util.module_from_spec(spec); spec.loader.exec_module(ad)
reg=json.load(open(os.path.join(HERE,'regime_2026-10-14.json'))); SC={d:s for d,s in zip(reg['d'],reg['sc'])}
D='/home/claude/work/astra_v050_data'; m=json.load(open(f'{D}/manifest.json'))['symbols']
uni=[s.strip() for s in open(os.path.join(R0,'universe_266.txt')) if s.strip() and not s.startswith('#')]
G=json.load(open(os.path.join(R0,'vendor/research/swing_tune_2026-10-12/groups.json'))); MAG7=set(G['MAG7'])
LO,HI='2021-03-17','2026-07-31'; H=19
rp=lambda x: round(x,3) if abs(x)>=1 else round(x,5)
sig={'強':[], '其他':[]}; base={'強':[], '其他':[]}; sig7={'強':[], '其他':[]}
for s in uni:
    b=json.load(open(f"{D}/{m[s]['adjustedFile']}"))['bars']; O=np.array([x[1] for x in b]); Dt=[x[0] for x in b]; n=len(b)
    r=ad.sw_series([[x[0],rp(x[1]),rp(x[2]),rp(x[3]),rp(x[4]),x[5]] for x in b]); top=set(r['top'])
    for t in sorted(set(r['bot'])|set(r['b2'])):
        d=Dt[t]
        if not(LO<=d<=HI) or t+41>=n or d not in SC: continue
        ft=next((j for j in range(t+1,t+41) if j in top),None); x=ft+1 if ft is not None else t+41
        ret=O[x]/O[t+1]-1; k='強' if SC[d]>=2 else '其他'
        sig[k].append(ret); (sig7[k].append(ret) if s in MAG7 else None)
    for t in range(199,n-H-1):
        d=Dt[t]
        if not(LO<=d<=HI) or d not in SC: continue
        base['強' if SC[d]>=2 else '其他'].append(O[t+H+1]/O[t+1]-1)
def st(a):
    a=np.array(a); w=a[a>0]; l=a[a<=0]
    return {'n':len(a),'mean':float(a.mean()),'win':float((a>0).mean()),'meanWin':float(w.mean()) if len(w) else None,'meanLoss':float(l.mean()) if len(l) else None,
            'payoff':float(w.mean()/abs(l.mean())) if len(w) and len(l) else None,'p05':float(np.percentile(a,5)),'median':float(np.median(a))}
out={'period':[LO,HI],'hold_baseline':H,'signal':{k:st(v) for k,v in sig.items()},'baseline':{k:st(v) for k,v in base.items()},'signal_MAG7':{k:st(v) for k,v in sig7.items()},
     'strongDays':sum(1 for d in reg['d'] if LO<=d<=HI and SC[d]>=2),'days':sum(1 for d in reg['d'] if LO<=d<=HI)}
json.dump(out,open(os.path.join(HERE,'x2_result.json'),'w'),indent=1,ensure_ascii=False)
print('期間',LO,HI,'強日',out['strongDays'],'/',out['days'])
for k in('強','其他'):
    a,b=out['signal'][k],out['baseline'][k]
    print(f"{k}: 訊號 n={a['n']} 期望值 {100*a['mean']:+.2f}% 勝 {100*a['win']:.1f}% 賺賠比 {a['payoff']:.2f} p05 {100*a['p05']:+.1f}% | 基準 n={b['n']} {100*b['mean']:+.2f}% 勝 {100*b['win']:.1f}% | 超額 {100*(a['mean']-b['mean']):+.2f} 點")
    c=out['signal_MAG7'][k]; print(f"   MAG7 訊號 n={c['n']} 期望值 {100*c['mean']:+.2f}% 勝 {100*c['win']:.1f}% 賺賠比 {c['payoff']:.2f}")
