import json
import unittest
from unittest.mock import Mock
from betting import Book

def snap(k=100,d=20,t=1000,source='api:steam'):
    return {'2':dict(kills=k,deaths=d,time=t,source=source)}

class BettingTests(unittest.TestCase):
    def setUp(self):
        self.store=Mock();self.store.get.return_value=None
        self.book=Book(self.store)

    def active(self,mode='kills'):
        b=self.book.offer(1,2,500,mode,20,1,10,1000)
        snapshots=snap()
        if mode=='race':snapshots['1']=dict(snapshots['2'])
        self.book.accept(b,2,snapshots,1000)
        return b

    def test_winner_pot_and_no_duplicate_payout(self):
        b=self.active()
        self.book.observe(b,snap(120,25,4600),4600)
        self.assertEqual(self.book.wallet(1),9500)
        self.assertEqual(self.book.wallet(2),10500)
        self.book.observe(b,snap(130,30,4700),4700)
        self.assertFalse(self.book.finish(b,2,'duplicate'))
        self.assertEqual(sum(self.book.data['wallets'].values()),20000)

    def test_limit_can_fail_despite_kills(self):
        b=self.active('limit')
        self.book.observe(b,snap(125,31,4600),4600)
        self.assertEqual(b['winner'],1)

    def test_race_tie_refunds(self):
        b=self.active('race');data=snap(120,25,4600);data['1']=dict(data['2'])
        self.book.observe(b,data,4600)
        self.assertEqual(self.book.wallet(1),10000)
        self.assertEqual(self.book.wallet(2),10000)

    def test_reset_and_source_change_refund(self):
        for data in (snap(99,20,1200),snap(110,20,1200,'other:steam')):
            self.setUp();b=self.active();self.book.observe(b,data,1200)
            self.assertEqual(b['status'],'settled');self.assertIsNone(b['winner'])

    def test_missing_late_or_future_data_never_awards(self):
        b=self.active()
        self.book.observe(b,snap(150,20,4600),4500)
        self.assertEqual(b['status'],'active')
        self.book.observe(b,snap(150,20,5000),5000)
        self.assertEqual(b['status'],'active')
        self.book.observe(b,{},5501)
        self.assertIsNone(b['winner']);self.assertEqual(self.book.wallet(2),10000)

    def test_accept_auth_staleness_and_duplicate(self):
        b=self.book.offer(1,2,500,'kills',20,1,10,1000)
        with self.assertRaises(ValueError):self.book.accept(b,1,snap(),1000)
        with self.assertRaises(ValueError):self.book.accept(b,2,snap(t=600),1000)
        self.assertEqual(self.book.wallet(2),10000)
        self.book.accept(b,2,snap(),1000)
        with self.assertRaises(ValueError):self.book.accept(b,2,snap(),1000)
        self.assertEqual(self.book.wallet(2),9500)

    def test_expired_offer_and_decline_return_only_reserved_stake(self):
        b=self.book.offer(1,2,500,'kills',20,1,10,1000)
        with self.assertRaises(ValueError):self.book.accept(b,2,snap(),1601)
        self.assertEqual(self.book.wallet(1),10000);self.assertEqual(self.book.wallet(2),10000)

    def test_restart_keeps_wallet_and_active_bet(self):
        b=self.active()
        saved=self.store.set.call_args.args[1]
        self.store.get.return_value=saved
        loaded=Book(self.store)
        self.assertEqual(loaded.wallet(1),9500)
        loaded.observe(loaded.data['bets'][b['id']],snap(120,25,4600),4600)
        self.assertEqual(loaded.wallet(2),10500)

    def test_self_bet_open_bet_and_balance_limits(self):
        with self.assertRaises(ValueError):self.book.offer(1,1,500,'kills',20,1,10,1000)
        with self.assertRaises(ValueError):self.book.offer(1,2,1001,'kills',20,1,10,1000)
        self.active()
        with self.assertRaises(ValueError):self.book.offer(1,3,500,'kills',20,1,10,1000)
        self.book.data['wallets']['3']=0
        with self.assertRaises(ValueError):self.book.offer(3,4,500,'kills',20,1,10,1000)
