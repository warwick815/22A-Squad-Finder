import unittest
from types import SimpleNamespace

import kill_feed

ME, MATE, ENEMY = '76561198071647614', '76561197988807107', '76561198018132245'
LINKED = {ME, MATE}


def kill(i, killer=ME, victim=ENEMY, kname='[22A] Peaches', vname='BritishSam', **extra):
    k = {'id': i, 'at': f'2026-10-13T13:{i % 60:02d}:00+00:00', 'server': 'uk2', 'map': 'NorthAmerica', 'outcome': 'kill',
         'team_kill': False, 'killer_steam_id': killer, 'killer_name': kname, 'killer_faction': 'Valkyra',
         'victim_steam_id': victim, 'victim_name': vname, 'victim_faction': 'Lonestar', 'weapon': 'SV98',
         'weapon_category': 'infantry', 'headshot': False, 'distance_m': 100.0}
    k.update(extra)
    return k


class DogTagTests(unittest.TestCase):
    def test_tiers_at_10_20_30_kills(self):
        state = kill_feed.blank()
        kill_feed.apply(state, [kill(i) for i in range(1, 10)], LINKED)
        self.assertIsNone(kill_feed.dogtags(state, ME)[0]['tier'])  # 9 kills: in progress
        kill_feed.apply(state, [kill(10)], LINKED)
        self.assertEqual(kill_feed.dogtags(state, ME)[0]['tier'], 'bronze')
        kill_feed.apply(state, [kill(i) for i in range(11, 31)], LINKED)
        tag = kill_feed.dogtags(state, ME)[0]
        self.assertEqual((tag['tier'], tag['kills'], tag['victim']), ('gold', 30, 'BritishSam'))

    def test_each_kill_counted_once_even_if_sent_again(self):
        state = kill_feed.blank()
        page = [kill(i) for i in range(1, 11)]
        kill_feed.apply(state, page, LINKED)
        kill_feed.apply(state, page, LINKED)
        self.assertEqual(kill_feed.dogtags(state, ME)[0]['kills'], 10)

    def test_team_kills_suicides_and_unlinked_killers_do_not_count(self):
        state = kill_feed.blank()
        kill_feed.apply(state, [kill(i, team_kill=True) for i in range(1, 15)]
                        + [kill(20, outcome='self', weapon=None, victim=ME)]
                        + [kill(i, killer=ENEMY, victim=ME, kname='BritishSam', vname='[22A] Peaches') for i in range(30, 45)], LINKED)
        self.assertEqual(kill_feed.dogtags(state, ME), [])
        self.assertEqual(state['members'][ME]['team_kills'], 14)


class CombatTests(unittest.TestCase):
    def test_summary_nemesis_longest_headshots_and_payback(self):
        state = kill_feed.blank()
        kills = [kill(i, killer=ENEMY, victim=ME, kname='BritishSam', vname='[22A] Peaches') for i in range(1, 4)]
        kills += [kill(10, headshot=True, distance_m=551.7, weapon='SKS'),
                  kill(11, weapon='M67 frag grenade', distance_m=None),
                  kill(12, weapon='Claymore'),
                  kill(13, weapon='STN_03 MainBarrel', weapon_category='vehicle_weapon')]
        kill_feed.apply(state, kills, LINKED)
        s = kill_feed.summary(state, ME)
        self.assertEqual(s['nemesis']['name'], 'BritishSam')
        self.assertEqual((s['kills'], s['headshots'], s['grenade'], s['explosive'], s['vehicle']), (4, 1, 1, 1, 1))
        self.assertEqual(s['longest']['m'], 551.7)
        self.assertEqual(s['revenge'], 4)  # every kill on the nemesis counts as payback


class ShameTests(unittest.TestCase):
    def test_only_22a_on_22a_kills_go_to_the_hall_of_shame(self):
        state = kill_feed.blank()
        kill_feed.apply(state, [kill(1, victim=MATE, vname='[22A] Warwick815', team_kill=True),
                                kill(2, victim=MATE, vname='[22A] Warwick815'),
                                kill(3),  # enemy kill
                                kill(4, killer='76561190000000009', kname='[22A] Unlinked', victim=MATE, vname='[22A] Warwick815')], LINKED)
        self.assertEqual([e['id'] for e in state['shame']], [1, 2, 4])
        self.assertTrue(state['shame'][0]['team_kill'])
        self.assertFalse(state['shame'][1]['team_kill'])


class MedalTests(unittest.TestCase):
    def test_dogtag_and_combat_ribbons(self):
        from website_medals import medals

        class Store:
            def __init__(self): self.data = {}
            def get(self, k): return self.data.get(k)
            def set(self, k, v): self.data[k] = v
        bot = SimpleNamespace(store=Store(), betting=None,
                              progression=SimpleNamespace(state={'season': 1, 'season_archives': [], 'community_hq': {'lockers': {}}}))
        feed = kill_feed.service(bot)
        kill_feed.apply(feed.state, [kill(i, headshot=True, distance_m=820.0) for i in range(1, 101)], LINKED)
        m = {x['id']: x for x in medals(bot, ME, {'discord_id': 1, 'rank': 0, 'history': [], 'points2': 0}, {})}
        for key in ('tags1', 'tagsilver', 'taggold', 'headhunter', 'marksman', 'hawkeye'):
            self.assertTrue(m[key]['earned'], key)
        self.assertFalse(m['tags10']['earned'])


if __name__ == '__main__':
    unittest.main()
