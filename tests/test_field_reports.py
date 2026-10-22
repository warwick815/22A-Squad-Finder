import asyncio
import io
import unittest
from unittest import mock
from datetime import datetime, timezone
from types import SimpleNamespace

import aar_card
import kill_feed
from field_reports import embed_for, message_for

ME, MATE, PAL, ENEMY = '76561198071647614', '76561197988807107', '76561198000000003', '76561198018132245'
LINKED = {ME, MATE, PAL}
WED = datetime(2026, 10, 14, 12, tzinfo=timezone.utc).timestamp()  # a Wednesday, week 42


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def kill(i, ts, killer=ME, victim=ENEMY, kname='[22A] Peaches', vname='BritishSam', **extra):
    k = {'id': i, 'at': iso(ts), 'server': 'uk2', 'map': 'Kavkazi', 'outcome': 'kill', 'team_kill': False,
         'killer_steam_id': killer, 'killer_name': kname, 'victim_steam_id': victim, 'victim_name': vname,
         'weapon': 'SV98', 'weapon_category': 'infantry', 'headshot': False, 'distance_m': 100.0}
    k.update(extra)
    return k


class BountyTests(unittest.TestCase):
    def test_last_weeks_top_killer_becomes_most_wanted_and_first_kill_claims(self):
        state = kill_feed.blank()
        kill_feed.apply(state, [kill(i, WED + i, killer=ENEMY, victim=ME, kname='BritishSam', vname='[22A] Peaches') for i in range(1, 5)], LINKED)
        next_monday = datetime(2026, 10, 19, 9, tzinfo=timezone.utc).timestamp()
        state['live_since'] = next_monday - 60
        kill_feed.ensure_bounty(state, next_monday)
        self.assertEqual((state['bounty']['name'], state['bounty']['kills']), ('BritishSam', 4))
        self.assertEqual(state['announce'][-1]['type'], 'bounty_set')
        kill_feed.apply(state, [kill(10, next_monday + 600, killer=MATE, kname='[22A] Warwick815')], LINKED)
        self.assertEqual(state['bounty']['claimed'], MATE)
        self.assertEqual(state['members'][MATE]['bounties'], 1)
        kill_feed.apply(state, [kill(11, next_monday + 900)], LINKED)  # second kill does not re-claim
        self.assertEqual(state['bounty']['claimed'], MATE)
        self.assertEqual(state['announce'][-1]['type'], 'bounty_claimed')

    def test_needs_three_kills_and_unclaimed_bounty_escapes(self):
        state = kill_feed.blank()
        kill_feed.apply(state, [kill(i, WED + i, killer=ENEMY, victim=ME, kname='X', vname='[22A] Peaches') for i in range(1, 3)], LINKED)
        kill_feed.ensure_bounty(state, datetime(2026, 10, 19, 9, tzinfo=timezone.utc).timestamp())
        self.assertIsNone(state['bounty'])
        state['bounty'] = {'week': '2026-W43', 'target': 'x', 'name': 'X', 'kills': 5, 'set_at': 0, 'claimed': None}
        kill_feed.ensure_bounty(state, datetime(2026, 10, 26, 9, tzinfo=timezone.utc).timestamp())
        self.assertEqual(state['bounties'][-1]['status'], 'escaped')


class StreakTests(unittest.TestCase):
    def test_streak_counts_until_death_or_two_hour_gap(self):
        state = kill_feed.blank()
        kill_feed.apply(state, [kill(i, WED + i * 60) for i in range(1, 11)], LINKED)
        self.assertEqual(state['members'][ME]['best_streak']['count'], 10)
        kill_feed.apply(state, [kill(20, WED + 700, killer=ENEMY, victim=ME, kname='BritishSam', vname='[22A] Peaches'),
                                kill(21, WED + 800)], LINKED)
        self.assertEqual(state['members'][ME]['streak']['count'], 1)
        kill_feed.apply(state, [kill(22, WED + 800 + 3 * 3600)], LINKED)
        self.assertEqual(state['members'][ME]['streak']['count'], 1)  # gap reset
        self.assertEqual(state['streak_week']['count'], 10)


class SessionTests(unittest.TestCase):
    def test_three_members_on_one_server_make_a_session(self):
        state = kill_feed.blank()
        kills = [kill(1, WED, killer=ME), kill(2, WED + 60, killer=MATE, kname='[22A] Warwick815'),
                 kill(3, WED + 120, killer=PAL, kname='[22A] Pal', distance_m=447.5), kill(4, WED + 180, killer=ME)]
        state['live_since'] = WED - 1
        kill_feed.apply(state, kills, LINKED)
        kill_feed.close_sessions(state, WED + 180 + 3601)
        s = state['sessions'][-1]
        self.assertEqual((s['kills'], len(s['members']), s['top']['steam'], s['longest']['m']), (4, 3, ME, 447.5))
        self.assertEqual(state['announce'][-1]['type'], 'session')
        self.assertEqual(state['members'][MATE]['sessions'], 1)

    def test_two_members_or_history_are_not_announced(self):
        state = kill_feed.blank()
        kill_feed.apply(state, [kill(1, WED), kill(2, WED + 60, killer=MATE, kname='[22A] W')], LINKED)
        kill_feed.close_sessions(state, WED + 4000)
        self.assertEqual(state['sessions'], [])
        kill_feed.apply(state, [kill(5, WED + 9000), kill(6, WED + 9060, killer=MATE, kname='[22A] W'), kill(7, WED + 9120, killer=PAL, kname='[22A] P')], LINKED)
        kill_feed.close_sessions(state, WED + 20000)
        self.assertEqual(len(state['sessions']), 1)
        self.assertEqual(state['announce'], [])  # before live_since: history stays quiet


