#!/usr/bin/env python3
"""Independent daily cash/share replay of the delivered Astra exit-study accounts.

No imports from experiment.py, data_tools.py, or previous audit algorithms.
Uses delivered episode dates/events as fixed instructions, NOT a new independent
implementation of entry or sell signal decisions. Prices, holdings, daily NAV,
MDD, compounding, calendar selection, CAGR and Calmar are recalculated here.
No network, strategy tuning, new tickers, or writes into the old study folder.
"""
from __future__ import annotations
import csv
import gzip
import hashlib
import json
import math
import statistics
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / 'astra-exits-20261013'
POLICIES = ('B0', 'R1', 'E1', 'C50')
PERIODS = {'A': ('2010-01-01', '2017-12-31'), 'B': ('2018-01-01', '2026-07-31')}
ATOL, RTOL = 1e-10, 1e-10


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def median(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    k = len(values)//2
    return values[k] if len(values)%2 else (values[k-1]+values[k])/2


class Audit:
    def __init__(self):
        self.inputs = {}
        self.counts = defaultdict(int)
        self.failures = []
        self.max_differences = defaultdict(float)

    def read(self, path):
        path = Path(path)
        blob = path.read_bytes()
        self.inputs[str(path.relative_to(OLD))] = sha(blob)
        return blob

    def check(self, ok, label, detail=None):
        self.counts[label] += 1
        if not ok:
            self.failures.append({'check': label, 'detail': detail})

    def near(self, got, expected, label, detail=None):
        if got is None or expected is None:
            self.check(got is expected, label, detail)
            return
        diff = abs(got-expected)
        self.max_differences[label] = max(self.max_differences[label], diff)
        self.check(math.isfinite(got) and math.isfinite(expected) and
                   diff <= ATOL + RTOL*abs(expected), label,
                   {'where': detail, 'actual': got, 'expected': expected, 'difference': diff})


def raw_price_map(doc):
    """Rebuild provider-adjusted OHLC from the original downloaded Yahoo body."""
    r = doc['chart']['result'][0]
    quote = r['indicators']['quote'][0]
    adjusted_close = r['indicators']['adjclose'][0]['adjclose']
    zone = ZoneInfo(r['meta']['exchangeTimezoneName'])
    out = {}
    for i, timestamp in enumerate(r['timestamp']):
        day = datetime.fromtimestamp(timestamp, zone).date().isoformat()
        raw_close, ac = quote['close'][i], adjusted_close[i]
        if not all(isinstance(v, (int,float)) and math.isfinite(v) and v > 0 for v in (raw_close, ac)):
            continue
        factor = ac/raw_close
        vals = [quote[k][i] for k in ('open','high','low')]
        if not all(isinstance(v, (int,float)) and math.isfinite(v) and v > 0 for v in vals):
            continue
        out[day] = [v*factor for v in vals] + [ac]
    return out


def select_campaigns(rows, calendar, ci):
    """Fixed reset: allow a new close signal on the prior campaign end date."""
    chosen = []
    unlocked = -1
    for signal_day in sorted(rows):
        t = ci[signal_day]
        if t < unlocked:
            continue
        chosen.append(rows[signal_day])
        unlocked = t + 64
    return chosen


def replay(bars, selected, start, end, policy, audit, label):
    """Daily open transaction ledger, independent from episode NAV multiplication."""
    purchases = {}
    sales = defaultdict(list)
    window_ends = set()
    for ep in selected:
        buy_day = ep['entry_date']
        audit.check(buy_day not in purchases, 'unique_buy_day', label)
        purchases[buy_day] = ep['date']
        window_ends.add(ep['end_date'])
        fractions = 0.
        for day, fraction, reason in ep['events']:
            sales[day].append((ep['date'], fraction, reason))
            fractions += fraction
            audit.check(buy_day <= day <= ep['end_date'] and fraction > 0,
                        'sale_time_and_fraction', (label, ep['date'], day, fraction))
        audit.near(fractions, 1., 'campaign_full_liquidation', (label, ep['date']))

    cash = 1.
    shares = initial_shares = 0.
    active_signal = None
    peak = 1.
    peak_date = start
    maximum_drawdown = 0.
    worst_pair = {'peak_date': start, 'trough_date': start, 'peak_nav': 1., 'trough_nav': 1.}
    curve = [1.]
    dates = [d for d in bars if start <= d <= end]
    exposure_sum = 0.
    transactions = 0
    turnover = 0.
    for day in dates:
        opening, _, _, closing = bars[day]
        if day in purchases:
            audit.near(shares, 0., 'flat_before_new_purchase', (label, day))
            budget = cash*(.5 if policy == 'C50' else 1.)
            initial_shares = budget/opening
            shares = initial_shares
            cash -= budget
            active_signal = purchases[day]
            transactions += 1
            turnover += budget
        for signal_day, fraction, reason in sales.get(day, []):
            audit.check(signal_day == active_signal, 'sale_matches_current_campaign', (label, day))
            amount = initial_shares*fraction
            audit.check(amount <= shares+1e-10, 'no_oversell', (label, day))
            cash += amount*opening
            shares -= amount
            transactions += 1
            turnover += amount*opening
            if abs(shares) < 1e-12*max(1,initial_shares):
                shares = 0.
        audit.check(cash >= -1e-12 and shares >= -1e-12, 'no_borrowing', (label, day))
        if day in window_ends:
            audit.near(shares, 0., 'flat_on_common_end_date', (label, day))
        equity = cash + shares*closing
        curve.append(equity)
        exposure_sum += shares*closing/equity
        if equity > peak:
            peak, peak_date = equity, day
        dd = (peak-equity)/peak
        if dd > maximum_drawdown:
            maximum_drawdown = dd
            worst_pair = {'peak_date': peak_date, 'trough_date': day, 'peak_nav': peak, 'trough_nav': equity}
    audit.near(shares, 0., 'flat_at_account_end', label)
    years = (date.fromisoformat(end)-date.fromisoformat(start)).days/365.25
    annual = curve[-1]**(1/years)-1 if years > 0 and curve[-1] > 0 else None
    return {'return': curve[-1]-1, 'cagr': annual, 'mdd': maximum_drawdown,
            'calmar': annual/maximum_drawdown if maximum_drawdown and annual is not None else None,
            'exposure': exposure_sum/len(dates), 'transactions': transactions, 'turnover': turnover,
            'campaigns': len(selected), 'start': start, 'end': end, 'days': len(dates),
            'curve_points': len(curve), 'worst_drawdown': worst_pair,
            'selected_signal_dates': [ep['date'] for ep in selected], 'curve': curve}


def main():
    audit = Audit()
    manifest = json.loads(audit.read(OLD/'data/manifest.json'))
    frozen = json.loads(audit.read(OLD/'freeze.json'))
    for name, expected in frozen['files'].items():
        audit.check(sha(audit.read(OLD/name)) == expected, 'frozen_source_hash', name)
    calendar_blob = audit.read(OLD/'data'/manifest['calendarFile'])
    audit.check(sha(calendar_blob) == manifest['calendarSha256'], 'calendar_hash')
    calendar = json.loads(calendar_blob)['dates']
    audit.check(calendar == sorted(set(calendar)), 'sorted_unique_calendar')
    ci = {d:i for i,d in enumerate(calendar)}
    period_limits = {}
    for period, (lo, hi) in PERIODS.items():
        start = next(d for d in calendar if d >= lo)
        last_signal = max(d for d in calendar if lo <= d <= hi and ci[d]+64 < len(calendar))
        period_limits[period] = {'start': start, 'end': calendar[ci[last_signal]+64], 'last_mature_signal': last_signal}

    expected_accounts = json.loads(audit.read(OLD/'evidence/accounts.json'))
    expected_index = {(r['symbol'],r['period'],r['policy']): r for r in expected_accounts}
    old_results = json.loads(audit.read(OLD/'evidence/results.json'))
    supplied_curves = json.loads(audit.read(OLD/'evidence/account-curves.json'))
    curve_index = {(r['symbol'],r['period'],r['policy']): r for r in supplied_curves}
    audit.check(len(expected_index) == len(expected_accounts), 'unique_original_accounts')

    # Only dates and order instructions are retained. Published return/NAV/MDD
    # columns are deliberately never used as replay inputs.
    episode_blob = audit.read(OLD/'evidence/episodes.csv.gz')
    episodes = defaultdict(dict)
    for r in csv.DictReader(gzip.decompress(episode_blob).decode('utf-8').splitlines()):
        if float(r['cost']) != 0:
            continue
        key = (r['symbol'],r['period'],r['policy'])
        audit.check(r['date'] not in episodes[key], 'unique_episode_key', (key,r['date']))
        episodes[key][r['date']] = {k:r[k] for k in ('date','entry_date','end_date')}
        episodes[key][r['date']]['events'] = json.loads(r['events'])

    replayed = []
    eligibility = []
    source_summary = []
    groups = manifest['groups']
    requested = sorted(set(groups['ALL'])|set(groups['IDX']))
    for symbol in requested:
        m = manifest['symbols'][symbol]
        blob = audit.read(OLD/'data'/m['adjustedFile'])
        audit.check(sha(blob) == m['adjustedSha256'], 'adjusted_price_hash', symbol)
        adjusted = json.loads(blob)
        provenance = adjusted['provenance']
        raw_gz = audit.read(OLD/'data'/provenance['rawFile'])
        raw_body = gzip.decompress(raw_gz)
        audit.check(sha(raw_gz) == provenance['rawGzipSha256'], 'raw_gzip_hash', symbol)
        audit.check(sha(raw_body) == provenance['rawSha256'] == m['rawSha256'], 'raw_body_hash', symbol)
        independent_prices = raw_price_map(json.loads(raw_body))
        adjusted_bars = adjusted['bars']
        days = [b[0] for b in adjusted_bars]
        audit.check(days == sorted(set(days)), 'sorted_unique_symbol_dates', symbol)
        bar_map = {}
        for b in adjusted_bars:
            audit.check(b[0] in independent_prices, 'raw_date_exists', (symbol,b[0]))
            actual = independent_prices[b[0]]
            for j, name in enumerate(('open','high','low','close')):
                audit.near(actual[j], b[j+1], 'raw_to_adjusted_'+name, (symbol,b[0]))
            # Replay the rederived price, not the published adjusted price values.
            bar_map[b[0]] = actual
        source_summary.append({'symbol':symbol,'adjustedSha256':sha(blob),
                               'rawSha256':sha(raw_body),'rawGzipSha256':sha(raw_gz),
                               'bars':len(bar_map),'corporate_actions_independently_verified':False})
        for period, limits in period_limits.items():
            start, end = limits['start'], limits['end']
            required = calendar[ci[start]-199:ci[end]+1]
            missing = [d for d in required if d not in bar_map]
            eligible = not missing
            eligibility.append({'symbol':symbol,'period':period,'eligible':eligible,
                                'missing_required_days':len(missing),'first_missing':missing[:3]})
            for policy in POLICIES:
                key=(symbol,period,policy)
                audit.check(eligible == (key in expected_index), 'independent_account_eligibility', key)
            if not eligible:
                continue
            candidate_dates = set(episodes[(symbol,period,'B0')])
            for policy in POLICIES:
                key=(symbol,period,policy)
                these=episodes[key]
                audit.check(set(these)==candidate_dates,'policy_common_candidate_dates',key)
                selected=select_campaigns(these,calendar,ci)
                for ep in selected:
                    t=ci[ep['date']]
                    audit.check(ep['entry_date']==calendar[t+1] and ep['end_date']==calendar[t+64],
                                'signal_entry_reset_calendar', (key,ep['date']))
                    audit.check(PERIODS[period][0] <= ep['date'] <= PERIODS[period][1],
                                'signal_period_membership', (key,ep['date']))
                account=replay(bar_map,selected,start,end,policy,audit,key)
                supplied=expected_index[key]
                for field in ('return','cagr','mdd','calmar','exposure','turnover'):
                    audit.near(account[field],supplied[field],'account_'+field,key)
                for field in ('days','campaigns','transactions','start','end'):
                    audit.check(account[field]==supplied[field],'account_'+field,key)
                audit.check(account['curve_points']==ci[end]-ci[start]+2,'account_curve_dates',key)
                if key in curve_index:
                    old_curve=curve_index[key]['curve']
                    audit.check(len(account['curve'])==len(old_curve),'stored_curve_length',key)
                    for i,(actual,expected) in enumerate(zip(account['curve'],old_curve)):
                        audit.near(actual,expected,'stored_daily_nav',(key,i))
                account.pop('curve')
                account.update(symbol=symbol,period=period,policy=policy,
                               groups=[g for g,syms in groups.items() if symbol in syms])
                replayed.append(account)

    summaries={}
    for group in ('IDX','MAG7','NDX','ALL'):
        for period in PERIODS:
            for policy in POLICIES:
                key=f'{group}|{period}|{policy}'
                rows=[r for r in replayed if group in r['groups'] and r['period']==period and r['policy']==policy]
                result={'n_stocks':len(rows)}
                for field in ('return','cagr','mdd','calmar','exposure','transactions','campaigns'):
                    result[field]=median([r[field] for r in rows])
                    audit.near(result[field],old_results['account_summary'][key][field],'group_median_'+field,key)
                audit.check(len(rows)==old_results['account_summary'][key]['n_stocks'],'group_count',key)
                ordered=sorted(rows,key=lambda r:r['mdd'])
                mid=len(ordered)//2
                center=ordered[mid:mid+1] if len(ordered)%2 else ordered[mid-1:mid+1]
                result['mdd_median_center']=[{'symbol':r['symbol'],'mdd':r['mdd'],'worst_drawdown':r['worst_drawdown']} for r in center]
                summaries[key]=result

    audit.check(len(replayed)==len(expected_accounts),'all_accounts_replayed')
    for name,digest in list(audit.inputs.items()):
        audit.check(sha((OLD/name).read_bytes())==digest,'old_input_unchanged',name)
    b0=summaries['ALL|B|B0']['mdd']*100
    r1=summaries['ALL|B|R1']['mdd']*100
    report={'schema':'astra-independent-account-audit/1','created_at':datetime.now(timezone.utc).isoformat(),
            'status':'PASS' if not audit.failures else 'FAIL',
            'scope':'Original A/B cohorts and all four policies; raw Yahoo price reconstruction plus independent daily cash/share accounting. Original entry/sell decisions reused from delivered episode instructions; strategy decisions not independently regenerated.',
            'new_strategy_or_new_universe_test':False,'cost':0,'cash_interest':0,
            'tolerance':{'absolute':ATOL,'relative':RTOL},'period_limits':period_limits,
            'accounts_replayed':len(replayed),'comparison_counts':dict(audit.counts),
            'max_absolute_differences':dict(audit.max_differences),'failure_count':len(audit.failures),
            'failures':audit.failures,'source_hashes':audit.inputs,'price_sources':source_summary,
            'eligibility':eligibility,'group_summaries':summaries,'accounts':replayed,
            'question_answer':{'ALL_B_B0_mdd_percent':b0,'ALL_B_R1_mdd_percent':r1,
                'B0_rounded_two_decimals':f'{b0:.2f}','R1_rounded_two_decimals':f'{r1:.2f}',
                'B0_minus_R1_percentage_points':b0-r1,
                'interpretation':'The original Astra B0 median of 41.26% is independently reproduced. The main review has separately verified that Claude accounts/results really report B0 at 41.00%; this is not assumed to be a transcription error. Differences between snapshots require stock-by-stock reconciliation.'},
            'limitations':['Provider corporate-action adjustments and historical point-in-time identity not independently certified.',
                          'Original event choices reused; independence covers raw-to-adjusted values, cohort calendar eligibility, fixed-reset selection, cash/share accounting and all derived account statistics.',
                          'Current-universe/complete-case selection bias remains; reproduction is not performance validation.']}
    (HERE/'account-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    rows=[]
    for period in PERIODS:
        for policy in POLICIES:
            r=summaries[f'ALL|{period}|{policy}']
            rows.append(f"| {period} | {policy} | {r['n_stocks']} | {r['return']*100:.8f}% | {r['mdd']*100:.8f}% | {r['cagr']*100:.8f}% | {r['calmar']:.8f} |")
    text=f'''# 有限資金帳戶獨立重播核對

建立：{report['created_at']}（UTC）；狀態 **{report['status']}**。此為舊結果核對，沒有新股票、新策略或調參回測。

**Astra ALL 後段 B0 帳戶 MDD 中位數是 {b0:.10f}%，四捨五入為 {b0:.2f}%；R1 為 {r1:.10f}%，四捨五入為 {r1:.2f}%。** 本輪重播支持原 B0 的41.26%，並非原報告誤植。主線另已核對Claude原始accounts/results，B0確為41.00%，不應視為文件誤植。本次核對只確認Astra原41.26%可重現；兩份快照的差異須另按股票、買點與帳戶路徑逐項核對，不能僅憑中位數相近判定原因。

## 核對範圍

從原下載Yahoo JSON重新計算每根還原OHLC（adjclose/raw close），再按既有成交指令，以每日開盤買賣、現金加剩餘股數乘收盤價，重建完整帳戶NAV。沒有import或呼叫原experiment、episode、ledger、data_tools或舊審計算法，也沒有直接複乘已報出的episode收益。

沿用的部分只有已交付episode的合格買點日期、卖出日期及股數比例：**訊號策略決策不是本次獨立重寫**。固定重置t+64、次開盤進場、半本金C50、費用0與現金息0，皆由本程式重新處理。由原價完整日曆自行判斷200根暖機及全段完整性，再與舊帳戶納入名單逐筆比對。

共重建 {len(replayed)} 份股票／期間／政策帳戶，A段150檔ALL加2檔IDX、B段184檔ALL加2檔IDX，各4政策。全數比較期末報酬、MDD、CAGR、Calmar、曝險、成交額、交易次數、campaign數及日期數；另外將舊檔保留的32條曲線每日逐點核對。

失敗 {len(audit.failures)} 項；日期／資金及數值比對明細與所有來源雜湊見account-audit.json。數值容差為abs {ATOL:g} + rel {RTOL:g}×原值，浮點運算次序差異不視為實質不一致。

## ALL 中位數重新計算

| 期間 | 政策 | 股票数 | 期末報酬中位 | 帳戶MDD中位 | CAGR中位 | Calmar中位 |
|---|---|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

MDD中位數、CAGR中位數及Calmar中位數各自跨股票計算，不可把前兩個中位數相除當作Calmar中位數。以上也不是跨股組合的績效。

## 日曆及限制

A帳戶 {period_limits['A']['start']} 至 {period_limits['A']['end']}；B帳戶 {period_limits['B']['start']} 至 {period_limits['B']['end']}。B最後完整成熟訊號日 {period_limits['B']['last_mature_signal']}，不能說已完整評估到2026-07-31。

這裡核對的是舊資料快照的數值重現；Yahoo公司行動调整、歷史ticker身分、當代名單與完整案例偏差仍未因此得到認證。沿用舊成交事件的獨立帳務重算，也不能冒稱獨立確認70%或策略外部複驗通過。原始研究目錄保持唯讀；本次只產生新回覆目錄內的程式及核對輸出。
'''
    (HERE/'account-audit.md').write_text(text,encoding='utf-8')
    print(json.dumps({'status':report['status'],'accounts':len(replayed),'checks':sum(audit.counts.values()),
                      'failures':len(audit.failures),'answer':report['question_answer'],
                      'account_max_errors':{k:v for k,v in audit.max_differences.items() if k.startswith('account_')}},ensure_ascii=False))
    if audit.failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
