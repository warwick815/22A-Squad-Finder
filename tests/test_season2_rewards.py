import unittest
from datetime import datetime, timezone, timedelta
from cash_rewards import apply_cash
from rank_divisions import division, thresholds
from progression import rank_for
from seasons import close_season

class SeasonTwoTests(unittest.TestCase):
 def setUp(self):
  self.p=dict(rank_rules=2,points2=0,rank=0,active=True,hold=None,pending=None,baseline={},discord_id=1)
  self.t=datetime(2026,10,14,12,tzinfo=timezone.utc)
 def feed(self,cash,source='a',seconds=300):
  self.t+=timedelta(seconds=seconds)
  return apply_cash(self.p,cash,self.t.isoformat(),source,now=self.t)
 def test_baseline_fraction_and_cap(self):
  self.assertEqual(self.feed(1000000),0)
  self.assertEqual(self.feed(1005000),0)
  self.assertEqual(self.feed(1010000),1)
  self.assertEqual(self.feed(2010000),24)
  self.assertEqual(self.feed(3010000),0)
  self.assertEqual(self.p['points2'],50)
  self.assertEqual(self.feed(3020000,seconds=86400),1)
 def test_correction_duplicate_and_source_switch(self):
  self.feed(100000);self.feed(120000)
  self.assertEqual(self.feed(120000,seconds=0),0)
  self.assertEqual(self.feed(50000),0)
  self.assertEqual(self.feed(120000),0)
  self.assertEqual(self.feed(130000),1)
  self.assertEqual(self.feed(999999,'b'),0)
 def test_paused_and_season_reset(self):
  self.feed(0);self.p['active']=False;self.assertEqual(self.feed(100000),0)
  self.p['active']=True;self.assertEqual(self.feed(110000),1)
  close_season(dict(players={'s':self.p},season=1),1)
  self.assertNotIn('cash_reward',self.p);self.assertEqual(self.p['points2'],0)
  self.assertEqual(thresholds(self.p)[1],313)
 def test_rank_boundaries_and_top_divisions(self):
  self.assertEqual(rank_for(624,0,thresholds(self.p)),0)
  self.assertEqual(rank_for(626,0,thresholds(self.p)),1)
  for score,name in [(0,'Bronze'),(105,'Silver'),(209,'Gold')]:
   self.p['points2']=score*2;self.assertEqual(division(self.p)['name'],name)
  self.p.update(rank=6,points2=25000)
  self.assertEqual(division(self.p)['name'],'Gold');self.assertIsNone(division(self.p)['target'])
 def test_old_season_no_cash(self):
  self.p['rank_rules']=1;self.feed(0);self.assertEqual(self.feed(999999),0)
 def test_cash_promotes_and_records_history(self):
  self.p['points2']=624;self.feed(0)
  self.assertEqual(self.feed(10000),1)
  self.assertEqual(self.p['rank'],1);self.assertEqual(self.p['pending']['to'],1)
  self.assertEqual(self.p['history'][-1]['kind'],'Cash earned bonus')
