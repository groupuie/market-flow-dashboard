import datetime as dt
import json
import math
import unittest
from data_tools import decode_chart, completed_cutoff, signals, load_groups, calendar_diagnostics


def payload(**updates):
    r={'meta':{'symbol':'SPY','exchangeTimezoneName':'America/New_York'},
       'timestamp':[int(dt.datetime(2020,1,2,14,30,tzinfo=dt.timezone.utc).timestamp())],
       'indicators':{'quote':[{'open':[100],'high':[110],'low':[90],'close':[105],'volume':[123]}],
                     'adjclose':[{'adjclose':[52.5]}]}}
    r.update(updates)
    return {'chart':{'result':[r],'error':None}}


def decode(p):
    return decode_chart(json.dumps(p).encode(),'SPY','2004-01-01','2026-10-12')


class DataTest(unittest.TestCase):
    def test_all_ohlc_same_factor_without_round(self):
        o=decode(payload())
        self.assertEqual(o['bars'],[['2020-01-02',50.,55.,45.,52.5,123]])
        self.assertEqual(o['adjustmentFactors'],[['2020-01-02',.5]])
        self.assertFalse(o['adjustmentVerified'])

    def test_missing_price_not_replaced(self):
        p=payload();p['chart']['result'][0]['indicators']['quote'][0]['open'][0]=None
        with self.assertRaisesRegex(ValueError,'no usable bars'):decode(p)

    def test_missing_adjustment_not_assumed_one(self):
        p=payload();del p['chart']['result'][0]['indicators']['adjclose']
        with self.assertRaisesRegex(ValueError,'adjusted close'):decode(p)

    def test_duplicate_date_rejected(self):
        p=payload();r=p['chart']['result'][0];r['timestamp']*=2
        for x in r['indicators']['quote'][0].values():x*=2
        r['indicators']['adjclose'][0]['adjclose']*=2
        with self.assertRaisesRegex(ValueError,'duplicate daily date'):decode(p)

    def test_alias_symbol_rejected(self):
        p=payload();p['chart']['result'][0]['meta']['symbol']='QQQ'
        with self.assertRaisesRegex(ValueError,'symbol mismatch'):decode(p)

    def test_intraday_never_completed(self):
        before=dt.datetime(2026,10,13,20,14,tzinfo=dt.timezone.utc)
        after=dt.datetime(2026,10,13,20,15,tzinfo=dt.timezone.utc)
        self.assertEqual(completed_cutoff('2026-10-13',before),'2026-10-12')
        self.assertEqual(completed_cutoff('2026-10-13',after),'2026-10-13')

    def test_pinned_b2_allows_flat_sma_and_six_bar_spacing(self):
        c=[90.]*140+[100.]*74
        bars=[[f'{i:04d}',v,v,v,v,100] for i,v in enumerate(c)]
        self.assertEqual(signals(bars)['b2'],[199,205,211])

    def test_bottom_and_top_reversal(self):
        mk=lambda seq:[[str(i),v,v,v,v,1] for i,v in enumerate(seq)]
        self.assertEqual(signals(mk([100.,90.,80.,91.]))['bot'],[3])
        self.assertEqual(signals(mk([100.,110.,120.,109.]))['top'],[3])

    def test_groups_are_frozen_intersection(self):
        g=load_groups()
        self.assertEqual({k:len(v) for k,v in g.items()},{'ALL':266,'IDX':2,'MAG7':7,'NDX':57})
        self.assertNotIn('WBD',g['NDX'])
        self.assertTrue(set(g['MAG7'])<=set(g['ALL']))

    def test_calendar_gap_not_filled(self):
        obj={'bars':[['2020-01-02',1,1,1,1,1],['2020-01-06',1,1,1,1,1]],
             'qa':{'firstDate':'2020-01-02','lastDate':'2020-01-06'}}
        q=calendar_diagnostics(obj,['2020-01-02','2020-01-03','2020-01-06'])
        self.assertEqual(q['missingInsideObservedRange'],['2020-01-03'])
        self.assertEqual(len(obj['bars']),2)

if __name__=='__main__':unittest.main()
