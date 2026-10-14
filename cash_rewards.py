"""Prospective WDUK cumulative cash rewards with a UTC daily cap."""
from datetime import datetime, timezone
import uuid
from rank_divisions import thresholds

def apply_cash(p, value, updated, source, now=None):
    if p.get('rank_rules',1)<2:return 0
    now=now or datetime.now(timezone.utc)
    try:
        stamp=datetime.fromisoformat(updated.replace('Z','+00:00'))
        if not 0<=(now-stamp).total_seconds()<=900:return 0
    except (ValueError,TypeError,AttributeError):return 0
    if type(value) is not int or not 0<=value<=10**12:return 0
    if p.get('season_started') and stamp<=datetime.fromisoformat(p['season_started']):return 0
    old=p.get('cash_reward');epoch=p.get('season_started')
    if not old or old['source']!=source or old.get('epoch')!=epoch:
        p['cash_reward']=dict(source=source,epoch=epoch,high=value,at=updated,remainder=0,day=stamp.date().isoformat(),paid=0)
        return 0
    if stamp<=datetime.fromisoformat(old['at']):return 0
    delta=max(0,value-old['high']);old.update(high=max(value,old['high']),at=updated)
    if not p['active'] or p.get('hold') or p.get('baseline') is None:
        old['remainder']=0;return 0
    day=stamp.date().isoformat()
    if old['day']!=day:old.update(day=day,paid=0)
    whole,remainder=divmod(old['remainder']+delta,10000)
    reward=min(whole,25-old['paid']);old.update(remainder=remainder,paid=old['paid']+reward)
    if not reward:return 0
    from progression import rank_for, COUNTERS
    before,rank=p['points2'],p['rank'];p['points2']+=reward*2
    p['rank']=rank_for(p['points2'],rank,thresholds(p))
    p.setdefault('history',[]).append(dict(at=now.isoformat(),source=updated,kind='Cash earned bonus',before=before,after=p['points2'],**{'from':rank,'to':p['rank']},reason=f'WDUK cash earned: +{reward} rating (daily cap 25).'))
    if p.get('pending'):p['pending'].update(to=p['rank'],after=p['points2'])
    elif rank!=p['rank']:p['pending']=dict(id=uuid.uuid4().hex,**{'from':rank,'to':p['rank']},before=before,after=p['points2'],delta=dict.fromkeys(COUNTERS,0),reason='Cash earned bonus')
    return reward
