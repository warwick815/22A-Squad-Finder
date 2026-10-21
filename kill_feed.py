"""TF21 kill feed: dog tags, the hall of shame and kill-based ribbons.

The first call (no cursor) returns recent history; later calls use ?after=<next>
to fetch only new kills. Kills are processed once each (by id) and folded into
per-member totals, so storage stays small however long it runs. Only linked
members (Steam IDs in progression) collect tags and stats.
"""
import asyncio
import json
import logging
import time
from urllib.parse import urlencode

import aiohttp

from tf21_api import api_key, enabled

log = logging.getLogger('22a.killfeed')
API_URL = 'https://tf21.net/api/v1/22a-kill-feed'
STORE_KEY = 'kill_feed_v1'
TIERS = ((30, 'gold'), (20, 'silver'), (10, 'bronze'))
SHAME_KEEP = 300
MAX_PAGES = 20


def tier(count):
    return next((name for need, name in TIERS if count >= need), None)


def next_tier(count):
    return next((need for need in (10, 20, 30) if count < need), None)


def _key(steam, name):
    return str(steam) if steam else 'name:' + (name or 'Unknown')


def _member(state, steam):
    return state['members'].setdefault(steam, {
        'kills': 0, 'deaths': 0, 'headshots': 0, 'team_kills': 0, 'grenade': 0, 'explosive': 0,
        'vehicle': 0, 'revenge': 0, 'longest': None, 'victims': {}, 'killers': {}})


def _nemesis(member):
    best = max(member['killers'].items(), key=lambda kv: kv[1]['count'], default=None)
    return best[0] if best and best[1]['count'] >= 3 else None


def blank():
    return {'cursor': None, 'max_id': 0, 'processed': 0, 'members': {}, 'shame': []}


def apply(state, kills, linked):
    """Fold a page of kills into the state. `linked` is the set of member Steam IDs.
    Returns how many new kills were processed."""
    new = 0
    for k in sorted((k for k in kills if isinstance(k, dict) and isinstance(k.get('id'), int)), key=lambda k: k['id']):
        if k['id'] <= state['max_id']:
            continue  # Already counted.
        state['max_id'] = k['id']
        new += 1
        if k.get('outcome') != 'kill':
            continue  # Suicides ("self") are not kills.
        ks, vs = str(k.get('killer_steam_id') or ''), str(k.get('victim_steam_id') or '')
        kn, vn = k.get('killer_name') or 'Unknown', k.get('victim_name') or 'Unknown'
        team_kill = bool(k.get('team_kill'))
        weapon = k.get('weapon') or 'Unknown'
        distance = k.get('distance_m') if isinstance(k.get('distance_m'), (int, float)) else None
        killer_ours = ks in linked or kn.startswith('[22A]')
        victim_ours = vs in linked or vn.startswith('[22A]')
        if killer_ours and victim_ours:
            state['shame'].append({'id': k['id'], 'at': k.get('at'), 'killer': ks, 'killer_name': kn,
                                   'victim': vs, 'victim_name': vn, 'weapon': weapon, 'team_kill': team_kill,
                                   'headshot': bool(k.get('headshot')), 'distance': distance,
                                   'map': k.get('map'), 'server': k.get('server')})
            del state['shame'][:-SHAME_KEEP]
        if vs in linked:
            victim = _member(state, vs)
            victim['deaths'] += 1
            if not team_kill:
                entry = victim['killers'].setdefault(_key(ks, kn), {'name': kn, 'count': 0})
                entry['name'] = kn
                entry['count'] += 1
        if ks not in linked:
            continue
        m = _member(state, ks)
        if team_kill:
            m['team_kills'] += 1
            continue  # Friendly fire never earns tags or ribbons.
        if _nemesis(m) == _key(vs, vn):
            m['revenge'] += 1
        m['kills'] += 1
        m['headshots'] += bool(k.get('headshot'))
        lw = weapon.lower()
        m['grenade'] += 'grenade' in lw
        m['explosive'] += any(w in lw for w in ('claymore', 'mine', 'c4', 'satchel'))
        m['vehicle'] += k.get('weapon_category') == 'vehicle_weapon'
        if distance is not None and (not m['longest'] or distance > m['longest']['m']):
            m['longest'] = {'m': distance, 'weapon': weapon, 'victim': vn, 'at': k.get('at')}
        tag = m['victims'].setdefault(_key(vs, vn), {'name': vn, 'count': 0, 'headshots': 0, 'first': k.get('at')})
        tag['name'] = vn
        tag['count'] += 1
        tag['headshots'] += bool(k.get('headshot'))
        tag['last'] = k.get('at')
    state['processed'] += new
    return new


