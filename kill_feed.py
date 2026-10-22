"""TF21 kill feed: dog tags, the hall of shame, bounties, kill streaks, squad
sessions, weapon mastery and kill-based ribbons.

The first call (no cursor) returns recent history; later calls use ?after=<next>
to fetch only new kills. Kills are processed once each (by id) and folded into
per-member totals, so storage stays small however long it runs. Only linked
members (Steam IDs in progression) collect tags and stats.
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import aiohttp

from tf21_api import api_key, enabled

log = logging.getLogger('22a.killfeed')
API_URL = 'https://tf21.net/api/v1/22a-kill-feed'
STORE_KEY = 'kill_feed_v1'
TIERS = ((30, 'gold'), (20, 'silver'), (10, 'bronze'))
SHAME_KEEP = 300
MAX_PAGES = 20
VERSION = 2               # Bump to rebuild everything from TF21's 90-day history.
WEAPON_TIERS = ((300, 'gold'), (150, 'silver'), (50, 'bronze'))
STREAK_GAP = 2 * 3600     # A streak ends at a death or after two hours without a TF21 kill.
SESSION_GAP = 3600        # A squad session ends after an hour with no squad kills on that server.
SESSION_MIN = 3           # Members needed for a squad session.
BOUNTY_MIN = 3            # Kills on 22A needed to make Most Wanted.
UK = ZoneInfo('Europe/London')


def _ts(at):
    try:
        d = datetime.fromisoformat(str(at).replace('Z', '+00:00'))
        return d.timestamp() if d.tzinfo else None
    except (TypeError, ValueError):
        return None


def week_key(ts):
    y, w, _ = datetime.fromtimestamp(ts, UK).isocalendar()
    return f'{y}-W{w:02d}'


def weapon_tier(kills):
    return next((name for need, name in WEAPON_TIERS if kills >= need), None)


def tier(count):
    return next((name for need, name in TIERS if count >= need), None)


def next_tier(count):
    return next((need for need in (10, 20, 30) if count < need), None)


def _key(steam, name):
    return str(steam) if steam else 'name:' + (name or 'Unknown')


def _member(state, steam):
    return state['members'].setdefault(steam, {
        'kills': 0, 'deaths': 0, 'headshots': 0, 'team_kills': 0, 'grenade': 0, 'explosive': 0,
        'vehicle': 0, 'revenge': 0, 'longest': None, 'victims': {}, 'killers': {},
        'weapons': {}, 'streak': {'count': 0, 'last': None, 'weapons': {}}, 'best_streak': None,
        'bounties': 0, 'sessions': 0})


def _nemesis(member):
    best = max(member['killers'].items(), key=lambda kv: kv[1]['count'], default=None)
    return best[0] if best and best[1]['count'] >= 3 else None


def blank():
    return {'version': VERSION, 'cursor': None, 'max_id': 0, 'processed': 0, 'members': {}, 'shame': [],
            'wanted': {}, 'bounty': None, 'bounties': [], 'deck': {}, 'streak_week': {}, 'open': {}, 'sessions': [],
            'announce': [], 'live_since': None}


def _announce(state, event, at_ts):
    # Only events after the feed went live are posted; history rebuilds stay quiet.
    if state.get('live_since') and at_ts is not None and at_ts >= state['live_since']:
        state['announce'].append(event)
        del state['announce'][:-20]


def _death(state, steam, t):
    m = _member(state, steam)
    m['streak'] = {'count': 0, 'last': t, 'weapons': {}}


def _close_session(state, server):
    o = state['open'].pop(server, None)
    if not o or len(o['members']) < SESSION_MIN:
        return
    top = max(o['members'].items(), key=lambda kv: (kv[1]['kills'], kv[1]['headshots']))
    session = {'server': server, 'map': max(o['maps'], key=o['maps'].get) if o['maps'] else None,
               'start': o['start'], 'end': o['last'], 'kills': o['kills'], 'headshots': o['headshots'],
               'members': [{'steam': k, **v} for k, v in sorted(o['members'].items(), key=lambda kv: -kv[1]['kills'])],
               'top': {'steam': top[0], **top[1]}, 'longest': o['longest'],
               'weapon': max(o['weapons'].items(), key=lambda kv: kv[1]) if o['weapons'] else None}
    # Extras for the after-action card (sessions saved before these existed simply lack them).
    for m in session['members']:
        m['deaths'] = m.get('deaths', 0)
        m.pop('run', None)
    session['deaths'] = sum(m['deaths'] for m in session['members'])
    best = max(session['members'], key=lambda m: m.get('best', 0))
    session['streak'] = {'steam': best['steam'], 'name': best['name'], 'count': best['best']} if best.get('best') else None
    for field, out in (('nemeses', 'nemesis'), ('targets', 'target')):
        top_entry = max((o.get(field) or {}).values(), key=lambda v: v['count'], default=None)
        session[out] = dict(top_entry) if top_entry and top_entry['count'] >= 2 else None
    for steam in o['members']:
        _member(state, steam)['sessions'] += 1
    state['sessions'].append(session)
    del state['sessions'][:-30]
    _announce(state, {'type': 'session', **session}, o['last'])


def close_sessions(state, now):
    for server, o in list(state['open'].items()):
        if now - o['last'] > SESSION_GAP:
            _close_session(state, server)


def deck_slot(week):
    """('2026', 42) for '2026-W42': each ISO week is one card in that year's deck."""
    year, number = str(week).split('-W')
    return year, int(number)


