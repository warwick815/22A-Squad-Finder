import os
import unittest
from types import SimpleNamespace
from unittest import mock

import merits
import patch_shop
from community_hq import locker_view


def state():
    return {'season': 2, 'players': {'s1': {'discord_id': 1, 'active': True}, 's2': {'discord_id': 2, 'active': True}}}


class ShopTests(unittest.TestCase):
    def test_catalogue(self):
        self.assertEqual(len(patch_shop.CATALOGUE), 50)
        tiers = [p['tier'] for p in patch_shop.CATALOGUE]
        self.assertEqual((tiers.count('legendary'), tiers.count('rare'), tiers.count('common'), tiers.count('originals')), (8, 17, 24, 1))
        self.assertEqual(patch_shop.BY_ID['20-check-check']['name'], 'Radio Check')
        for p in patch_shop.CATALOGUE:
            self.assertTrue(os.path.exists(f"web/patches/{p['id']}.webp"), p['id'])

    def test_website_names_match_the_shop(self):
        import re
        js = open('web/community-hq.js').read()
        names = dict(re.findall(r"'(\d\d-[a-z0-9-]+)':'([^']*)'", js))
        self.assertEqual(names, {p['id']: p['name'] for p in patch_shop.CATALOGUE})

    def test_rules(self):
        s = state()
        merits.credit(s, 1, 30, 'x', 0)
        merits.credit(s, 1, 30, 'x', 86400)
        patch_shop.buy(s, 1, '04-british-grit')
        self.assertEqual(merits.member(s, 1)['balance'], 40)
        self.assertEqual(locker_view(s, 1)['display'], ['04-british-grit'])
        with self.assertRaisesRegex(ValueError, 'already own'):
            patch_shop.buy(s, 1, '04-british-grit')
        with self.assertRaisesRegex(ValueError, 'need 75'):
            patch_shop.buy(s, 1, '01-old-guard')
        with self.assertRaisesRegex(ValueError, '22A role'):
            patch_shop.buy(s, 1, patch_shop.ORIGINALS)
        with self.assertRaisesRegex(ValueError, 'Choose a patch'):
            patch_shop.buy(s, 1, 'shock')
        patch_shop.buy(s, 1, '06-last-out')  # Patches do not use the daily booster allowance…
        merits.credit(s, 1, 30, 'x', 86400 * 2)
        merits.buy(s, 1, 'flak', now=86400 * 3)  # …and a booster can still be used the same day.
        s['season'] = 3
        self.assertIn('04-british-grit', locker_view(s, 1)['earned'])  # Kept after Merits reset.
        self.assertEqual(merits.member(s, 1)['balance'], 0)  # Merits reset with the season.

    def test_originals_follow_the_22a_role(self):
        s = state()
        role = SimpleNamespace(id=9, name='22A', members=[SimpleNamespace(id=1)])
        guild = SimpleNamespace(roles=[SimpleNamespace(id=8, name='Member'), role], get_role=lambda i: None)
        patch_shop.sync_originals(s, guild)
        self.assertIn(patch_shop.ORIGINALS, locker_view(s, 1)['earned'])
        self.assertNotIn(patch_shop.ORIGINALS, locker_view(s, 2)['earned'])
        from community_hq import select_patches
        select_patches(s, 1, [patch_shop.ORIGINALS])
        role.members = []
        patch_shop.sync_originals(s, guild)
        box = locker_view(s, 1)
        self.assertNotIn(patch_shop.ORIGINALS, box['earned'])
        self.assertEqual(box['display'], [])
        member = SimpleNamespace(guild=guild, roles=[role])
        self.assertTrue(patch_shop.view(s, 1, member)[-1]['eligible'])
        with mock.patch.dict(os.environ, {'ORIGINALS_ROLE_ID': '77'}):
            other = SimpleNamespace(id=77, name='Founders', members=[SimpleNamespace(id=2)])
            patch_shop.sync_originals(s, SimpleNamespace(roles=[], get_role=lambda i: other if i == 77 else None))
        self.assertIn(patch_shop.ORIGINALS, locker_view(s, 2)['earned'])

    def test_bought_patches_do_not_count_towards_collector_ribbons(self):
        from website_medals import medals
        s = state()
        s['community_hq'] = {'lockers': {'1': {'earned': {'shock': {}, '01-old-guard': {'bought': 1}, '02-silent-watch': {'bought': 1},
                                                         patch_shop.ORIGINALS: {'role': True}}, 'display': []}}}
        bot = SimpleNamespace(store=None, betting=None, progression=SimpleNamespace(state=s))
        m = {x['id']: x for x in medals(bot, 's1', {'discord_id': 1, 'rank': 0, 'history': [], 'points2': 0}, {})}
        self.assertEqual(m['patches3']['value'], 1)


if __name__ == '__main__':
    unittest.main()
