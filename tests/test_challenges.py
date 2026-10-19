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


class PodiumPatchTests(unittest.TestCase):
    def ranks(self):
        players = {f's{i}': {'discord_id': i, 'points2': pts} for i, pts in [(1, 900), (2, 700), (3, 500), (4, 100)]}
        return {'season': 2, 'season_archives': [{'season': 1, 'closed': 't', 'players': players}]}

    def test_top_three_of_season_one_get_their_patch(self):
        ranks = self.ranks()
        self.assertIn('season1gold', community_hq.locker_view(ranks, 1)['earned'])
        self.assertIn('season1silver', community_hq.locker_view(ranks, 2)['earned'])
        self.assertIn('season1bronze', community_hq.locker_view(ranks, '3')['earned'])
        self.assertEqual(community_hq.locker_view(ranks, 4)['earned'], {})

    def test_winner_can_display_podium_patch_others_cannot(self):
        ranks = self.ranks()
        community_hq.select_patches(ranks, 1, ['season1gold'])
        self.assertEqual(community_hq.locker_view(ranks, 1)['display'], ['season1gold'])
        with self.assertRaises(ValueError):
            community_hq.select_patches(ranks, 4, ['season1gold'])
        with self.assertRaises(ValueError):
            community_hq.select_patches(ranks, 2, ['season1gold'])

    def test_podium_patches_cannot_be_run_as_operations(self):
        with self.assertRaises(ValueError):
            community_hq.create_operation({'season': 2}, 'season1gold', 1, now=1)


if __name__ == '__main__':
    unittest.main()