class MasteryTests(unittest.TestCase):
    def test_weapon_tiers(self):
        state = kill_feed.blank()
        kill_feed.apply(state, [kill(i, WED + i) for i in range(1, 151)], LINKED)
        rack = kill_feed.weapons(state, ME)
        self.assertEqual((rack[0]['weapon'], rack[0]['kills'], rack[0]['tier'], rack[0]['next']), ('SV98', 150, 'silver', 300))

    def test_old_saves_rebuild_from_history(self):
        class Store:
            data = {kill_feed.STORE_KEY: '{"max_id": 99, "members": {}}'}
            def get(self, k): return self.data.get(k)
            def set(self, k, v): self.data[k] = v
        feed = kill_feed.KillFeed(SimpleNamespace(store=Store()))
        self.assertEqual((feed.state['max_id'], feed.state['version']), (0, kill_feed.VERSION))


class EmbedTests(unittest.TestCase):
    def test_cards_render(self):
        bot = SimpleNamespace(progression=SimpleNamespace(state={'players': {ME: {'discord_id': 42}}}))
        session = {'type': 'session', 'server': 'uk2', 'map': 'Kavkazi', 'start': WED, 'end': WED + 1800, 'kills': 9, 'headshots': 2,
                   'members': [{'steam': ME, 'name': '[22A] Peaches', 'kills': 5, 'headshots': 1}], 'top': {'steam': ME, 'name': '[22A] Peaches', 'kills': 5},
                   'longest': {'m': 300.0, 'weapon': 'SV98', 'name': '[22A] Peaches'}, 'weapon': ['SV98', 5]}
        self.assertIn('<@42>', embed_for(bot, session).fields[0].value)
        self.assertIn('Most Wanted', embed_for(bot, {'type': 'bounty_set', 'name': 'X', 'kills': 4}).title)
        self.assertIn('<@42>', embed_for(bot, {'type': 'bounty_claimed', 'name': 'X', 'claimed': ME, 'claimed_name': 'P', 'weapon': 'SV98', 'distance': 300, 'headshot': True}).description)


class CardTests(unittest.TestCase):
    def session(self):
        state = kill_feed.blank()
        kills = [kill(1, WED, killer=ME), kill(2, WED + 60, killer=MATE, kname='[22A] Warwick815'),
                 kill(3, WED + 120, killer=PAL, kname='[22A] Pal', distance_m=447.5), kill(4, WED + 180, killer=ME),
                 kill(5, WED + 200, killer=ENEMY, victim=ME, kname='BritishSam', vname='[22A] Peaches'),
                 kill(6, WED + 230, killer=ENEMY, victim=MATE, kname='BritishSam', vname='[22A] Warwick815'),
                 kill(7, WED + 260, killer=ME), kill(8, WED + 300, killer=ME)]
        kill_feed.apply(state, kills, LINKED)
        kill_feed.close_sessions(state, WED + 5000)
        return state['sessions'][-1]

    def test_session_records_deaths_streak_nemesis_and_target(self):
        s = self.session()
        self.assertEqual(s['deaths'], 2)
        self.assertEqual(s['streak'], {'steam': ME, 'name': '[22A] Peaches', 'count': 2})
        self.assertEqual(s['nemesis'], {'name': 'BritishSam', 'count': 2})
        self.assertEqual(s['target'], {'name': 'BritishSam', 'count': 6})

    def test_card_draws_a_png(self):
        png = aar_card.render({'type': 'session', **self.session()})
        self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
        from PIL import Image
        self.assertEqual(Image.open(io.BytesIO(png)).width, 1080)

    def test_headline(self):
        base = {'start': 0, 'end': 3600, 'members': [{}] * 3, 'deaths': 0}
        self.assertEqual(aar_card.headline({**base, 'kills': 20, 'headshots': 9})[0], 'HEADHUNTERS')
        self.assertEqual(aar_card.headline({**base, 'kills': 5, 'headshots': 0, 'longest': {'m': 500}})[0], 'SHARPSHOOTERS')
        self.assertEqual(aar_card.headline({**base, 'kills': 5, 'headshots': 0})[0], 'THE PACK')

    def test_message_attaches_card_and_falls_back(self):
        bot = SimpleNamespace(progression=SimpleNamespace(state={'players': {}}), guild=None)
        e = {'type': 'session', **self.session()}
        msg = asyncio.run(message_for(bot, e))
        self.assertEqual(msg['file'].filename, 'after-action.png')
        self.assertEqual(msg['embed'].image.url, 'attachment://after-action.png')
        with mock.patch('aar_card.render', side_effect=RuntimeError):
            self.assertNotIn('file', asyncio.run(message_for(bot, e)))


