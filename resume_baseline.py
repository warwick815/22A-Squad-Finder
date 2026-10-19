"""Validate a non-destructive staff resume without accepting incompatible counters."""
from datetime import datetime, timezone
from progression import COUNTERS

def validate_preserved_resume(player, row, updated, source):
    base=player.get('baseline')
    if not base or source!=player.get('rating_source'):
        raise ValueError('Existing baseline and matching source required. Use fresh-baseline resume after a source reset.')
    try:
        stamp=datetime.fromisoformat(updated.replace('Z','+00:00'))
        old=datetime.fromisoformat(player['updated'].replace('Z','+00:00'))
        age=(datetime.now(timezone.utc)-stamp).total_seconds()
        if not 0<=age<=900 or stamp<=old:raise ValueError()
        if any(type(row[k]) is not int or row[k]<base[k] for k in COUNTERS):raise ValueError()
        hours=max(1,(stamp-old).total_seconds()/3600)
        if sum(row[k]-base[k] for k in ('kills','deaths'))>10000*hours or sum(row[k]-base[k] for k in ('wins','losses'))>60*hours:raise ValueError()
    except (KeyError,TypeError,ValueError):
        raise ValueError('Fresh, later, consistent counters at or above the saved baseline are required. Existing baseline and review status were preserved.') from None
