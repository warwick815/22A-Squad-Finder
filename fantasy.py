"""Daily fantasy squads. State and ELO receipts persist together in progression_v1."""
import copy
import math
import time
import uuid
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

DAY=86400
# Three picks while the community is small; the budget keeps the same 130-credit average per pick.
SQUAD_SIZE=3
BUDGET=390
BOOSTERS=('captain','team','reinforcements')
WEIGHTS={'kills':5,'deaths':-3,'teamKills':-20,'wins':20,'losses':-10}


def state(ranks):
    return ranks.setdefault('fantasy',{'rounds':{},'awards':{},'champions':{}})


def migrate(book):
    if book.data.get('fantasy_exchange_refunded'):return
    ex=book.data.get('exchange',{})
    for uid,positions in ex.get('holdings',{}).items():
        cost=sum(p['cost'] for p in positions.values())
        if cost:
            book.data['wallets'].setdefault(str(uid),10000);book.data['wallets'][str(uid)]+=cost
            ex.setdefault('history',[]).append(dict(uid=uid,side='fantasy migration refund',quantity=sum(p['quantity'] for p in positions.values()),total=cost,name='Exchange replaced by Fantasy Squad',at=time.time()))
    ex['holdings']={};ex['revision']=ex.get('revision',0)+1
    book.data['exchange']=ex
    book.data['fantasy_exchange_refunded']=True
    book.save()


def next_lock(now):
    local=datetime.fromtimestamp(now,ZoneInfo('Europe/London'))
    lock=local.replace(hour=18,minute=0,second=0,microsecond=0)
    if lock.timestamp()<=now:lock+=timedelta(days=1)
    return int(lock.timestamp())


def selection_prices(ranks,catalog,start):
    prior=[rd for rd in state(ranks)['rounds'].values() if rd['season']==ranks.get('season',1) and rd['start']<start and rd['status']!='cancelled']
    previous=max(prior,key=lambda rd:rd['start']) if prior else None
    average=sum(p['price'] for p in catalog)/len(catalog)
    players={}
    for item in catalog:
        old=previous['players'].get(item['id']) if previous else None
        base=old['cost']*item['price']/old['price'] if old and old.get('price',0)>0 else item['price']/average*100
        cost=max(30,min(200,round(base)))
        players[item['id']]=dict(item,cost=cost,previous_cost=old['cost'] if old else None,cost_change=cost-old['cost'] if old else None)
    return players


def ensure_round(ranks, catalog, now=None):
    now=time.time() if now is None else now
    f=state(ranks);season=ranks.get('season',1)
    # Never move a running round or overlap its already-promised scoring window.
    running=[r['end'] for r in f['rounds'].values() if r['season']==season and r['start']<=now<r['end'] and r['status'] not in ('void','cancelled','completed')]
    day=next_lock(max([now,*[end-1 for end in running]]))
    key=f'{season}:{day}'
    legacy=[r for r in f['rounds'].values() if r['season']==season and r['status']=='selection' and r['start']>now and r.get('schedule')!='uk18']
    if key not in f['rounds'] and (len(catalog)>=SQUAD_SIZE or legacy):
        if legacy:players=copy.deepcopy(max(legacy,key=lambda r:r['start'])['players'])
        else:
            players=selection_prices(ranks,catalog,day)
        f['rounds'][key]=dict(id=key,season=season,start=day,end=next_lock(day),status='selection',schedule='uk18',squad_size=SQUAD_SIZE,budget=BUDGET,players=players,entries={},start_stats={},end_stats={},last_stats={},invalid=[])
    target=f['rounds'].get(key)
    if target:
        for old in legacy:
            if old is target:continue
            for uid,entry in old['entries'].items():
                if entry.get('saved',0)>=target['entries'].get(uid,{}).get('saved',-1):target['entries'][uid]=copy.deepcopy(entry)
            old['status']='cancelled';old['reason']='Selection moved to 18:00 UK time; saved squad transferred.'
        # Keep existing prices, identities and saved squads frozen, but allow
        # eligible members omitted at creation to join the open catalogue.
        if target['status']=='selection' and now<target['start'] and catalog:
            for uid,item in selection_prices(ranks,catalog,day).items():
                target['players'].setdefault(uid,item)
        target['schedule']='uk18'
        if target.get('squad_size',3)!=SQUAD_SIZE or target.get('budget')!=BUDGET or any(len(e['players'])!=SQUAD_SIZE+(1 if e['booster']=='reinforcements' else 0) for e in target['entries'].values()):
            target.setdefault('drafts',{}).update(copy.deepcopy(target['entries']));target['entries']={}
            target['squad_size']=SQUAD_SIZE;target['budget']=BUDGET
            average=sum(p['price'] for p in catalog)/len(catalog) if catalog else 100
            for p in catalog:target['players'].setdefault(p['id'],dict(p,cost=max(30,min(200,round(p['price']/average*100)))))
    return target


