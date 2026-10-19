# Claude 2026-10-16:把 sim3_result.json 整理成 markdown 表(誤判率、資訊不足、功效);用法:python3 -I sim3_tables.py <sim3_result.json>
# 2026-10-17 更正(Astra v0.7.4 §3.4):最後一欄原名「上線候選(H3)」不對 — 它只累計「單獨 H3 下界 > 0」,沒有和 PASS、缺漏、持倉重播取交集;歷史庫的貼法是壓力測試(真值未知);這份表是草案 2 舊方法(Poisson + 刪空格)的結果,只當歷史
import json, sys
R = json.load(open(sys.argv[1]))
f = lambda x: f"{x['k']}/{R['meta']['windows_per_scenario']}({x['pct']:.1f}%;上界 {x['wilson95'][1]:.1f}%)"
NAME = {'synthetic|random': '合成・每筆擲銅板', 'synthetic_heavy|random': '合成・更厚的尾巴', 'synthetic|stock': '合成・固定偏好某些股票',
        'synthetic|market': '合成・跟著大盤漲跌', 'historical|random': '歷史庫壓力測試・每筆擲銅板', 'historical|stock': '歷史庫壓力測試・固定偏好某些股票',
        'historical|market': '歷史庫壓力測試・跟著大盤漲跌'}
print('選定的日期區塊長度 L =', R['chosen_L'], '|', R['chosen_L_note'])
print('\n| 情境 | 收案期 | 同意比例 | 缺漏 | H1 下界 > 0 | PASS(H2 原樣) | PASS(H2 改成同意 vs 不同意) | PASS(不要 H2) | 資訊不足 |')
print('|---|---:|---:|---|---:|---:|---:|---:|---:|')
for k, v in R['report'].items():
    src, how, T, a, miss = k.split('|')
    print(f"| {NAME.get(src + '|' + how, src + '|' + how)} | {T[1:]} 天 | {a[1:]} | {miss.split('=')[1]} | {f(v['H1_lb_gt0'])} | {f(v['PASS']['gap_vs_all_10pp'])} | {f(v['PASS']['agree_vs_disagree_lb'])} | {f(v['PASS']['none'])} | {v['INSUFFICIENT']['pct']:.1f}% |")
print('\n| 判斷力(格子等權平均差 δ 個百分點;不是每筆都多賺 δ)| 收案期 | 實際平均差 | 同意 − 不同意勝率差 | PASS(H2 原樣) | PASS(H2 改) | PASS(不要 H2) | 單獨 H3 下界 > 0(不是上線候選) |')
print('|---|---:|---:|---:|---:|---:|---:|---:|')
for k, v in R['power'].items():
    _, _, d, T = k.split('|')
    print(f"| {d[5:]} | {T[1:]} 天 | {v['h1_pp_mean']:.2f} | {v['win_gap_agree_minus_disagree_pp_mean']:.1f} | {v['PASS']['gap_vs_all_10pp']['pct']:.0f}% | {v['PASS']['agree_vs_disagree_lb']['pct']:.0f}% | {v['PASS']['none']['pct']:.0f}% | {v['H3_lb_gt0']['pct']:.0f}% |")
