"""Public, read-only view for people outside the Discord. No sign-in.

Shows only what a recruit would want to see: current standings, past season
winners and the Fantasy leaderboard. No Discord or Steam IDs, wallets, rating
history, online status or staff data are included. The result is cached for a
minute so public traffic cannot hammer the bot.
"""
import time
from pathlib import Path

from aiohttp import web

import fantasy
from progression import RANKS
from rank_divisions import division

BADGES = ('pte', 'lcpl', 'cpl', 'sgt', 'ssgt', 'wo2', 'wo1')
CACHE_SECONDS = 60
PAGE = Path(__file__).resolve().parent / 'web' / 'public.html'


def _number(value):
    return value if type(value) in (int, float) and value == value and value >= 0 else None


def _avatar(member):
    return str(getattr(getattr(member, 'display_avatar', None), 'url', '') or '')


def build(bot):
    state = bot.progression.state
    guild = bot.guild
    rows = getattr(getattr(bot, 'player_panel', None), 'rows', {}) or {}
    players = []
    for steam, p in state['players'].items():
        member = guild.get_member(p['discord_id'])
        # Only current, active members appear publicly.
        if not member or member.bot or not p.get('active') or p.get('hold'):
            continue
        from tf21_api import combined
        row = combined(rows.get(steam, {}), (getattr(getattr(bot, 'tf21_api', None), 'rows', None) or {}).get(steam))
        players.append({'name': member.display_name, 'avatar': _avatar(member),
            'rating': p['points2'] / 2, 'rank': RANKS[p['rank']][0],
            'badge': '/badges/' + BADGES[p['rank']] + '.png',
            'division': (division(p) or {}).get('name'),
            'kd': _number(row.get('kd')), 'wins': _number(row.get('wins')), 'kills': _number(row.get('kills'))})
    players.sort(key=lambda p: (-p['rating'], p['name'].casefold()))
    position, previous = 0, None
    for n, p in enumerate(players, 1):
        if p['rating'] != previous:
            position = n
        p['position'], previous = position, p['rating']

    names = lambda uid: getattr(guild.get_member(int(uid)), 'display_name', 'Former member')
    archives = []
    for archive in state.get('season_archives', []):
        top = sorted(archive['players'].values(), key=lambda p: (-p['points2'], p['discord_id']))[:3]
        archives.append({'season': archive['season'], 'closed': archive.get('closed'),
            'podium': [{'name': names(p['discord_id']), 'avatar': _avatar(guild.get_member(p['discord_id'])),
                        'rating': p['points2'] / 2, 'rank': RANKS[p['rank']][0]} for p in top]})
    archives.sort(key=lambda a: a['season'], reverse=True)

    season = state.get('season', 1)
    totals = fantasy.totals(state, season)
    top_fantasy = [{'name': names(uid), 'avatar': _avatar(guild.get_member(int(uid))), 'points': points}
                   for uid, points in sorted(totals.items(), key=lambda x: (-x[1], x[0]))[:10]]

    return {'season': season, 'members': len(players), 'players': players, 'archives': archives,
            'fantasy': top_fantasy, 'updated': getattr(getattr(bot, 'player_panel', None), 'updated', None),
            'invite': 'https://discord.gg/Y3D4Y5SM5X'}


class PublicActions:
    async def public_page(self, request):
        return web.Response(body=PAGE.read_bytes(), content_type='text/html',
                            headers={'Cache-Control': 'no-cache'})

    async def public_data(self, request):
        if not getattr(self.bot, 'initialized', False) or not getattr(self.bot, 'guild', None):
            raise web.HTTPServiceUnavailable(reason='The bot is starting. Try again shortly.')
        cached = getattr(self, '_public_cache', None)
        now = time.monotonic()
        if not cached or now - cached[0] > CACHE_SECONDS:
            cached = (now, build(self.bot))
            self._public_cache = cached
        return web.json_response(cached[1], headers={'Cache-Control': 'public, max-age=60'})
