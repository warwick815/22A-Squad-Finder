"""Combat rating: a skill score from six parts, blended into ELO as a points multiplier.

Each part is where a member sits among every WarDogs UK player who has played (a
percentile from 0 to 1, with "lower is better" parts flipped). Rates are steadied
towards the server average so a lucky few minutes cannot top the board, and the
whole score is scaled by confidence: hours / (hours + 1).

The rating shown is 1,000 plus up to 2,000 points by weight. In ELO, kills and wins
earn points multiplied by 1 ± SPREAD: an average player is x1.00, the best x1.20 and
the weakest x0.80. Deaths and losses always cost the normal amount. A new player has
low confidence, so their multiplier stays close to x1.00 until there is enough play.
"""
import json
import logging
import time
from bisect import bisect_left, bisect_right

log = logging.getLogger('22a.skill')
STORE_KEY = 'skill_population_v1'
REFRESH = 3600          # rebuild the server-wide comparison at most hourly
MIN_HOURS = 1           # players with less than an hour are left out of the comparison
SPREAD = 0.2            # multiplier range: 1 - SPREAD to 1 + SPREAD
PRIOR_HOURS = 2         # rates are steadied as if two average hours were already played
# key, name, what it measures, weight (%), lower is better
PARTS = (
    ('firepower', 'Firepower', 'Kills per hour played.', 25, False),
    ('survival', 'Survival', 'Kills per death, steadied towards 1.0 for players with few fights.', 25, False),
    ('winning', 'Winning', 'Share of matches won, steadied towards 50%.', 15, False),
    ('earnings', 'Earnings', 'In-game cash earned per hour.', 15, False),
    ('durability', 'Durability', 'Fewest deaths per hour played; lower is better.', 10, True),
    ('discipline', 'Discipline', 'Fewest team kills per 100 kills; lower is better.', 10, True),
)


def _int(v):
    return v if type(v) is int and v >= 0 else None


def _num(v):
    return float(v) if type(v) in (int, float) and v == v and v >= 0 else None


def values(row, avg):
    """The six steadied measures for one stats row (None where the data is missing)."""
    hours = _num(row.get('hoursPlayed'))
    kills, deaths = _int(row.get('kills')), _int(row.get('deaths'))
    if hours is None or kills is None or deaths is None:
        return None
    wins, losses, tk = _int(row.get('wins')), _int(row.get('losses')), _int(row.get('teamKills'))
    cash = _num(row.get('cashEarned'))
    cash_hours = _num(row.get('cashHours'))
    cash_hours = hours if cash_hours is None else cash_hours
    out = {
        'firepower': (kills + avg['kph'] * PRIOR_HOURS) / (hours + PRIOR_HOURS),
        'survival': (kills + 10) / (deaths + 10),
        'winning': (wins + 5) / (wins + losses + 10) if wins is not None and losses is not None else None,
        'earnings': (cash + avg['cph'] * PRIOR_HOURS) / (cash_hours + PRIOR_HOURS) if cash is not None else None,
        'durability': (deaths + avg['dph'] * PRIOR_HOURS) / (hours + PRIOR_HOURS),
        'discipline': 100 * (tk + 0.5) / (kills + 50) if tk is not None else None,
    }
    return out


def build(rows, now=None):
    """Sorted comparison lists for every part, from all players' WarDogs UK rows."""
    rows = [r for r in rows if (_num(r.get('hoursPlayed')) or 0) >= MIN_HOURS
            and _int(r.get('kills')) is not None and _int(r.get('deaths')) is not None]
    if len(rows) < 20:
        raise ValueError('Not enough players to compare against.')
    hours = sum(_num(r['hoursPlayed']) for r in rows) or 1
    cash_rows = [r for r in rows if _num(r.get('cashEarned')) is not None]
    avg = {'kph': sum(r['kills'] for r in rows) / hours, 'dph': sum(r['deaths'] for r in rows) / hours,
           'cph': sum(_num(r['cashEarned']) for r in cash_rows) / (sum(_num(r['hoursPlayed']) for r in cash_rows) or 1)}
    lists = {key: [] for key, *_ in PARTS}
    for r in rows:
        for key, v in (values(r, avg) or {}).items():
            if v is not None:
                lists[key].append(v)
    return {'avg': avg, 'parts': {k: sorted(v) for k, v in lists.items()}, 'players': len(rows),
            'updated': now if now is not None else time.time()}


