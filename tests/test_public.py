import unittest
from types import SimpleNamespace

import website_public


def member(uid, name, bot=False):
    return SimpleNamespace(id=uid, display_name=name, bot=bot, display_avatar=SimpleNamespace(url=f'https://cdn.discordapp.com/{uid}.png'))


def make_bot():
    members = {1: member(1, 'Alpha'), 2: member(2, 'Bravo'), 3: member(3, 'Held'), 4: member(4, 'Robot', bot=True)}
    players = {
        's1': {'discord_id': 1, 'active': True, 'points2': 1200, 'rank': 1},
        's2': {'discord_id': 2, 'active': True, 'points2': 3000, 'rank': 2},
        's3': {'discord_id': 3, 'active': True, 'hold': 'review', 'points2': 9000, 'rank': 3},
        's4': {'discord_id': 4, 'active': True, 'points2': 100, 'rank': 0},
        's5': {'discord_id': 5, 'active': True, 'points2': 100, 'rank': 0},  # left the server
    }
    state = {'season': 2, 'players': players, 'fantasy': {'rounds': {}},
             'season_archives': [{'season': 1, 'closed': 't', 'players': {'s1': {'discord_id': 1, 'points2': 5000, 'rank': 2}}}]}
    return SimpleNamespace(progression=SimpleNamespace(state=state), guild=SimpleNamespace(get_member=members.get),
                           player_panel=SimpleNamespace(rows={'s1': {'kd': 1.5, 'wins': 10, 'kills': 300}}, updated='now'))


class PublicViewTests(unittest.TestCase):
    def test_only_active_current_members_in_order(self):
        data = website_public.build(make_bot())
        self.assertEqual([p['name'] for p in data['players']], ['Bravo', 'Alpha'])
        self.assertEqual(data['players'][0]['position'], 1)
        self.assertEqual(data['members'], 2)

    def test_no_private_fields(self):
        data = website_public.build(make_bot())
        allowed = {'name', 'avatar', 'rating', 'rank', 'badge', 'division', 'kd', 'wins', 'kills', 'position'}
        for p in data['players']:
            self.assertLessEqual(set(p), allowed)
        self.assertNotIn('s1', str(data))  # no Steam IDs

    def test_hall_of_fame_podium(self):
        data = website_public.build(make_bot())
        self.assertEqual(data['archives'][0]['podium'][0]['name'], 'Alpha')


if __name__ == '__main__':
    unittest.main()
