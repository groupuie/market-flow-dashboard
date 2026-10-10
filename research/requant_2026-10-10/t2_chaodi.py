# 「抄底」(深跌後站回均線 × 全球資金寬鬆)參數重新檢驗
import sys; sys.path.insert(0,"."); from qlib import *
def row(tag,sig):
    out=[tag]
    for per in ("p1","p2"):
        r=evaluate(sig,"bot",per,20,vmatch=False); r4=evaluate(sig,"bot",per,40,vmatch=False)
        out.append(f"{per}: n={r['n']:4d} 20日命中{r['hit']-r['base']:+5.1f} 平均{r['mean']-r['bmean']:+5.2f}% 扣大盤{r['xmean']:+5.2f}% | 40日命中{r4['hit']-r4['base']:+5.1f} 平均{r4['mean']-r4['bmean']:+5.2f}% 再跌≥10% {r4['risk']:.0f}%")
    print(" | ".join(out),flush=True)
print("== 現行:先跌10%(深跌15%)/看20天/站回20日線/冷卻20/氣候≥80%");row("現行",chaodi())
print("== 深跌門檻");[row(f"deep={d}",chaodi(deep=d)) for d in (0.10,0.15,0.20,0.25,0.30)]
print("== 回看天數");[row(f"win={w}",chaodi(win=w)) for w in (10,20,30,40)]
print("== 站回哪條均線");[row(f"ma_x={m}",chaodi(ma_x=m)) for m in (10,20,30,50)]
print("== 冷卻");[row(f"cd={c}",chaodi(cd=c)) for c in (5,10,20,40)]
print("== 氣候門檻");[row(f"cut={c}",chaodi(cut=c)) for c in (-0.01,0.35,0.50,0.65,0.80,0.90)]
print("== 二維:深跌 × 氣候(40日命中差,前半/後半)")
for d in (0.10,0.15,0.20,0.25):
    line=f"deep={d:.2f}:"
    for c in (-0.01,0.50,0.65,0.80,0.90):
        sig=chaodi(deep=d,cut=c); a=evaluate(sig,"bot","p1",40,vmatch=False); b=evaluate(sig,"bot","p2",40,vmatch=False)
        line+=f"  cut{c:.2f} {a['hit']-a['base']:+5.1f}/{b['hit']-b['base']:+5.1f}(n{a['n']}/{b['n']})"
    print(line,flush=True)
print("== 四段期間(40日命中差):現行", sub4(chaodi(),"bot",40), " 不看氣候", sub4(chaodi(cut=-0.01),"bot",40))