def percentile(sorted_values, v):
    if not sorted_values:
        return 0.5
    return (bisect_left(sorted_values, v) + bisect_right(sorted_values, v)) / (2 * len(sorted_values))


def member_row(wduk, tf21=None):
    """A member's stats across WarDogs UK and TF21. TF21 reports no hours, so its play
    time is estimated from kills / kills-per-hour; cash per hour stays WarDogs UK only."""
    from tf21_api import combined
    row = combined(wduk or {}, tf21)
    hours = _num((wduk or {}).get('hoursPlayed'))
    row['cashHours'] = hours
    if tf21 and hours is not None:
        kph = _num(tf21.get('killsPerHour'))
        if kph and _int(tf21.get('kills')):
            row['hoursPlayed'] = hours + tf21['kills'] / kph
    return row


def rate(row, population):
    """Combat rating for one member: parts (0-1), rating, confidence, multiplier and top %."""
    avg = population['avg']
    measured = values(row, avg)
    if measured is None:
        return None
    parts, total = {}, 0.0
    for key, _, _, weight, lower in PARTS:
        v = measured.get(key)
        if v is None:
            parts[key] = None
            total += weight * 0.5  # Unknown: treated as average.
            continue
        p = percentile(population['parts'][key], v)
        parts[key] = round(1 - p if lower else p, 4)
        total += weight * parts[key]
    share = total / 100
    hours = _num(row.get('hoursPlayed')) or 0
    confidence = hours / (hours + 1)
    return {'rating': round(1000 + 2000 * share * confidence), 'share': round(share, 4), 'confidence': round(confidence, 4),
            'multiplier': round(1 + SPREAD * (2 * share - 1) * confidence, 3), 'parts': parts,
            'top': max(1, round(100 * (1 - share))), 'compared': population['players'], 'updated': time.time()}


def multiplier(player):
    m = (player.get('skill') or {}).get('multiplier')
    return min(1 + SPREAD, max(1 - SPREAD, m)) if type(m) in (int, float) else 1.0


def points2(delta, weights, m=1.0):
    """ELO change in half-points: gains (kills, wins) are multiplied by skill, costs are not."""
    gain = sum(weights[k] * delta[k] for k in delta if weights.get(k, 0) > 0)
    cost = sum(weights[k] * delta[k] for k in delta if weights.get(k, 0) < 0)
    return round(2 * gain * m) + 2 * cost


class Population:
    """The server-wide comparison, refreshed at most hourly from the public all-time feed."""

    def __init__(self, ranks):
        self.ranks = ranks
        try:
            self.data = json.loads(ranks.bot.store.get(STORE_KEY) or 'null')
        except (ValueError, AttributeError, TypeError):
            self.data = None

    async def get(self, now=None):
        now = time.time() if now is None else now
        if not self.data or now - self.data.get('updated', 0) >= REFRESH:
            try:
                payload = await self.ranks.fetch_public_payload()
                fields = payload['fields']
                rows = [dict(zip(fields, p)) for p in payload['players']]
                self.data = build(rows, now)
                self.ranks.bot.store.set(STORE_KEY, json.dumps(self.data))
                log.info('Combat rating: compared against %d WarDogs UK players', self.data['players'])
            except Exception as exc:
                log.warning('Combat rating comparison not refreshed (%s); keeping the last one', exc)
                if self.data:
                    self.data['updated'] = now - REFRESH + 600  # Retry in ten minutes.
        return self.data


def update_players(state, population, wduk_rows, tf21_rows):
    """Recalculate every linked member's combat rating (used for their next ELO gains)."""
    if not population:
        return
    for steam, player in state['players'].items():
        wduk = wduk_rows.get(steam)
        if not wduk:
            continue
        result = rate(member_row(wduk, tf21_rows.get(steam)), population)
        if result:
            player['skill'] = result
