# s2:s1 的延伸 —— 加「大盤也超賣」與「深跌站回 20 日線(抄底,不看資金氣候)」;同口徑(10 天、隔天開盤進場)
import numpy as np, pandas as pd, json, os, warnings; warnings.filterwarnings("ignore")
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "s1_candidates.py"), encoding="utf-8").read().split("CAND = {")[0]
exec(src)
q = cols.index("QQQ")
qR2 = R2[:, q]; qOS = np.nan_to_num(qR2, nan=50) <= 10; qOS20 = np.nan_to_num(qR2, nan=50) <= 20
qLB = Cv[:, q] <= lo[:, q]
QQ = pd.Series(Cv[:, q]); qdd = (QQ / QQ.rolling(252, min_periods=200).max() - 1).values
mkt_os3 = lastk(qOS20[:, None] | qLB[:, None], 3)                      # 近 3 天大盤(QQQ)也超賣:RSI2≤20 或 碰布林下緣
stock_bot = lastk(osold10 | belowLB | td9b) & revUp
# 抄底(不看資金):近 20 根內曾低於 50 日線 15% 以上,今天第一次收回 20 日線上(冷卻 20 根)— 與網站 fcSeriesJS 同式
s20 = C.rolling(20, min_periods=20).mean().values; s50 = C.rolling(50, min_periods=50).mean().values
rel = Cv / s50 - 1; dip = pd.DataFrame(rel).rolling(20, min_periods=20).min().values
upx = np.zeros_like(belowLB); upx[1:] = (Cv[1:] > s20[1:]) & (Cv[:-1] <= s20[:-1])
def cool_turn(turn, ok, k=20):   # 冷卻以「轉折」計(dip≤−10% 的站回都算轉折),符合 ok 才標
    out = np.zeros_like(turn)
    for j in range(turn.shape[1]):
        last = -10**9
        for i in np.flatnonzero(turn[:, j]):
            if i - last > k:
                last = i
                if ok[i, j]: out[i, j] = True
    return out
turn = upx & (np.nan_to_num(dip, nan=0) <= -0.10)
cdb = cool_turn(turn, np.nan_to_num(dip, nan=0) <= -0.15, 20)
G20 = np.log(np.roll(Cv, -20, axis=0) / np.roll(Ov, -1, axis=0)); G20[-20:] = np.nan
G40 = np.log(np.roll(Cv, -40, axis=0) / np.roll(Ov, -1, axis=0)); G40[-40:] = np.nan
G[20] = G20; G[40] = G40
def stat2(mask, gm, hs=(10, 20, 40)):
    o = {}
    for nm, ps in (("前段", per & ~half2), ("後段", per & half2), ("全期", per)):
        for h in hs:
            sel = mask & ps[:, None] & np.array(gm)[None, :]; g = G[h][sel]; g = g[~np.isnan(g)]
            b = G[h][ps[:, None] & np.array(gm)[None, :]]; b = b[~np.isnan(b)]
            o[f"{nm}{h}"] = (len(g), round((g > 0).mean() * 100, 1) if len(g) else None, round((b > 0).mean() * 100, 1), round(np.mean(g) * 100, 2) if len(g) else None)
    return o
CASES = {"個股短底(s1)": cool(stock_bot & ~np.isnan(Cv), 5),
         "個股短底 + 大盤也超賣(近3天 QQQ RSI2≤20 或碰下緣)": cool(stock_bot & mkt_os3 & ~np.isnan(Cv), 5),
         "個股 RSI2≤10 + QQQ RSI2≤10 同一天": cool(osold10 & qOS[:, None] & ~np.isnan(Cv), 5),
         "抄底(不看資金):深跌站回20日線": cdb,
         "抄底(不看資金)+ QQQ 離一年高點 ≥10%": cdb & (np.nan_to_num(qdd, nan=0) <= -0.10)[:, None],
         "抄底(不看資金)+ QQQ 離一年高點 ≥5%": cdb & (np.nan_to_num(qdd, nan=0) <= -0.05)[:, None],
         "抄底(不看資金)+ QQQ 沒回檔 5%": cdb & (np.nan_to_num(qdd, nan=0) > -0.05)[:, None]}
out = {}
for nm, sig in CASES.items():
    out[nm] = {}
    print(f"\n== {nm}")
    for g, gm in groups.items():
        s = stat2(sig, gm); out[nm][g] = s
        yrs = per.sum() / 252
        print(f"  {g:<10} 每檔每年 {s['全期10'][0]/max(1,sum(gm))/yrs:4.1f}|10天 前 {s['前段10'][1]}%({s['前段10'][2]}) 後 {s['後段10'][1]}%({s['後段10'][2]})"
              f"|20天 前 {s['前段20'][1]}%({s['前段20'][2]}) 後 {s['後段20'][1]}%({s['後段20'][2]})|40天 全 {s['全期40'][1]}%({s['全期40'][2]}) n={s['全期40'][0]} 平均 {s['全期40'][3]}%")
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "s2_context.json"), "w"), ensure_ascii=False, indent=1)
# 抄底(不看資金)分級的數字(給網站 hover 用):強 = QQQ 離一年高點 ≥10%;弱 = 其餘
strong = cdb & (np.nan_to_num(qdd, nan=0) <= -0.10)[:, None]; weak = cdb & ~(np.nan_to_num(qdd, nan=0) <= -0.10)[:, None]
gm = groups["全部追蹤股"]
for nm, sig in (("強", strong), ("弱", weak), ("全部", cdb)):
    s = stat2(sig, gm, hs=(20, 40))
    allg = G[20][sig & per[:, None] & np.array(gm)[None, :]]; allg = allg[~np.isnan(allg)]
    print(f"抄底(不看資金){nm}:20天 全期 {round((allg>0).mean()*100,1)}%(平常 {s['全期20'][2]})n={len(allg)};前 {s['前段20'][1]} 後 {s['後段20'][1]};40天 全期 {s['全期40'][1]}%(平常 {s['全期40'][2]})")
