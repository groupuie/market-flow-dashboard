# 「頂K」與「減碼(頂K 隔天收破低點)」參數重新檢驗(當晚收盤賣 → 用收盤進場口徑)
import sys; sys.path.insert(0,"."); from qlib import *
def row(tag,sig,entry="close"):
    out=[tag]
    for per in ("p1","p2"):
        r=evaluate(sig,"top",per,20,vmatch=True,entry=entry); r4=evaluate(sig,"top",per,40,vmatch=False,entry=entry)
        out.append(f"{per}: n={r['n']:4d}({r['rate']:.2f}/檔年) 20日命中{r['hit']-r['base']:+5.1f} 平均{r['mean']-r['bmean']:+5.2f}% 扣大盤{r['xmean']:+5.2f}% 跌≥10% {r['risk']:.0f}/{r['risk_base']:.0f} | 40日命中{r4['hit']-r4['base']:+5.1f} 平均{r4['mean']-r4['bmean']:+5.2f}%")
    print(" | ".join(out),flush=True)
tk=topk()
print("== 現行頂K(漲多:20日+30%/離20日線3ATR/離50日線+25% 任一;碰布林上緣(20,2);收盤離高≥5%)");row("頂K 現行",tk)
print("== 減碼(頂K隔天收破低點,隔天收盤賣)");row("減碼 現行",confirm(tk))
print("== 收盤離高點幅度");[row(f"off={o}",topk(off=o)) for o in (0.0,0.03,0.05,0.07,0.10)]
print("== 20日漲幅門檻(其餘兩條仍在)");[row(f"r20={x}",topk(r20=x)) for x in (0.2,0.3,0.4,9)]
print("== ATR 倍數");[row(f"atr={x}",topk(atrm=x)) for x in (2,3,4,99)]
print("== 離50日線門檻");[row(f"ext={x}",topk(ext=x)) for x in (0.15,0.25,0.35,9)]
print("== 布林寬度");[row(f"bbk={x}",topk(bbk=x)) for x in (1.5,2.0,2.5)]
print("== 不要漲多條件(只看碰上緣+離高5%)");row("無漲多",topk(r20=9,atrm=99,ext=9))
print("== 四段期間(20日命中差):頂K", sub4(tk,"top",20,entry="close"), " 減碼", sub4(confirm(tk),"top",20,entry="close"))
