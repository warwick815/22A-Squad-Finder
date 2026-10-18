from rank_divisions import thresholds, division
"""Same-process member portal. Discord identity; existing bot services own all data."""
import asyncio
import logging
import math
import json
import os
import secrets
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode

import aiohttp
from aiohttp import web
import discord

from progression import RANKS, SCORING
from specialities import OPTIONS, label, validate
from tools_stats import get_service
from preferences import TEAMS, CLASSES
from website_actions import HQActions
from website_club import ClubActions
from website_exchange import ExchangeActions
from website_medals import medals
from website_analytics import history, milestones, movement, date

ROOT = Path(__file__).resolve().parent
SESSION_COOKIE = '__Host-22a-web'
STATE_COOKIE = '__Host-22a-oauth'
BADGES = ('pte', 'lcpl', 'cpl', 'sgt', 'ssgt', 'wo2', 'wo1')
STATS = ('kills', 'deaths', 'kd', 'wins', 'losses', 'hoursPlayed',
         'cashEarned', 'killsPerHour', 'teamKills', 'suicides')
log = logging.getLogger('22a.website')


def number(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


class Website(HQActions, ClubActions, ExchangeActions):
    def __init__(self, bot, origin):
        self.bot, self.origin = bot, origin
        self.client_id = os.getenv('WEBSITE_DISCORD_CLIENT_ID', '').strip()
        self.client_secret = os.getenv('WEBSITE_DISCORD_CLIENT_SECRET', '').strip()
        self.sessions, self.states = {}, {}

    def install(self, app):
        app.middlewares.append(self.errors)
        for path, handler in [('/', self.index), ('/auth/login', self.login),
                              ('/auth/callback', self.callback), ('/api/site', self.site),
                              ('/api/dashboard', self.dashboard), ('/api/profile/{uid}', self.profile)]:
            app.router.add_get(path, handler)
        app.router.add_post('/api/specialities', self.specialities)
        app.router.add_post('/api/soldier', self.soldier)
        app.router.add_post('/auth/logout', self.logout)
        app.router.add_get('/api/staff', self.staff_status)
        app.router.add_post('/api/staff/prepare', self.staff_prepare)
        app.router.add_post('/api/staff/confirm', self.staff_confirm)
        app.router.add_post('/api/squads', self.squad_action)
        app.router.add_post('/api/share', self.share_profile)
        app.router.add_get('/api/exchange', self.exchange_status)
        app.router.add_post('/api/exchange/quote', self.exchange_quote)
        app.router.add_post('/api/exchange/trade', self.exchange_trade)
        app.router.add_get('/api/club', self.club_status)
        app.router.add_post('/api/club', self.club_action)
        app.router.add_static('/assets/', ROOT / 'web', show_index=False)
        app.router.add_static('/badges/', ROOT / 'rank_badges', show_index=False)

    @web.middleware
    async def errors(self, request, handler):
        try:
            response = await handler(request)
        except web.HTTPException as exc:
            response = exc if 300 <= exc.status < 400 else web.json_response(
                {'error': exc.reason}, status=exc.status)
        except Exception:
            # Never log URLs, OAuth assertions, cookies or request bodies.
            log.error('Website request failed; existing bot data retained')
            response = web.json_response({'error': 'Service unavailable. Try again shortly.'}, status=503)
        response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY',
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' https://cdn.discordapp.com https://media.discordapp.net; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
        return response

    async def index(self, request):
        return web.FileResponse(ROOT / 'web' / 'index.html')

    async def site(self, request):
        return web.json_response({'login_enabled': bool(self.client_id and self.client_secret),
            'invite': 'https://discord.gg/Y3D4Y5SM5X', 'ranks': RANKS, 'scoring': SCORING})

    def purge(self):
        now = time.monotonic()
        for collection in (self.sessions, self.states):
            for key in list(collection):
                if collection[key]['expires'] <= now:
                    del collection[key]

    async def login(self, request):
        if not self.client_id or not self.client_secret:
            raise web.HTTPServiceUnavailable(reason='Website sign-in is not configured. Ask staff to finish WEBSITE-SETUP.md.')
        self.purge()
        if len(self.states) >= 500:
            raise web.HTTPTooManyRequests(reason='Too many sign-in requests. Try again in a few minutes.')
        state, binding = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        self.states[state] = {'binding': binding, 'expires': time.monotonic() + 600}
        response = web.HTTPFound('https://discord.com/oauth2/authorize?' + urlencode({
            'client_id': self.client_id, 'redirect_uri': self.origin + '/auth/callback',
            'response_type': 'code', 'scope': 'identify', 'state': state}))
        response.set_cookie(STATE_COOKIE, binding, secure=True, httponly=True, samesite='Lax', path='/', max_age=600)
        return response

    async def exchange(self, code):
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.post('https://discord.com/api/oauth2/token', data={
                'client_id': self.client_id, 'client_secret': self.client_secret,
                'grant_type': 'authorization_code', 'code': code,
                'redirect_uri': self.origin + '/auth/callback'}, allow_redirects=False) as response:
                if response.status != 200:
                    raise web.HTTPBadRequest(reason='Discord sign-in expired. Start again from the homepage.')
                token = (await response.json())['access_token']
            async with session.get('https://discord.com/api/v10/users/@me',
                    headers={'Authorization': 'Bearer ' + token}, allow_redirects=False) as response:
                if response.status != 200:
                    raise web.HTTPUnauthorized(reason='Could not verify Discord identity.')
                return int((await response.json())['id'])

    async def member(self, uid):
        if not getattr(self.bot, 'initialized', False) or not getattr(self.bot, 'guild', None):
            raise web.HTTPServiceUnavailable(reason='The bot is starting. Try again shortly.')
        try:
            return await asyncio.wait_for(self.bot.guild.fetch_member(uid), 10)
        except discord.NotFound:
            raise web.HTTPForbidden(reason='Join the 22A Discord to access the member hub.') from None
        except (discord.HTTPException, asyncio.TimeoutError):
            raise web.HTTPServiceUnavailable(reason='Could not check Discord membership. Try again shortly.') from None

    async def callback(self, request):
        self.purge()
        state = request.query.get('state', '')
        pending = self.states.get(state)
        if not pending or not secrets.compare_digest(pending['binding'], request.cookies.get(STATE_COOKIE, '')):
            raise web.HTTPBadRequest(reason='Sign-in expired or belongs to another browser. Start again.')
        del self.states[state]
        code = request.query.get('code', '')
        if not code or len(code) > 2048:
            raise web.HTTPBadRequest(reason='Discord sign-in was cancelled. Return to the homepage.')
        uid = await self.exchange(code)
        await self.member(uid)
        if len(self.sessions) >= 2000:
            raise web.HTTPTooManyRequests(reason='Sign-in is busy. Try later.')
        for key in list(self.sessions):
            if self.sessions[key]['uid'] == uid:
                del self.sessions[key]
        sid = secrets.token_urlsafe(32)
        self.sessions[sid] = {'uid': uid, 'csrf': secrets.token_urlsafe(32),
            'expires': time.monotonic() + 43200, 'write_after': 0}
        response = web.HTTPFound('/#overview')
        response.set_cookie(SESSION_COOKIE, sid, secure=True, httponly=True, samesite='Lax', path='/', max_age=43200)
        response.del_cookie(STATE_COOKIE, path='/', secure=True, httponly=True, samesite='Lax')
        return response

    def session(self, request, write=False):
        self.purge()
        session = self.sessions.get(request.cookies.get(SESSION_COOKIE, ''))
        if not session:
            raise web.HTTPUnauthorized(reason='Sign in with Discord to continue.')
        if write and (request.headers.get('Origin') != self.origin or not secrets.compare_digest(
                request.headers.get('X-CSRF-Token', ''), session['csrf'])):
            raise web.HTTPForbidden(reason='This request could not be verified. Reload the page.')
        return session

    def player(self, member, own=False):
        found = self.bot.progression.find(member.id)
        choice = self.bot.specialities.state['members'].get(str(member.id), {'primary': None, 'secondary': []})
        result = {'id': str(member.id), 'name': member.display_name,
            'avatar': str(member.display_avatar.url), 'linked': bool(found),
            'specialities': {k: choice.get(k) for k in ('primary', 'secondary', 'pending')}}
        result['soldier'] = self.bot.specialities.state.get('soldiers', {}).get(str(member.id), {'role': 'auto'})
        preferences = getattr(self.bot, 'preferences', None)
        role_ids = {r.id for r in member.roles}
        pref_roles = preferences.state['roles'] if preferences else {}
        result['preferences'] = {'teams': [value[0] for key, value in TEAMS.items() if pref_roles.get(key) in role_ids],
            'classes': [value[0] for key, value in CLASSES.items() if pref_roles.get(key) in role_ids]}
        betting = getattr(self.bot, 'betting', None)
        if betting and getattr(betting, 'book', None):
            book = betting.book.data
            uid = str(member.id)
            reserved = sum(b['stake'] for b in book.get('bets', {}).values()
                if b['status'] in ('offered', 'active') and
                (b['a'] == member.id or (b['b'] == member.id and b['status'] == 'active')))
            positions = book.get('exchange', {}).get('holdings', {}).get(uid, {})
            result['wallet'] = dict(available=book.get('wallets', {}).get(uid, 10000),
                reserved=reserved, invested_cost=sum(p['cost'] for p in positions.values()))
        else:
            result['wallet'] = None
        if not found:
            return result
        steam, p = found
        row = self.bot.player_panel.rows.get(steam, {})
        rank = p['rank']
        floors=thresholds(p)
        result['division']=division(p)
        stats = {k: number(row.get(k)) for k in STATS}
        w, l = stats['wins'], stats['losses']
        stats['winRate'] = 100 * w / (w + l) if w is not None and l is not None and w + l else None
        result.update(rating=p['points2'] / 2, rank=rank, rank_name=RANKS[rank][0],
            badge='/badges/' + BADGES[rank] + '.png', stats=stats,
            status='Paused' if not p['active'] else 'Under review' if p.get('hold') else
                'Awaiting baseline' if p.get('baseline') is None else 'Active',
            updated=p.get('updated'), stats_updated=self.bot.player_panel.updated,
            next_rank={'name': RANKS[rank+1][0], 'points': floors[rank+1]} if rank < len(RANKS)-1 else None,
            rank_floor=floors[rank])
        result['milestones'] = milestones(p, row)
        result['medals'] = medals(self.bot, steam, p, row)
        result['season_started'] = p.get('season_started')
        result['source'] = p.get('rating_source', 'WDUK')
        if own:
            result['review'] = p.get('hold')
            result['history'] = history(p)
        service = get_service(self.bot)
        pid = service.state['links'].get(str(member.id))
        if not pid and steam == '76561197988807107':
            pid = 'd8f9bef7-7dc6-4017-8228-0fd1ce527c93'
        tools = service.state['cache'].get(pid)
        result['tools'] = ({'url': 'https://wardogs.tools/player/' + pid,
            'values': {k: tools['values'].get(k) for k in ('wardogLevel', 'xp', 'cash', 'worth', 'gold')},
            'levels': {k: tools['levels'].get(k) for k in ('infantry', 'medic', 'recon', 'support', 'driver', 'pilot')}, 'updated': tools['updated'],
            'failed': tools.get('failed', False)} if tools else None)
        return result

    async def dashboard(self, request):
        session = self.session(request)
        member = await self.member(session['uid'])
        players = []
        for p in self.bot.progression.state['players'].values():
            m = member if p['discord_id'] == member.id else self.bot.guild.get_member(p['discord_id'])
            if m and not m.bot:
                players.append(self.player(m))
        players.sort(key=lambda p: (-p['rating'], p['name'].casefold(), p['id']))
        rank, previous = 0, None
        for n, p in enumerate(players, 1):
            if p['rating'] != previous: rank = n
            p['position'] = rank; previous = p['rating']
        season = self.bot.progression.state.get('season', 1)
        store = getattr(self.bot, 'store', None)
        snapshots = json.loads(store.get('website_standings_v1') or '[]') if store else []
        now = datetime.now(timezone.utc)
        changes = movement(snapshots, players, season, now)
        for p in players: p['week_movement'] = changes.get(p['id'])
        if store and players and not any(s['season'] == season and s['at'][:10] == now.date().isoformat() for s in snapshots):
            snapshots = [s for s in snapshots if date(s['at']) and date(s['at']) > now-timedelta(days=35)]
            snapshots.append({'at':now.isoformat(), 'season':season, 'order':{p['id']:p['position'] for p in players}})
            store.set('website_standings_v1', json.dumps(snapshots))
        archives = []
        for archive in self.bot.progression.state.get('season_archives', []):
            winners = sorted(archive['players'].values(), key=lambda p:(-p['points2'],p['discord_id']))[:10]
            archives.append({'season':archive['season'], 'closed':archive['closed'], 'players':[
                {'name':getattr(self.bot.guild.get_member(p['discord_id']), 'display_name', 'Former member'),
                 'rating':p['points2']/2, 'rank':RANKS[p['rank']][0]} for p in winners]})
        roster = []
        for m in self.bot.guild.members:
            if m.bot:
                continue
            selected = [key for key, rid in self.bot.specialities.state['roles'].items()
                        if any(role.id == rid for role in m.roles)]
            if selected:
                roster.append({'id': str(m.id), 'name': m.display_name, 'roles': selected})
        from season_stats import standings
        season_boards=standings(self.bot.progression.state,self.bot.guild)
        live={p['id']:p for p in players}
        for board in season_boards:
            if board['current']:
                for row in board['players']:
                    row['wallet']=live.get(row['id'],{}).get('wallet')
                    row['week_movement']=live.get(row['id'],{}).get('week_movement')
        return web.json_response({'season_standings':season_boards, 'me': self.player(member, own=True), 'players': players,
            'roster': roster, 'options': [{'key': key, 'label': label(key), 'group': OPTIONS[key][0]} for key in OPTIONS],
            'csrf': session['csrf'], 'scoring': SCORING, 'ranks': RANKS,
            'season':season, 'archives':archives,
            'staff':bool(getattr(getattr(member, 'guild_permissions', None), 'manage_guild', False)),
            'squads':self.squad_list(member),
            'updated': self.bot.player_panel.updated})

    async def profile(self, request):
        session = self.session(request)
        await self.member(session['uid'])
        raw = request.match_info['uid']
        if not raw.isdecimal() or len(raw) > 20:
            raise web.HTTPBadRequest(reason='Invalid player.')
        member = await self.member(int(raw))
        return web.json_response(self.player(member, own=member.id == session['uid']))

    async def specialities(self, request):
        session = self.session(request, write=True)
        if time.monotonic() < session['write_after']:
            raise web.HTTPTooManyRequests(reason='Please wait a few seconds before saving again.')
        session['write_after'] = time.monotonic() + 5
        member = await self.member(session['uid'])
        try:
            data = await request.json()
            if not isinstance(data, dict) or set(data) != {'primary', 'secondary'}:
                raise ValueError('Choose a primary speciality and up to three secondaries.')
            primary, secondary = data['primary'], data['secondary']
            if (primary is not None and not isinstance(primary, str)) or not isinstance(secondary, list) or any(not isinstance(k, str) for k in secondary):
                raise ValueError('Invalid speciality selection.')
            validate(primary, secondary)
        except (ValueError, TypeError):
            raise web.HTTPBadRequest(reason='Choose one valid primary and up to three different secondary specialities.') from None
        service = self.bot.specialities
        async with service.lock:
            service.state['members'][str(member.id)] = {'primary': primary, 'secondary': secondary, 'pending': True}
            service.save()
            try:
                await asyncio.wait_for(service.sync_member(member), 15)
                message = 'Specialities saved and Discord roles updated.'
            except (discord.HTTPException, ValueError, asyncio.TimeoutError):
                message = 'Choices saved. Discord roles are pending; the bot will retry. Ask staff to check the roles panel if this persists.'
        return web.json_response({'message': message, 'choice': service.state['members'][str(member.id)]})

    async def soldier(self, request):
        session = self.session(request, write=True)
        member = await self.member(session['uid'])
        if not self.bot.progression.find(member.id):
            raise web.HTTPBadRequest(reason='Link Steam before customising your soldier.')
        try:
            payload = await request.json()
            if not isinstance(payload, dict) or set(payload) != {'role'} or payload['role'] not in ('auto','rifle','medic','crew','recon','at','lmg','pilot','engineer'):
                raise ValueError()
        except (ValueError, TypeError):
            raise web.HTTPBadRequest(reason='Choose a valid soldier appearance.') from None
        service = self.bot.specialities
        async with service.lock:
            service.state.setdefault('soldiers', {})[str(member.id)] = {'role': payload['role']}
            service.save()
        return web.json_response({'message': 'Soldier appearance saved. Your earned rank controls equipment progression.', 'soldier': {'role': payload['role']}})

    async def logout(self, request):
        self.session(request, write=True)
        self.sessions.pop(request.cookies.get(SESSION_COOKIE), None)
        response = web.json_response({'ok': True})
        response.del_cookie(SESSION_COOKIE, path='/', secure=True, httponly=True, samesite='Lax')
        return response