def used_boosters(ranks,uid,season,now=None):
    now=time.time() if now is None else now
    return {r['entries'][uid]['booster'] for r in state(ranks)['rounds'].values() if r['season']==season and r['start']<=now and r['status'] not in ('void','cancelled') and uid in r['entries'] and r['entries'][uid]['booster']}


def submit(ranks,uid,body,now=None):
    now=time.time() if now is None else now
    if not isinstance(body,dict) or set(body)!={'round','players','captain','booster'}:raise ValueError('Review all squad selections before saving.')
    r=state(ranks)['rounds'].get(body['round']) if isinstance(body['round'],str) else None
    if not r or r['season']!=ranks.get('season',1) or now>=r['start'] or r['status']!='selection':raise ValueError('Selection has closed. Choose the next available round.')
    ids=body['players'];boost=body['booster'];captain=body['captain']
    if not isinstance(boost,str) or boost not in ('',*BOOSTERS):raise ValueError('Choose a valid booster.')
    if not isinstance(ids,list) or any(not isinstance(i,str) for i in ids) or len(ids)!=(r.get('squad_size',3)+(1 if boost=='reinforcements' else 0)) or len(set(ids))!=len(ids):raise ValueError(f'Select {SQUAD_SIZE} distinct players, or {SQUAD_SIZE+1} with Reinforcements.')
    if any(i not in r['players'] for i in ids) or captain not in ids:raise ValueError('Choose an eligible squad and captain.')
    if sum(r['players'][i]['cost'] for i in ids)>r.get('budget',400):raise ValueError('Squad exceeds the selection budget.')
    if boost and boost in used_boosters(ranks,uid,r['season'],now):raise ValueError('That booster has already been used this season.')
    r['entries'][uid]=dict(players=ids,captain=captain,booster=boost,saved=now)
    r.get('drafts',{}).pop(uid,None)


def score_entry(entry,scores):
    total=0
    for uid in entry['players']:
        multiplier=2 if uid==entry['captain'] and entry['booster']=='captain' else 1.5 if uid==entry['captain'] else 1
        if entry['booster']=='team':multiplier*=1.5
        total+=scores[uid]*multiplier
    return total


def totals(ranks,season):
    result={}
    for r in state(ranks)['rounds'].values():
        if r['season']!=season or r['status']!='completed':continue
        for uid,score in r['results'].items():result[uid]=result.get(uid,0)+score
    return result


def award(ranks,key,results,pool):
    f=state(ranks)
    if key in f['awards']:return
    best=max(results.values(),default=0)
    winners=sorted(uid for uid,score in results.items() if score==best) if best>0 else []
    points2=(pool*2)//len(winners) if winners else 0
    f['awards'][key]=dict(winners=winners,points2=points2,paid=[],season=ranks.get('season',1))


def apply_awards(ranks,now=None,closing=False):
    from progression import rank_for,COUNTERS
    from rank_divisions import thresholds
    now=time.time() if now is None else now
    members={str(p['discord_id']):p for p in ranks['players'].values()}
    for key,a in state(ranks)['awards'].items():
        if a['season']!=ranks.get('season',1):continue
        for uid in a['winners']:
            if uid in a['paid'] or uid not in members:continue
            p=members[uid]
            if not closing and (not p.get('active') or p.get('hold') or p.get('baseline') is None):continue
            before,rank=p['points2'],p['rank'];p['points2']+=a['points2'];p['rank']=rank_for(p['points2'],rank,thresholds(p))
            p.setdefault('history',[]).append(dict(at=datetime.fromtimestamp(now,timezone.utc).isoformat(),kind='Fantasy Squad bonus',before=before,after=p['points2'],**{'from':rank,'to':p['rank']},reason=f'{key}: shared winner reward.'))
            if p.get('pending'):p['pending'].update(to=p['rank'],after=p['points2'])
            elif rank!=p['rank'] and not closing:p['pending']=dict(id=uuid.uuid4().hex,**{'from':rank,'to':p['rank']},before=before,after=p['points2'],delta=dict.fromkeys(COUNTERS,0),reason='Fantasy Squad winner')
            a['paid'].append(uid)


