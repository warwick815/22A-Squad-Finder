"""Prospective daily net realised profit; reward receipts live with ELO state."""
import time
import json
import uuid
from datetime import datetime, timezone


def record_profit(book, uid, amount, now=None):
    now=time.time() if now is None else now
    season=book.data.get('exchange',{}).get('season') or 1
    raw=book.store.get('progression_v1')
    if isinstance(raw,str):
        season=json.loads(raw).get('season',1)
    day=int(now//86400)
    key=f'{season}:{day}:{uid}'
    row=book.data.setdefault('market_profit_days',{}).setdefault(key,dict(season=season,day=day,uid=str(uid),profit=0))
    row['profit']+=amount


def reward_status(book, uid, season, now=None):
    now=time.time() if now is None else now
    day=int(now//86400)
    row=book.data.get('market_profit_days',{}).get(f'{season}:{day}:{uid}',{})
    profit=row.get('profit',0)
    return dict(profit=profit,projected_elo=max(0,profit//1000)*20,settles_at=(day+1)*86400)


def settle_rewards(ranks, book, now=None):
    """Called under progression lock; ELO and receipts persisted together, without await."""
    now=time.time() if now is None else now
    season=ranks.state.get('season',1)
    receipts=ranks.state.setdefault('market_reward_receipts',{})
    changed=False
    for key,row in book.data.get('market_profit_days',{}).items():
        if row['season']!=season or row['day']>=int(now//86400) or key in receipts:continue
        found=ranks.find(int(row['uid']))
        if not found:continue
        _,p=found
        if not p.get('active') or p.get('hold') or p.get('baseline') is None:continue
        reward=max(0,row['profit']//1000)*20
        receipts[key]=dict(profit=row['profit'],elo=reward,at=now)
        changed=True
        if not reward:continue
        from progression import rank_for, COUNTERS
        from rank_divisions import thresholds
        before,rank=p['points2'],p['rank']
        p['points2']+=reward*2
        p['rank']=rank_for(p['points2'],rank,thresholds(p))
        date=datetime.fromtimestamp(row['day']*86400,timezone.utc).date().isoformat()
        p.setdefault('history',[]).append(dict(at=datetime.fromtimestamp(now,timezone.utc).isoformat(),kind='Black Market daily bonus',before=before,after=p['points2'],**{'from':rank,'to':p['rank']},reason=f'{date} UTC: ${row["profit"]:,} net realised profit; +{reward} ELO.'))
        if p.get('pending'):p['pending'].update(to=p['rank'],after=p['points2'])
        elif rank!=p['rank']:p['pending']=dict(id=uuid.uuid4().hex,**{'from':rank,'to':p['rank']},before=before,after=p['points2'],delta=dict.fromkeys(COUNTERS,0),reason='Black Market daily bonus')
    if changed:ranks.save()
