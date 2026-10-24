"""Merits: earned by playing and taking part, spent in the Armoury on timed ELO boosters.

Merits can only be earned, never bought, and reset at the start of each season. Each
member may use one Armoury item per UK day. Boosters multiply the ELO earned from kills
and wins only (like the combat rating); deaths and losses are never made worse.

Earning is worked out from records the bot already keeps (rating history, the TF21 kill
feed, operations and Fantasy rounds), so each award is given once and can be audited.
"""
import time
from datetime import datetime
from zoneinfo import ZoneInfo

UK = ZoneInfo('Europe/London')
DAILY_CAP = 30            # most Merits one member can earn in a UK day
KILLS_PER_MERIT = 25
KILL_MERITS_PER_DAY = 4
LOG_KEEP = 60
EARN = {'first_match': 2, 'hour': 2, 'kills': 1, 'squad': 3, 'bounty': 5, 'operation': 10, 'promotion': 5,
        'fantasy1': 5, 'fantasy2': 3, 'fantasy3': 2}
# id: name, cost, description, booster multiplier, minutes (flak covers deaths instead)
ITEMS = {
    'boost15': dict(name='1.5x ELO booster', cost=15, multiplier=1.5, minutes=60,
                    detail='Kills and wins earn 1.5x ELO for 1 hour.'),
    'boost2': dict(name='2x ELO booster', cost=30, multiplier=2.0, minutes=30,
                   detail='Kills and wins earn 2x ELO for 30 minutes.'),
    'flak': dict(name='Flak jacket', cost=10, deaths=10,
                 detail='Your next 10 deaths cost no ELO (lasts until used or the season ends).'),
    'squad': dict(name='Squad booster', cost=40, multiplier=1.25, minutes=60,
                  detail='Everyone in your TF21 squad session (you included) earns 1.25x ELO for 1 hour.'),
}


def day(ts=None):
    return datetime.fromtimestamp(time.time() if ts is None else ts, UK).date().isoformat()


def book(state):
    """The season's Merits ledger; a new season starts everyone from zero."""
    season = state.get('season', 1)
    m = state.get('merits')
    if not m or m.get('season') != season:
        m = state['merits'] = {'season': season, 'members': {}, 'seen': {}}
    return m


def member(state, uid):
    return book(state)['members'].setdefault(str(uid), {'balance': 0, 'earned': 0, 'log': [], 'days': {}, 'used': {}})


def _today(entry, ts):
    d = day(ts)
    entry['days'] = {k: v for k, v in entry['days'].items() if k >= day(ts - 7 * 86400)}
    return entry['days'].setdefault(d, {'earned': 0, 'kills': 0, 'kill_merits': 0, 'played': False})


def credit(state, uid, amount, reason, ts=None):
    """Give Merits, respecting the daily cap. Returns how many were actually given."""
    ts = time.time() if ts is None else ts
    entry = member(state, uid)
    today = _today(entry, ts)
    amount = max(0, min(amount, DAILY_CAP - today['earned']))
    if not amount:
        return 0
    today['earned'] += amount
    entry['balance'] += amount
    entry['earned'] += amount
    entry['log'].append({'at': ts, 'amount': amount, 'reason': reason})
    del entry['log'][:-LOG_KEEP]
    return amount


def _once(state, key):
    seen = book(state)['seen']
    if key in seen:
        return False
    seen[key] = True
    if len(seen) > 5000:
        for old in list(seen)[:1000]:
            del seen[old]
    return True


# --- Earning -----------------------------------------------------------------

def _ts(iso):
    try:
        return datetime.fromisoformat(str(iso).replace('Z', '+00:00')).timestamp()
    except (TypeError, ValueError):
        return None


