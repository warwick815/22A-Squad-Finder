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


HOUR = 3600 * int(WED // 3600)  # The start of an hour on the test Wednesday.


class BountyTests(unittest.TestCase):
    def enemy_kills(self, start, count, first_id=1, name='BritishSam', steam=ENEMY):
        return [kill(first_id + i, start + 60 * i, killer=steam, victim=ME, kname=name, vname='[22A] Peaches') for i in range(count)]

    def test_last_hours_top_killer_becomes_most_wanted_and_first_kill_collects_a_card(self):
        state = kill_feed.blank()
        kill_feed.apply(state, self.enemy_kills(HOUR + 60, 4), LINKED)
        state['live_since'] = HOUR
        kill_feed.ensure_bounty(state, HOUR + 3600 + 30)
        b = state['bounty']
        self.assertEqual((b['name'], b['kills'], b['expires'], b['card']), ('BritishSam', 4, HOUR + 7200, 1))
        self.assertEqual(state['announce'][-1]['type'], 'bounty_set')
        kill_feed.apply(state, [kill(10, HOUR + 3600 + 600, killer=MATE, kname='[22A] Warwick815')], LINKED)
        self.assertEqual((b['claimed'], state['members'][MATE]['bounties']), (MATE, 1))
        deck_id = f"{datetime.fromtimestamp(HOUR, kill_feed.UK).year}-1"
        self.assertEqual(state['deck'][deck_id]['1']['claimed'], MATE)
        kill_feed.apply(state, [kill(11, HOUR + 3600 + 900)], LINKED)  # A second kill does not collect again.
        self.assertEqual((b['claimed'], len(state['deck'][deck_id])), (MATE, 1))
        self.assertEqual(state['announce'][-1]['type'], 'bounty_claimed')

    def test_kills_after_the_hour_do_not_collect_and_quiet_hours_have_no_bounty(self):
        state = kill_feed.blank()
        kill_feed.apply(state, self.enemy_kills(HOUR + 60, 3), LINKED)
        kill_feed.ensure_bounty(state, HOUR + 3600 + 30)
        kill_feed.apply(state, [kill(10, HOUR + 7200 + 5)], LINKED)  # Too late: the bounty ran out.
        self.assertIsNone(state['bounty'].get('claimed'))
        kill_feed.ensure_bounty(state, HOUR + 7200 + 30)
        self.assertEqual(state['bounties'][-1]['status'], 'escaped')
        self.assertIsNone(state['bounty'])  # Nobody killed 22A three times in that hour.
        self.assertEqual(state['deck'], {})  # Escaped bounties stay in the ledger, not the deck.

    def test_one_kill_is_enough_and_ties_go_to_the_most_recent_killer(self):
        state = kill_feed.blank()
        kill_feed.apply(state, self.enemy_kills(HOUR + 60, 1, 1, 'Early') + self.enemy_kills(HOUR + 900, 1, 5, 'Late', '76561198011111111'), LINKED)
        kill_feed.ensure_bounty(state, HOUR + 3600 + 30)
        self.assertEqual((state['bounty']['name'], state['bounty']['kills']), ('Late', 1))

    def test_unlinked_members_wearing_the_tag_count_but_team_kills_do_not(self):
        state = kill_feed.blank()
        kill_feed.apply(state, [kill(1, HOUR + 60, killer=ENEMY, victim='76561198099999999', kname='Foe', vname='[22A] Unlinked'),
                                kill(2, HOUR + 90, killer=ENEMY, victim=ME, kname='Foe', vname='[22A] Peaches', team_kill=True)], LINKED)
        kill_feed.ensure_bounty(state, HOUR + 3600 + 30)
        self.assertEqual(state['bounty']['kills'], 1)

    def test_no_kills_on_22a_means_no_bounty(self):
        state = kill_feed.blank()
        kill_feed.apply(state, [kill(1, HOUR + 60)], LINKED)  # Only our kills, nobody killed us.
        with self.assertLogs('22a.killfeed', 'INFO') as logs:
            kill_feed.ensure_bounty(state, HOUR + 3600 + 30)
            kill_feed.ensure_bounty(state, HOUR + 3600 + 330)  # Logged once per hour, not every check.
        self.assertIsNone(state['bounty'])
        self.assertEqual(len(logs.output), 1)
        self.assertIn('no bounty', logs.output[0])


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
        self.assertEqual(pc.deck_label('2026-3'), '2026 · Deck 3')

    def test_cards_are_dealt_in_order_and_a_full_deck_starts_a_new_one(self):
        state = kill_feed.blank()
        for i in range(55):
            kill_feed.deal_card(state, {'hour': i, 'name': f'T{i}', 'claimed': ME if i % 3 else MATE, 'claimed_name': 'P'}, WED)
        year = datetime.fromtimestamp(WED, kill_feed.UK).year
        self.assertEqual((len(state['deck'][f'{year}-1']), len(state['deck'][f'{year}-2'])), (53, 2))
        self.assertEqual(state['deck'][f'{year}-2']['2']['name'], 'T54')
        self.assertEqual(kill_feed.hunter_of_deck(state, f'{year}-1')['steam'], ME)
        self.assertEqual(kill_feed.current_deck(state, datetime(year + 1, 1, 2, tzinfo=timezone.utc).timestamp()), (f'{year + 1}-1', 1))

    def test_old_weekly_deck_is_redealt_and_survives_a_rebuild(self):
        import json

        old = {'2026': {'7': {'n': 7, 'week': '2026-W07', 'name': 'B', 'status': 'claimed', 'claimed': ME, 'claimed_at': '2026-02-12T20:00:00+00:00'},
                        '3': {'n': 3, 'week': '2026-W03', 'name': 'A', 'status': 'claimed', 'claimed': MATE, 'claimed_at': '2026-01-15T20:00:00+00:00'},
                        '5': {'n': 5, 'week': '2026-W05', 'name': 'C', 'status': 'escaped'}}}

        class Store:
            data = {kill_feed.STORE_KEY: json.dumps({'version': 1, 'deck': old, 'wanted': {'2026-W07': {}}})}
            def get(self, k): return self.data.get(k)
            def set(self, k, v): self.data[k] = v
        feed = kill_feed.KillFeed(SimpleNamespace(store=Store()))
        deck = feed.state['deck']['2026-1']
        self.assertEqual((deck['1']['name'], deck['2']['name'], len(deck)), ('A', 'B', 2))
        self.assertNotIn('2026', feed.state['deck'])
        self.assertEqual(feed.state['wanted'], {})

    def test_cards_draw_and_the_api_lists_54_slots_with_this_hours_card(self):
        import playing_card
        from website_shame import deck_view
        from PIL import Image
        for entry in ({'n': 1, 'name': 'X', 'kills': 3, 'hour': 490000, 'status': 'open'},
                      {'n': 53, 'name': 'Y', 'kills': 3, 'hour': 490000, 'status': 'claimed', 'claimed_name': 'P'},
                      {'n': 54, 'name': '[22A] Z', 'count': 2}):
            self.assertEqual(Image.open(io.BytesIO(playing_card.render(entry, '2026-1'))).size, (750, 1050))
        state = kill_feed.blank()
        kill_feed.deal_card(state, {'hour': 1, 'name': 'X', 'kills': 3, 'claimed': ME, 'claimed_name': 'P'}, WED)
        deck_id, n = kill_feed.current_deck(state, WED)
        state['bounty'] = {'hour': 2, 'name': 'Open', 'kills': 3, 'set_at': WED, 'expires': WED + 3600, 'claimed': None, 'deck': deck_id, 'card': n}
        who = lambda steam, name: {'id': None, 'name': name, 'avatar': ''}
        deck = deck_view(state, who)[0]
        self.assertEqual((deck['deck'], len(deck['slots']), deck['collected']), (deck_id, 54, 1))
        self.assertTrue(deck['slots'][0]['image'].startswith(f'/api/reports/card/{deck_id}/1.png?v='))
        self.assertEqual((deck['slots'][1]['status'], deck['slots'][1]['name']), ('open', 'Open'))
        self.assertEqual(deck['slots'][53]['status'], 'hunter')
        self.assertNotIn('image', deck['slots'][2])

    def test_discord_posts_use_the_playing_card(self):
        bot = SimpleNamespace(progression=SimpleNamespace(state={'players': {}}), guild=None,
                              kill_feed=SimpleNamespace(state={'deck': {'2026-1': {'1': {}, '2': {}, '3': {}}}}))
        e = {'type': 'bounty_claimed', 'hour': 490000, 'expires': 490001 * 3600, 'deck': '2026-1', 'card': 3,
             'name': 'X', 'kills': 4, 'claimed': ME, 'claimed_name': 'P'}
        msg = asyncio.run(message_for(bot, e))
        self.assertEqual(msg['file'].filename, 'most-wanted-card.png')
        self.assertIn('Ace of Hearts', msg['embed'].description)
        self.assertIn('3 of 53 cards collected in 2026 · Deck 1', msg['embed'].description)
        e = {**e, 'type': 'bounty_set', 'claimed': None}
        self.assertIn('Up for grabs: the **Ace of Hearts**', asyncio.run(message_for(bot, e))['embed'].description)


class FeedReadTests(unittest.TestCase):
    def test_reply_arriving_in_pieces_is_read_in_full(self):
        import json

        body = json.dumps({'data': [kill(i, WED + i) for i in range(400)], 'next': '9'}).encode()
        self.assertGreater(len(body), 65536)

        class Content:
            async def read(self, n=-1):  # The old code's single read only got the first piece.
                return body[:20000]

            async def iter_chunked(self, size):
                for i in range(0, len(body), 20000):
                    yield body[i:i + 20000]

        class Response:
            status, content = 200, Content()
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False

        session = SimpleNamespace(get=lambda *a, **k: Response())
        feed = kill_feed.KillFeed(SimpleNamespace(store=None))
        with mock.patch('kill_feed.api_key', return_value='k'):
            payload = asyncio.run(feed.page(session, None))
        self.assertEqual((len(payload['data']), payload['next']), (400, '9'))
