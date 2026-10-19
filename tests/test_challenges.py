import unittest
from types import SimpleNamespace

import community_hq
from website_medals import medals


class Store:
    def __init__(self): self.data = {}
    def get(self, key): return self.data.get(key)
    def set(self, key, value): self.data[key] = value


def bot(lockers=None):
    state = {'season': 1, 'season_archives': [], 'community_hq': {'lockers': lockers or {}}}
    return SimpleNamespace(store=Store(), progression=SimpleNamespace(state=state), betting=None)


def player(rank=0):
    return {'discord_id': 7, 'rank': rank, 'history': [], 'points2': 0}


def by_id(items): return {m['id']: m for m in items}


class NewRibbonTests(unittest.TestCase):
    def test_new_tiers_award_from_lifetime_stats(self):
        row = {'kills': 10500, 'kd': 2.3, 'killsPerHour': 21, 'hoursPlayed': 520, 'wins': 260, 'cashEarned': 60_000_000}
        m = by_id(medals(bot(), 's1', player(5), row))
        for key in ('kills10000', 'wins100', 'wins250', 'sharpshooter', 'rapidfire', 'hours250', 'hours500', 'cash10m', 'cash50m', 'sergeant', 'staffsgt', 'warrant'):
            self.assertTrue(m[key]['earned'], key)

    def test_ratio_awards_need_enough_play(self):
        m = by_id(medals(bot(), 's1', player(), {'kills': 40, 'kd': 5.0, 'killsPerHour': 40, 'hoursPlayed': 3}))
        self.assertFalse(m['sharpshooter']['earned'])
        self.assertFalse(m['rapidfire']['earned'])

    def test_missing_stats_do_not_award(self):
        m = by_id(medals(bot(), 's1', player(), {}))
        self.assertIsNone(m['sharpshooter']['value'])
        self.assertFalse(m['kills10000']['earned'])

    def test_patch_collector_counts_earned_patches(self):
        lockers = {'7': {'earned': {'shock': {}, 'brew': {}, 'tinhat': {}}, 'display': []}}
        m = by_id(medals(bot(lockers), 's1', player(), {}))
        self.assertTrue(m['patches3']['earned'])
        self.assertFalse(m['patches6']['earned'])


class NewOperationTests(unittest.TestCase):
    def test_twelve_patches_with_supported_metrics(self):
        self.assertEqual(len(community_hq.PATCHES), 12)
        self.assertEqual(len({p['id'] for p in community_hq.PATCHES}), 12)
        for p in community_hq.PATCHES:
            self.assertIn(p['metric'], ('kills', 'wins', 'hoursPlayed', 'cashEarned'))

    def test_new_operation_can_be_created(self):
        ranks = {'season': 1}
        op = community_hq.create_operation(ranks, 'lionheart', 1, now=100)
        self.assertEqual((op['title'], op['metric'], op['target']), ('Lionheart', 'wins', 500))

    def test_each_patch_runs_once_per_season(self):
        ranks = {'season': 1}
        op = community_hq.create_operation(ranks, 'tinhat', 1, now=100)
        op['status'] = 'expired'
        with self.assertRaisesRegex(ValueError, 'already run this season'):
            community_hq.create_operation(ranks, 'tinhat', 1, now=200)
        community_hq.create_operation(ranks, 'stagon', 1, now=200)  # other patches still available
        ranks['season'] = 2
        community_hq.create_operation(ranks, 'tinhat', 1, now=300)  # back next season


if __name__ == '__main__':
    unittest.main()
