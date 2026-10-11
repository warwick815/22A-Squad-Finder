import unittest
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock, patch
from progression_sources import fetch_progression
from wduk_api import API_SOURCE, PUBLIC_SOURCE, apply_source
from progression import new_player, advance

A='76561198000000001'
B='76561198000000002'
def payload(ids,age=0,kills=100):
    return dict(updatedAt=(datetime.now(timezone.utc)-timedelta(seconds=age)).isoformat(),
                fields=['steamId','kills','deaths','wins','losses'],
                players=[[s,kills,20,3,4] for s in ids])

class SourceTests(unittest.IsolatedAsyncioTestCase):
    def make(self):
        return SimpleNamespace(state={'players':{A:new_player(1,None,None),B:new_player(2,None,None)}},
            bot=SimpleNamespace(player_panel=Mock()),save=Mock(),fetch_public_payload=AsyncMock(return_value=payload([A,B])))

    async def test_missing_player_routes_by_steam_and_stays_public_after_restart(self):
        r=self.make()
        with patch('wduk_api.enabled',return_value=True),patch('wduk_api.fetch_clan',new=AsyncMock(return_value=payload([A]))):
            _,rows=await fetch_progression(r)
        self.assertEqual(set(rows),{A,B})
        self.assertEqual(r.source_overrides,{A:API_SOURCE,B:PUBLIC_SOURCE})
        self.assertEqual(r.state['public_source_players'],[B])
        r.fetch_public_payload.return_value=payload([B],kills=200)
        with patch('wduk_api.enabled',return_value=True),patch('wduk_api.fetch_clan',new=AsyncMock(return_value=payload([A,B],kills=999))):
            _,rows=await fetch_progression(r)
        self.assertEqual(rows[B]['kills'],200)

    async def test_api_failure_falls_back_and_migration_preserves_rating(self):
        r=self.make();p=r.state['players'][A]
        p.update(rating_source=API_SOURCE,points2=500,rank=1,baseline={'kills':10,'deaths':5,'wins':1,'losses':1})
        with patch('wduk_api.enabled',return_value=True),patch('wduk_api.fetch_clan',new=AsyncMock(side_effect=ValueError('401'))):
            _,rows=await fetch_progression(r)
        self.assertTrue(apply_source(p,rows[A],r.source_times[A],r.source_overrides[A]))
        self.assertEqual(p['points2'],500)
        self.assertEqual(p['baseline']['kills'],100)

    async def test_stale_public_does_not_replace_good_api_or_pin_player(self):
        r=self.make();r.fetch_public_payload.return_value=payload([B],age=3600)
        with patch('wduk_api.enabled',return_value=True),patch('wduk_api.fetch_clan',new=AsyncMock(return_value=payload([A]))):
            _,rows=await fetch_progression(r)
        self.assertIn(A,rows);self.assertNotIn(B,rows)
        self.assertEqual(r.state['public_source_players'],[])

    async def test_public_pin_does_not_switch_back_if_public_fails(self):
        r=self.make();r.state['public_source_players']=[B]
        r.fetch_public_payload.side_effect=ValueError('unavailable')
        with patch('wduk_api.enabled',return_value=True),patch('wduk_api.fetch_clan',new=AsyncMock(return_value=payload([A,B]))):
            _,rows=await fetch_progression(r)
        self.assertNotIn(B,rows)

    async def test_both_unavailable_preserve_player_state(self):
        r=self.make();r.fetch_public_payload.side_effect=ValueError('down')
        with patch('wduk_api.enabled',return_value=True),patch('wduk_api.fetch_clan',new=AsyncMock(side_effect=ValueError('down'))):
            with self.assertRaises(ValueError):await fetch_progression(r)
        self.assertIsNone(r.state['players'][B]['baseline'])
        self.assertEqual(r.state['players'][B]['points2'],0)
