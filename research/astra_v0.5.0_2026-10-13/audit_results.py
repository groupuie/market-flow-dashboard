#!/usr/bin/env python3
"""Independent read-only exit-result audit. Never imports experiment or data_tools.

This checks numerical consistency, not trading effectiveness. All result source
files are read-only. Sampling is fixed before outcomes: earliest/middle/latest
cohort per symbol plus its earliest R1 reduction and E1 trailing exit for branch
coverage. No strategy parameter is selected or changed here.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
PERIODS = {'A': ('2010-01-01', '2017-12-31'), 'B': ('2018-01-01', '2026-07-31')}
POLICIES = ('B0', 'R1', 'E1', 'C50')
MEAN_FIELDS = ('mdd', 'giveback', 'exposure', 'hold', 'turnover', 'transactions', 'triggered')
FLOAT_FIELDS = ('return', 'mdd', 'giveback', 'exposure', 'hold', 'turnover', 'transactions', 'cost')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Checks:
    def __init__(self):
        self.n = 0
        self.failures = []
        self.max_abs_error = 0.

    def equal(self, key, got, want):
        self.n += 1
        if got is None or want is None:
            ok = got is None and want is None
        elif isinstance(got, bool) or isinstance(want, bool):
            ok = got == want
        elif isinstance(got, (int, float)) and isinstance(want, (int, float)):
            ok = math.isfinite(got) and math.isfinite(want) and math.isclose(got, want, rel_tol=5e-10, abs_tol=2e-10)
            if math.isfinite(got) and math.isfinite(want):
                self.max_abs_error = max(self.max_abs_error, abs(got-want))
        else:
            ok = got == want
        if not ok:
            def safe(value):
                if isinstance(value, set): return sorted((safe(x) for x in value), key=str)
                if isinstance(value, (list, tuple)): return [safe(x) for x in value]
                if isinstance(value, dict): return {str(k): safe(v) for k,v in value.items()}
                if isinstance(value, float) and not math.isfinite(value): return str(value)
                return value
            self.failures.append({'check': key, 'independent': safe(got), 'reported': safe(want)})
        return ok

    def check(self, key, condition):
        return self.equal(key, bool(condition), True)


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    rank = fraction * (len(ordered)-1)
    left = math.floor(rank)
    if left == len(ordered)-1:
        return ordered[left]
    return ordered[left] + (ordered[left+1]-ordered[left])*(rank-left)


class Aggregate:
    def __init__(self):
        self.returns = []
        self.sums = dict.fromkeys(MEAN_FIELDS, 0.)

    def add(self, row):
        self.returns.append(row['return'])
        for k in MEAN_FIELDS:
            self.sums[k] += row[k]

    def finish(self):
        r = self.returns
        if not r:
            return {'n': 0}
        plus = [x for x in r if x > 0]
        minus = [x for x in r if x < 0]
        return {'n': len(r), 'win': len(plus)/len(r), 'zero': sum(x == 0 for x in r)/len(r),
            'mean_win': math.fsum(plus)/len(plus) if plus else None,
            'mean_loss': math.fsum(minus)/len(minus) if minus else None,
            'mean': math.fsum(r)/len(r), 'median': statistics.median(r),
            'p05': percentile(r, .05), 'p95': percentile(r, .95),
            **{k: v/len(r) for k, v in self.sums.items()}}


def csv_rows(path):
    with gzip.open(path, 'rt', newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            for k in FLOAT_FIELDS:
                row[k] = float(row[k])
            if row['triggered'] not in ('True', 'False'):
                raise ValueError('Unexpected CSV boolean')
            row['triggered'] = row['triggered'] == 'True'
            row['events'] = json.loads(row['events'])
            yield row


def cohorts(path):
    previous = None
    frame = []
    for row in csv_rows(path):
        key = row['symbol'], row['date']
        if key != previous and frame:
            yield previous, frame
            frame = []
        previous = key
        frame.append(row)
    if frame:
        yield previous, frame


def independent_bootstrap(daily, length, repetitions=2000):
    """Directly sum each calendar block; no imported helper or prefix sums.

    Matching the registered random stream is intentional: it audits the exact
    reported interval rather than drawing another random estimate of it.
    """
    n = len(daily)
    if n < length:
        return {'valid': 0, 'error': 'short_calendar'}
    block_lengths = {length, n % length or length}
    totals = {}
    for width in block_lengths:
        totals[width] = [tuple(math.fsum(v[k] for v in daily[start:start+width]) for k in range(3))
                         for start in range(n-length+1)]
    rng = random.Random(20261013)
    dd_draws = []
    r_draws = []
    for _ in range(repetitions):
        selected = []
        remaining = n
        while remaining > 0:
            start = rng.randrange(n-length+1)
            width = min(length, remaining)
            selected.append(totals[width][start])
            remaining -= width
        count = math.fsum(x[0] for x in selected)
        if count > 0:
            dd_draws.append(math.fsum(x[1] for x in selected)/count)
            r_draws.append(math.fsum(x[2] for x in selected)/count)
    return {'valid': len(dd_draws), 'dd90': [percentile(dd_draws, .05), percentile(dd_draws, .95)],
            'return90': [percentile(r_draws, .05), percentile(r_draws, .95)]}


def split_on_calendar(bars, calendar):
    position = {d: n for n, d in enumerate(calendar)}
    result = []
    current = []
    last = None
    for bar in bars:
        if bar[0] not in position:
            continue
        here = position[bar[0]]
        if last is not None and here != last+1:
            if current:
                result.append(current)
            current = []
        current.append(bar)
        last = here
    if current:
        result.append(current)
    return result


def independent_indicators(bars):
    """Independent Wilder ATR and causal pinned top formula, no vendor import."""
    close = [b[4] for b in bars]
    n = len(close)
    rsi = [None] * n
    if n >= 4:
        changes = [close[j]-close[j-1] for j in range(1, n)]
        gain = math.fsum(max(v, 0.) for v in changes[:2])/2
        loss = math.fsum(max(-v, 0.) for v in changes[:2])/2
        for j in range(2, n):
            if j > 2:
                gain = (gain + max(changes[j-1], 0.))/2
                loss = (loss + max(-changes[j-1], 0.))/2
            rsi[j] = 100. if loss == 0 else 100. - 100./(1.+gain/loss)
    overbought = []
    streak = 0
    for j in range(n):
        if j >= 4:
            streak = streak+1 if close[j] > close[j-4] else 0
        bb = False
        if j >= 19:
            values = close[j-19:j+1]
            center = sum(values)/20
            deviation = math.sqrt(sum((v-center)**2 for v in values)/20)
            bb = close[j] >= center+2*deviation
        overbought.append((rsi[j] is not None and rsi[j] >= 90) or bb or streak == 9)
    tops = set()
    for j in range(2, n):
        if any(overbought[j-2:j+1]) and close[j] < bars[j-1][3] and (not tops or j-max(tops) > 5):
            tops.add(j)
    tr = []
    atr = [None] * n
    for j, bar in enumerate(bars):
        prior = bars[j-1][4] if j else bar[4]
        tr.append(max(bar[2]-bar[3], abs(bar[2]-prior), abs(bar[3]-prior)))
        if j == 13:
            atr[j] = math.fsum(tr)/14
        elif j > 13:
            atr[j] = atr[j-1] + (tr[j]-atr[j-1])/14
    return tops, atr


def replay(bars, signal_index, tops, atr_at_signal, policy, cost):
    """Forward pending-order state machine on a 100-unit cash budget.

    Closing conditions only queue next-open orders; original implementation's
    precomputed event schedule is neither used nor reproduced here.
    """
    t = signal_index
    entry_index, final_index = t+1, t+64
    budget = 50. if policy == 'C50' else 100.
    entry_price = bars[entry_index][1]
    original_quantity = budget/(entry_price*(1.+cost))
    cash = 100.-budget
    quantity = original_quantity
    remaining_fraction = 1.
    pending = None
    reduced = False
    first_top_seen = False
    qualified = False
    running_close_peak = -math.inf
    events = []
    nav = [100.]
    exposures = []
    held_closes = 0
    turnover = original_quantity*entry_price
    trigger_gap_examples = []
    for j in range(entry_index, final_index+1):
        if j == final_index and pending is None and remaining_fraction > 0:
            pending = (remaining_fraction, 'time63')
        if pending is not None:
            fraction, reason = pending
            if fraction > remaining_fraction+1e-12:
                raise AssertionError('Independent replay attempted oversell')
            units = original_quantity*fraction
            gross = units*bars[j][1]
            cash += gross-gross*cost
            quantity -= units
            remaining_fraction -= fraction
            turnover += gross
            events.append([bars[j][0], fraction, reason])
            if reason in ('profit_giveback', 'first_top_half'):
                reduced = True
            if reason in ('profit_giveback', 'prior10_close_low'):
                trigger_gap_examples.append({'reason': reason, 'triggerDate': bars[j-1][0],
                    'executionDate': bars[j][0], 'triggerClose': bars[j-1][4],
                    'actualOpen': bars[j][1], 'gapReturn': bars[j][1]/bars[j-1][4]-1})
            if remaining_fraction == 0:
                quantity = 0.
            pending = None
        mark = bars[j][1] if j == final_index else bars[j][4]
        wealth = cash + quantity*mark
        nav.append(wealth)
        if j == final_index:
            break
        exposures.append(quantity*mark/wealth)
        held_closes += remaining_fraction > 0
        if remaining_fraction <= 0:
            continue
        # The next-open baseline exit dominates a simultaneous R1 trim.
        new_top = not first_top_seen and t+1 <= j <= t+40 and j in tops
        if new_top:
            first_top_seen = True
        baseline_due = new_top or (j == t+40 and not first_top_seen)
        if policy in ('B0', 'C50', 'R1') and baseline_due:
            pending = (remaining_fraction, 'first_top' if new_top else 'time40')
            continue
        if policy == 'R1' and not reduced:
            running_close_peak = max(running_close_peak, bars[j][4])
            qualified |= running_close_peak >= entry_price+2*atr_at_signal
            if qualified and bars[j][4] <= running_close_peak-atr_at_signal:
                pending = (.5, 'profit_giveback')
        if policy == 'E1':
            if new_top:
                pending = (.5, 'first_top_half')
            elif not first_top_seen and j == t+40:
                pending = (remaining_fraction, 'time40')
            elif reduced and bars[j][4] < min(b[4] for b in bars[j-10:j]):
                pending = (remaining_fraction, 'prior10_close_low')
    if remaining_fraction != 0 or abs(quantity) > 1e-9:
        raise AssertionError('Independent replay did not close position')
    peak = 100.
    dd = 0.
    for amount in nav:
        peak = max(peak, amount)
        dd = max(dd, (peak-amount)/peak)
    return {'events': events, 'return': nav[-1]/100-1, 'mdd': dd,
        'giveback': (max(nav)-nav[-1])/max(nav), 'hold': held_closes,
        'exposure': math.fsum(exposures)/len(exposures), 'turnover': turnover/100,
        'transactions': 1+len(events), 'triggered': reduced, 'gap_examples': trigger_gap_examples}


def self_test():
    dates = [(dt.date(2020, 1, 1)+dt.timedelta(days=j)).isoformat() for j in range(100)]
    def flat():
        return [[d, 100., 125., 65., 100., 1000] for d in dates]
    bars = flat()
    bars[21][4], bars[22][4], bars[23][1], bars[61][1] = 103., 101., 90., 120.
    r = replay(bars, 20, set(), 1., 'R1', 0.)
    assert abs(r['return']-.05) < 1e-12
    assert r['events'][0] == [dates[23], .5, 'profit_giveback']
    assert r['gap_examples'][0]['actualOpen'] == 90.
    fees = replay(bars, 20, set(), 1., 'R1', .001)
    assert abs(fees['return']-(1.05*.999/1.001-1)) < 1e-12
    priority = replay(bars, 20, {22}, 1., 'R1', 0.)
    assert priority['events'] == [[dates[23], 1., 'first_top']]
    assert not priority['triggered']
    bars = flat()
    bars[26][1], bars[26][4], bars[27][1] = 110., 80., 70.
    tail = replay(bars, 20, {25}, 1., 'E1', 0.)
    assert abs(tail['return']+.1) < 1e-12
    assert tail['events'] == [[dates[26], .5, 'first_top_half'], [dates[27], .5, 'prior10_close_low']]
    assert len(independent_bootstrap([(0, 0., 0.)]*65, 20)['dd90']) == 2
    assert independent_bootstrap([(0, 0., 0.)]*65, 20)['valid'] == 0
    return {'status': 'PASS', 'cases': ['R1_next_open_gap', 'actual_value_fees', 'baseline_priority', 'E1_next_open_after_trim_close', 'empty_bootstrap']}


def run(root, data_dir):
    ev = root/'evidence'
    results = json.loads((ev/'results.json').read_text())
    manifest = json.loads((data_dir/'manifest.json').read_text())
    calendar_obj = json.loads((data_dir/'calendar.json').read_text())
    calendar = [d for d in calendar_obj['dates'] if d <= '2026-10-12']
    ci = {d: j for j, d in enumerate(calendar)}
    groups = manifest['groups']
    checks = Checks()
    source_paths = [root/'experiment.py', root/'protocol.md', ev/'results.json', ev/'episodes.csv.gz',
                    ev/'paired-dates.csv.gz', ev/'accounts.json', data_dir/'manifest.json']
    before = {str(p.relative_to(root)) if p.is_relative_to(root) else str(p): sha(p) for p in source_paths}
    checks.equal('manifest_hash', sha(data_dir/'manifest.json'), results['data_manifest_sha256'])
    checks.equal('calendar_last', calendar[-1], results['calendar_last'])
    checks.equal('mature_last', calendar[-65], results['mature_signal_last'])
    for name, want in results['freeze']['files'].items():
        checks.equal('freeze/'+name, sha(root/name), want)
    aggregates = defaultdict(Aggregate)
    paired = defaultdict(lambda: defaultdict(lambda: [0, 0., 0.]))
    identity_pairs = defaultdict(lambda: [0, 0., 0.])
    dates_by_symbol = defaultdict(list)
    branches = {}
    seen_cohorts = set()
    row_count = 0
    frame_count = 0
    for key, rows in cohorts(ev/'episodes.csv.gz'):
        sym, day = key
        checks.check('unique_cohort/'+str(key), key not in seen_cohorts)
        seen_cohorts.add(key)
        dates_by_symbol[sym].append(day)
        frame_count += 1
        frame = {(r['cost'], r['policy']): r for r in rows}
        checks.equal('policy_cost_frame/'+str(key), set(frame), {(c, p) for c in (0., .001) for p in POLICIES})
        checks.equal('row_count_frame/'+str(key), len(rows), 8)
        memberships = [g for g in ('IDX', 'MAG7', 'NDX', 'ALL') if sym in groups[g]]
        for row in rows:
            row_count += 1
            period = 'A' if PERIODS['A'][0] <= day <= PERIODS['A'][1] else 'B'
            checks.equal('period/'+str(key), row['period'], period)
            checks.check('period_bounds/'+str(key), PERIODS[period][0] <= day <= PERIODS[period][1])
            checks.equal('entry_date/'+str(key), row['entry_date'], calendar[ci[day]+1])
            checks.equal('end_date/'+str(key), row['end_date'], calendar[ci[day]+64])
            for g in memberships:
                aggregates[(g, row['period'], row['cost'], row['policy'])].add(row)
            reasons = [e[2] for e in row['events']]
            if row['policy'] == 'R1' and 'profit_giveback' in reasons:
                branches.setdefault((sym, 'R1'), day)
            if row['policy'] == 'E1' and 'prior10_close_low' in reasons:
                branches.setdefault((sym, 'E1'), day)
        for cost in (0., .001):
            base = frame[(cost, 'B0')]
            for pol in ('R1', 'E1', 'C50'):
                row = frame[(cost, pol)]
                dd = base['mdd']-row['mdd']
                rr = row['return']-base['return']
                for g in memberships:
                    label = (g, row['period'], cost, pol)
                    v = paired[label][day]
                    v[0] += 1; v[1] += dd; v[2] += rr
                    if sym not in ('SNDK', 'WOLF', 'NBIS'):
                        q = identity_pairs[label]
                        q[0] += 1; q[1] += dd; q[2] += rr
    for key, aggregate in aggregates.items():
        label = '|'.join(map(str, key))
        expected = results['episode_summary'][label]
        independent = aggregate.finish()
        checks.equal('summary_fields/'+label, set(independent), set(expected))
        for metric, value in independent.items():
            checks.equal('summary/'+label+'/'+metric, value, expected[metric])
    checks.equal('summary_keys', set(results['episode_summary']), {'|'.join(map(str,k)) for k in aggregates})
    expected_daily = set()
    with gzip.open(ev/'paired-dates.csv.gz', 'rt', newline='') as f:
        for row in csv.DictReader(f):
            key = (row['group'], row['period'], float(row['cost']), row['policy'])
            identity = key+(row['date'],)
            checks.check('unique_daily/'+str(identity), identity not in expected_daily)
            expected_daily.add(identity)
            independent = paired[key].get(row['date'], [0, 0., 0.])
            for j, field in enumerate(('n', 'sum_dd', 'sum_return')):
                checks.equal('paired_daily/'+str(identity)+'/'+field, independent[j], float(row[field]))
    checks.equal('paired_keys', set(results['paired_tests']), {'|'.join(map(str,k)) for k in paired})
    votes = dict.fromkeys(PERIODS, 0)
    bootstrap_results = {}
    for key, by_date in paired.items():
        g, period, cost, policy = key
        label = '|'.join(map(str, key))
        reported = results['paired_tests'][label]
        n = sum(v[0] for v in by_date.values())
        average_dd = math.fsum(v[1] for v in by_date.values())/n
        average_return = math.fsum(v[2] for v in by_date.values())/n
        for metric, value in [('n', n), ('delta_dd', average_dd), ('delta_return', average_return)]:
            checks.equal('paired/'+label+'/'+metric, value, reported[metric])
        lo, hi = PERIODS[period]
        dates = [d for d in calendar if lo <= d <= hi and ci[d]+64 < len(calendar)]
        for d in dates:
            checks.check('complete_calendar/'+label+'/'+d, key+(d,) in expected_daily)
        if cost == 0 and policy == 'R1':
            daily = [by_date.get(d, (0, 0., 0.)) for d in dates]
            intervals = {str(L): independent_bootstrap(daily, L) for L in (20, 60, 126)}
            for length, interval in intervals.items():
                original = reported['bootstrap'][length]
                checks.equal('bootstrap/'+label+'/'+length+'/valid', interval['valid'], original['valid'])
                for metric in ('dd90', 'return90'):
                    for tail in (0, 1):
                        checks.equal('bootstrap/'+label+'/'+length+'/'+metric+'/'+str(tail), interval[metric][tail], original[metric][tail])
            gates = {'enough': n >= (30 if g == 'IDX' else 50), 'dd_effect': average_dd >= .01,
                'dd_ci': all(intervals[str(L)]['valid'] == 2000 and intervals[str(L)]['dd90'][0] is not None and intervals[str(L)]['dd90'][0] > 0 for L in (20,60)),
                'return_noninferior': all(intervals[str(L)]['valid'] == 2000 and intervals[str(L)]['return90'][0] is not None and intervals[str(L)]['return90'][0] > -.005 for L in (20,60))}
            checks.equal('gates/'+label, gates, reported['checks'])
            passed = all(gates.values())
            checks.equal('passed/'+label, passed, reported['passed'])
            votes[period] += int(passed)
            n2, d2, r2 = identity_pairs[key]
            sensitivity = {'n': n2, 'delta_dd': d2/n2, 'delta_return': r2/n2} if n2 else None
            if sensitivity is not None:
                for field, value in sensitivity.items():
                    checks.equal('identity_sensitivity/'+label+'/'+field, value, reported['identity_exclusion_sensitivity'][field])
            bootstrap_results[label] = intervals
    checks.equal('votes', votes, results['votes'])
    checks.equal('numerical_criteria_passed', all(v >= 3 for v in votes.values()), results['numerical_criteria_passed'])

    # Sample raw-price replay only after all aggregate calculations are complete.
    sample = set()
    for sym, days in dates_by_symbol.items():
        ordered = sorted(set(days))
        for day in (ordered[0], ordered[len(ordered)//2], ordered[-1]):
            sample.add((sym, day))
    sample.update((sym, day) for (sym, branch), day in branches.items())
    sample_rows = {}
    for key, rows in cohorts(ev/'episodes.csv.gz'):
        if key in sample:
            sample_rows[key] = rows
    checks.check('at_least_200_available_cohorts', len(sample_rows) >= min(200, frame_count))
    sampled_symbols = sorted({sym for sym, day in sample_rows})
    gap_examples = []
    raw_replays = 0
    for sym in sampled_symbols:
        path = data_dir/'adjusted'/(sym+'.json')
        checks.equal('adjusted_hash/'+sym, sha(path), manifest['symbols'][sym]['adjustedSha256'])
        stored = json.loads(path.read_text())
        checks.equal('adjusted_symbol/'+sym, stored['symbol'], sym)
        segments = split_on_calendar(stored['bars'], calendar)
        needed = {day: sample_rows[(sym, day)] for s, day in sample_rows if s == sym}
        for bars in segments:
            indices = {b[0]: j for j, b in enumerate(bars)}
            selected = sorted(set(needed) & set(indices))
            if not selected:
                continue
            tops, atr = independent_indicators(bars)
            for day in selected:
                t = indices[day]
                checks.check('warmup/'+sym+'/'+day, t >= 199)
                checks.check('complete_window/'+sym+'/'+day, t+64 < len(bars))
                for row in needed[day]:
                    observed = replay(bars, t, tops, atr[t], row['policy'], row['cost'])
                    label = f"{sym}/{day}/{row['cost']}/{row['policy']}"
                    checks.equal('replay_events/'+label, observed['events'], row['events'])
                    for metric in ('return',)+MEAN_FIELDS:
                        checks.equal('replay/'+label+'/'+metric, observed[metric], row[metric])
                    if row['cost'] == 0:
                        for example in observed['gap_examples']:
                            gap_examples.append({'symbol': sym, 'signalDate': day, 'policy': row['policy'], **example})
                    raw_replays += 1
    checks.equal('replayed_policy_rows', raw_replays, len(sample_rows)*8)
    reason_counts = {reason: sum(x['reason'] == reason for x in gap_examples) for reason in ('profit_giveback','prior10_close_low')}
    nonzero_gaps = {reason: sum(x['reason'] == reason and abs(x['gapReturn']) > 1e-12 for x in gap_examples) for reason in reason_counts}
    for reason in reason_counts:
        if any(k[1] == ('R1' if reason == 'profit_giveback' else 'E1') for k in branches):
            checks.check('gap_branch_covered/'+reason, reason_counts[reason] > 0)

    # The full account path is a separate diagnostic. Check every reported group
    # median here, without claiming this re-executes the account financing ledger.
    accounts = json.loads((ev/'accounts.json').read_text())
    for label, reported in results['account_summary'].items():
        group, period, policy = label.split('|')
        eligible = [r for r in accounts if group in r['groups'] and r['period'] == period and r['policy'] == policy]
        checks.equal('account_n/'+label, len(eligible), reported['n_stocks'])
        for metric in ('return','cagr','mdd','calmar','exposure','transactions','campaigns'):
            values = [r[metric] for r in eligible if r[metric] is not None]
            checks.equal('account_median/'+label+'/'+metric, statistics.median(values) if values else None, reported[metric])
    for p in source_paths:
        key = str(p.relative_to(root)) if p.is_relative_to(root) else str(p)
        checks.equal('read_only/'+key, sha(p), before[key])
    report = {'schemaVersion': 'astra-exit-independent-audit/1',
        'status': 'PASS_CONSISTENCY_ONLY' if not checks.failures else 'FAIL_INCONSISTENCIES',
        'completedAt': dt.datetime.now(dt.timezone.utc).isoformat(),
        'comparisons': checks.n, 'mismatches': len(checks.failures), 'failures': checks.failures[:200],
        'maxAbsoluteNumericDifference': checks.max_abs_error,
        'tolerance': {'absolute': 2e-10, 'relative': 5e-10},
        'sourceHashes': before, 'auditCodeSha256': sha(__file__),
        'episodeRows': row_count, 'pairedCohorts': frame_count,
        'sampledCohorts': len(sample_rows), 'sampledSymbols': len(sampled_symbols),
        'rawPolicyReplays': raw_replays, 'replayedPolicyCosts': 'all four policies at cost 0 and 0.001',
        'selection': 'per-symbol first/middle/last plus earliest R1 and E1 branch dates; no performance ranking',
        'actualNextOpenBranchExamples': reason_counts, 'nonzeroOpenGapExamples': nonzero_gaps,
        'gapExamples': gap_examples[:40], 'bootstrap': bootstrap_results,
        'independentVotes': votes, 'reportedNumericalCriteriaPassed': results['numerical_criteria_passed'],
        'selfTests': self_test(),
        'scopeLimits': ['No import of experiment.py, data_tools.py or vendor signal code.',
            'Independent top/ATR and 100-unit pending-order replay checks selected cohorts; all CSV group/daily aggregates checked.',
            'Account group medians checked; full account financing/time-series ledger is not independently replayed by this script.',
            'Numerical consistency is not evidence of predictive accuracy, causal benefit, identity accuracy, deployability or a 70% win rate.',
            'Complete-window selection and current-universe biases remain; no new strategy or market backtest is selected.']}
    target = ev/'independent-audit.json'
    if target.exists():
        raise RuntimeError('Preserve existing independent-audit.json; choose a separate evidence snapshot for a rerun')
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    lines = ['# 獨立結果一致性查核', '', f"狀態：{report['status']}。共{checks.n:,}項比較，{len(checks.failures):,}項不一致。",
        f"全體CSV {row_count:,}列／{frame_count:,}配對窗口；原價抽核{len(sample_rows):,}窗口、{len(sampled_symbols)}股票、{raw_replays:,}組政策與成本。",
        '依原始調整價格重建ATR及頂訊號，再用獨立逐日待成交狀態機，以次開盤價格核對股數、現金、成交日期、報酬、回撤及費用。',
        f"R1減碼及E1餘部出場的非零跳空例數：{nonzero_gaps}。", '',
        '全量核對分組n／正報酬比例／平均賺賠／均值／中位數及其他報表欄位、配對差及日期數列；以獨立直接區塊加總重抽20/60/126日CI與判定。',
        '帳戶組別中位數另核對accounts.json；本程式沒有独立重播完整有限資金帳戶曲線，不能把此範圍冒充已全面查核。'.replace('独立','獨立'),
        '程式和結果來源雜湊在查核前後相同。查核通過只表示本程式檢查範圍內的數字一致，不表示策略有效、能辨識機構或有70%未來勝率。']
    if checks.failures:
        lines.extend(['', '前20項差異：', '```json', json.dumps(checks.failures[:20], ensure_ascii=False, indent=2), '```'])
    (ev/'independent-audit.md').write_text('\n\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('status','comparisons','mismatches','episodeRows','sampledCohorts','rawPolicyReplays','nonzeroOpenGapExamples','independentVotes')},ensure_ascii=False), flush=True)
    return 1 if checks.failures else 0


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=HERE)
    p.add_argument('--data-dir', type=Path)
    p.add_argument('--self-test', action='store_true')
    args = p.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), indent=2))
    else:
        raise SystemExit(run(args.root.resolve(), (args.data_dir or args.root/'data').resolve()))
