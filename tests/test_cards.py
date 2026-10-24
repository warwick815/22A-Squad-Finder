import asyncio
import io
import os
import unittest
from types import SimpleNamespace
from unittest import mock

import discord
from PIL import Image

import card_send
import cards


def size(png):
    return Image.open(io.BytesIO(png)).size


FULL = {'name': '[22A] Warwick815 🐕', 'rank': 2, 'rank_name': 'Corporal', 'division': {'name': 'Silver', 'index': 1},
        'status': 'Active', 'season': 2, 'rating': 1204.5, 'floor': 938, 'next_rank': {'name': 'Sergeant', 'points': 1875},
        'position': 3, 'members': 24,
        'stats': {'hoursPlayed': 169, 'wins': 63, 'losses': 95, 'kills': 1310, 'kd': 2.0, 'winRate': 39.9},
        'combat': {'kills': 240, 'headshots': 113, 'longest': {'m': 553, 'weapon': 'SV98', 'victim': 'Sam'},
                   'best_streak': {'count': 34, 'weapon': 'Mosin'}, 'nemesis': {'name': 'badbwai', 'count': 8},
                   'favourite': None, 'bounties': 0},
        'top_weapon': {'weapon': 'Mosin Nagant', 'kills': 115, 'headshots': 54}}


class CardDrawingTests(unittest.TestCase):
    def test_profile_with_full_and_empty_data(self):
        self.assertEqual(size(cards.profile(FULL))[0], 1080)
        bare = {**FULL, 'stats': {k: None for k in FULL['stats']}, 'combat': None, 'top_weapon': None,
                'next_rank': None, 'position': None}
        self.assertEqual(size(cards.profile(bare))[0], 1080)

    def test_playstyle(self):
        self.assertEqual(cards.playstyle(FULL['stats'], FULL['combat'])[0], 'HEADHUNTER')
        self.assertEqual(cards.playstyle({}, None)[0], 'WARDOG')
        self.assertEqual(cards.playstyle({'kd': 2.5}, {})[0], 'APEX PREDATOR')

    def test_other_cards(self):
        rows = [('Kills', '10', '—', 10, None, False), ('Deaths', '5', '9', 5, 9, True)]
        side = {'name': 'A', 'rank_name': 'Private', 'rating': 0}
        self.assertEqual(size(cards.compare({'left': side, 'right': side, 'rows': rows}))[0], 1080)
        self.assertEqual(size(cards.rank_change({'name': 'A', 'from': 1, 'to': 0, 'to_name': 'Private', 'before': 260,
                                                 'after': 199, 'delta': None, 'reason': 'Admin fix'})), (1200, 640))
        two = [{'name': 'A', 'rating': 10, 'rank': 0, 'rank_name': 'Private'}, {'name': 'B', 'rating': 0, 'rank': 0, 'rank_name': 'Private'}]
        self.assertEqual(size(cards.standings({'kicker': 'K', 'title': 'T', 'rows': two}))[0], 1080)
        week = {'range': '1 – 7 Oct', 'totals': {'wins': 0, 'losses': 0, 'kills': 0, 'deaths': 0}, 'gains': [],
                'promotions': 0, 'demotions': 0}
        self.assertEqual(size(cards.weekly(week))[0], 1080)


class SendTests(unittest.TestCase):
    def embed(self):
        e = discord.Embed(title='T', description='long text')
        e.add_field(name='Review needed', value='x')
        e.add_field(name='Other', value='y')
        e.set_footer(text='marker')
        return e

    def test_card_attached_with_slim_embed(self):
        sent = asyncio.run(card_send.with_card(self.embed(), cards.weekly, ({'range': 'r', 'totals': {}, 'gains': [], 'promotions': 0, 'demotions': 0},), 'w.png',
                                               description='short', keep=('Review needed',)))
        self.assertEqual((sent['file'].filename, sent['embed'].image.url), ('w.png', 'attachment://w.png'))
        self.assertEqual((sent['embed'].description, sent['embed'].footer.text), ('short', 'marker'))
        self.assertEqual([f.name for f in sent['embed'].fields], ['Review needed'])

    def test_falls_back_when_drawing_fails_or_cards_are_off(self):
        original = self.embed()
        broken = lambda: 1 / 0
        self.assertIs(asyncio.run(card_send.with_card(original, broken, (), 'x.png'))['embed'], original)
        with mock.patch.dict(os.environ, {'DISCORD_CARDS': 'false'}):
            sent = asyncio.run(card_send.with_card(original, cards.weekly, ({'range': 'r', 'totals': {}, 'gains': [], 'promotions': 0, 'demotions': 0},), 'x.png'))
        self.assertEqual(sent, {'embed': original})

    def test_profile_data_from_bot_state(self):
        steam = '76561198000000001'
        player = {'discord_id': 1, 'rank': 1, 'points2': 800, 'active': True, 'hold': None, 'baseline': {}, 'rank_rules': 2}
        other = {**player, 'discord_id': 2, 'points2': 1200}
        bot = SimpleNamespace(progression=SimpleNamespace(state={'season': 2, 'players': {steam: player, 'x': other}}),
                              player_panel=SimpleNamespace(rows={steam: {'kills': 10, 'deaths': 5, 'wins': 3, 'losses': 1}}),
                              store=None)
        with mock.patch('kill_feed.service', side_effect=RuntimeError):
            d = card_send.profile_data(bot, SimpleNamespace(display_name='Me'), steam, player)
        self.assertEqual((d['position'], d['members'], d['rating'], d['stats']['winRate']), (2, 2, 400, 75.0))
        self.assertEqual(d['next_rank']['name'], 'Corporal')
        cards.profile(d)