def dogtags(state, steam):
    """Earned and nearly-earned tags for one member, best first."""
    m = state['members'].get(str(steam))
    if not m:
        return []
    result = []
    for key, v in m['victims'].items():
        t, nxt = tier(v['count']), next_tier(v['count'])
        if t or (nxt and v['count'] >= nxt - 5):
            result.append({'victim': v['name'], 'steam': None if key.startswith('name:') else key, 'kills': v['count'],
                           'headshots': v['headshots'], 'tier': t, 'next': nxt, 'first': v.get('first'), 'last': v.get('last')})
    order = {'gold': 0, 'silver': 1, 'bronze': 2, None: 3}
    return sorted(result, key=lambda d: (order[d['tier']], -d['kills'], d['victim'].lower()))


def summary(state, steam):
    m = state['members'].get(str(steam))
    if not m:
        return None
    nem = _nemesis(m)
    fav = max(m['victims'].values(), key=lambda v: v['count'], default=None)
    tags = [tier(v['count']) for v in m['victims'].values()]
    return {'kills': m['kills'], 'deaths': m['deaths'], 'headshots': m['headshots'], 'team_kills': m['team_kills'],
            'grenade': m['grenade'], 'explosive': m['explosive'], 'vehicle': m['vehicle'], 'revenge': m['revenge'],
            'longest': m['longest'], 'nemesis': m['killers'][nem] if nem else None,
            'favourite': {'name': fav['name'], 'count': fav['count']} if fav else None,
            'tags': {t: tags.count(t) for t in ('gold', 'silver', 'bronze')}}


class KillFeed:
    def __init__(self, bot):
        self.bot = bot
        # Without a database (e.g. some tests) the feed simply starts empty and stays in memory.
        self.store = getattr(bot, 'store', None)
        try:
            self.state = {**blank(), **json.loads((self.store.get(STORE_KEY) if self.store else None) or '{}')}
        except ValueError:
            self.state = blank()
        self.lock = asyncio.Lock()

    def save(self):
        if self.store:
            self.store.set(STORE_KEY, json.dumps(self.state))

    async def page(self, session, cursor):
        url = API_URL + ('?' + urlencode({'after': cursor}) if cursor is not None else '')
        async with session.get(url, allow_redirects=False, headers={'Authorization': 'Bearer ' + api_key(),
                               'Accept': 'application/json', 'User-Agent': '22A-Discord-Bot/1.0'}) as response:
            if response.status != 200:
                raise ValueError(f'TF21 kill feed HTTP {response.status}')
            body = await response.content.read(20 * 1024 * 1024 + 1)
            if len(body) > 20 * 1024 * 1024:
                raise ValueError('TF21 kill feed reply too large')
            payload = json.loads(body)
        if not isinstance(payload, dict) or not isinstance(payload.get('data'), list):
            raise ValueError('TF21 kill feed reply not recognised')
        return payload

    async def refresh(self, linked):
        """Fetch new kills (history on the first run) and fold them in."""
        if not enabled():
            return 0
        async with self.lock:
            total = 0
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=40)) as session:
                    for _ in range(MAX_PAGES):
                        payload = await self.page(session, self.state['cursor'])
                        total += apply(self.state, payload['data'], linked)
                        nxt = payload.get('next')
                        if nxt is None or nxt == self.state['cursor']:
                            break
                        self.state['cursor'] = nxt
                        if not payload['data']:
                            break
            finally:
                self.save()
            if total:
                log.info('Kill feed: %d new kill(s); %d processed in total', total, self.state['processed'])
            return total


def service(bot):
    if not hasattr(bot, 'kill_feed'):
        bot.kill_feed = KillFeed(bot)
    return bot.kill_feed
