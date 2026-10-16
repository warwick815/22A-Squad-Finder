import asyncio
import time
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace as NS
from unittest.mock import Mock
from betting import Book
from player_exchange import Exchange, price, fee, available
import test_website_club as base

class ExchangeTests(unittest.TestCase):
    def setUp(self):
        self.store=Mock();self.store.get.return_value=None
        self.book=Book(self.store);self.ex=Exchange(self.book);self.ex.sync(1)
    def test_price_rounding_and_fee(self):
        self.assertEqual(price(0),100);self.assertEqual(price(1000),150)
        self.assertEqual(price(1019),150);self.assertEqual(price(1020),151)
        self.assertEqual(fee(101),3)
    def test_global_supply_sells_release_stock(self):
        for uid in range(10,15):self.ex.execute(uid,2,'steam','P','buy',100,25)
        self.assertEqual(self.ex.supply(2)['remaining'],0)
        with self.assertRaises(ValueError):self.ex.execute(20,2,'steam','P','buy',1,25)
        self.assertEqual(self.book.wallet(20),10000)
        self.ex.execute(10,2,'steam','P','sell',3,25)
        self.assertEqual(self.ex.supply(2)['remaining'],3)
        self.ex.execute(20,2,'steam','P','buy',3,25)
        self.assertEqual(self.ex.supply(2)['remaining'],0)
        self.ex.sync(2);self.assertEqual(self.ex.supply(2)['remaining'],500)
    def test_legacy_over_cap_holdings_preserved(self):
        self.ex.state['holdings']={'9':{'2':dict(steam='steam',name='P',quantity=550,cost=13750)}}
        with self.assertRaises(ValueError):self.ex.execute(20,2,'steam','P','buy',1,25)
        self.ex.execute(9,2,'steam','P','sell',60,25)
        self.assertEqual(self.ex.supply(2)['remaining'],10)
    def test_buy_sell_partial_cost_basis_and_wallet(self):
        self.ex.execute(1,2,'steam','Player','buy',3,150)
        self.ex.execute(1,2,'steam','Player','buy',2,200)
        self.assertEqual(self.book.wallet(1),9150)
        self.ex.execute(1,2,'steam','Player','sell',2,250)
        self.assertEqual(self.book.wallet(1),9640)
        p=self.ex.state['holdings']['1']['2'];self.assertEqual(p['cost'],510);self.assertEqual(p['quantity'],3)
        self.ex.execute(1,2,'steam','Player','sell',3,250)
        self.assertEqual(self.book.wallet(1),10375);self.assertEqual(self.ex.state['holdings']['1'],{})
    def test_refund_once_and_betting_reset_no_double_credit(self):
        self.ex.execute(1,2,'steam','P','buy',3,150);self.ex.sync(2);self.ex.sync(2)
        self.assertEqual(self.book.wallet(1),10000)
        self.ex.execute(1,2,'steam','P','buy',2,100)
        self.book.reset(9,0,time.time());self.ex.sync(3)
        self.assertEqual(self.book.wallet(1),10000);self.assertEqual(self.ex.state['holdings'],{})
    def test_insufficient_self_oversell_and_identity_protection(self):
        for args in [(1,1,'s','P','buy',1,100),(1,2,'s','P','buy',100,200),(1,2,'s','P','sell',1,100),(1,2,'s','P','buy',True,100)]:
            with self.assertRaises(ValueError):self.ex.execute(*args)
        self.ex.execute(1,2,'s','P','buy',1,100)
        with self.assertRaises(ValueError):self.ex.execute(1,2,'new','P','sell',1,100)
        self.assertEqual(self.book.wallet(1),9900)
    def test_bet_and_shares_share_available_cash(self):
        self.ex.execute(1,2,'s','P','buy',95,100)
        self.book.offer(1,3,500,'kills',20,1,10,time.time())
        with self.assertRaises(ValueError):self.ex.execute(1,2,'s','P','buy',1,100)
        self.assertEqual(self.book.wallet(1),0)
    def test_fresh_active_only(self):
        p=dict(active=True,hold=None,pending=None,baseline={},updated=datetime.now(timezone.utc).isoformat())
        self.assertTrue(available(p));p['hold']='review';self.assertFalse(available(p))
        p['hold']=None;p['updated']='2000-01-01T00:00:00Z';self.assertFalse(available(p))

