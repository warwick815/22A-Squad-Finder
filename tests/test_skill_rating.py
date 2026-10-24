import asyncio
import json
import unittest
from types import SimpleNamespace

import skill_rating as sr
from progression import SCORING, advance
from tf21_progress import advance_tf21


def row(kph=10, kd=1.0, hours=50, wr=0.5, cph=100000, tk_per_100=1.0, games=100):
    kills = int(kph * hours)
    return {'hoursPlayed': hours, 'kills': kills, 'deaths': int(kills / kd), 'wins': int(games * wr), 'losses': games - int(games * wr),
            'cashEarned': int(cph * hours), 'teamKills': int(kills * tk_per_100 / 100)}


def population():
    rows = [row(kph=4 + i * 0.2, kd=0.5 + i * 0.02, wr=0.3 + i * 0.004, cph=50000 + i * 1000, tk_per_100=3 - i * 0.025) for i in range(100)]
    return sr.build(rows, now=0)


class RatingTests(unittest.TestCase):
    def test_better_players_rate_higher_and_average_is_x1(self):
        pop = population()
        top = sr.rate(row(kph=30, kd=3, wr=0.7, cph=200000, tk_per_100=0.1), pop)
        mid = sr.rate(row(kph=14, kd=1.5, wr=0.5, cph=100000, tk_per_100=1.75), pop)
        low = sr.rate(row(kph=2, kd=0.3, wr=0.2, cph=10000, tk_per_100=5), pop)
        self.assertGreater(top['rating'], mid['rating'])
        self.assertGreater(mid['rating'], low['rating'])
        self.assertAlmostEqual(mid['multiplier'], 1.0, delta=0.03)
        self.assertGreater(top['multiplier'], 1.15)
        self.assertLess(low['multiplier'], 0.85)
        self.assertTrue(0.8 <= low['multiplier'] and top['multiplier'] <= 1.2)
        self.assertEqual(top['compared'], 100)

    def test_new_players_stay_near_x1_and_lucky_minutes_do_not_top_the_board(self):
        pop = population()
        lucky = sr.rate({'hoursPlayed': 0.1, 'kills': 10, 'deaths': 0, 'wins': 1, 'losses': 0, 'cashEarned': 0, 'teamKills': 0}, pop)
        self.assertLess(lucky['confidence'], 0.1)
        self.assertAlmostEqual(lucky['multiplier'], 1.0, delta=0.02)
        self.assertLess(lucky['rating'], 1200)

    def test_missing_parts_count_as_average(self):
        r = sr.rate({'hoursPlayed': 50, 'kills': 700, 'deaths': 500}, population())
        self.assertIsNone(r['parts']['winning'])
        self.assertIsNotNone(r['parts']['firepower'])

    def test_needs_enough_players(self):
        with self.assertRaises(ValueError):
            sr.build([row()] * 5)

    def test_tf21_play_counts_with_estimated_hours_and_cash_rate_stays_wduk(self):
        merged = sr.member_row({'hoursPlayed': 10, 'kills': 100, 'deaths': 50, 'wins': 5, 'losses': 5, 'cashEarned': 1000},
                               {'kills': 60, 'deaths': 20, 'wins': 3, 'losses': 1, 'killsPerHour': 30.0})
        self.assertEqual((merged['kills'], merged['hoursPlayed'], merged['cashHours']), (160, 12, 10))


class EloBlendTests(unittest.TestCase):
    def test_gains_scale_and_costs_do_not(self):
        delta = {'wins': 1, 'losses': 1, 'kills': 10, 'deaths': 10}
        self.assertEqual(sr.points2(delta, SCORING, 1.0), 2 * (20 - 10 + 50 - 30))
        self.assertEqual(sr.points2(delta, SCORING, 1.2), round(2 * 70 * 1.2) - 2 * 40)
        self.assertEqual(sr.points2(delta, SCORING, 0.8), round(2 * 70 * 0.8) - 2 * 40)

    def test_multiplier_is_clamped_and_defaults_to_one(self):
        self.assertEqual(sr.multiplier({}), 1.0)
        self.assertEqual(sr.multiplier({'skill': {'multiplier': 5}}), 1.2)

    def test_wduk_and_tf21_results_use_the_members_multiplier(self):
        t = lambda m: f'2026-10-24T12:{m:02d}:00+00:00'
        p = {'discord_id': 1, 'points2': 0, 'rank': 0, 'active': True, 'hold': None, 'pending': None, 'rank_rules': 2,
             'baseline': {'wins': 0, 'losses': 0, 'kills': 0, 'deaths': 0}, 'updated': t(0), 'skill': {'multiplier': 1.2}}
        advance(p, {'wins': 0, 'losses': 0, 'kills': 10, 'deaths': 0}, t(5))
        self.assertEqual(p['points2'], 120)  # 10 kills x5 x1.2, in half-points.
        self.assertEqual(p['history'][-1]['multiplier'], 1.2)
        advance_tf21(p, {'wins': 0, 'losses': 0, 'kills': 0, 'deaths': 0}, t(6))
        advance_tf21(p, {'wins': 0, 'losses': 0, 'kills': 0, 'deaths': 10}, t(10))
        self.assertEqual(p['points2'], 120 - 60)  # Deaths are never scaled.


class PopulationTests(unittest.TestCase):
    def test_refreshes_hourly_saves_and_survives_failures(self):
        saved = {}
        fields = ['steamId', 'hoursPlayed', 'kills', 'deaths', 'wins', 'losses', 'cashEarned', 'teamKills']
        payload = {'fields': fields, 'players': [[str(i)] + [row(kph=5 + i)[f] for f in fields[1:]] for i in range(30)]}
        calls = []

        async def fetch():
            calls.append(1)
            if len(calls) > 1:
                raise ValueError('down')
            return payload
        ranks = SimpleNamespace(bot=SimpleNamespace(store=SimpleNamespace(get=saved.get, set=saved.__setitem__)), fetch_public_payload=fetch)
        pop = sr.Population(ranks)
        first = asyncio.run(pop.get(now=10_000))
        self.assertEqual(first['players'], 30)
        asyncio.run(pop.get(now=10_100))
        self.assertEqual(len(calls), 1)  # Cached within the hour.
        self.assertIs(asyncio.run(pop.get(now=20_000)), pop.data)  # Failure keeps the last comparison.
        self.assertEqual(sr.Population(ranks).data['players'], 30)  # Saved across restarts.
        state = {'players': {'s': {'discord_id': 1}}}
        sr.update_players(state, first, {'s': row()}, {})
        self.assertIn('multiplier', state['players']['s']['skill'])


if __name__ == '__main__':
    unittest.main()
