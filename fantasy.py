"""Daily fantasy squads. State and ELO receipts persist together in progression_v1."""
import copy
import math
import time
import uuid
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

DAY=86400
BUDGET=400
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
            book.wallet(uid);book.data['wallets'][uid]+=cost
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


def ensure_round(ranks, catalog, now=None):
    now=time.time() if now is None else now
    f=state(ranks);season=ranks.get('season',1)
    # Never move a running round or overlap its already-promised scoring window.
    running=[r['end'] for r in f['rounds'].values() if r['season']==season and r['start']<=now<r['end'] and r['status'] not in ('void','cancelled','completed')]
    day=next_lock(max([now,*[end-1 for end in running]]))
    key=f'{season}:{day}'
    legacy=[r for r in f['rounds'].values() if r['season']==season and r['status']=='selection' and r['start']>now and r.get('schedule')!='uk18']
    if key not in f['rounds'] and (len(catalog)>=3 or legacy):
        if legacy:players=copy.deepcopy(max(legacy,key=lambda r:r['start'])['players'])
        else:
            average=sum(p['price'] for p in catalog)/len(catalog)
            players={p['id']:dict(p,cost=max(30,min(200,round(p['price']/average*100)))) for p in catalog}
        f['rounds'][key]=dict(id=key,season=season,start=day,end=next_lock(day),status='selection',schedule='uk18',players=players,entries={},start_stats={},end_stats={},last_stats={},invalid=[])
    target=f['rounds'].get(key)
    if target:
        for old in legacy:
            if old is target:continue
            for uid,entry in old['entries'].items():
                if entry.get('saved',0)>=target['entries'].get(uid,{}).get('saved',-1):target['entries'][uid]=copy.deepcopy(entry)
            old['status']='cancelled';old['reason']='Selection moved to 18:00 UK time; saved squad transferred.'
        target['schedule']='uk18'
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
    if not isinstance(ids,list) or any(not isinstance(i,str) for i in ids) or len(ids)!=(4 if boost=='reinforcements' else 3) or len(set(ids))!=len(ids):raise ValueError('Select three distinct players, or four with Reinforcements.')
    if any(i not in r['players'] for i in ids) or captain not in ids:raise ValueError('Choose an eligible squad and captain.')
    if sum(r['players'][i]['cost'] for i in ids)>BUDGET:raise ValueError('Squad exceeds the 400-credit budget.')
    if boost and boost in used_boosters(ranks,uid,r['season'],now):raise ValueError('That booster has already been used this season.')
    r['entries'][uid]=dict(players=ids,captain=captain,booster=boost,saved=now)


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


def tick(ranks,now=None):
    now=time.time() if now is None else now
    for r in state(ranks)['rounds'].values():
        if r['season']!=ranks.get('season',1) or r['status'] in ('completed','void','cancelled'):continue
        if now<r['start']:continue
        r['status']='live' if now<r['end'] else 'awaiting data'
        if now<r['end']:continue
        needed={i for e in r['entries'].values() for i in e['players']}
        if not needed:r['status']='void';r['reason']='No squads entered';continue
        if r['invalid'] or not needed<=r['start_stats'].keys() or not needed<=r['end_stats'].keys():
            if now>=r['end']+21600:r['status']='void';r['reason']='Required source data could not be verified; boosters released'
            continue
        scores={i:sum((r['end_stats'][i]['values'][k]-r['start_stats'][i]['values'][k])*w for k,w in WEIGHTS.items()) for i in needed}
        r['scores']=scores;r['results']={uid:score_entry(e,scores) for uid,e in r['entries'].items()};r['status']='completed'
        award(ranks,r['id'],r['results'],30)
    apply_awards(ranks,now)


def observe(ranks,selected,times,sources,now=None):
    now=time.time() if now is None else now
    members={str(p['discord_id']):(steam,p) for steam,p in ranks['players'].items()}
    for r in state(ranks)['rounds'].values():
        if r['season']!=ranks.get('season',1) or r['status'] in ('completed','void','cancelled') or now<r['start']:continue
        needed={i for e in r['entries'].values() for i in e['players']}
        for uid in needed:
            if uid in r['end_stats']:continue
            steam=r['players'][uid]['steam']
            if uid not in members or members[uid][0]!=steam:
                if uid not in r['invalid']:r['invalid'].append(uid)
                continue
            if steam not in selected:continue
            try:
                date=datetime.fromisoformat(times[steam].replace('Z','+00:00'))
                if date.tzinfo is None:continue
                stamp=date.timestamp()
                values={k:selected[steam][k] for k in WEIGHTS}
                if not 0<=now-stamp<=900 or any(type(v) is not int or not 0<=v<=10**10 for v in values.values()):continue
                snap=dict(at=stamp,source=sources[steam],values=values)
            except (KeyError,TypeError,ValueError,AttributeError):continue
            if stamp<r['start'] or stamp>r['end']+900:continue
            previous=r['last_stats'].get(uid)
            if previous and stamp<=previous['at']:continue
            if previous and (previous['source']!=snap['source'] or any(values[k]<previous['values'][k] for k in WEIGHTS) or sum(values[k]-previous['values'][k] for k in ('kills','deaths'))>10000*max(1,(stamp-previous['at'])/3600)):
                if uid not in r['invalid']:r['invalid'].append(uid)
            r['last_stats'][uid]=snap
            if uid not in r['start_stats'] and r['start']<=stamp<=r['start']+900:r['start_stats'][uid]=copy.deepcopy(snap)
            if uid not in r['end_stats'] and r['end']<=stamp<=r['end']+900:r['end_stats'][uid]=copy.deepcopy(snap)
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
