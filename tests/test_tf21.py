import os
import unittest
from unittest.mock import patch

import tf21_api
from tf21_progress import advance_tf21

STEAM = '76561190000000001'
T = lambda m: f'2026-10-21T12:{m:02d}:00+00:00'


def player(**extra):
    p = {'discord_id': 1, 'points2': 400, 'rank': 0, 'active': True, 'hold': None, 'pending': None, 'rank_rules': 2}
    p.update(extra)
    return p


def counters(kills=100, deaths=50, wins=10, losses=5):
    return dict(kills=kills, deaths=deaths, wins=wins, losses=losses)


class NormalizeTests(unittest.TestCase):
    def test_accepts_common_layouts_and_field_names(self):
        for payload in (
            {'players': [{'steamId': STEAM, 'kills': 10, 'deaths': 5, 'wins': 2, 'losses': 1, 'teamKills': 0, 'kd': 2.0, 'online': True}],
             'updatedAt': '2026-10-21T12:00:00Z'},
            {'data': [{'steam_id': int(STEAM), 'kills': '10', 'deaths': 5.0, 'wins': 2, 'losses': 1, 'team_kills': 0, 'is_online': False}]},
            [{'steamid': STEAM, 'kills': 10, 'deaths': 5, 'wins': 2, 'losses': 1}],
        ):
            _, rows = tf21_api.normalize(payload)
            self.assertEqual({k: rows[STEAM][k] for k in tf21_api.COUNTERS}, dict(kills=10, deaths=5, wins=2, losses=1))

    def test_skips_bad_rows_and_rejects_unknown_shape(self):
        _, rows = tf21_api.normalize({'players': [{'steamId': 'abc', 'kills': 1, 'deaths': 1, 'wins': 1, 'losses': 1},
                                                  {'steamId': STEAM, 'kills': -1, 'deaths': 1, 'wins': 1, 'losses': 1}]})
        self.assertEqual(rows, {})
        with self.assertRaises(ValueError):
            tf21_api.normalize({'error': 'nope'})

    def test_reads_lowercase_railway_variable(self):
        with patch.dict(os.environ, {'tf21_api_key': ' tf21_abc '}, clear=False):
            os.environ.pop('TF21_API_KEY', None)
            self.assertEqual(tf21_api.api_key(), 'tf21_abc')

    def test_combined_adds_counters_and_recomputes_kd(self):
        row = tf21_api.combined({'kills': 100, 'deaths': 50, 'wins': 10, 'losses': 5, 'hoursPlayed': 20, 'kd': 2.0},
                                {'kills': 50, 'deaths': 50, 'wins': 5, 'losses': 5, 'teamKills': 1})
        self.assertEqual((row['kills'], row['deaths'], row['wins'], row['hoursPlayed'], row['kd'], row['teamKills']), (150, 100, 15, 20, 1.5, 1))


class ScoringTests(unittest.TestCase):
    def test_first_reading_is_baseline_only_then_new_results_score(self):
        p = player()
        self.assertEqual(advance_tf21(p, counters(), T(0)), 0)
        self.assertEqual(p['points2'], 400)
        advance_tf21(p, counters(kills=110, deaths=52, wins=11), T(5))
        # +10 kills x5, +2 deaths x-3, +1 win x20 = 64 points (128 half-points)
        self.assertEqual(p['points2'], 400 + 128)
        self.assertEqual(p['history'][-1]['origin'], 'TF21')

    def test_bad_readings_restart_without_points_or_hold(self):
        p = player()
        advance_tf21(p, counters(), T(0))
        advance_tf21(p, counters(kills=90), T(5))
        self.assertEqual((p['points2'], p['hold']), (400, None))
        self.assertIn('went down', p['tf21']['note'])
        advance_tf21(p, counters(kills=90 + 50000), T(10))
        self.assertEqual((p['points2'], p['hold']), (400, None))

    def test_waits_while_paused_held_or_pending(self):
        for state in ({'active': False}, {'hold': 'review'}, {'pending': {'id': 'x'}}):
            p = player(**state)
            advance_tf21(p, counters(), T(0))
            self.assertNotIn('tf21', p)

    def test_promotion_creates_pending_rank_change(self):
        p = player(points2=600)  # 300 ELO; Lance Corporal needs 313
        advance_tf21(p, counters(), T(0))
        advance_tf21(p, counters(wins=13), T(5))
        self.assertEqual(p['rank'], 1)
        self.assertIsNotNone(p['pending'])

    def test_readings_before_season_start_are_ignored(self):
        p = player(season_started=T(30))
        advance_tf21(p, counters(), T(10))
        self.assertNotIn('tf21', p)


if __name__ == '__main__':
    unittest.main()


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def serve(self, handler):
        from aiohttp import web
        app = web.Application()
        app.router.add_get('/api', handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0)
        await site.start()
        self.addAsyncCleanup(runner.cleanup)
        port = site._server.sockets[0].getsockname()[1]
        return f'http://127.0.0.1:{port}/api'

    async def test_sends_bearer_key_and_parses_reply(self):
        from aiohttp import web
        seen = {}
        async def handler(request):
            seen['auth'] = request.headers.get('Authorization')
            return web.json_response({'players': [{'steamId': STEAM, 'kills': 3, 'deaths': 1, 'wins': 1, 'losses': 0}]})
        url = await self.serve(handler)
        with patch.object(tf21_api, 'API_URL', url), patch.dict(os.environ, {'tf21_api_key': 'tf21_secret'}):
            updated, rows = await tf21_api.TF21API().fetch()
        self.assertEqual(seen['auth'], 'Bearer tf21_secret')
        self.assertEqual(rows[STEAM]['kills'], 3)

    async def test_rejected_key_gives_safe_error(self):
        from aiohttp import web
        async def handler(request):
            return web.json_response({'error': 'Not authorised.'}, status=401)
        url = await self.serve(handler)
        with patch.object(tf21_api, 'API_URL', url), patch.dict(os.environ, {'tf21_api_key': 'tf21_secret'}):
            with self.assertRaisesRegex(ValueError, 'Key rejected') as ctx:
                await tf21_api.TF21API().fetch()
        self.assertNotIn('tf21_secret', str(ctx.exception))