# --- Live stat tracking -------------------------------------------------
# Each picked player gets a tracker: the snapshot their round started from,
# the latest snapshot, and (once the round ends) the final one. If the feed
# changes source, a counter goes backwards, or a jump looks impossible, the
# points so far are banked and tracking restarts from the new snapshot, so one
# bad reading never voids everyone's round. Missing data scores 0 for that
# player only, and the round always settles one hour after it ends.
# Snapshot times come from the stats feed itself, not from when the bot polled.
FRESH=3600          # accept feed snapshots up to an hour old
PRE_START=1800      # a snapshot up to 30 min before lock can be the baseline
ON_TIME=900         # first snapshot within 15 min of lock counts as on time
FINAL_GRACE=900     # first snapshot within 15 min after the end is the final
SETTLE_AFTER=3600   # settle with the best data available an hour after the end


def points(a,b):
    return sum((b['values'][k]-a['values'][k])*w for k,w in WEIGHTS.items())


def _consistent(prev,snap):
    if prev['source']!=snap['source']:return 'Stats feed changed'
    if any(snap['values'][k]<prev['values'][k] for k in WEIGHTS):return 'Source counters decreased'
    hours=max(1,(snap['at']-prev['at'])/3600)
    if sum(snap['values'][k]-prev['values'][k] for k in ('kills','deaths'))>10000*hours:return 'Implausible counter increase'
    return None


def tracks(r):
    """Per-player trackers, upgrading rounds that were live under the old rules."""
    if 'track' in r:return r['track']
    track={}
    for uid in {i for e in r['entries'].values() for i in e['players']}:
        recovery=r.get('live_recovery',{}).get(uid)
        if uid in r.get('invalid',[]) or uid not in r.get('start_stats',{}):
            if recovery:track[uid]=dict(banked=0,start=recovery['start'],last=recovery['last'],final=None,late=True,notes=[r.get('invalid_reasons',{}).get(uid,'Tracking restarted')])
            continue
        track[uid]=dict(banked=0,start=r['start_stats'][uid],last=r.get('last_stats',{}).get(uid) or r['start_stats'][uid],final=r.get('end_stats',{}).get(uid),late=False,notes=[])
    r['track']=track;r.setdefault('pre',{})
    return track


def player_score(r,uid):
    t=tracks(r).get(uid)
    if not t or not t.get('start') or uid in r.get('blocked',{}):return None
    return t['banked']+points(t['start'],t['final'] or t['last'])


def player_status(r,uid,now=None):
    """Display details for one picked player: score, freshness and a plain-English status."""
    now=time.time() if now is None else now
    if r['status'] in ('void','cancelled'):return dict(base=None,updated=None,status='Round '+r['status']+(' · '+r['reason'] if r.get('reason') else ''),partial=True,tracked_from=None)
    t=tracks(r).get(uid);done=r['status']=='completed'
    base=r['scores'].get(uid) if done and 'scores' in r else player_score(r,uid)
    if base is not None and not done:base+=r.get('staff_offsets',{}).get(uid,0)
    snap=(t.get('final') or t.get('last')) if t else None
    updated=snap['at'] if snap else None
    if uid in r.get('blocked',{}):status=r['blocked'][uid]+' · not scored'
    elif not t or not t.get('start'):status='No stats received · scored 0' if done else 'Waiting for the first stats snapshot'
    else:
        status='Final score' if done else 'Live score'
        if t.get('late'):status+=' · tracking started late, earlier play not counted'
        if len(t.get('notes',[]))>0:status+=' · '+t['notes'][-1].lower()+', scores combined'
        if not done and updated and now-updated>1800:status+=' · stats feed delayed'
    return dict(base=base,updated=updated,status=status,partial=bool(t and (t.get('late') or t.get('notes'))) or base is None,
                tracked_from=t['start']['at'] if t and t.get('start') and t.get('late') else None)


