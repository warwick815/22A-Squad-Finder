import asyncio
import time
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import urlsplit, parse_qs

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer, make_mocked_request
import discord
from website import Website, SESSION_COOKIE, STATE_COOKIE


class WebsiteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.member = NS(id=123, display_name='<script>name</script>', display_avatar=NS(url='https://cdn.discordapp.com/a.png'), bot=False, roles=[])
        player = {'discord_id':123, 'rank':0, 'points2':380, 'active':True, 'baseline':{}, 'updated':'2026-10-11T00:00:00Z', 'history':[{'kind':'Admin adjustment','before':0,'after':380,'reason':'private staff note','actor':999}]}
        self.bot = NS(initialized=True, guild=NS(fetch_member=AsyncMock(return_value=self.member),get_member=Mock(return_value=self.member),members=[self.member]),
            progression=NS(find=Mock(return_value=('76561190000000000',player)),state={'players':{'76561190000000000':player}}),
            player_panel=NS(rows={'76561190000000000':{'kills':25,'deaths':5,'kd':5,'wins':2,'losses':1}},updated='2026-10-11T00:00:00Z'),
            specialities=NS(state={'members':{},'roles':{}},lock=asyncio.Lock(),save=Mock(),sync_member=AsyncMock()),
            tools_stats=NS(state={'links':{},'cache':{}}))
        self.site = Website(self.bot, 'https://example.test')
        self.site.client_id='123';self.site.client_secret='SECRET-NEVER-RETURN'
        self.site.sessions['session']={'uid':123,'csrf':'csrf','expires':time.monotonic()+1000,'write_after':0}
        app=web.Application(client_max_size=32768);self.site.install(app)
        self.client=TestClient(TestServer(app));await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()

    def headers(self, csrf='csrf', origin='https://example.test'):
        return {'Cookie':SESSION_COOKIE+'=session','X-CSRF-Token':csrf,'Origin':origin}

    async def test_public_shell_and_assets_without_private_data(self):
        r=await self.client.get('/');self.assertEqual(r.status,200)
        self.assertIn('22A WarDogs',await r.text())
        self.assertEqual(r.headers['X-Frame-Options'],'DENY')
        r=await self.client.get('/api/site');self.assertNotIn('SECRET',await r.text())
        for path in ['/assets/logo.png','/assets/app.js','/badges/pte.png']:
            r=await self.client.get(path);self.assertEqual(r.status,200)
        r=await self.client.get('/api/dashboard');self.assertEqual(r.status,401)

    async def test_assets_are_bundled_compressed_and_cached(self):
        r=await self.client.get('/');html=await r.text()
        self.assertEqual(r.headers['Cache-Control'],'no-cache')
        self.assertIn('/assets/bundle.css?v=',html);self.assertEqual(html.count('rel="stylesheet"'),1)
        version=self.site.assets.assets['bundle.css'].version
        r=await self.client.get('/assets/bundle.css?v='+version,headers={'Accept-Encoding':'gzip'})
        self.assertEqual(r.status,200);self.assertIn('immutable',r.headers['Cache-Control'])
        self.assertEqual(r.headers['Content-Encoding'],'gzip');self.assertIn('.pf-hero',await r.text())
        r=await self.client.get('/assets/medals-realistic.webp')
        self.assertEqual(r.status,200);self.assertEqual(r.headers['Cache-Control'],'public, max-age=86400')
        r=await self.client.get('/assets/missing.js');self.assertEqual(r.status,404)
        r=await self.client.get('/api/site');self.assertEqual(r.headers['Cache-Control'],'no-store')

    async def test_member_data_and_private_history_fields(self):
        r=await self.client.get('/api/dashboard',headers=self.headers());self.assertEqual(r.status,200)
        result=await r.json();self.assertEqual(result['me']['rating'],190)
        self.assertEqual(result['me']['stats']['kills'],25)
        self.assertNotIn('private staff note',str(result));self.assertNotIn('actor',str(result))
        self.assertNotIn('history',result['players'][0])
        self.bot.guild.fetch_member.assert_awaited_with(123)

    async def test_season_board_does_not_replace_lifetime_profile(self):
        from season_stats import fresh_state
        p=self.bot.progression.state['players']['76561190000000000']
        p['season_stats']=fresh_state()
        p['season_stats']['totals'].update(kills=3,deaths=1,wins=1,losses=1,hoursPlayed=2)
        response=await self.client.get('/api/dashboard',headers=self.headers())
        result=await response.json()
        season=result['season_standings'][0]['players'][0]
        self.assertEqual(season['stats']['kills'],3)
        self.assertEqual(season['stats']['kd'],3)
        self.assertEqual(season['stats']['winRate'],50)
        self.assertEqual(result['me']['stats']['kills'],25)
        self.assertEqual(result['players'][0]['stats']['kills'],25)

    async def test_wallet_breakdown_is_read_only_and_excludes_unaccepted_stakes(self):
        book={'wallets':{'123':7200},'bets':{
            'a':dict(a=123,b=456,status='offered',stake=500),
            'b':dict(a=456,b=123,status='offered',stake=1000),
            'c':dict(a=456,b=123,status='active',stake=300)},
            'exchange':{'holdings':{'123':{'456':dict(cost=2000,quantity=10)}}}}
        self.bot.betting=NS(book=NS(data=book))
        r=await self.client.get('/api/dashboard',headers=self.headers())
        d=await r.json()
        self.assertEqual(d['me']['wallet'],dict(available=7200,reserved=800,invested_cost=2000))
        self.assertEqual(d['players'][0]['wallet'],d['me']['wallet'])
        self.assertEqual(book['wallets'],{'123':7200})

    async def test_rejects_csrf_and_spoofed_member(self):
        for headers in [self.headers(csrf='bad'),self.headers(origin='https://evil.test'),{}]:
            r=await self.client.post('/api/specialities',json={'primary':'inf_at','secondary':[]},headers=headers)
            self.assertIn(r.status,(401,403))
        r=await self.client.post('/api/specialities',json={'primary':'inf_at','secondary':[],'uid':999},headers=self.headers())
        self.assertEqual(r.status,400);self.bot.specialities.save.assert_not_called()

    async def test_role_change_uses_signed_in_member_only(self):
        r=await self.client.post('/api/specialities',json={'primary':'inf_at','secondary':['sup_medic']},headers=self.headers())
        self.assertEqual(r.status,200)
        self.assertEqual(self.bot.specialities.state['members']['123']['primary'],'inf_at')
        self.bot.specialities.sync_member.assert_awaited_once_with(self.member)
        self.assertEqual(self.bot.progression.state['players']['76561190000000000']['points2'],380)

    async def test_discord_failure_keeps_pending_choice(self):
        self.bot.specialities.sync_member.side_effect=ValueError('missing role')
        r=await self.client.post('/api/specialities',json={'primary':None,'secondary':[]},headers=self.headers())
        self.assertEqual(r.status,200);self.assertIn('pending',(await r.json())['message'])
        self.assertTrue(self.bot.specialities.state['members']['123']['pending'])

    async def test_removed_member_denied(self):
        self.bot.guild.fetch_member.side_effect=discord.NotFound(NS(status=404,reason='Not Found'), 'gone')
        r=await self.client.get('/api/dashboard',headers=self.headers());self.assertEqual(r.status,403)
        r=await self.client.post('/api/specialities',json={'primary':'inf_at','secondary':[]},headers=self.headers())
        self.assertEqual(r.status,403);self.bot.specialities.save.assert_not_called()

    async def test_logout_and_expiry(self):
        r=await self.client.post('/auth/logout',json={},headers=self.headers());self.assertEqual(r.status,200)
        r=await self.client.get('/api/dashboard',headers=self.headers());self.assertEqual(r.status,401)
        self.site.sessions['session']={'expires':0}
        r=await self.client.get('/api/dashboard',headers=self.headers());self.assertEqual(r.status,401)

    async def test_oauth_state_binding_and_one_use(self):
        login=await self.site.login(make_mocked_request('GET','/auth/login'))
        query=parse_qs(urlsplit(login.location).query)
        self.assertEqual(query['scope'],['identify'])
        state=query['state'][0];binding=login.cookies[STATE_COOKIE].value
        self.site.exchange=AsyncMock(return_value=123)
        request=make_mocked_request('GET','/auth/callback?state='+state+'&code=good',headers={'Cookie':STATE_COOKIE+'='+binding})
        response=await self.site.callback(request)
        self.assertEqual(response.status,302);self.assertTrue(response.cookies[SESSION_COOKIE]['secure']);self.assertTrue(response.cookies[SESSION_COOKIE]['httponly'])
        with self.assertRaises(web.HTTPBadRequest):await self.site.callback(request)
        self.site.exchange.assert_awaited_once()

    async def test_wrong_browser_and_expired_oauth_rejected(self):
        self.site.states['known']={'binding':'right','expires':time.monotonic()+60}
        r=await self.client.get('/auth/callback?state=known&code=x',headers={'Cookie':STATE_COOKIE+'=wrong'})
        self.assertEqual(r.status,400)
        self.site.states['known']['expires']=0
        r=await self.client.get('/auth/callback?state=known&code=x',headers={'Cookie':STATE_COOKIE+'=right'})
        self.assertEqual(r.status,400)

    async def test_missing_settings_do_not_break_homepage(self):
        self.site.client_secret=''
        r=await self.client.get('/auth/login');self.assertEqual(r.status,503)
        r=await self.client.get('/');self.assertEqual(r.status,200)


if __name__=='__main__':unittest.main()
