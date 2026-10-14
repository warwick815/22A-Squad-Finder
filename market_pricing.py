"""Conservative, prospective virtual-share pricing from verified source snapshots."""
import json
import math
import time
from datetime import datetime
from player_exchange import price as legacy_price

DAY=86400
KEY='player_market_v2'
FIELDS=('kills','deaths','teamKills','hoursPlayed','wins','losses')


def observe(state, steam, player, row, updated, source, now=None):
    now=time.time() if now is None else now
    def reject():
        if steam in state:state[steam].update(ready=False,valid_snapshot=False,baseline=None,events=[],inactive=0,decay_anchor=None,reason='Invalid or stale source; awaiting baseline')
    try:
        stamp=datetime.fromisoformat(updated.replace('Z','+00:00'))
        if stamp.tzinfo is None:return reject()
        stamp=stamp.timestamp()
        if not 0<=now-stamp<=900:return reject()
        values={k:row[k] for k in FIELDS}
        if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=10**10 for v in values.values()):return reject()
        if any(type(values[k]) is not int for k in FIELDS if k!='hoursPlayed'):return reject()
    except (ValueError,TypeError,KeyError,AttributeError):return reject()
    market=state.setdefault(steam,dict(value=float(legacy_price(player['points2'])),events=[],prices=[],inactive=0,decay_anchor=None))
    if market.get('epoch')!=player.get('season_started'):
        market.update(baseline=None,events=[],inactive=0,decay_anchor=None,epoch=player.get('season_started'))
    previous=market.get('baseline')
    if previous and stamp<=previous['at']:
        # A repeated snapshot is not activity and must not apply decay twice.
        market['ready']=market.get('valid_snapshot',False)
        return
    market['baseline']=dict(at=stamp,source=source,values=values)
    market['updated']=stamp
    market['ready']=False;market['valid_snapshot']=False
    gap=stamp-previous['at'] if previous else 0
    delta={k:values[k]-previous['values'][k] for k in FIELDS} if previous else {}
    bad=(not previous or previous['source']!=source or gap>900 or any(v<0 for v in delta.values())
         or delta.get('kills',0)+delta.get('deaths',0)>10000*max(gap/3600,1)
         or delta.get('teamKills',0)>1000*max(gap/3600,1)
         or not player.get('active') or player.get('hold') or player.get('pending'))
    if bad:
        market.update(events=[],inactive=0,decay_anchor=None,reason='New baseline / interrupted or corrected source')
        return
    market['ready']=True;market['valid_snapshot']=True;market['reason']='Fresh verified snapshot'
    market['events']=[e for e in market['events'] if e['at']>stamp-DAY]
    if any(delta[k] for k in ('kills','deaths','teamKills')):
        market['events'].append(dict(at=stamp,**{k:delta[k] for k in ('kills','deaths','teamKills')}))
    totals={k:sum(e[k] for e in market['events']) for k in ('kills','deaths','teamKills')}
    score=2*totals['kills']-3*totals['deaths']-20*totals['teamKills']
    elo_bonus=min(20,max(0,player['points2']//200))
    market.update(totals=totals,score=score,elo_bonus=elo_bonus)
    old=market['value'];before_idle=market['inactive']
    if any(v>0 for v in delta.values()):
        market.update(inactive=0,decay_anchor=None)
    else:market['inactive']+=gap
    if market['inactive']>DAY:
        if market['decay_anchor'] is None:market['decay_anchor']=old
        eligible=market['inactive']-max(DAY,before_idle)
        desired=max(market['decay_anchor']*.8,old*(.98**(eligible/DAY)))
        market['reason']='Inactivity decay' if desired<old else 'Maximum inactivity reduction reached'
    elif market['events']:
        desired=max(25,100+elo_bonus+score)
    else:desired=old
    # Rate-limit every step and every retained observation in the previous 24 hours.
    lower=old*(.85**(gap/DAY));upper=old*(1.15**(gap/DAY))
    recent=[p for p in market['prices'] if p['at']>=stamp-DAY]
    if recent:
        lower=max(lower,max(p['value']*.85 for p in recent))
        upper=min(upper,min(p['value']*1.15 for p in recent))
    market['value']=max(25,min(upper,max(lower,desired)))
    shown=int(round(market['value']))
    if recent:
        shown=max(math.ceil(max(p.get('quote',round(p['value']))*.85 for p in recent)),min(math.floor(min(p.get('quote',round(p['value']))*1.15 for p in recent)),shown))
    market['display_price']=max(25,shown)
    market['prices']=(recent+[dict(at=stamp,value=market['value'],quote=market['display_price'])])[-600:]


def record_feed(bot, selected, times, sources, players):
    store=getattr(bot,'store',None)
    if not store:return
    state=json.loads(store.get(KEY) or '{}')
    for steam,row in selected.items():
        player=players.get(steam)
        if player:observe(state,steam,player,row,times[steam],sources[steam])
    for steam in players:
        if steam not in selected and steam in state:state[steam].update(ready=False,valid_snapshot=False,baseline=None,events=[],inactive=0,decay_anchor=None,reason='Player missing from source')
    store.set(KEY,json.dumps(state))


def quote_state(bot, steam):
    store=getattr(bot,'store',None)
    state=json.loads(store.get(KEY) or '{}') if store else {}
    p=state.get(steam)
    if not p:return None
    fresh=0<=time.time()-p.get('updated',0)<=900
    return dict(price=p.get('display_price',max(25,int(round(p['value'])))),market_ready=bool(p.get('ready') and fresh),
        market_updated=p.get('updated'),performance=p.get('totals',{}),performance_score=p.get('score',0),
        elo_bonus=p.get('elo_bonus',0),inactive_hours=round(p.get('inactive',0)/3600,1),
        inactivity_discount=round(100*(1-p['value']/p['decay_anchor']),2) if p.get('decay_anchor') else 0,
        market_reason=p.get('reason','Awaiting fresh baseline'))