if __name__ == '__main__':
    unittest.main()


class RoastPauseTests(unittest.TestCase):
    def test_scheduled_roasts_pause_once(self):
        import json
        import roasts

        class Store(dict):
            def get(self, k, d=None): return super().get(k, d)
            def set(self, k, v): self[k] = v
        store = Store(roasts_v1=json.dumps({'last': {}, 'next': 0, 'paused': False}))
        r = roasts.Roasts(SimpleNamespace(store=store))
        self.assertTrue(r.state['paused'])
        r.state['paused'] = False  # staff resume with /roasts paused:false
        r.save()
        self.assertFalse(roasts.Roasts(SimpleNamespace(store=store)).state['paused'])


class UpsertTests(unittest.TestCase):
    def test_card_is_sent_and_replaced_on_edit(self):
        import community
        sent, edited = [], []
        message = SimpleNamespace(id=5, edit=mock.AsyncMock(side_effect=lambda **k: edited.append(k)))
        async def history(limit):
            return
            yield
        channel = SimpleNamespace(fetch_message=mock.AsyncMock(return_value=message), history=history,
                                  send=mock.AsyncMock(side_effect=lambda **k: sent.append(k) or message))
        store = {}
        ranks = SimpleNamespace(bot=SimpleNamespace(store=SimpleNamespace(get=store.get, set=store.__setitem__)))
        f = discord.File(io.BytesIO(b'x'), filename='c.png')
        asyncio.run(community.upsert(ranks, channel, 'k', discord.Embed(title='t'), file=f))
        self.assertIs(sent[0]['file'], f)
        asyncio.run(community.upsert(ranks, channel, 'k', discord.Embed(title='t'), file=f))
        self.assertEqual(edited[0]['attachments'], [f])


class HonoursCardTests(unittest.TestCase):
    def test_ribbon_designs_match_the_website(self):
        import json
        import re
        import ribbons
        js = open('web/medals.js').read()
        body = re.search(r'const ribbonDesigns=(\{.*?\n?\});', js, re.S).group(1)
        body = re.sub(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', body.replace("'", '"'))
        designs = json.loads(body)
        self.assertEqual(set(designs), set(ribbons.DESIGNS), 'Run the ribbon export again: web/medals.js changed.')
        for key, d in designs.items():
            self.assertEqual([list(s) for s in ribbons.DESIGNS[key]['stripes']], d['stripes'], key)
            self.assertEqual(ribbons.DESIGNS[key].get('device'), d.get('device'), key)

    def test_card_draws_with_and_without_honours(self):
        full = {'name': 'A', 'rank': 2, 'rank_name': 'Corporal', 'season': 2,
                'ribbons': [{'id': 'bounty1'}, {'id': 's', 'metal': 'gold'}, {'id': 'unknown-award'}] * 9, 'total': 46,
                'patches': [('shock', 'Shock Troop'), ('missing', 'Missing art')],
                'accolades': [('COMBAT RATING', 'Top 5%', '2,900')]}
        self.assertEqual(size(cards.honours(full))[0], 1080)
        empty = {**full, 'ribbons': [], 'patches': [], 'accolades': []}
        self.assertEqual(size(cards.honours(empty))[0], 1080)

    def test_share_posts_profile_and_honours_cards(self):
        embed = discord.Embed(title='Profile', description='x')
        profile = {'embed': discord.Embed(title='p'), 'file': discord.File(io.BytesIO(b'1'), filename='profile.png')}
        honours = (discord.Embed(title='h'), discord.File(io.BytesIO(b'2'), filename='honours.png'))
        with mock.patch('card_send.profile_message', mock.AsyncMock(return_value=profile)), \
             mock.patch('card_send.honours_message', mock.AsyncMock(return_value=honours)):
            sent = asyncio.run(card_send.share_message(None, None, 's', {}, embed))
        self.assertEqual([f.filename for f in sent['files']], ['profile.png', 'honours.png'])
        self.assertEqual(len(sent['embeds']), 2)
        with mock.patch('card_send.profile_message', mock.AsyncMock(return_value=profile)), \
             mock.patch('card_send.honours_message', mock.AsyncMock(return_value=None)):
            self.assertIs(asyncio.run(card_send.share_message(None, None, 's', {}, embed)), profile)

    def test_honours_data_from_bot_state(self):
        steam = '76561198000000001'
        player = {'discord_id': 1, 'rank': 1, 'points2': 800, 'active': True, 'hold': None, 'history': [],
                  'skill': {'top': 20, 'rating': 2300, 'multiplier': 1.1}}
        state = {'season': 2, 'players': {steam: player}, 'season_archives': [],
                 'community_hq': {'lockers': {'1': {'earned': {'shock': {}}, 'display': []}}}}
        bot = SimpleNamespace(progression=SimpleNamespace(state=state), store=None, betting=None,
                              player_panel=SimpleNamespace(rows={steam: {'kills': 1200, 'deaths': 600, 'kd': 2.0, 'wins': 60, 'losses': 40,
                                                                         'hoursPlayed': 120, 'killsPerHour': 10, 'cashEarned': 100}}))
        with mock.patch('kill_feed.service', side_effect=RuntimeError):
            d = card_send.honours_data(bot, SimpleNamespace(display_name='Me'), steam, player)
        self.assertEqual(d['patches'], [('shock', 'Shock Troop')])
        self.assertEqual(d['accolades'][0][0], 'COMBAT RATING')
        self.assertGreater(d['total'], 20)
        cards.honours(d)
