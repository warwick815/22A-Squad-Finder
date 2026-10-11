import asyncio
import json
import time
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock
import test_website as base
from betting import Betting
from website_medals import medals

class ClubTests(unittest.IsolatedAsyncioTestCase):
    headers=base.WebsiteTests.headers
    async def asyncSetUp(self):
        await base.WebsiteTests.asyncSetUp(self)
        self.saved={}
        self.bot.store=NS(get=lambda k:self.saved.get(k),set=lambda k,v:self.saved.update({k:v}))
        self.other=NS(id=456,display_name='Opponent',bot=False)
        self.stranger=NS(id=789,display_name='Stranger',bot=False)
        self.members={123:self.member,456:self.other,789:self.stranger}
        self.bot.guild.fetch_member=AsyncMock(side_effect=lambda uid:self.members[uid])
        self.bot.guild.get_member=Mock(side_effect=lambda uid:self.members.get(uid))
        self.bot.guild.members=list(self.members.values())
        self.bot.guild.me=NS(id=999)
        self.perms=NS(view_channel=True,send_messages=True,embed_links=True,read_message_history=True)
        self.channel=NS(id=77,permissions_for=Mock(return_value=self.perms))
        self.bot.guild.get_channel=Mock(return_value=self.channel)
        self.bot.betting=Betting(self.bot)
        self.book=self.bot.betting.book
        self.book.data['channel']=77
        self.bot.betting.snapshots=AsyncMock(return_value={'456':dict(kills=100,deaths=10,time=time.time(),source='api:private-steam')})
    async def asyncTearDown(self):await base.WebsiteTests.asyncTearDown(self)
    async def post(self,**changes):
        return await self.client.post('/api/club',headers=self.headers(),json=dict(action='offer',confirm=True,opponent='456',mode='kills',stake=500,hours=1,target=20,limit=10,**changes))
    async def action(self,uid,action,bid):
        self.site.sessions['session']['uid']=uid
        return await self.client.post('/api/club',headers=self.headers(),json={'action':action,'id':bid,'confirm':True})
    async def test_shared_wallet_no_get_reset_and_duplicate_offer(self):
        response=await self.client.get('/api/club',headers=self.headers())
        self.assertEqual(response.status,200);self.assertEqual((await response.json())['balance'],10000)
        self.assertEqual(self.book.data['wallets'],{})
        response=await self.post();self.assertEqual(response.status,200)
        self.assertEqual(self.book.wallet(123),9500)
        response=await self.post();self.assertEqual(response.status,400)
        self.assertEqual(self.book.wallet(123),9500)
        response=await self.client.get('/api/club',headers=self.headers());d=await response.json()
        self.assertEqual(d['reserved'],500);self.assertEqual(d['balance'],9500)
    async def test_accept_once_and_settle_using_existing_engine(self):
        await self.post();bid=next(iter(self.book.data['bets']))
        response=await self.action(123,'accept',bid);self.assertEqual(response.status,403)
        response=await self.action(456,'accept',bid);self.assertEqual(response.status,200)
        self.assertEqual(self.book.wallet(456),9500)
        response=await self.action(456,'accept',bid);self.assertEqual(response.status,400)
        b=self.book.data['bets'][bid]
        self.book.observe(b,{'456':dict(kills=125,deaths=15,time=b['end'],source='api:private-steam')},b['end'])
        self.assertEqual(self.book.wallet(456),10500)
        response=await self.client.get('/api/club',headers=self.headers());d=await response.json()
        self.assertNotIn('private-steam',str(d));self.assertEqual(d['bets'][0]['status'],'settled')
    async def test_missing_stale_future_baselines_do_not_charge(self):
        await self.post();bid=next(iter(self.book.data['bets']))
        for snap in ({},{'456':dict(kills=1,deaths=1,time=time.time()-400,source='a')},{'456':dict(kills=1,deaths=1,time=time.time()+400,source='a')}):
            self.bot.betting.snapshots.return_value=snap
            response=await self.action(456,'accept',bid);self.assertEqual(response.status,400)
            self.assertEqual(self.book.wallet(456),10000)
    async def test_nonparticipant_cannot_cancel_or_read_bet(self):
        await self.post();bid=next(iter(self.book.data['bets']))
        response=await self.action(789,'cancel',bid);self.assertEqual(response.status,403)
        response=await self.client.get('/api/club',headers=self.headers());self.assertEqual((await response.json())['bets'],[])
        response=await self.action(123,'cancel',bid);self.assertEqual(response.status,200)
        response=await self.action(123,'cancel',bid);self.assertEqual(response.status,400)
        self.assertEqual(self.book.wallet(123),10000)
    async def test_csrf_channel_and_numeric_validation(self):
        response=await self.client.post('/api/club',headers=self.headers(csrf='bad'),json={});self.assertEqual(response.status,403)
        for value in (True,500.5,'500'):
            payload=dict(action='offer',confirm=True,opponent='456',mode='kills',stake=value,hours=1,target=20,limit=10)
            response=await self.client.post('/api/club',headers=self.headers(),json=payload);self.assertEqual(response.status,400)
        self.perms.view_channel=False
        response=await self.client.get('/api/club',headers=self.headers());self.assertEqual(response.status,403)
        self.assertEqual(self.book.data['wallets'],{})
    async def test_expiry_refunds_and_active_cancel_rejected(self):
        await self.post();bid=next(iter(self.book.data['bets']));self.book.data['bets'][bid]['expires']=0
        response=await self.action(456,'accept',bid);self.assertEqual(response.status,400);self.assertEqual(self.book.wallet(123),10000)
    async def test_medals_persist_without_changing_rating(self):
        p=self.bot.progression.state['players']['76561190000000000']
        p['rank']=2
        m=medals(self.bot,'steam',p,{'kills':1001,'wins':55,'hoursPlayed':101})
        self.assertTrue(next(x for x in m if x['id']=='kills1000')['earned'])
        p['rank']=0
        m=medals(self.bot,'steam',p,{})
        self.assertTrue(next(x for x in m if x['id']=='nco')['earned'])
        self.assertTrue(next(x for x in m if x['id']=='kills1000')['earned'])
        self.assertIsNone(next(x for x in m if x['id']=='kills5000')['value'])
        self.assertEqual(p['points2'],380)

    async def test_race_requires_both_snapshots_and_active_cancel_fails(self):
        payload=dict(action='offer',confirm=True,opponent='456',mode='race',stake=500,hours=1,target=20,limit=10)
        response=await self.client.post('/api/club',headers=self.headers(),json=payload)
        self.assertEqual(response.status,200)
        bid=next(iter(self.book.data['bets']))
        response=await self.action(456,'accept',bid);self.assertEqual(response.status,400)
        snapshots=self.bot.betting.snapshots.return_value
        snapshots['123']=dict(snapshots['456'])
        response=await self.action(456,'accept',bid);self.assertEqual(response.status,200)
        response=await self.action(123,'cancel',bid);self.assertEqual(response.status,400)
        self.assertEqual(self.book.wallet(123),9500)
    async def test_concurrent_offers_reserve_one_stake(self):
        responses=await asyncio.gather(self.post(),self.post())
        self.assertEqual(sorted(r.status for r in responses),[200,400])
        self.assertEqual(len(self.book.data['bets']),1)
        self.assertEqual(self.book.wallet(123),9500)
    async def test_insufficient_wallet_and_confirmation_gate(self):
        self.book.data['wallets']['123']=50
        response=await self.post();self.assertEqual(response.status,400)
        response=await self.client.post('/api/club',headers=self.headers(),json={'action':'offer'})
        self.assertEqual(response.status,400);self.assertEqual(self.book.wallet(123),50)
        self.assertEqual(self.book.data['bets'],{})
