"""Independent synthetic accounting/clock oracles. No market inputs or network."""
import copy
import datetime as dt
import math
import unittest

import experiment as x

T = 20
E = T + 1
END = T + 64


def bars(n=170):
    out = []
    day = dt.date(2020, 1, 1)
    while len(out) < n:
        if day.weekday() < 5:
            out.append([day.isoformat(), 100., 101., 99., 100., 1000])
        day += dt.timedelta(days=1)
    return out


def put(b, i, opening=None, close=None, high=None):
    if opening is not None:
        b[i][1] = float(opening)
    if close is not None:
        b[i][4] = float(close)
    b[i][2] = max(b[i][1], b[i][4]) + 1 if high is None else float(high)
    b[i][3] = min(b[i][1], b[i][4]) - 1


class EpisodeOracles(unittest.TestCase):
    def run_episode(self, b=None, tops=(), policy='B0', cost=0):
        return x.episode(b if b is not None else bars(), T, set(tops), 10., policy, cost)

    def test_flat_prices_common_window_and_no_cash_interest(self):
        for policy in x.POLICIES:
            with self.subTest(policy=policy):
                r = self.run_episode(policy=policy)
                self.assertEqual(len(r['nav']), 65)
                self.assertEqual(r['nav'], [1.] * 65)
                self.assertEqual(r['return'], 0.)
                self.assertEqual(r['mdd'], 0.)
                self.assertEqual(r['hold'], 40)
                self.assertEqual(r['events'], [(T + 41, 1., 'time40')])

    def test_first_top_executes_next_open_even_after_gap(self):
        b = bars()
        put(b, T + 5, close=150)
        put(b, T + 6, opening=70)
        r = self.run_episode(b, [T + 5])
        self.assertAlmostEqual(r['return'], -.30)
        self.assertEqual(r['events'], [(T + 6, 1., 'first_top')])

    def test_top_on_signal_day_is_not_new_position_exit(self):
        r = self.run_episode(tops=[T])
        self.assertEqual(r['events'], [(T + 41, 1., 'time40')])

    def test_top_search_right_boundary_inclusive(self):
        r = self.run_episode(tops=[T + 40])
        self.assertEqual(r['events'], [(T + 41, 1., 'first_top')])
        beyond = self.run_episode(tops=[T + 41])
        self.assertEqual(beyond['events'], [(T + 41, 1., 'time40')])

    def test_first_top_selected_not_later_better_price(self):
        b = bars()
        put(b, T + 6, opening=80)
        put(b, T + 11, opening=200)
        r = self.run_episode(b, [T + 5, T + 10])
        self.assertAlmostEqual(r['return'], -.20)
        self.assertEqual(r['events'][0][0], T + 6)

    def test_r1_arms_on_close_reduces_once_with_fixed_initial_quantity(self):
        b = bars()
        put(b, E, close=120)
        put(b, E + 1, close=140)
        put(b, E + 2, close=130)
        put(b, E + 3, opening=90)
        put(b, T + 11, opening=110)
        r = self.run_episode(b, [T + 10], 'R1')
        self.assertEqual(r['events'], [(E + 3, .5, 'profit_giveback'), (T + 11, .5, 'first_top')])
        self.assertAlmostEqual(r['return'], 0.)  # .5*.90 + .5*1.10 - 1
        self.assertTrue(r['triggered'])
        self.assertEqual(r['transactions'], 3)
        self.assertAlmostEqual(sum(f for _, f, _ in r['events']), 1.)

    def test_r1_only_intraday_high_is_not_qualification(self):
        b = bars()
        put(b, E, close=110, high=200)
        put(b, E + 1, close=100)
        r = self.run_episode(b, [T + 10], 'R1')
        self.assertFalse(r['triggered'])
        self.assertEqual(r['events'], [(T + 11, 1., 'first_top')])

    def test_r1_same_open_full_exit_takes_priority(self):
        b = bars()
        put(b, E, close=120)
        put(b, E + 1, close=110)
        put(b, E + 2, opening=75)
        r = self.run_episode(b, [E + 1], 'R1')
        self.assertEqual(r['events'], [(E + 2, 1., 'first_top')])
        self.assertFalse(r['triggered'])
        self.assertAlmostEqual(r['return'], -.25)
        self.assertEqual(r['transactions'], 2)

    def test_r1_does_not_arm_below_exact_2atr_threshold(self):
        b = bars()
        put(b, E, close=119.999)
        put(b, E + 1, close=80)
        r = self.run_episode(b, [T + 10], 'R1')
        self.assertFalse(r['triggered'])

    def test_e1_prior10_is_strict_and_half_sale_is_not_own_win(self):
        b = bars()
        put(b, E + 2, opening=120, close=100)  # equal prior min, no trend exit
        put(b, E + 3, close=99)  # below prior 10, execution one day later
        put(b, E + 4, opening=60)
        r = self.run_episode(b, [E + 1], 'E1')
        self.assertEqual(r['events'], [(E + 2, .5, 'first_top_half'), (E + 4, .5, 'prior10_close_low')])
        self.assertAlmostEqual(r['return'], -.10)  # 0.5*1.20 + 0.5*.60 - 1
        self.assertEqual(x.summarize([r])['win'], 0.)
        self.assertEqual(x.summarize([r])['mean_loss'], r['return'])

    def test_e1_prior10_excludes_current_close(self):
        b = bars()
        put(b, E + 2, opening=110, close=90)  # first half executes then close can trigger
        put(b, E + 3, opening=80)
        r = self.run_episode(b, [E + 1], 'E1')
        self.assertEqual(r['events'][-1], (E + 3, .5, 'prior10_close_low'))
        self.assertAlmostEqual(r['return'], -.05)

    def test_e1_trend_break_before_half_cannot_exit_early(self):
        b = bars()
        put(b, E, close=50)
        r = self.run_episode(b, [T + 10], 'E1')
        self.assertEqual(r['events'][0], (T + 11, .5, 'first_top_half'))
        self.assertEqual(r['events'][-1], (END, .5, 'time63'))

    def test_e1_second_top_does_not_reduce_again(self):
        r = self.run_episode(tops=[T + 5, T + 12, T + 20], policy='E1')
        self.assertEqual(r['events'], [(T + 6, .5, 'first_top_half'), (END, .5, 'time63')])

    def test_e1_time63_uses_final_open_not_final_close(self):
        b = bars()
        put(b, END, opening=150, close=20)
        r = self.run_episode(b, [T + 5], 'E1')
        self.assertAlmostEqual(r['return'], .25)
        self.assertEqual(r['events'][-1], (END, .5, 'time63'))
        self.assertEqual(r['hold'], 63)
        self.assertAlmostEqual(r['nav'][-1], 1.25)

    def test_cash_plus_remaining_shares_mdd(self):
        b = bars()
        put(b, E, close=120)
        put(b, E + 1, close=140)
        put(b, E + 2, close=130)
        put(b, E + 3, opening=120, close=100)
        for j in range(E + 4, T + 12):
            put(b, j, opening=80, close=80)
        r = self.run_episode(b, [T + 10], 'R1')
        self.assertAlmostEqual(r['return'], 0.)  # .60 cash + .40 residual
        self.assertAlmostEqual(r['mdd'], 1 - 1 / 1.4)
        self.assertAlmostEqual(r['nav'][E + 3 - E + 1], 1.10)

    def test_cost_on_executed_value_and_initial_budget(self):
        c = .001
        for policy in ('B0', 'E1'):
            r = self.run_episode(tops=[T + 5], policy=policy, cost=c)
            self.assertAlmostEqual(r['return'], (1-c)/(1+c)-1)
        half = self.run_episode(policy='C50', cost=c)
        self.assertAlmostEqual(half['return'], .5 + .5*(1-c)/(1+c)-1)

    def test_cash_control_and_exposure_use_common63days(self):
        b = bars()
        put(b, T + 41, opening=120)
        r = self.run_episode(b, policy='C50')
        self.assertAlmostEqual(r['return'], .10)
        self.assertAlmostEqual(r['exposure'], .5*40/63)
        self.assertAlmostEqual(r['turnover'], .5+.6)

    def test_incomplete_common_window_is_not_shortened(self):
        for policy in x.POLICIES:
            with self.subTest(policy=policy):
                with self.assertRaisesRegex(ValueError, 'incomplete'):
                    self.run_episode(bars(END), tops=[T + 2], policy=policy)

    def test_invalid_ohlc_rejected_even_after_early_exit(self):
        for bad in (None, float('nan'), 0., -1.):
            with self.subTest(bad=bad):
                b = bars()
                b[END - 1][1] = bad
                with self.assertRaises(ValueError):
                    self.run_episode(b, tops=[T + 2])
        b = bars()
        b[E][2] = 50
        with self.assertRaisesRegex(ValueError, 'inconsistent'):
            self.run_episode(b)

    def test_future_tail_changes_do_not_change_earlier_reduction(self):
        b = bars()
        put(b, E, close=130)
        put(b, E + 1, close=120)
        altered = copy.deepcopy(b)
        for j in range(T + 15, len(b)):
            put(altered, j, opening=40, close=45)
        one = self.run_episode(b, [T + 30], 'R1')
        two = self.run_episode(altered, [T + 30], 'R1')
        self.assertEqual(one['events'][0], two['events'][0])
        self.assertEqual(one['events'][0], (E + 2, .5, 'profit_giveback'))
        self.assertEqual(one['nav'][:12], two['nav'][:12])

    def test_atr_is_prefix_invariant_wilder_recurrence(self):
        b = bars()
        a = x.atr14(b)
        self.assertIsNone(a[12])
        self.assertEqual(a[13], 2.)
        put(b, 14, high=113)  # TR14=14, preceding 14 TR values were 2
        aa = x.atr14(b)
        self.assertAlmostEqual(aa[14], (13*2+14)/14)
        altered = copy.deepcopy(b)
        for j in range(T+1, len(b)):
            put(altered, j, opening=500, close=500)
        self.assertEqual(x.atr14(altered)[:T+1], aa[:T+1])


