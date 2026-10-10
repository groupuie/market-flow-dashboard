# 「出」(漲多後跌破均線 × 全球資金偏緊)參數重新檢驗:一次動一個參數 + 漲幅門檻×氣候門檻二維 + 前半選參數/後半驗證
import sys; sys.path.insert(0,"."); from qlib import *
def row(tag,sig):
    out=[tag]
    for per in ("p1","p2"):
        r=evaluate(sig,"top",per,20,vmatch=False); r4=evaluate(sig,"top",per,40,vmatch=False)
        out.append(f"{per}: n={r['n']:4d} 20日命中{r['hit']-r['base']:+5.1f} 平均{r['mean']-r['bmean']:+5.2f}% 扣大盤{r['xmean']:+5.2f}% | 40日命中{r4['hit']-r4['base']:+5.1f} 平均{r4['mean']-r4['bmean']:+5.2f}%")
    print(" | ".join(out),flush=True)
print("== 現行:漲幅15%/看20天/跌破20日線/冷卻20/氣候≤35%");row("現行",chu())
print("== 漲幅門檻");[row(f"thr={t}",chu(thr=t)) for t in (0.08,0.10,0.15,0.20,0.25,0.30)]
print("== 回看天數");[row(f"win={w}",chu(win=w)) for w in (10,20,30,40)]
print("== 跌破哪條均線");[row(f"ma_x={m}",chu(ma_x=m)) for m in (10,20,30,50)]
print("== 漲幅相對哪條均線");[row(f"ma_ext={m}",chu(ma_ext=m)) for m in (20,50,100)]
print("== 冷卻天數");[row(f"cd={c}",chu(cd=c)) for c in (5,10,20,40)]
print("== 氣候門檻");[row(f"cut={c}",chu(cut=c)) for c in (0.10,0.20,0.35,0.50,0.65,1.01)]
print("== 二維:漲幅 × 氣候(20日命中差,前半/後半)")
for t in (0.10,0.15,0.20,0.25):
    line=f"thr={t:.2f}:"
    for c in (0.20,0.35,0.50,1.01):
        sig=chu(thr=t,cut=c); a=evaluate(sig,"top","p1",20,vmatch=False); b=evaluate(sig,"top","p2",20,vmatch=False)
        line+=f"  cut{c:.2f} {a['hit']-a['base']:+5.1f}/{b['hit']-b['base']:+5.1f}(n{a['n']}/{b['n']})"
    print(line,flush=True)
print("== 四段期間(20日命中差):現行", sub4(chu(),"top",20), " 不看氣候", sub4(chu(cut=1.01),"top",20))
