import copy
import unittest
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
from season_stats import observe,statistics,fresh_state,standings,FIELDS
from seasons import close_season
from progression import new_player

class SeasonStatsTests(unittest.TestCase):
 def setUp(self):
  self.p=new_player(1,None,None);self.t=datetime(2026,10,16,12,tzinfo=timezone.utc)
  self.row=dict(kills=100,deaths=50,wins=20,losses=30,hoursPlayed=100,cashEarned=100000,teamKills=10,suicides=20)
 def feed(self,**changes):
  self.t+=timedelta(minutes=5);self.row.update(changes)
  observe(self.p,self.row,self.t.isoformat(),'a',now=self.t)
 def test_all_fields_and_ratios_are_season_deltas(self):
  original=copy.deepcopy(self.row);self.feed()
  self.assertEqual(statistics(self.p)['kills'],0)
  self.feed(kills=120,deaths=55,wins=22,losses=31,hoursPlayed=102,cashEarned=130000,teamKills=12,suicides=21)
  d=statistics(self.p)
  self.assertEqual([d[k] for k in FIELDS],[20,5,2,1,2,30000,2,1])
  self.assertEqual(d['kd'],4);self.assertEqual(d['killsPerHour'],10);self.assertAlmostEqual(d['winRate'],200/3)
  snapshot=copy.deepcopy(self.row);self.feed();self.assertEqual(statistics(self.p),d);self.assertEqual(self.row,snapshot)
 def test_reset_archive_immutable_and_lifetime_untouched(self):
  self.feed();self.feed(kills=110)
  state=dict(players={'steam':self.p});row=copy.deepcopy(self.row)
  archive=close_season(state,1)
  self.assertEqual(statistics(archive['players']['steam'])['kills'],10)
  self.assertTrue(all(statistics(self.p)[k]==0 for k in FIELDS));self.assertEqual(row,self.row)
  self.p['season_started']=self.t.isoformat()
  self.feed(kills=120);self.feed(kills=125)
  self.assertEqual(statistics(self.p)['kills'],5);self.assertEqual(statistics(archive['players']['steam'])['kills'],10)
 def test_old_archives_do_not_use_lifetime_or_current_stats(self):
  old=copy.deepcopy(self.p);old.pop('season_stats');old['points2']=400
  state=dict(players={'steam':self.p},season=2,season_archives=[dict(season=1,players={'steam':old},closed='date')])
  result=standings(state,SimpleNamespace(get_member=lambda uid:SimpleNamespace(display_name='Player')))
  self.assertEqual(result[1]['players'][0]['rating'],200)
  self.assertIsNone(result[1]['players'][0]['stats']['kills'])
  self.assertEqual(result[0]['players'][0]['stats']['kills'],0)
 def test_correction_and_stale_data_do_not_duplicate(self):
  self.feed();self.feed(kills=110);self.feed(kills=90);self.feed(kills=110)
  self.assertEqual(statistics(self.p)['kills'],10)
  observe(self.p,dict(self.row,kills=999),self.t.isoformat(),'a',now=self.t+timedelta(hours=1))
  self.assertEqual(statistics(self.p)['kills'],10)