class CalendarAndAccountOracles(unittest.TestCase):
    def test_ledger_terminal_cash_and_curve_dates(self):
        b = bars()
        put(b, T + 6, opening=120)
        put(b, END, opening=5, close=2)
        ep = x.episode(b, T, {T+5}, 10, 'B0')
        r = x.ledger(b, [T], {(T, 'B0'): ep}, T, END, 'B0')
        self.assertEqual(len(r['curve']), END-T+2)
        self.assertEqual(r['days'], END-T+1)
        self.assertEqual(r['curve'][:2], [1., 1.])  # initial + signal-day cash
        self.assertAlmostEqual(r['curve'][-1], 1.20)
        self.assertAlmostEqual(r['return'], .20)
        self.assertEqual(r['end'], b[END][0])
        years = (dt.date.fromisoformat(b[END][0])-dt.date.fromisoformat(b[T][0])).days/365.25
        self.assertAlmostEqual(r['cagr'], 1.2**(1/years)-1)

    def test_fixed_reset_same_day_new_signal_then_next_open(self):
        b = bars()
        t2 = END
        end2 = t2+64
        put(b, T+6, opening=120)
        put(b, t2+6, opening=120)
        trades = {(t, 'B0'): x.episode(b, t, {t+5}, 10, 'B0') for t in (T, t2)}
        r = x.ledger(b, [T, t2], trades, T, end2, 'B0')
        self.assertEqual(len(r['curve']), end2-T+2)
        self.assertAlmostEqual(r['return'], 1.2*1.2-1)
        self.assertAlmostEqual(r['curve'][END-T+1], 1.2)  # first terminal cash day
        self.assertAlmostEqual(r['curve'][END-T+2], 1.2)  # next entry same price
        self.assertEqual(r['campaigns'], 2)
        self.assertEqual(r['transactions'], 4)

    def test_ledger_zero_drawdown_calmar_is_undefined(self):
        b = bars()
        r = x.ledger(b, [], {}, T, END, 'B0')
        self.assertEqual(r['curve'], [1.]*(END-T+2))
        self.assertEqual(r['return'], 0.)
        self.assertEqual(r['mdd'], 0.)
        self.assertIsNone(r['calmar'])

    def test_gap_splits_warmup_segments_not_compress_trading_days(self):
        b = bars(10)
        cal = [row[0] for row in b]
        parts = x.longest_gap_free_segments(b[:4]+b[5:], cal)
        self.assertEqual([len(p) for p in parts], [4, 5])
        self.assertEqual(parts[1][0][0], cal[5])

    def test_bootstrap_weighted_counts_not_daily_equal_means(self):
        daily = [(1, .1, .2), (0, 0., 0.), (9, -.9, -.45), (0, 0., 0.)]
        # A full-length noncircular block only has one possible start.
        r = x.paired_bootstrap(daily, blocks=(4,), draws=20)['4']
        self.assertEqual(r['valid'], 20)
        for v in r['dd90']:
            self.assertAlmostEqual(v, -.08)
        for v in r['return90']:
            self.assertAlmostEqual(v, -.025)

    def test_bootstrap_empty_and_short_calendar_are_explicit(self):
        empty = x.paired_bootstrap([(0, 0, 0)]*10, blocks=(2,), draws=20)['2']
        self.assertEqual(empty['valid'], 0)
        self.assertEqual(empty['dd90'], [None, None])
        self.assertEqual(empty['return90'], [None, None])
        short = x.paired_bootstrap([(1, 0, 0)], blocks=(20,), draws=20)['20']
        self.assertEqual(short['valid'], 0)
        self.assertEqual(short['error'], 'short_calendar')


if __name__ == '__main__':
    unittest.main(verbosity=2)