class ExchangeAPITests(unittest.IsolatedAsyncioTestCase):
    headers=base.ClubTests.headers
    async def asyncSetUp(self):
        await base.ClubTests.asyncSetUp(self)
        self.player=self.bot.progression.state['players']['76561190000000000']
        self.player.update(updated=datetime.now(timezone.utc).isoformat(),hold=None,pending=None)
        import json
        self.saved['player_market_v2']=json.dumps({'76561190000000000':dict(value=119,ready=True,updated=time.time(),inactive=0,reason='Fresh snapshot')})
    async def asyncTearDown(self):await base.ClubTests.asyncTearDown(self)
    async def quote(self):
        return await self.client.post('/api/exchange/quote',headers=self.headers(),json=dict(target='456',side='buy',quantity=2))
    async def trade(self,token):
        return await self.client.post('/api/exchange/trade',headers=self.headers(),json={'token':token})
    async def test_review_does_not_charge_confirm_once(self):
        q=await self.quote();self.assertEqual(q.status,200)
        token=(await q.json())['token'];self.assertEqual(self.book.wallet(123),10000)
        r=await self.trade(token);self.assertEqual(r.status,200)
        self.assertEqual(self.book.wallet(123),9762)
        r=await self.trade(token);self.assertEqual(r.status,409);self.assertEqual(self.book.wallet(123),9762)
        r=await self.client.get('/api/exchange',headers=self.headers());d=await r.json()
        self.assertEqual(d['portfolio'][0]['quantity'],2);self.assertNotIn('7656119',str(d))
    async def test_price_season_and_expiry_invalidate_quote(self):
        for change in ('rating','season','expiry','hold','reset'):
            self.player.update(points2=380,hold=None)
            q=await self.quote();token=(await q.json())['token']
            if change=='rating':self.player['points2']=400
            if change=='season':self.bot.progression.state['season']=2
            if change=='expiry':self.site.sessions['session']['exchange_quote']['expires']=0
            if change=='hold':self.player['hold']='review'
            if change=='reset':self.book.reset(9,0,time.time())
            r=await self.trade(token);self.assertEqual(r.status,409,change)
            self.assertEqual(self.book.wallet(123),10000)
    async def test_csrf_cross_session_and_channel_permissions(self):
        r=await self.client.post('/api/exchange/quote',headers=self.headers(csrf='bad'),json={});self.assertEqual(r.status,403)
        q=await self.quote();token=(await q.json())['token']
        self.site.sessions['other']=dict(uid=456,csrf='x',expires=time.monotonic()+100,write_after=0)
        from website import SESSION_COOKIE
        r=await self.client.post('/api/exchange/trade',headers={'Cookie':SESSION_COOKIE+'=other','Origin':'https://example.test','X-CSRF-Token':'x'},json={'token':token});self.assertEqual(r.status,409)
        self.perms.view_channel=False
        r=await self.trade(token);self.assertEqual(r.status,403)
        self.assertEqual(self.book.wallet(123),10000)
    async def test_own_listing_aggregate_and_self_trade_blocked(self):
        q=await self.quote();await self.trade((await q.json())['token'])
        self.site.sessions['session']['uid']=456
        r=await self.client.get('/api/exchange',headers=self.headers());d=await r.json()
        self.assertEqual(d['own_stock']['supply']['owned'],2)
        self.assertEqual(d['own_stock']['holders'],1)
        self.assertTrue(next(p for p in d['market'] if p['id']=='456')['self'])
        self.assertNotIn('steam',d['own_stock'])
        r=await self.client.post('/api/exchange/quote',headers=self.headers(),json=dict(target='456',side='buy',quantity=1))
        self.assertEqual(r.status,400)