def from_history(state, steam, player):
    """First match of the day, kills and promotions, from the member's rating history."""
    uid = str(player['discord_id'])
    entry = member(state, uid)
    last = entry.get('history_at')
    newest = last
    for e in player.get('history', []):
        at = _ts(e.get('at'))
        if at is None or (last is not None and at <= last):
            continue
        newest = max(newest or at, at)
        if last is None:
            continue  # First run this season: start from now, no back-pay.
        if e.get('kind') == 'results':
            d = e.get('delta') or {}
            today = _today(entry, at)
            if (d.get('wins', 0) + d.get('losses', 0)) > 0 and not today['played']:
                today['played'] = True
                credit(state, uid, EARN['first_match'], 'First match of the day', at)
            today['kills'] += d.get('kills', 0)
            due = min(KILL_MERITS_PER_DAY, today['kills'] // KILLS_PER_MERIT) - today['kill_merits']
            if due > 0:
                today['kill_merits'] += due
                credit(state, uid, due * EARN['kills'], f'{due * KILLS_PER_MERIT} kills', at)
        if isinstance(e.get('to'), int) and isinstance(e.get('from'), int) and e['to'] > e['from']:
            credit(state, uid, EARN['promotion'], 'Promotion', at)
    entry['history_at'] = newest if newest is not None else time.time()


def from_feed(state, feed):
    """Squad sessions and collected bounties from the TF21 kill feed."""
    by_steam = {s: str(p['discord_id']) for s, p in state['players'].items()}
    start = book(state).setdefault('feed_from', time.time())  # Nothing before Merits began.
    for s in feed.get('sessions', []):
        if s.get('end', 0) < start or not _once(state, f"session:{s.get('server')}:{s.get('start')}"):
            continue
        for m in s.get('members', []):
            if m.get('steam') in by_steam:
                credit(state, by_steam[m['steam']], EARN['squad'], f"Squad session on {str(s.get('server')).upper()}", s['end'])
    bounties = list(feed.get('bounties', [])) + ([feed['bounty']] if feed.get('bounty') else [])
    for b in bounties:
        at = _ts(b.get('claimed_at')) or b.get('set_at') or 0
        if not b.get('claimed') or at < start or b['claimed'] not in by_steam:
            continue
        if _once(state, f"bounty:{b.get('hour') or b.get('week')}:{b.get('target')}"):
            credit(state, by_steam[b['claimed']], EARN['bounty'], f"Bounty on {b.get('name')}", at)


def from_operations(state):
    start = book(state).setdefault('ops_from', time.time())
    for op in state.get('community_hq', {}).get('operations', {}).values():
        if op.get('status') != 'completed' or op.get('completed', 0) < start or not _once(state, f"op:{op['id']}"):
            continue
        for uid, m in op.get('members', {}).items():
            if m.get('total', 0) > 0:
                credit(state, uid, EARN['operation'], f"Operation {op.get('title')} complete", op['completed'])


def from_fantasy(state):
    start = book(state).setdefault('fantasy_from', time.time())
    season = state.get('season', 1)
    for r in state.get('fantasy', {}).get('rounds', {}).values():
        if r.get('season') != season or r.get('status') != 'completed' or r.get('end', 0) < start:
            continue
        if not _once(state, f"fantasy:{r['id']}"):
            continue
        results = sorted(((v, uid) for uid, v in (r.get('results') or {}).items() if isinstance(v, (int, float))), reverse=True)
        scores = sorted({v for v, _ in results}, reverse=True)[:3]
        for v, uid in results:
            if v > 0 and v in scores:
                place = scores.index(v) + 1  # Equal scores share a place.
                credit(state, uid, EARN[f'fantasy{place}'], f'Fantasy round: {("1st", "2nd", "3rd")[place - 1]}', r['end'])


def from_hours(state, rows):
    """+2 Merits for every hour played, from WarDogs UK's hours-played counter. Part-hours
    carry over to the next check; the first reading (or an odd jump) only sets the baseline."""
    now = time.time()
    for steam, player in state['players'].items():
        hours = (rows.get(steam) or {}).get('hoursPlayed')
        if type(hours) not in (int, float) or hours != hours or hours < 0:
            continue
        entry = member(state, player['discord_id'])
        seen = entry.get('hours_seen')
        entry['hours_seen'] = hours
        if seen is None or hours < seen or hours - seen > 24:
            entry['hours_part'] = 0.0  # Start (or restart) counting from here, with no back-pay.
            continue
        entry['hours_part'] = entry.get('hours_part', 0.0) + (hours - seen)
        whole = int(entry['hours_part'] + 1e-9)
        if whole:
            entry['hours_part'] -= whole
            credit(state, player['discord_id'], whole * EARN['hour'], f"{whole} hour{'s' if whole > 1 else ''} played", now)


def update(state, feed=None, rows=None):
    """Award everything new since the last check. Called after each ELO update."""
    book(state)
    for steam, player in state['players'].items():
        from_history(state, steam, player)
    if rows:
        from_hours(state, rows)
    if feed:
        from_feed(state, feed)
    from_operations(state)
    from_fantasy(state)


# --- Spending ----------------------------------------------------------------

def squad_mates(feed, steam, now):
    """Linked members sharing a live TF21 squad session with this member."""
    for o in (feed or {}).get('open', {}).values():
        if steam in o.get('members', {}) and now - o.get('last', 0) <= 3600:
            return set(o['members'])
    return set()


def buy(state, uid, item_id, feed=None, now=None):
    """Spend Merits on an Armoury item (one a day). Returns a message for the member."""
    now = time.time() if now is None else now
    item = ITEMS.get(item_id)
    if not item:
        raise ValueError('Choose an item from the Armoury.')
    found = next(((s, p) for s, p in state['players'].items() if str(p['discord_id']) == str(uid)), None)
    if not found:
        raise ValueError('Link your Steam account first.')
    steam, player = found
    if not player.get('active') or player.get('hold'):
        raise ValueError('Your progression is paused or under review, so boosters cannot be used right now.')
    entry = member(state, uid)
    today = day(now)
    if today in entry['used']:
        raise ValueError(f"You have already used today's Armoury item ({ITEMS[entry['used'][today]]['name']}). Come back tomorrow.")
    if entry['balance'] < item['cost']:
        raise ValueError(f"You need {item['cost']} Merits for the {item['name']}; you have {entry['balance']}.")
    if item_id in ('boost15', 'boost2', 'squad') and (player.get('booster') or {}).get('until', 0) > now:
        raise ValueError('A booster is already running for you. Wait for it to finish.')
    targets = [player]
    if item_id == 'squad':
        mates = squad_mates(feed, steam, now)
        if not mates:
            raise ValueError('The squad booster needs a live TF21 squad session (3+ members getting kills on one server).')
        targets = [state['players'][s] for s in mates if s in state['players']]
    entry['balance'] -= item['cost']
    entry['used'] = {k: v for k, v in entry['used'].items() if k >= day(now - 7 * 86400)}
    entry['used'][today] = item_id
    entry['log'].append({'at': now, 'amount': -item['cost'], 'reason': item['name']})
    del entry['log'][:-LOG_KEEP]
    if item_id == 'flak':
        player['flak'] = player.get('flak', 0) + item['deaths']
        return f"Flak jacket on: your next {player['flak']} deaths cost no ELO."
    until = now + item['minutes'] * 60
    boosted = 0
    for p in targets:
        current = p.get('booster') or {}
        if current.get('until', 0) > now and current.get('multiplier', 1) >= item['multiplier'] and p is not player:
            continue  # A mate's own stronger booster is never replaced.
        p['booster'] = {'item': item_id, 'multiplier': item['multiplier'], 'from': now, 'until': until, 'by': str(uid)}
        boosted += 1
    if item_id == 'squad':
        return f"Squad booster on: {boosted} members earn 1.25x ELO for the next hour."
    return f"{item['name']} on until {datetime.fromtimestamp(until, UK):%H:%M} UK time."


def boost(player, delta, at):
    """(multiplier for gains, deaths that still cost ELO) for a result at timestamp `at`.
    Uses up flak jacket cover as deaths are absorbed."""
    b = player.get('booster') or {}
    m = b['multiplier'] if b.get('from', 0) <= at < b.get('until', 0) else 1.0
    deaths = delta.get('deaths', 0)
    cover = min(player.get('flak', 0), deaths)
    if cover:
        player['flak'] -= cover
        if not player['flak']:
            player.pop('flak')
    return m, deaths - cover


def view(state, uid, feed=None, now=None):
    """Everything the Armoury page shows for one member."""
    now = time.time() if now is None else now
    entry = member(state, uid)
    found = next(((s, p) for s, p in state['players'].items() if str(p['discord_id']) == str(uid)), None)
    player = found[1] if found else {}
    b = player.get('booster') or {}
    today = entry['days'].get(day(now), {})
    return {'season': book(state)['season'], 'balance': entry['balance'], 'earned': entry['earned'],
            'earned_today': today.get('earned', 0), 'daily_cap': DAILY_CAP,
            'used_today': ITEMS[entry['used'][day(now)]]['name'] if day(now) in entry['used'] else None,
            'booster': {'name': ITEMS[b['item']]['name'], 'multiplier': b['multiplier'], 'until': b['until']} if b.get('until', 0) > now else None,
            'flak': player.get('flak', 0), 'in_squad': bool(found and squad_mates(feed, found[0], now)),
            'items': [dict(id=k, **{x: v[x] for x in ('name', 'cost', 'detail')}) for k, v in ITEMS.items()],
            'earn': [('Every hour played (WarDogs UK)', EARN['hour']), ('First match of the day', EARN['first_match']), (f'Every {KILLS_PER_MERIT} kills (up to {KILL_MERITS_PER_DAY} a day)', EARN['kills']),
                     ('Taking part in a squad session', EARN['squad']), ('Collecting a bounty', EARN['bounty']),
                     ('An operation you took part in completing', EARN['operation']), ('Promotion', EARN['promotion']),
                     ('Fantasy round 1st / 2nd / 3rd', '5 / 3 / 2')],
            'log': list(reversed(entry['log']))[:20], 'linked': bool(found)}