if __name__ == '__main__':
    unittest.main()


class DeckTests(unittest.TestCase):
    def test_card_faces_follow_the_deck(self):
        import playing_card as pc
        self.assertEqual([pc.face(n) for n in (1, 2, 5, 52, 53, 54)],
                         [('A', 'spades'), ('A', 'clubs'), ('K', 'spades'), ('2', 'diamonds'), ('JOKER', 'black'), ('JOKER', 'red')])
        self.assertEqual(pc.label(42), '4 of Clubs')
        self.assertEqual(len({pc.face(n) for n in range(1, 55)}), 54)

    def test_bounty_week_becomes_a_card_that_is_collected_or_escapes(self):
        state = kill_feed.blank()
        kill_feed.apply(state, [kill(i, WED + i, killer=ENEMY, victim=ME, kname='BritishSam', vname='[22A] Peaches') for i in range(1, 5)], LINKED)
        monday = datetime(2026, 10, 19, 9, tzinfo=timezone.utc).timestamp()
        kill_feed.ensure_bounty(state, monday)
        self.assertEqual(state['deck']['2026']['43']['status'], 'open')
        kill_feed.apply(state, [kill(10, monday + 600, killer=MATE, kname='[22A] Warwick815', distance_m=250.0)], LINKED)
        card = state['deck']['2026']['43']
        self.assertEqual((card['status'], card['claimed'], card['n']), ('claimed', MATE, 43))
        self.assertEqual(kill_feed.hunter_of_year(state, 2026)['steam'], MATE)
        state['bounty'] = {'week': '2026-W44', 'target': 'x', 'name': 'X', 'kills': 5, 'set_at': 0, 'claimed': None}
        kill_feed.deck_card(state, state['bounty'], 'open')
        kill_feed.ensure_bounty(state, datetime(2026, 11, 2, 9, tzinfo=timezone.utc).timestamp())
        self.assertEqual(state['deck']['2026']['44']['status'], 'escaped')

    def test_deck_survives_a_rebuild_and_old_bounties_are_backfilled(self):
        import json

        class Store:
            data = {kill_feed.STORE_KEY: json.dumps({'version': 1, 'deck': {'2025': {'7': {'n': 7, 'status': 'claimed'}}}})}
            def get(self, k): return self.data.get(k)
            def set(self, k, v): self.data[k] = v
        feed = kill_feed.KillFeed(SimpleNamespace(store=Store()))
        self.assertEqual(feed.state['deck']['2025']['7']['status'], 'claimed')
        state = kill_feed.blank()
        state['bounties'] = [{'week': '2026-W40', 'name': 'Y', 'kills': 4, 'claimed': None, 'status': 'escaped'}]
        kill_feed.backfill_deck(state)
        self.assertEqual(state['deck']['2026']['40']['status'], 'escaped')

    def test_cards_draw_and_the_api_lists_54_slots(self):
        import playing_card
        from website_shame import deck_view
        from PIL import Image
        for entry in ({'n': 1, 'name': 'X', 'kills': 3, 'week': '2026-W01', 'status': 'open'},
                      {'n': 53, 'name': 'Y', 'kills': 3, 'week': '2026-W53', 'status': 'escaped'},
                      {'n': 54, 'name': '[22A] Z', 'count': 2}):
            self.assertEqual(Image.open(io.BytesIO(playing_card.render(entry, '2026'))).size, (750, 1050))
        state = kill_feed.blank()
        kill_feed.deck_card(state, {'week': '2026-W02', 'name': 'X', 'kills': 3, 'claimed': ME, 'claimed_name': 'P'}, 'claimed')
        who = lambda steam, name: {'id': None, 'name': name, 'avatar': ''}
        deck = deck_view(state, who)[0]
        self.assertEqual((deck['year'], len(deck['slots']), deck['collected']), ('2026', 54, 1))
        self.assertTrue(deck['slots'][1]['image'].startswith('/api/reports/card/2026/2.png?v='))
        self.assertEqual(deck['slots'][53]['status'], 'hunter')
        self.assertNotIn('image', deck['slots'][2])

    def test_discord_posts_use_the_playing_card(self):
        bot = SimpleNamespace(progression=SimpleNamespace(state={'players': {}}), guild=None,
                              kill_feed=SimpleNamespace(state={'deck': {'2026': {'43': {'status': 'claimed'}}}}))
        e = {'type': 'bounty_claimed', 'week': '2026-W43', 'name': 'X', 'kills': 4, 'claimed': ME, 'claimed_name': 'P'}
        msg = asyncio.run(message_for(bot, e))
        self.assertEqual(msg['file'].filename, 'most-wanted-card.png')
        self.assertIn('4 of Hearts', msg['embed'].description)
        self.assertIn('1 of 54', msg['embed'].description)
