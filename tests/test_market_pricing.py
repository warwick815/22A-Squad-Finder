import copy
import unittest
import json
from types import SimpleNamespace
from datetime import datetime, timezone
from market_pricing import observe, record_feed, DAY, KEY

class MarketPricingTests(unittest.TestCase):
    def setUp(self):
        self.s={};self.p=dict(points2=0,active=True,hold=None,pending=None)
        self.row=dict(kills=100,deaths=40,teamKills=3,hoursPlayed=10.0,wins=2,losses=4)
        self.t=1700000000
        self.feed(0)
    def feed(self,seconds=300,source='a',**changes):
        self.t+=seconds;self.row.update(changes)
        observe(self.s,'steam',self.p,self.row,datetime.fromtimestamp(self.t,timezone.utc).isoformat(),source,now=self.t)
        return self.s['steam']
    def idle(self,days):
        for _ in range(int(days*DAY/300)):self.feed()
        return self.s['steam']
    def test_no_historical_penalties_and_one_day_grace(self):
        self.assertFalse(self.s['steam']['ready'])
        m=self.idle(1);self.assertEqual(m['value'],100)
        self.feed();self.assertLess(m['value'],100)
        self.assertEqual(m['score'],0)
    def test_two_percent_next_day_and_twenty_percent_cap(self):
        m=self.idle(2);self.assertAlmostEqual(m['value'],98,places=6)
        m=self.idle(12);self.assertAlmostEqual(m['value'],80,places=6)
        self.idle(1);self.assertAlmostEqual(m['value'],80,places=6)
    def test_activity_stops_decay_without_rebound(self):
        m=self.idle(3);old=m['value']
        self.feed(kills=101,hoursPlayed=10.1)
        self.assertEqual(m['inactive'],0);self.assertIsNone(m['decay_anchor'])
        self.assertLess(m['value']-old,.1)
    def test_outage_correction_and_switch_rebaseline_without_penalty(self):
        self.idle(1.5);old=self.s['steam']['value']
        m=self.feed(seconds=DAY*5,teamKills=30)
        self.assertEqual(m['value'],old);self.assertFalse(m['ready']);self.assertEqual(m['inactive'],0)
        self.feed();self.assertTrue(m['ready']);self.assertEqual(m['score'],0)
        self.feed(kills=1);self.assertFalse(m['ready']);self.assertEqual(m['value'],old)
        self.feed(source='b');self.assertFalse(m['ready'])
    def test_tk_weight_and_rolling_window(self):
        m=self.feed(kills=130,deaths=50,teamKills=5)
        self.assertEqual(m['score'],-10);self.assertLess(m['value'],100)
        self.idle(1);self.assertEqual(m['score'],0)
    def test_invalid_stale_duplicate_snapshots_do_not_charge_decay(self):
        m=self.feed();before=copy.deepcopy(m)
        self.feed(seconds=0);self.assertEqual(m['value'],before['value']);self.assertEqual(m['inactive'],before['inactive'])
        bad=dict(self.row);bad.pop('teamKills')
        observe(self.s,'steam',self.p,bad,datetime.fromtimestamp(self.t+300,timezone.utc).isoformat(),'a',now=self.t+300)
        self.assertFalse(m['ready']);self.assertEqual(m['value'],before['value'])
    def test_daily_move_limit_elo_cap_and_floor(self):
        self.p['points2']=100000
        for i in range(288):self.feed(kills=100+(i+1)*20)
        m=self.s['steam'];self.assertLessEqual(m['value'],115.000001);self.assertEqual(m['elo_bonus'],20)
        for i in range(288):self.feed(teamKills=3+i+1)
        self.assertGreaterEqual(m['value'],25)
    def test_season_baseline_preserves_market_value(self):
        m=self.feed(kills=110);old=m['value'];self.p['season_started']='new'
        self.feed(kills=140);self.assertFalse(m['ready']);self.assertEqual(m['value'],old);self.assertEqual(m['events'],[])

    def test_missing_player_resets_inactivity_without_changing_value(self):
        self.idle(1.5)
        old=self.s['steam']['value']
        saved={KEY:json.dumps(self.s)}
        bot=SimpleNamespace(store=SimpleNamespace(get=saved.get,set=saved.__setitem__))
        record_feed(bot,{}, {}, {}, {'steam':self.p})
        m=json.loads(saved[KEY])['steam']
        self.assertFalse(m['ready']);self.assertIsNone(m['baseline'])
        self.assertEqual(m['inactive'],0);self.assertEqual(m['value'],old)

    def test_playtime_alone_stops_inactivity(self):
        self.idle(1.5)
        m=self.feed(hoursPlayed=10.1)
        self.assertEqual(m['inactive'],0);self.assertIsNone(m['decay_anchor'])
