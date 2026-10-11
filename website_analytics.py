"""Read-only projections of saved ratings; never invent historical snapshots."""
from datetime import datetime, timezone, timedelta


def date(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed if parsed.tzinfo else None
    except (ValueError, TypeError, AttributeError):
        return None


def history(player):
    start = date(player.get('season_started'))
    rows = []
    for event in player.get('history', []):
        at = date(event.get('at'))
        if not at or (start and at < start):
            continue
        parts = []
        if event.get('kind') == 'results':
            for key, amount in event.get('delta', {}).items():
                weight = event.get('weights', {}).get(key)
                if isinstance(weight, (int, float)):
                    parts.append({'label': key, 'amount': amount, 'points': amount * weight})
        elif event.get('kind') == 'Level bonus':
            parts.append({'label': 'Approved level gains', 'amount': None,
                          'points': (event['after']-event['before'])/2})
        rows.append({'at': event['at'], 'kind': event.get('kind', 'Rating update'),
                     'before': event['before']/2, 'rating': event['after']/2,
                     'change': (event['after']-event['before'])/2, 'parts': parts})
    return sorted(rows, key=lambda e: date(e['at']))


def milestones(player, row):
    badges = []
    for label, earned, detail in [
        ('On the roster', True, 'Steam account linked to 22A'),
        ('First stripes', player['rank'] >= 1, 'Reach Lance Corporal this season'),
        ('NCO', player['rank'] >= 2, 'Reach Corporal this season'),
        ('1,000 kills', (row.get('kills') or 0) >= 1000, '1,000 lifetime kills in the source stats'),
        ('50 wins', (row.get('wins') or 0) >= 50, '50 lifetime wins in the source stats'),
        ('100 hours', (row.get('hoursPlayed') or 0) >= 100, '100 lifetime hours in the source stats')]:
        badges.append({'name': label, 'earned': earned, 'detail': detail})
    return badges


def movement(snapshots, players, season, now=None):
    now = now or datetime.now(timezone.utc)
    cutoff = now-timedelta(days=7)
    eligible = [s for s in snapshots if s['season'] == season and date(s['at'])
                and cutoff-timedelta(days=1) <= date(s['at']) <= cutoff]
    if not eligible:
        return {}
    previous = max(eligible, key=lambda s: date(s['at']))['order']
    # Preserve equal ranks, including tied ratings.
    return {p['id']: previous[p['id']]-p['position'] for p in players if p['id'] in previous}
