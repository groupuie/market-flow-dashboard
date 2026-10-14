"""Reproduce published descriptive intervals from daily aggregates only.

Independent implementation: explicit date indices and direct sums, not prefix sums.
Does not read stock prices or validate signals, regime availability, or strategy alpha.
Requires Python 3 and NumPy; no imports from expectancy_audit.py.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
NAMES = (
    'legacy_pooled_b0_minus_fixed19_all',
    'fixed19_same_date_non_signal_date_equal',
    'fixed19_same_date_non_signal_signal_weighted',
    'same_b0_rule_same_date_non_signal_date_equal',
)


def ratios(z):
    def div(a, b):
        return a / b if b > 0 else np.nan
    return (div(z[1], z[0]) - div(z[3], z[2]),
            div(z[5], z[4]), div(z[7], z[6]), div(z[9], z[8]))


def replay(daily_path, result_path, tolerance=1e-12):
    raw_daily = daily_path.read_bytes()
    raw_result = result_path.read_bytes()
    rows = json.loads(raw_daily)
    expected = json.loads(raw_result)
    by_date = {row['date']: row for row in rows}
    if len(by_date) != len(rows):
        raise ValueError('Daily aggregate file contains duplicate dates')
    dates = sorted(by_date)
    if len(dates) != expected['calendarN']:
        raise ValueError('Daily aggregates do not cover the reported full calendar')
    meta = expected['bootstrap']
    block, draws, seed = meta['block'], meta['draws'], meta['seed']
    if meta['rng'] != 'numpy.default_rng' or not meta['zeroDaysRetained']:
        raise ValueError('Unsupported RNG/calendar convention')
    if not 0 < block <= len(dates) or draws <= 0:
        raise ValueError('Invalid bootstrap parameters')
    alpha = (1 - meta['interval']) / 2
    max_difference = 0.0
    comparisons = 0
    detail = {}
    for state in ('strong', 'other'):
        values = np.zeros((len(dates), 10))
        for i, date in enumerate(dates):
            row = by_date[date]
            if row['state'] not in ('strong', 'other'):
                raise ValueError('Unknown regime label')
            if row['state'] == state:
                agg = np.asarray(row['aggregate'], dtype=float)
                if agg.shape != (10,) or not np.isfinite(agg).all():
                    raise ValueError('Invalid daily aggregate vector')
                values[i] = agg
        point = ratios(values.sum(axis=0))
        rng = np.random.default_rng(seed)
        distribution = []
        for _ in range(draws):
            sampled_dates = []
            while len(sampled_dates) < len(dates):
                start = int(rng.integers(0, len(dates) - block + 1))
                take = min(block, len(dates) - len(sampled_dates))
                sampled_dates.extend(range(start, start + take))
            distribution.append(ratios(values[sampled_dates].sum(axis=0)))
        distribution = np.asarray(distribution)
        detail[state] = {}
        for j, name in enumerate(NAMES):
            ref = expected['results'][state]['bootstrap'][name]
            finite = distribution[:, j][np.isfinite(distribution[:, j])]
            if len(finite) != ref['validDraws']:
                raise AssertionError(f'Valid-draw count differs: {state}/{name}')
            interval = np.quantile(finite, [alpha, 1-alpha]) if len(finite) else None
            if interval is None or ref['ci95'] is None:
                raise ValueError('Empty bootstrap distribution requires explicit review')
            differences = np.abs(np.asarray([point[j], *interval]) -
                                    np.asarray([ref['mean'], *ref['ci95']]))
            if not np.isfinite(differences).all() or (differences > tolerance).any():
                raise AssertionError(f'Estimate/interval differs: {state}/{name}')
            max_difference = max(max_difference, float(differences.max()))
            comparisons += 4  # point, lower, upper, and valid-draw count
            detail[state][name] = {'mean': point[j], 'ci95': interval.tolist(),
                                  'validDraws': len(finite)}
    return {'status': 'PASS_AGGREGATE_CONSISTENCY_ONLY',
            'scope': 'No raw-price, signal, point-in-time, or alpha validation.',
            'calendarN': len(dates), 'comparisons': comparisons,
            'maxAbsoluteDifference': max_difference, 'tolerance': tolerance,
            'numpyVersion': np.__version__,
            'dailySha256': hashlib.sha256(raw_daily).hexdigest(),
            'resultsSha256': hashlib.sha256(raw_result).hexdigest(),
            'replayed': detail}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--daily', type=Path, default=HERE/'audit-output/daily-aggregates.json')
    parser.add_argument('--results', type=Path, default=HERE/'audit-output/audit-results.json')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = replay(args.daily, args.results)
    text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.write_text(text, encoding='utf-8')
    print(text, end='')
