"""Scores TF21 server play into the same ELO, on a baseline kept separate from WarDogs UK.

Each player has player['tf21'] = {baseline, updated, note}. The first TF21 reading only
sets the baseline, so earlier TF21 play never earns points. Bad readings (counters going
down, or impossible jumps) re-baseline the TF21 side without points and never put the
whole player on hold, so a TF21 problem cannot block WarDogs UK scoring.
"""
import logging
import uuid
from datetime import datetime, timezone

from leaderboard import timestamp
from progression import COUNTERS, SCORING, rank_for
from rank_divisions import thresholds

LABEL = 'TF21'
log = logging.getLogger('22a.tf21')


def _rebaseline(player, counters, updated, note):
    player['tf21'] = {'baseline': counters, 'updated': updated, 'note': note}
    log.warning('TF21 for member %s: %s', player.get('discord_id'), note)
    return 0


def advance_tf21(player, counters, updated, now=None):
    """Apply one TF21 reading. Returns the points (half-points x2) awarded, 0 if none."""
    now = now or datetime.now(timezone.utc)
    counters = {k: counters[k] for k in COUNTERS}
    track = player.get('tf21')
    if player.get('season_started') and timestamp(updated) <= timestamp(player['season_started']):
        return 0
    if not player.get('active') or player.get('hold') or player.get('pending'):
        return 0  # Paused, under review, or a rank change still to deliver: wait.
    if not track:
        player['tf21'] = {'baseline': counters, 'updated': updated, 'note': 'Baseline set; earlier TF21 play not scored.'}
        log.info('TF21 baseline set for member %s (%d kills); TF21 results score from now on', player.get('discord_id'), counters['kills'])
        return 0
    if timestamp(updated) <= timestamp(track['updated']):
        return 0
    delta = {k: counters[k] - track['baseline'][k] for k in COUNTERS}
    hours = max(1, (timestamp(updated) - timestamp(track['updated'])).total_seconds() / 3600)
    if any(v < 0 for v in delta.values()):
        return _rebaseline(player, counters, updated, 'TF21 totals went down; restarted from the new totals without points.')
    if delta['wins'] + delta['losses'] > 60 * hours or delta['kills'] + delta['deaths'] > 10000 * hours:
        return _rebaseline(player, counters, updated, 'Unusually large TF21 jump; restarted from the new totals without points.')
    track.update(baseline=counters, updated=updated, note=None)
    if not any(delta.values()):
        return 0
    before, old_rank = player['points2'], player['rank']
    player['points2'] = max(0, before + 2 * sum(SCORING[k] * delta[k] for k in COUNTERS))
    player['rank'] = rank_for(player['points2'], old_rank, thresholds(player))
    player.setdefault('history', []).append({'at': now.isoformat(), 'source': updated, 'kind': 'results',
        'origin': LABEL, 'before': before, 'after': player['points2'], 'from': old_rank, 'to': player['rank'],
        'delta': delta, 'weights': SCORING.copy(), 'reason': 'Results on TF21 community servers.'})
    log.info('TF21 scored for member %s: %+.1f ELO (%d kills, %d deaths, %d wins, %d losses)', player.get('discord_id'),
             (player['points2'] - before) / 2, delta['kills'], delta['deaths'], delta['wins'], delta['losses'])
    if player['rank'] != old_rank:
        player['pending'] = {'id': uuid.uuid4().hex, 'from': old_rank, 'to': player['rank'],
                             'before': before, 'after': player['points2'], 'delta': delta}
    return player['points2'] - before
