"""Verified community operations, earned-only patch lockers and member research."""
import math,time,uuid
from datetime import datetime

PATCHES=[dict(id=k,name=n,metric=m,target=t,description=d) for k,n,m,t,d in [
 ('shock','Shock Troop','kills',1000,'Earn 1,000 new kills together.'),
 ('brew','Brew Crew','hoursPlayed',100,'Put in 100 hours together.'),
 ('watch','Night Watch','kills',2000,'Earn 2,000 new kills together; no time-of-day restriction.'),
 ('logistics','Keep It Moving','cashEarned',10000000,'Earn $10 million of new in-game cash together.'),
 ('together','Together','wins',100,'Record 100 player wins together; multiple players in a match each contribute.'),
 ('laststand','Last Stand','wins',200,'Record 200 player wins together.'),
 ('thinred','Thin Red Line','kills',500,'Earn 500 new kills together. A good first operation.'),
 ('tinhat','Tin Hat','wins',50,'Record 50 player wins together.'),
 ('stagon','Stag On','hoursPlayed',250,'Put in 250 hours together.'),
 ('quartermaster','Quartermaster','cashEarned',25000000,'Earn $25 million of new in-game cash together.'),
 ('hammerdown','Hammer Down','kills',5000,'Earn 5,000 new kills together. Hard.'),
 ('lionheart','Lionheart','wins',500,'Record 500 player wins together. Elite.')]]

def state(ranks):return ranks.setdefault('community_hq',dict(operations={},lockers={},finales={}))
def locker(ranks,uid):return state(ranks)['lockers'].setdefault(str(uid),dict(earned={},display=[]))
def select_patches(ranks,uid,ids):
    box=locker(ranks,uid)
    if not isinstance(ids,list) or len(ids)>3 or any(not isinstance(i,str) for i in ids) or len(set(ids))!=len(ids) or any(i not in box['earned'] for i in ids):raise ValueError('Choose up to three distinct patches earned through operations.')
    box['display']=ids.copy()
def create_operation(ranks,patch,actor,now=None):
    now=time.time() if now is None else now
    template=next((p for p in PATCHES if p['id']==patch),None)
    if not template:raise ValueError('Choose a valid operation patch.')
    ops=state(ranks)['operations']
    season=ranks.get('season',1)
    # Each patch runs once per season. When it ends, only the members who took part
    # keep the chance to earn it; nobody else can until next season.
    if any(o['patch']==patch and o.get('season',season)==season and o['status']!='cancelled' for o in ops.values()):
        raise ValueError(f"{template['name']} has already run this season. It can run again next season.")
    oid=uuid.uuid4().hex[:12]
    ops[oid]=dict(id=oid,patch=patch,title=template['name'],metric=template['metric'],target=template['target'],start=now,end=now+7*86400,status='active',members={},actor=str(actor),season=ranks.get('season',1))
    return ops[oid]
def join_operation(ranks,oid,uid,now=None):
    now=time.time() if now is None else now
    op=state(ranks)['operations'].get(oid)
    if not op or op['status']!='active' or not op['start']<=now<op['end']:raise ValueError('This operation is not accepting members.')
    op['members'].setdefault(str(uid),dict(joined=now,total=0,baseline=None))
def expire(ranks,now):
    for op in state(ranks)['operations'].values():
        if op['status']=='active' and now>=op['end']:op['status']='expired'
def observe(ranks,rows,times,sources,now=None):
    now=time.time() if now is None else now
    h=state(ranks)
    for op in h['operations'].values():
        if op['status']!='active':continue
        for steam,p in ranks['players'].items():
            uid=str(p['discord_id']);member=op['members'].get(uid)
            if not member or not p.get('active') or p.get('hold') or steam not in rows:continue
            try:
                date=datetime.fromisoformat(times[steam].replace('Z','+00:00'))
                if date.tzinfo is None:continue
                stamp=date.timestamp();value=rows[steam][op['metric']];source=sources[steam]
                if type(value) not in (int,float) or not math.isfinite(value) or value<0 or not 0<=now-stamp<=900 or not max(op['start'],member['joined'])<=stamp<=op['end']:continue
                if op['metric']!='hoursPlayed' and type(value) is not int:continue
            except (KeyError,ValueError,TypeError,AttributeError):continue
            old=member['baseline']
            if old and stamp<=old['at']:continue
            member['baseline']=dict(at=stamp,value=value,source=source,steam=steam)
            if not old or old['source']!=source or old['steam']!=steam or value<old['value'] or stamp-old['at']>900:continue
            delta=value-old['value'];hours=(stamp-old['at'])/3600
            cap={'kills':10000*max(hours,1),'wins':100*max(hours,1),'hoursPlayed':hours+.1,'cashEarned':100000000*max(hours,1)}[op['metric']]
            if delta<=cap:member['total']+=delta
        if sum(m['total'] for m in op['members'].values())>=op['target']:
            op.update(status='completed',completed=now)
            for uid,m in op['members'].items():
                if m['total']>0:locker(ranks,uid)['earned'].setdefault(op['patch'],dict(operation=op['id'],at=now))
    expire(ranks,now)
def confidence(bot,uid,now=None):
    now=time.time() if now is None else now;found=bot.progression.find(int(uid))
    if not found:return dict(status='Unlinked',detail='Link Steam to receive verified statistics.',updated=None)
    steam,p=found;stamp=p.get('season_stats',{}).get('updated') or p.get('updated')
    try:updated=datetime.fromisoformat(stamp.replace('Z','+00:00')).timestamp()
    except (ValueError,TypeError,AttributeError):updated=None
    if p.get('hold') or not p.get('active'):return dict(status='Under review',detail='Progression is paused or under review.',updated=updated)
    # Standings confidence is about the player's game data only. Fantasy tracking
    # notes (late start, restarts) belong on the Fantasy page, not the ELO board.
    if updated is None:return dict(status='Awaiting data',detail='No usable player snapshot is recorded.',updated=None)
    if not 0<=now-updated<=1800:return dict(status='Delayed',detail='Player snapshot is older than 30 minutes or has an invalid time.',updated=updated)
    return dict(status='Verified',detail='Recent player snapshot available.',updated=updated)
def scouting(ranks,uid):
    rounds=sorted((r for r in ranks.get('fantasy',{}).get('rounds',{}).values() if r['season']==ranks.get('season',1) and r['status']=='completed' and uid in r.get('scores',{})),key=lambda r:r['start'])[-7:]
    samples=[]
    for r in rounds:
        a=r['start_stats'].get(uid);b=r['end_stats'].get(uid)
        tk=max(0,b['values']['teamKills']-a['values']['teamKills']) if a and b else None
        samples.append(dict(at=r['start'],points=r['scores'][uid],team_kills=tk))
    n=len(samples)
    return dict(rounds=n,history=samples,average=sum(s['points'] for s in samples)/n if n>=3 else None,consistency=100*sum(s['points']>0 for s in samples)/n if n>=3 else None,tk_penalty=sum(s['team_kills']*20 for s in samples) if n>=3 and all(s['team_kills'] is not None for s in samples) else None)