def deck_card(state, b, status):
    """Record a bounty as its week's playing card. Cards are kept forever, one deck per year."""
    year, n = deck_slot(b['week'])
    card = {k: b.get(k) for k in ('week', 'target', 'name', 'kills', 'set_at', 'claimed', 'claimed_name',
                                  'claimed_at', 'weapon', 'distance', 'headshot')}
    card.update(n=n, status=status)
    state.setdefault('deck', {}).setdefault(year, {})[str(n)] = card
    return card


def backfill_deck(state):
    """Give bounties posted before the deck existed their cards (never overwrites a card)."""
    deck = state.setdefault('deck', {})
    old = [(b, b.get('status') or ('claimed' if b.get('claimed') else 'escaped')) for b in state.get('bounties', [])]
    if state.get('bounty'):
        old.append((state['bounty'], 'claimed' if state['bounty'].get('claimed') else 'open'))
    for b, status in old:
        year, n = deck_slot(b['week'])
        if str(n) not in deck.get(year, {}):
            deck_card(state, b, status)


def hunter_of_year(state, year):
    """The member with the most claimed cards in a year's deck (the Red Joker), or None."""
    counts = {}
    for card in state.get('deck', {}).get(str(year), {}).values():
        if card.get('status') == 'claimed' and card.get('claimed'):
            entry = counts.setdefault(card['claimed'], {'steam': card['claimed'], 'name': card.get('claimed_name'), 'count': 0})
            entry['count'] += 1
    return max(counts.values(), key=lambda e: (e['count'], -len(e['name'] or '')), default=None)


def ensure_bounty(state, now):
    """Each UK week, last week's top outside killer of 22A members becomes Most Wanted."""
    current = week_key(now)
    b = state.get('bounty')
    if b and b['week'] == current:
        return
    if b:
        state['bounties'].append({**b, 'status': 'claimed' if b.get('claimed') else 'escaped'})
        deck_card(state, b, 'claimed' if b.get('claimed') else 'escaped')
        del state['bounties'][:-20]
    pool = state['wanted'].get(week_key(now - 7 * 86400), {})
    key, entry = max(pool.items(), key=lambda kv: kv[1]['count'], default=(None, None))
    if not entry or entry['count'] < BOUNTY_MIN:
        state['bounty'] = None
        return
    state['bounty'] = {'week': current, 'target': key, 'name': entry['name'], 'kills': entry['count'],
                       'set_at': now, 'claimed': None}
    deck_card(state, state['bounty'], 'open')
    _announce(state, {'type': 'bounty_set', **state['bounty']}, now)