def tick(ranks,now=None):
    now=time.time() if now is None else now
    for r in state(ranks)['rounds'].values():
        if r['season']!=ranks.get('season',1) or r['status'] in ('completed','void','cancelled'):continue
        if now<r['start']:continue
        r['status']='live' if now<r['end'] else 'awaiting data'
        if now<r['end']:continue
        needed={i for e in r['entries'].values() for i in e['players']}
        if not needed:r['status']='void';r['reason']='No squads entered';continue
        track=tracks(r)
        finished=all(uid in r.get('blocked',{}) or (track.get(uid) or {}).get('final') for uid in needed)
        if not finished and now<r['end']+SETTLE_AFTER:continue
        raw={uid:player_score(r,uid) for uid in needed}
        if all(v is None for v in raw.values()):
            r['status']='void';r['reason']='No stats were received for any picked player; boosters released';continue
        scores={uid:(v or 0)+r.get('staff_offsets',{}).get(uid,0) for uid,v in raw.items()}
        for uid in needed:
            t=track.get(uid)
            if t and t.get('start'):r['start_stats'][uid]=t['start'];r['end_stats'][uid]=t['final'] or t['last']
        r['missing']=sorted(uid for uid,v in raw.items() if v is None)
        r['scores']=scores;r['results']={uid:score_entry(e,scores) for uid,e in r['entries'].items()};r['status']='completed'
        award(ranks,r['id'],r['results'],30)
    apply_awards(ranks,now)


def _snapshot(selected,times,sources,steam,now):
    try:
        date=datetime.fromisoformat(times[steam].replace('Z','+00:00'))
        if date.tzinfo is None:return None
        stamp=date.timestamp()
        values={k:selected[steam][k] for k in WEIGHTS}
        if not 0<=now-stamp<=FRESH or any(type(v) is not int or not 0<=v<=10**10 for v in values.values()):return None
        return dict(at=stamp,source=sources[steam],values=values)
    except (KeyError,TypeError,ValueError,AttributeError):return None


def observe(ranks,selected,times,sources,now=None):
    now=time.time() if now is None else now
    members={str(p['discord_id']):steam for steam,p in ranks['players'].items()}
    for r in state(ranks)['rounds'].values():
        if r['season']!=ranks.get('season',1) or r['status'] in ('completed','void','cancelled'):continue
        if now<r['start']-PRE_START:continue
        track=tracks(r);pre=r.setdefault('pre',{})
        live=now>=r['start']
        targets={i for e in r['entries'].values() for i in e['players']} if live else set(r['players'])
        for uid in targets:
            steam=r['players'][uid]['steam']
            if members.get(uid)!=steam:
                if live:r.setdefault('blocked',{})[uid]='Linked Steam account changed'
                continue
            if steam not in selected:continue
            snap=_snapshot(selected,times,sources,steam,now)
            if not snap:continue
            if snap['at']<r['start']:
                if snap['at']>=r['start']-PRE_START and snap['at']>pre.get(uid,{}).get('at',0):pre[uid]=snap
                continue
            if snap['at']>r['end']+FINAL_GRACE:continue
            t=track.get(uid)
            if t is None or not t.get('start'):
                before=pre.get(uid)
                if snap['at']<=r['start']+ON_TIME:t=dict(banked=0,start=snap,last=snap,final=None,late=False,notes=[])
                elif before and not _consistent(before,snap):t=dict(banked=0,start=before,last=before,final=None,late=False,notes=[])
                else:t=dict(banked=0,start=snap,last=snap,final=None,late=True,notes=[])
                track[uid]=t
            if t['final'] or snap['at']<=t['last']['at']:continue
            reason=_consistent(t['last'],snap)
            if reason:
                t['banked']+=points(t['start'],t['last']);t['start']=snap;t['notes'].append(reason)
            t['last']=snap;r['last_stats'][uid]=snap
            if snap['at']>=r['end']:t['final']=snap
    tick(ranks,now)


def close(ranks,now=None):
    now=time.time() if now is None else now
    tick(ranks,now)
    season=ranks.get('season',1);f=state(ranks)
    for r in f['rounds'].values():
        if r['season']==season and r['status'] not in ('completed','void','cancelled'):r['status']='cancelled';r['reason']='Season closed; unfinished round excluded'
    result=totals(ranks,season);key=f'season:{season}'
    award(ranks,key,result,150)
    f['champions'][str(season)]=dict(totals=result,winners=f['awards'][key]['winners'],points2=f['awards'][key]['points2'])
    apply_awards(ranks,now,closing=True)
