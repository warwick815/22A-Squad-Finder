import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import fantasy

T0 = 1_760_000_000


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


class FantasyTrackingTests(unittest.TestCase):
    def setUp(self):
        patcher = patch('fantasy.apply_awards')
        patcher.start()
        self.addCleanup(patcher.stop)
        self.ranks = {'season': 1, 'players': {f's{i}': {'discord_id': i, 'points2': 100} for i in range(1, 7)}}
        catalog = [dict(id=str(i), name=f'P{i}', steam=f's{i}', price=100) for i in range(1, 7)]
        self.round = fantasy.ensure_round(self.ranks, catalog, T0)
        fantasy.submit(self.ranks, '1', dict(round=self.round['id'], players=['1', '2', '3'], captain='1', booster=''), T0)
        self.kills = {f's{i}': 1000 for i in range(1, 7)}

    def play(self, skip=lambda t: False, missing=(), source=lambda steam, t: 'api', lag=0, until=None):
        r = self.round
        t = r['start'] - 3600
        until = until or r['end'] + 2 * 3600
        while t < until:
            t += 300
            for steam in self.kills:
                self.kills[steam] += 1
            if skip(t - r['start']):
                continue
            rows = {s: dict(kills=k, deaths=10, teamKills=0, wins=0, losses=0) for s, k in self.kills.items() if s not in missing}
            fantasy.observe(self.ranks, rows, {s: iso(t - lag) for s in rows}, {s: source(s, t) for s in rows}, t)
        return r

    def test_normal_round_scores_every_player(self):
        r = self.play()
        self.assertEqual(r['status'], 'completed')
        self.assertEqual(set(r['scores'].values()), {1440})

    def test_bot_offline_at_lock_uses_pre_lock_baseline(self):
        r = self.play(skip=lambda d: -60 <= d <= 1200)
        self.assertEqual(r['status'], 'completed')
        self.assertTrue(all(1440 <= v <= 1450 for v in r['scores'].values()))

    def test_delayed_feed_still_tracks(self):
        r = self.play(lag=50 * 60)
        self.assertEqual(r['status'], 'completed')
        self.assertEqual(r['scores']['1'], 1440)

    def test_source_switch_banks_points_instead_of_voiding(self):
        r = self.play(source=lambda s, t: 'public' if s == 's3' and t > self.round['start'] + 7200 else 'api')
        self.assertEqual(r['status'], 'completed')
        self.assertGreater(r['scores']['3'], 1400)
        self.assertIn('feed changed', fantasy.player_status(r, '3')['status'])

    def test_missing_player_scores_zero_without_voiding_round(self):
        r = self.play(missing={'s2'})
        self.assertEqual(r['status'], 'completed')
        self.assertEqual(r['scores']['2'], 0)
        self.assertEqual(r['missing'], ['2'])

    def test_offline_at_end_settles_an_hour_later(self):
        length = self.round['end'] - self.round['start']
        r = self.play(skip=lambda d: d >= length - 60)
        fantasy.tick(self.ranks, r['end'] + fantasy.SETTLE_AFTER)
        self.assertEqual(r['status'], 'completed')
        self.assertTrue(all(v > 1400 for v in r['scores'].values()))

    def test_round_with_no_data_is_void(self):
        r = self.play(missing=set(self.kills))
        self.assertEqual(r['status'], 'void')

    def test_live_status_reports_score_during_round(self):
        r = self.play(until=self.round['start'] + 3600)
        self.assertEqual(r['status'], 'live')
        info = fantasy.player_status(r, '2', self.round['start'] + 3600)
        self.assertEqual(info['base'], 60)
        self.assertEqual(info['status'], 'Live score')

    def test_legacy_live_round_is_upgraded(self):
        r = self.round
        snap = lambda at, kills: dict(at=at, source='api', values=dict(kills=kills, deaths=10, teamKills=0, wins=0, losses=0))
        r['status'] = 'live'
        r['start_stats'] = {uid: snap(r['start'], 1000) for uid in ['1', '2', '3', '4', '5']}
        r['last_stats'] = {uid: snap(r['start'] + 600, 1004) for uid in ['1', '2', '3', '4', '5']}
        self.assertEqual(fantasy.player_score(r, '1'), 20)


class SquadSizeTests(unittest.TestCase):
    def setUp(self):
        self.ranks = {'season': 1, 'players': {}}
        self.catalog = [dict(id=str(i), name=f'P{i}', steam=f's{i}', price=100) for i in range(1, 7)]

    def test_three_picks_and_matching_budget(self):
        r = fantasy.ensure_round(self.ranks, self.catalog, T0)
        self.assertEqual((r['squad_size'], r['budget']), (3, 390))
        with self.assertRaises(ValueError):
            fantasy.submit(self.ranks, '1', dict(round=r['id'], players=['1', '2', '3', '4', '5'], captain='1', booster=''), T0)
        fantasy.submit(self.ranks, '1', dict(round=r['id'], players=['1', '2', '3'], captain='1', booster=''), T0)
        # Reinforcements adds a fourth pick but shares the same budget.
        with self.assertRaisesRegex(ValueError, 'budget'):
            fantasy.submit(self.ranks, '2', dict(round=r['id'], players=['1', '2', '3', '4'], captain='1', booster='reinforcements'), T0)

    def test_open_five_player_round_switches_and_keeps_picks_as_draft(self):
        r = fantasy.ensure_round(self.ranks, self.catalog, T0)
        r.update(squad_size=5, budget=650)
        r['entries']['1'] = dict(players=['1', '2', '3', '4', '5'], captain='1', booster='', saved=T0)
        r = fantasy.ensure_round(self.ranks, self.catalog, T0 + 60)
        self.assertEqual((r['squad_size'], r['budget'], r['entries']), (3, 390, {}))
        self.assertEqual(r['drafts']['1']['players'], ['1', '2', '3', '4', '5'])

    def test_three_members_are_enough_to_open_selection(self):
        self.assertIsNotNone(fantasy.ensure_round(self.ranks, self.catalog[:3], T0))


if __name__ == '__main__':
    unittest.main()