def apply(state, kills, linked):
    """Fold a page of kills into the state. `linked` is the set of member Steam IDs.
    Returns how many new kills were processed."""
    new = 0
    for k in sorted((k for k in kills if isinstance(k, dict) and isinstance(k.get('id'), int)), key=lambda k: k['id']):
        if k['id'] <= state['max_id']:
            continue  # Already counted.
        state['max_id'] = k['id']
        new += 1
        ks, vs = str(k.get('killer_steam_id') or ''), str(k.get('victim_steam_id') or '')
        kn, vn = k.get('killer_name') or 'Unknown', k.get('victim_name') or 'Unknown'
        t = _ts(k.get('at'))
        if k.get('outcome') != 'kill':
            if vs in linked:
                _death(state, vs, t)  # A suicide still ends a streak.
            continue  # Suicides ("self") are not kills.
        team_kill = bool(k.get('team_kill'))
        weapon = k.get('weapon') or 'Unknown'
        distance = k.get('distance_m') if isinstance(k.get('distance_m'), (int, float)) else None
        headshot = bool(k.get('headshot'))
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
            _death(state, vs, t)
            o = state['open'].get(k.get('server'))
            if o and t is not None and t - o['last'] <= SESSION_GAP and vs in o['members']:
                mem = o['members'][vs]
                mem['deaths'] = mem.get('deaths', 0) + 1
                mem['run'] = 0
                if not team_kill and not killer_ours:
                    foe = o.setdefault('nemeses', {}).setdefault(_key(ks, kn), {'name': kn, 'count': 0})
                    foe['name'] = kn
                    foe['count'] += 1
            if not team_kill:
                entry = victim['killers'].setdefault(_key(ks, kn), {'name': kn, 'count': 0})
                entry['name'] = kn
                entry['count'] += 1
                if not killer_ours and t is not None:
                    wanted = state['wanted'].setdefault(week_key(t), {}).setdefault(_key(ks, kn), {'name': kn, 'count': 0})
                    wanted['name'] = kn
                    wanted['count'] += 1
                    for old in sorted(state['wanted'])[:-4]:
                        del state['wanted'][old]
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
        # Weapon mastery.
        w = m['weapons'].setdefault(weapon, {'kills': 0, 'headshots': 0})
        w['kills'] += 1
        w['headshots'] += headshot
        # Kill streak: kills since the last death, broken by a two-hour gap.
        st = m['streak']
        if t is not None and st['last'] is not None and t - st['last'] > STREAK_GAP:
            st = m['streak'] = {'count': 0, 'last': t, 'weapons': {}}
        st['count'] += 1
        st['last'] = t if t is not None else st['last']
        st['weapons'][weapon] = st['weapons'].get(weapon, 0) + 1
        best_weapon = max(st['weapons'], key=st['weapons'].get)
        if not m['best_streak'] or st['count'] > m['best_streak']['count']:
            m['best_streak'] = {'count': st['count'], 'weapon': best_weapon, 'at': k.get('at')}
        if t is not None:
            wk, sw = week_key(t), state['streak_week']
            if sw.get('week') != wk or st['count'] > sw.get('count', 0):
                state['streak_week'] = {'week': wk, 'steam': ks, 'name': kn, 'count': st['count'], 'weapon': best_weapon, 'at': k.get('at')}
        # Bounty: the first member to kill Most Wanted after it was posted claims it.
        b = state.get('bounty')
        if b and not b.get('claimed') and _key(vs, vn) == b['target'] and t is not None and t >= b['set_at']:
            b.update(claimed=ks, claimed_name=kn, claimed_at=k.get('at'), weapon=weapon, distance=distance, headshot=headshot)
            m['bounties'] += 1
            deck_card(state, b, 'claimed')
            _announce(state, {'type': 'bounty_claimed', **b}, t)
        # Squad session on this server.
        server = k.get('server')
        if server and t is not None:
            o = state['open'].get(server)
            if o and t - o['last'] > SESSION_GAP:
                _close_session(state, server)
                o = None
            if not o:
                o = state['open'][server] = {'start': t, 'last': t, 'maps': {}, 'members': {}, 'kills': 0,
                                             'headshots': 0, 'longest': None, 'weapons': {}}
            o['last'] = max(o['last'], t)
            o['kills'] += 1
            o['headshots'] += headshot
            if k.get('map'):
                o['maps'][k['map']] = o['maps'].get(k['map'], 0) + 1
            o['weapons'][weapon] = o['weapons'].get(weapon, 0) + 1
            mem = o['members'].setdefault(ks, {'name': kn, 'kills': 0, 'headshots': 0})
            mem['kills'] += 1
            mem['headshots'] += headshot
            mem['run'] = mem.get('run', 0) + 1
            mem['best'] = max(mem.get('best', 0), mem['run'])
            if not victim_ours:
                prey = o.setdefault('targets', {}).setdefault(_key(vs, vn), {'name': vn, 'count': 0})
                prey['name'] = vn
                prey['count'] += 1
            if distance is not None and (not o['longest'] or distance > o['longest']['m']):
                o['longest'] = {'m': distance, 'weapon': weapon, 'name': kn}
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
    m = {**_member({'members': {}}, steam), **m}  # Fill fields added since the member was stored.
    nem = _nemesis(m)
    fav = max(m['victims'].values(), key=lambda v: v['count'], default=None)
    tags = [tier(v['count']) for v in m['victims'].values()]
    return {'kills': m['kills'], 'deaths': m['deaths'], 'headshots': m['headshots'], 'team_kills': m['team_kills'],
            'grenade': m['grenade'], 'explosive': m['explosive'], 'vehicle': m['vehicle'], 'revenge': m['revenge'],
            'longest': m['longest'], 'nemesis': m['killers'][nem] if nem else None,
            'favourite': {'name': fav['name'], 'count': fav['count']} if fav else None,
            'tags': {t: tags.count(t) for t in ('gold', 'silver', 'bronze')},
            'best_streak': m['best_streak'], 'bounties': m['bounties'], 'sessions': m['sessions'],
            'mastery': {t: sum(1 for w in m['weapons'].values() if weapon_tier(w['kills']) == t) for t in ('gold', 'silver', 'bronze')}}


