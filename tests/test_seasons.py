import unittest
from datetime import datetime, timezone, timedelta
from seasons import apply_levels, close_season
from progression import new_player
from tools_stats import ROLES


class SeasonsTests(unittest.TestCase):
    def stats(self, now, wardog=100, role=10):
        return {'updated': now.isoformat(), 'values': {'wardogLevel': wardog}, 'levels': dict.fromkeys(ROLES, role)}

    def test_no_historical_reward_and_idempotency(self):
        now = datetime.now(timezone.utc)
        p = new_player(1, None, None)
        self.assertEqual(apply_levels(p, self.stats(now), 'id', now), 0)
        later = now+timedelta(minutes=15)
        data = self.stats(later, 103, 11)
        self.assertEqual(apply_levels(p, data, 'id', later), 12)
        self.assertEqual(p['points2'], 24)
        self.assertEqual(apply_levels(p, data, 'id', later), 0)

    def test_counter_drop_and_rebound_do_not_award(self):
        now = datetime.now(timezone.utc)
        p = new_player(1, None, None)
        apply_levels(p, self.stats(now), 'id', now)
        for i, level in enumerate((1, 100), 1):
            date = now+timedelta(minutes=15*i)
            self.assertEqual(apply_levels(p, self.stats(date, level), 'id', date), 0)

    def test_archive_retains_links_and_history(self):
        p = new_player(1, None, None)
        p.update(points2=999, rank=1, steam_verified=True, active=False, history=[{'reason': 'old'}])
        state = {'players': {'steam': p}}
        archived = close_season(state, 1)
        self.assertEqual(archived['players']['steam']['points2'], 999)
        self.assertEqual(p['points2'], 0)
        self.assertTrue(p['steam_verified'])
        self.assertFalse(p['active'])
        self.assertEqual(p['history'], [{'reason': 'old'}])
        with self.assertRaises(ValueError):
            close_season(state, 1)

    def test_previous_season_cached_levels_cannot_baseline(self):
        now = datetime.now(timezone.utc)
        p = new_player(1, None, None)
        p['season_started'] = now.isoformat()
        self.assertEqual(apply_levels(p, self.stats(now-timedelta(minutes=1)), 'id', now), 0)
        self.assertNotIn('level_baseline', p)

    def test_failed_and_stale_do_not_award(self):
        now = datetime.now(timezone.utc)
        p = new_player(1, None, None)
        self.assertEqual(apply_levels(p, self.stats(now-timedelta(hours=2)), 'id', now), 0)
        self.assertNotIn('level_baseline', p)
