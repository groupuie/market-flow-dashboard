# Claude 2026-10-17:把 sim4 / sim5 的結果整理成 markdown 表(欄名照 Astra v0.7.4 更正:「單獨 H3 下界 > 0」≠ 上線候選;歷史庫叫壓力測試)
# 用法:python3 -I sim5_tables.py <sim4_select.json> <sim5_select.json> <sim5_result.json>
import json, sys
S4, S5, R = (json.load(open(p)) for p in sys.argv[1:4])
f = lambda x: f"{x['k']}/{x['n']}({x['pct']:.1f}%;Wilson 上界 {x['wilson95'][1]:.1f}%)"
fs = lambda x: f"{x['k']}/{x['n']}"
NAME = {'syn_random': '合成・擲銅板', 'syn_random_a43': '合成・擲銅板', 'syn_random_a25': '合成・擲銅板(同意 25%)', 'syn_random_a70': '合成・擲銅板(同意 70%)',
        'syn_stock': '合成・固定偏好股票', 'syn_market': '合成・跟大盤', 'syn_shift_plus1': '合成・同意 +1 點(真值 +1)', 'syn_shift_minus1': '合成・同意 −1 點(真值 −1)',
        'syn_heavy_random': '合成・更厚尾', 'syn_sparse_random': '合成・稀疏(買點少)', 'density_null_alt': '稠密/稀疏交替 +1/−1(真值 0)',
        'density_astra_alt': 'Astra 反例結構 +1/−1.2(真值 −0.1)', 'density_random_mix': '稠密/稀疏隨機 +1/−1',
        'syn_missing_mixed': '合成・大跌的筆缺(兩邊都缺)', 'syn_missing_agree_only': '合成・大跌的筆缺(只缺同意)',
        'hist_random': '歷史庫・擲銅板', 'hist_stock': '歷史庫・固定偏好股票', 'hist_market': '歷史庫・跟大盤'}
print('## A. 第一輪(sim4,事先規則;M1 / M2 × L;每格「下界 > 真值 / 上界 < 真值」,合格 = 兩側都 ≤ 3.5% 且不顯著高於 2.5%)\n')
print('| 情境(120 天、300 視窗)| ' + ' | '.join(f'{m} L={L}' for L in ('5', '10', '20') for m in ('M1', 'M2')) + ' | 草案 2 舊法 L=5(下界 > 真值)|')
print('|---|' + '---:|' * 7)
for nm in S4['by_L']['5']:
    cells = [f"{S4['by_L'][L][nm][m]['lb_above_truth']['k']} / {S4['by_L'][L][nm][m]['ub_below_truth']['k']}{'' if S4['by_L'][L][nm][m]['passes'] else ' ✗'}" for L in ('5', '10', '20') for m in ('M1', 'M2')]
    print(f"| {NAME.get(nm, nm)} | " + ' | '.join(cells) + f" | {S4['legacy_L5'][nm]['lb_above_truth']['k']} |")
print(f"\n選出:{S4['chosen']}\n")
print('## B. 第二輪(sim5,換全新抽樣;C3 / C1,L=5;參照 M1 / M2 不參選)\n')
print('| 情境(120 天、300 視窗)| 實際標準差 | C3 標準誤 | C1 標準誤 | C3 下/上 | C1 下/上 | 參照 M1 下/上 |')
print('|---|---:|---:|---:|---:|---:|---:|')
for nm, v in S5['scen'].items():
    g = lambda m: f"{v[m]['lb_above_truth']['k']} / {v[m]['ub_below_truth']['k']}{'' if v[m]['passes'] else ' ✗'}"
    print(f"| {NAME.get(nm, nm)} | {v['empirical_sd_pp']:.3f} | {v['mean_se_pp']['C3']:.3f} | {v['mean_se_pp']['C1']:.3f} | {g('C3')} | {g('C1')} | {g('M1')} |")
print(f"\n選出:{S5['chosen']}\n")
rep = R['report']
print('## C. 報告(第三批全新合成市場;選中的方法;200 視窗;PASS = 完整判定,含門檻與缺漏規則)\n')
print('### C1. 已知真值的合成情境(真值 ≤ 0 時 PASS = 誤判)\n')
print('| 情境 | 天 | 真值 | PASS 甲 | PASS 乙 | PASS 丙 | 下界 > 真值 | 上界 < 真值 | 資訊不足 |')
print('|---|---:|---:|---:|---:|---:|---:|---:|---:|')
for k, v in sorted(rep.items(), key=lambda kv: (kv[1]['kind'], kv[1]['name'], kv[1]['T'])):
    if v['kind'] not in ('known', 'missing'): continue
    m = R['meta']['chosen']['method']
    lbt = fs(v['lb_above_truth'][m]) if 'lb_above_truth' in v else '—'; ubt = fs(v['ub_below_truth'][m]) if 'ub_below_truth' in v else '—'
    tr = f"{v['mean_truth_pp']:+.2f}" if 'mean_truth_pp' in v else '0(缺漏)'
    print(f"| {NAME.get(v['name'], v['name'])} | {v['T']} | {tr} | {f(v['PASS']['gap_vs_all_10pp'])} | {f(v['PASS']['agree_vs_disagree_lb'])} | {f(v['PASS']['none'])} | {lbt} | {ubt} | {v['INSUFFICIENT']['pct']:.1f}% |")
print('\n### C2. 歷史固定庫的壓力測試(真值未知 → 不叫誤判)\n')
print('| 貼法 | 天 | PASS 甲 | PASS 乙 | PASS 丙 | 資訊不足 |')
print('|---|---:|---:|---:|---:|---:|')
for k, v in sorted(rep.items(), key=lambda kv: (kv[1]['name'], kv[1]['T'])):
    if v['kind'] != 'stress': continue
    print(f"| {NAME.get(v['name'], v['name'])} | {v['T']} | {f(v['PASS']['gap_vs_all_10pp'])} | {f(v['PASS']['agree_vs_disagree_lb'])} | {f(v['PASS']['none'])} | {v['INSUFFICIENT']['pct']:.1f}% |")
print('\n### C3. 功效(歷史庫 + 有判斷力的貼法;δ = 格子等權平均差,不是每筆都多賺 δ)\n')
print('| 目標 δ | 天 | 實際格子平均差 | 同意−不同意勝率差(事件加權)| PASS 甲 | PASS 乙 | PASS 丙 | 單獨 H3 下界 > 0 | 上線候選(PASS 且兩版 H3)乙 / 丙 |')
print('|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
for k, v in sorted(rep.items(), key=lambda kv: (kv[1].get('delta_target_pp') or 0, kv[1]['T'])):
    if v['kind'] != 'power': continue
    print(f"| {v['delta_target_pp']:.0f} | {v['T']} | {v['mean_point_pp']:.2f} | {v['win_gap_agree_minus_disagree_pp_mean']:.1f} | {v['PASS']['gap_vs_all_10pp']['pct']:.1f}% | "
          f"{v['PASS']['agree_vs_disagree_lb']['pct']:.1f}% | {v['PASS']['none']['pct']:.1f}% | {v['H3_alone_excluded']['pct']:.1f}% | "
          f"{v['go_live_candidate']['agree_vs_disagree_lb']['pct']:.1f}% / {v['go_live_candidate']['none']['pct']:.1f}% |")
