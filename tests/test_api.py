import unittest
from datetime import datetime,timezone,timedelta
from wduk_api import normalize,apply_source,API_SOURCE,PUBLIC_SOURCE,FIELDS
from progression import new_player,advance

class ApiTests(unittest.TestCase):
    def payload(self):
        row=dict.fromkeys(FIELDS,0)
        row.update(steamId='76561198000000001',name='Test',favouriteServer='WDUK #1')
        return {'tag':'22A','period':'all','updatedAt':datetime.now(timezone.utc).isoformat(),'players':[row]}
    def test_real_schema(self):
        result=normalize(self.payload())
        self.assertEqual(result['fields'],list(FIELDS))
        self.assertEqual(len(result['players']),1)
    def test_reject_wrong_clan_period_missing_counters(self):
        for key,value in [('tag','OTHER'),('period','weekly')]:
            p=self.payload();p[key]=value
            with self.assertRaises(ValueError):normalize(p)
        p=self.payload();del p['players'][0]['wins']
        with self.assertRaises(ValueError):normalize(p)
    def test_stale_and_duplicate(self):
        p=self.payload();p['updatedAt']=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
        normalized=normalize(p)
        from progression import decode_stats
        with self.assertRaises(ValueError):decode_stats(normalized)
        p=self.payload();p['players']*=2
        with self.assertRaises(ValueError):normalize(p)
    def test_source_switch_preserves_rating_and_next_delta(self):
        counters=dict(wins=100,losses=80,kills=2000,deaths=1000)
        p=new_player(1,dict.fromkeys(counters,0),'2026-10-01T00:00:00+00:00')
        p.update(points2=500,rank=1,steam_verified=True,history=[{'test':'existing'}])
        self.assertTrue(apply_source(p,counters,'2026-10-01T01:00:00+00:00',API_SOURCE))
        self.assertEqual(p['points2'],500)
        self.assertEqual(p['history'],[{'test':'existing'}])
        self.assertTrue(p['steam_verified'])
        self.assertFalse(apply_source(p,counters,'2026-10-01T01:00:00+00:00',API_SOURCE))
        counters=counters.copy();counters['wins']+=1
        advance(p,counters,'2026-10-01T02:00:00+00:00')
        self.assertEqual(p['points2'],540)
        self.assertTrue(apply_source(p,counters,'2026-10-01T03:00:00+00:00',PUBLIC_SOURCE))
        self.assertEqual(p['points2'],540)
    def test_pause_and_hold_preserved(self):
        p=new_player(1,None,None);p.update(active=False,hold='review')
        apply_source(p,dict.fromkeys(('wins','losses','kills','deaths'),0),'2026-10-01T01:00:00+00:00',API_SOURCE)
        self.assertFalse(p['active']);self.assertEqual(p['hold'],'review')

class FetchErrors(unittest.IsolatedAsyncioTestCase):
    async def test_http_error_is_specific_and_cached_without_key(self):
        import os
        from unittest.mock import patch,MagicMock
        from wduk_api import ClanAPI
        response=MagicMock();response.status=403
        context=MagicMock();context.__aenter__.return_value=response
        session=MagicMock();session.get.return_value=context
        manager=MagicMock();manager.__aenter__.return_value=session
        api=ClanAPI()
        with patch.dict(os.environ,{'WDUK_API_KEY':'secret-test-value'}),patch('wduk_api.aiohttp.ClientSession',return_value=manager):
            for _ in range(2):
                with self.assertRaisesRegex(ValueError,'HTTP 403') as error:
                    await api.fetch()
                self.assertNotIn('secret-test-value',str(error.exception))
            self.assertEqual(session.get.call_count,1)

    async def test_cached_stale_payload_can_display(self):
        import time
        from wduk_api import ClanAPI
        api=ClanAPI();api.payload={'updatedAt':'2020-01-01T00:00:00Z'};api.until=time.monotonic()+60
        self.assertEqual(await api.fetch(),api.payload)
