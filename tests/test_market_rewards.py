import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock
from betting import Book
from player_exchange import Exchange
from market_rewards import record_profit, reward_status, settle_rewards

class MarketRewardTests(unittest.TestCase):
    def setUp(self):
        store=Mock();store.get.return_value=None
        self.book=Book(store);Exchange(self.book).sync(2)
        self.p=dict(points2=0,rank=0,rank_rules=2,active=True,hold=None,baseline={},pending=None)
        self.ranks=NS(state={'season':2},find=lambda uid:('steam',self.p) if uid==1 else None,save=Mock())
    def test_net_profit_boundary_and_idempotence(self):
        record_profit(self.book,1,3200,86401)
        record_profit(self.book,1,-700,86402)
        self.assertEqual(reward_status(self.book,1,2,86403)['projected_elo'],40)
        settle_rewards(self.ranks,self.book,172799);self.assertEqual(self.p['points2'],0)
        settle_rewards(self.ranks,self.book,172800);self.assertEqual(self.p['points2'],80)
        settle_rewards(self.ranks,self.book,172801);self.assertEqual(self.p['points2'],80)
        self.assertEqual(len(self.p['history']),1)
    def test_losses_no_deduction_no_remainder_carry(self):
        record_profit(self.book,1,-1000,1)
        record_profit(self.book,1,999,86401)
        record_profit(self.book,1,999,172801)
        settle_rewards(self.ranks,self.book,259200)
        self.assertEqual(self.p['points2'],0)
        self.assertEqual(len(self.ranks.state['market_reward_receipts']),3)
    def test_hold_delays_and_previous_season_excluded(self):
        record_profit(self.book,1,1000,1);self.p['hold']='review'
        settle_rewards(self.ranks,self.book,86400);self.assertEqual(self.p['points2'],0)
        self.p['hold']=None;settle_rewards(self.ranks,self.book,86400);self.assertEqual(self.p['points2'],40)
        record_profit(self.book,1,2000,86401);self.ranks.state['season']=3
        settle_rewards(self.ranks,self.book,172800);self.assertEqual(self.p['points2'],40)
    def test_sale_uses_net_profit_and_refunds_excluded(self):
        ex=Exchange(self.book);ex.execute(1,2,'s','P','buy',10,100)
        self.assertFalse(self.book.data.get('market_profit_days'))
        ex.execute(1,2,'s','P','sell',5,200)
        self.assertEqual(sum(r['profit'] for r in self.book.data['market_profit_days'].values()),480)
        ex.sync(3)
        self.assertEqual(sum(r['profit'] for r in self.book.data['market_profit_days'].values()),480)
    def test_challenge_win_loss_and_duplicate_finish(self):
        b=dict(a=1,b=2,stake=1000,status='active')
        self.book.wallet(1);self.book.wallet(2)
        self.book.finish(b,1,'Won');self.book.finish(b,1,'Repeated')
        values={r['uid']:r['profit'] for r in self.book.data['market_profit_days'].values()}
        self.assertEqual(values,{'1':1000,'2':-1000})
    def test_reset_keeps_ledger(self):
        record_profit(self.book,1,1000,1)
        self.book.reset(9,0,2)
        settle_rewards(self.ranks,self.book,86400);self.assertEqual(self.p['points2'],40)
    def test_promotion_creates_pending_transition(self):
        record_profit(self.book,1,100000,1)
        settle_rewards(self.ranks,self.book,86400)
        self.assertGreater(self.p['rank'],0)
        self.assertEqual(self.p['pending']['after'],self.p['points2'])