def weapons(state, steam):
    """Weapon rack: weapons with 10+ kills, with mastery tier and progress."""
    m = state['members'].get(str(steam)) or {}
    rows = []
    for name, w in (m.get('weapons') or {}).items():
        if w['kills'] < 10:
            continue
        nxt = next((need for need in (50, 150, 300) if w['kills'] < need), None)
        rows.append({'weapon': name, 'kills': w['kills'], 'headshots': w['headshots'], 'tier': weapon_tier(w['kills']), 'next': nxt})
    return sorted(rows, key=lambda r: -r['kills'])


class KillFeed:
    def __init__(self, bot):
        self.bot = bot
        # Without a database (e.g. some tests) the feed simply starts empty and stays in memory.
        self.store = getattr(bot, 'store', None)
        try:
            saved = json.loads((self.store.get(STORE_KEY) if self.store else None) or '{}')
        except ValueError:
            saved = {}
        # Older saves lack weapon and timing detail, so rebuild once from TF21's history.
        self.state = {**blank(), **saved} if saved.get('version') == VERSION else blank()
        # The bounty deck is a permanent record, so it survives any rebuild.
        if isinstance(saved.get('deck'), dict):
            self.state['deck'] = saved['deck']
        backfill_deck(self.state)
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
            # read(n) returns only what has arrived so far, so keep reading to the end
            # (a single read cut long replies off mid-JSON).
            body = bytearray()
            async for chunk in response.content.iter_chunked(65536):
                body.extend(chunk)
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
                now = time.time()
                close_sessions(self.state, now)
                if not self.state['live_since']:
                    self.state['live_since'] = now  # History loaded; announce from here on.
                ensure_bounty(self.state, now)
                await self.post_announcements()
            finally:
                self.save()
            if total:
                log.info('Kill feed: %d new kill(s); %d processed in total', total, self.state['processed'])
            return total


    def channel(self):
        import os
        raw = os.getenv('FIELD_REPORTS_CHANNEL_ID', '').strip()
        ranks = getattr(self.bot, 'progression', None)
        channel_id = int(raw) if raw.isdecimal() else getattr(ranks, 'channel_id', None)
        return self.bot.get_channel(channel_id) if channel_id else None

    async def post_announcements(self):
        queue = self.state['announce']
        if not queue:
            return
        channel = self.channel()
        if channel is None:
            log.warning('Field reports channel not found; set FIELD_REPORTS_CHANNEL_ID')
            return
        from field_reports import message_for
        while queue:
            event = queue[0]
            try:
                await channel.send(**await message_for(self.bot, event))
            except Exception:
                log.exception('Could not post a field report; will retry next update')
                return
            queue.pop(0)


def service(bot):
    if not hasattr(bot, 'kill_feed'):
        bot.kill_feed = KillFeed(bot)
    return bot.kill_feed
