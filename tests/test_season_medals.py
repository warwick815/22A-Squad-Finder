import unittest
from season_medals import podium, awards
from seasons import close_season
from progression import new_player

class SeasonMedalTests(unittest.TestCase):
 def players(self,scores):
  result={}
  for i,score in enumerate(scores,1):
   p=new_player(i,None,None);p['points2']=score;result[str(i)]=p
  return result
 def test_award_at_close_survives_reset(self):
  state=dict(players=self.players([300,200,100,0]))
  close_season(state,1)
  self.assertEqual([a['metal'] for a in state['season_archives'][0]['podium']],['gold','silver','bronze'])
  self.assertEqual(awards(state,1)[0]['name'],'Season 1 Gold Medal')
  state['players']['1']['points2']=9999
  self.assertEqual(len(awards(state,1)),1)
  self.assertEqual(awards(state,4),[])
 def test_ties_follow_competition_ranks(self):
  result=podium(self.players([300,300,100,0]),1,'date')
  self.assertEqual([a['place'] for a in result],[1,1,3])
  self.assertEqual([a['metal'] for a in result],['gold','gold','bronze'])
 def test_old_archive_backfill_and_empty(self):
  state=dict(season_archives=[dict(season=1,players=self.players([200,100]),closed='date')])
  self.assertEqual(awards(state,2)[0]['metal'],'silver')
  self.assertEqual(podium({},1,'date'),[])
