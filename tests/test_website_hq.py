import asyncio
import time
import unittest
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock
import test_website as base
from state import Room
from website_analytics import history, movement


class HQTests(unittest.IsolatedAsyncioTestCase):
    headers = base.WebsiteTests.headers
    async def asyncSetUp(self):
        await base.WebsiteTests.asyncSetUp(self)
        self.member.guild_permissions=NS(manage_guild=True)
        self.bot.cfg=NS(guild_id=100)
        self.bot.mutation=asyncio.Lock()
        self.bot.rooms={}
        self.bot.reconcile=AsyncMock()
        self.bot.lfg=NS(permissions_for=Mock(return_value=NS(view_channel=True)))
        self.saved={}
        self.bot.store=NS(get=lambda k:self.saved.get(k),set=lambda k,v:self.saved.update({k:v}),save=Mock())
        self.bot.progression.lock=asyncio.Lock()
        self.bot.progression.save=Mock()
        self.player=self.bot.progression.state['players']['76561190000000000']
        self.player.update(hold=None,pending=None)

    async def asyncTearDown(self):
        await base.WebsiteTests.asyncTearDown(self)

    async def prepare(self, **command):
        response=await self.client.post('/api/staff/prepare',json={'action':'pause','target':'123','reason':'Staff review',**command},headers=self.headers())
        self.assertEqual(response.status,200,await response.text())
        return (await response.json())['token']

    async def confirm(self, token):
        return await self.client.post('/api/staff/confirm',json={'token':token},headers=self.headers())

    def bounty_feed(self):
        import kill_feed
        from unittest.mock import patch
        feed=kill_feed.KillFeed(NS(store=None))
        now=time.time()
        feed.state['last_on_22a']={'key':'76561198000000009','name':'Runner','victim':'[22A] Ghost','at':now-300}
        feed.state['live_since']=now-3600
        feed.post_announcements=AsyncMock()
        self.bot.kill_feed=feed
        p=patch('kill_feed.enabled',return_value=True);p.start();self.addCleanup(p.stop)
        return feed

    async def test_staff_can_post_then_cancel_a_bounty_with_review(self):
        feed=self.bounty_feed()
        status=await (await self.client.get('/api/staff',headers=self.headers())).json()
        self.assertEqual((status['bounty']['open'],status['bounty']['last']['name']),(None,'Runner'))
        response=await self.client.post('/api/staff/prepare',json={'action':'bounty-post','reason':'Posted from HQ'},headers=self.headers())
        review=await response.json()
        self.assertIn('Make Runner Most Wanted',review['summary'])
        self.assertIsNone(feed.state['bounty'])  # Review changes nothing.
        response=await self.confirm(review['token'])
        self.assertEqual(response.status,200,await response.text())
        self.assertEqual(feed.state['bounty']['name'],'Runner')
        feed.post_announcements.assert_awaited()
        token=await self.prepare(action='bounty-cancel',reason='Target left the game')
        response=await self.confirm(token);self.assertEqual(response.status,200,await response.text())
        self.assertIsNone(feed.state['bounty'])
        self.assertEqual(feed.state['bounties'][-1]['status'],'cancelled')
        self.assertIn('bounty-cancel',self.saved['website_audit_v1'])

    async def test_bounty_actions_refuse_when_not_possible(self):
        feed=self.bounty_feed()
        response=await self.client.post('/api/staff/prepare',json={'action':'bounty-cancel','reason':'No bounty'},headers=self.headers())
        self.assertEqual(response.status,409)
        token=await self.prepare(action='bounty-post',reason='First post')
        feed.state['last_on_22a']['at']+=1  # Something changed after the review.
        self.assertEqual((await self.confirm(token)).status,409)

    async def test_armoury_shows_merits_and_uses_one_item_a_day(self):
        import merits
        self.bot.kill_feed=NS(state={'open':{}},channel=lambda:None)
        self.player.update(active=True,hold=None)
        status=await (await self.client.get('/api/merits',headers=self.headers())).json()
        self.assertEqual((status['balance'],status['linked']),(0,True))
        response=await self.client.post('/api/merits',json={'item':'flak','confirm':True},headers=self.headers())
        self.assertEqual(response.status,409)  # Not enough Merits yet.
        merits.credit(self.bot.progression.state,self.player['discord_id'],20,'test',time.time()-86400)
        response=await self.client.post('/api/merits',json={'item':'flak'},headers=self.headers())
        self.assertEqual(response.status,400)  # Must confirm.
        response=await self.client.post('/api/merits',json={'item':'flak','confirm':True},headers=self.headers())
        body=await response.json()
        self.assertEqual((response.status,body['balance'],body['flak']),(200,10,10))
        response=await self.client.post('/api/merits',json={'item':'boost15','confirm':True},headers=self.headers())
        self.assertIn('already used',await response.text())

    async def test_staff_requires_current_permission_and_csrf(self):
        self.member.guild_permissions.manage_guild=False
        for route in ('/api/staff/prepare','/api/staff/confirm'):
            response=await self.client.post(route,json={},headers=self.headers())
            self.assertEqual(response.status,403)
        response=await self.client.get('/api/staff',headers=self.headers())
        self.assertEqual(response.status,403)
        self.member.guild_permissions.manage_guild=True
        response=await self.client.post('/api/staff/prepare',json={},headers=self.headers(csrf='wrong'))
        self.assertEqual(response.status,403)

    async def test_staff_review_has_no_effect_until_single_use_confirmation(self):
        token=await self.prepare()
        self.assertTrue(self.player['active'])
        response=await self.confirm(token);self.assertEqual(response.status,200)
        self.assertFalse(self.player['active']);self.assertIn('website_audit_v1',self.saved)
        response=await self.confirm(token);self.assertEqual(response.status,400)

    async def test_changed_player_expired_and_revoked_permission_are_rejected(self):
        token=await self.prepare();self.player['points2']+=2
        response=await self.confirm(token);self.assertEqual(response.status,409)
        token=await self.prepare();self.site.sessions['session']['confirmation']['expires']=0
        response=await self.confirm(token);self.assertEqual(response.status,400)
        token=await self.prepare();self.member.guild_permissions.manage_guild=False
        response=await self.confirm(token);self.assertEqual(response.status,403)
        self.assertTrue(self.player['active'])

    async def test_adjustment_preserves_identity_and_zero_floor(self):
        token=await self.prepare(action='adjust',amount=-500)
        response=await self.confirm(token);self.assertEqual(response.status,200)
        self.assertEqual(self.player['points2'],0)
        self.assertIn('76561190000000000',self.bot.progression.state['players'])
        self.assertEqual(self.player['history'][-1]['kind'],'Adjust rating')

    async def test_resume_missing_source_does_not_clear_review(self):
        self.player.update(active=False,hold='Counters decreased')
        self.bot.progression.fetch=AsyncMock(return_value=('2026-10-11T00:00:00Z',{}))
        token=await self.prepare(action='resume')
        response=await self.confirm(token);self.assertEqual(response.status,409)
        self.assertFalse(self.player['active']);self.assertEqual(self.player['hold'],'Counters decreased')

    async def test_resume_uses_member_source_timestamp(self):
        self.player.update(active=False,hold='Review',rating_source='public')
        stats={'kills':30,'deaths':5,'wins':3,'losses':1}
        self.bot.progression.fetch=AsyncMock(return_value=('2026-10-11T00:00:00Z',{'76561190000000000':stats}))
        self.bot.progression.source_times={'76561190000000000':'2026-10-11T01:00:00Z'}
        self.bot.progression.source_overrides={'76561190000000000':'public'}
        token=await self.prepare(action='resume');response=await self.confirm(token)
        self.assertEqual(response.status,200,await response.text())
        self.assertEqual(self.player['updated'],'2026-10-11T01:00:00Z');self.assertEqual(self.player['points2'],380)

    async def test_season_reset_archives_and_rejects_stale_second_request(self):
        self.player['steam_verified']=True;self.player['active']=False
        token=await self.prepare(action='end-season')
        response=await self.confirm(token);self.assertEqual(response.status,200)
        state=self.bot.progression.state
        self.assertEqual(state['season'],2);self.assertEqual(state['season_archives'][0]['players']['76561190000000000']['points2'],380)
        self.assertEqual(self.player['points2'],0);self.assertFalse(self.player['active']);self.assertTrue(self.player['steam_verified'])
        response=await self.confirm(token);self.assertEqual(response.status,400)

    async def test_tools_link_requires_verified_ownership_and_no_duplicate_approval(self):
        url='https://wardogs.tools/player/d8f9bef7-7dc6-4017-8228-0fd1ce527c93'
        response=await self.client.post('/api/staff/prepare',json={'action':'tools-link','target':'123','reason':'Correction','url':url},headers=self.headers())
        self.assertEqual(response.status,400)
        self.bot.tools_stats.fetch=AsyncMock(return_value={'failed':False});self.bot.tools_stats.save=Mock()
        token=await self.prepare(action='tools-link',url=url,ownership_checked=True)
        response=await self.confirm(token);self.assertEqual(response.status,200)
        self.assertEqual(self.player['approved_tools_profile'],url.split('/')[-1]);self.assertEqual(self.player['points2'],380)

    async def test_private_squad_hidden_and_not_joinable_by_guess(self):
        self.bot.rooms['private']=Room('private',999,'Secret','WarDogs',4,private=True,members=[999],status='active')
        self.assertEqual(self.site.squad_list(self.member),[])
        response=await self.client.post('/api/squads',json={'room':'private','action':'join'},headers=self.headers())
        self.assertEqual(response.status,404);self.assertEqual(self.bot.rooms['private'].members,[999])

    async def test_join_full_locked_and_leave_squad(self):
        room=Room('alpha',999,'Alpha','WarDogs',2,members=[999],status='active')
        self.bot.rooms['alpha']=room
        response=await self.client.post('/api/squads',json={'room':'alpha','action':'join','uid':777},headers=self.headers())
        self.assertEqual(response.status,200);self.assertEqual(room.members,[999,123])
        response=await self.client.post('/api/squads',json={'room':'alpha','action':'leave'},headers=self.headers())
        self.assertEqual(response.status,200);self.assertEqual(room.members,[999])
        room.locked=True
        response=await self.client.post('/api/squads',json={'room':'alpha','action':'join'},headers=self.headers())
        self.assertEqual(response.status,409)

    async def test_share_requires_explicit_confirmation_and_csrf(self):
        for payload,headers,status in [({},self.headers(),400),({'confirm':True},self.headers(csrf='bad'),403)]:
            response=await self.client.post('/api/share',json=payload,headers=headers)
            self.assertEqual(response.status,status)


class AnalyticsTests(unittest.TestCase):
    def test_history_excludes_previous_season_and_staff_reasons(self):
        p={'season_started':'2026-10-01T00:00:00Z','history':[
            {'at':'2026-09-01T00:00:00Z','kind':'results','before':0,'after':50},
            {'at':'2026-10-02T00:00:00Z','kind':'results','before':0,'after':100,'delta':{'kills':10},'weights':{'kills':5}},
            {'at':'2026-10-03T00:00:00Z','kind':'Adjust rating','before':100,'after':120,'reason':'Staff only'}]}
        result=history(p);self.assertEqual(len(result),2)
        self.assertEqual(result[0]['parts'][0]['points'],50);self.assertNotIn('Staff only',str(result))

    def test_weekly_movement_needs_real_same_season_snapshot(self):
        now=datetime.now(timezone.utc);players=[{'id':'1','position':2}]
        snapshot={'at':(now-timedelta(days=7)).isoformat(),'season':1,'order':{'1':4}}
        self.assertEqual(movement([snapshot],players,1,now),{'1':2})
        self.assertEqual(movement([snapshot],players,2,now),{})
        self.assertEqual(movement([],players,1,now),{})
