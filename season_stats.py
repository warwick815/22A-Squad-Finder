"""Independent season counters. Never mutate lifetime source rows."""
import math
from datetime import datetime, timezone
FIELDS=('kills','deaths','wins','losses','hoursPlayed','cashEarned','teamKills','suicides')
def fresh_state():return dict(totals=dict.fromkeys(FIELDS,0),high={},updated=None,source=None,coverage='Complete from season baseline')
def observe(p,row,updated,source,now=None):
    now=now or datetime.now(timezone.utc)
    try:
        stamp=datetime.fromisoformat(updated.replace('Z','+00:00'))
        if not 0<=(now-stamp).total_seconds()<=900:return
        if p.get('season_started') and stamp<=datetime.fromisoformat(p['season_started']):return
    except (ValueError,TypeError,AttributeError):return
    s=p.get('season_stats')
    if s is None:
        s=fresh_state();s['coverage']='Partial: tracking began after season started';p['season_stats']=s
    if s['updated'] and stamp<=datetime.fromisoformat(s['updated']):return
    if s['source']!=source:
        if s['source'] is not None:s['coverage']='Partial: source changed; new baseline established'
        s['high']={};s['source']=source
    for k in FIELDS:
        v=row.get(k)
        if type(v) not in (int,float) or not math.isfinite(v) or v<0:continue
        if k in s['high']:s['totals'][k]+=max(0,v-s['high'][k])
        s['high'][k]=max(v,s['high'].get(k,v))
    s['updated']=updated

def statistics(p):
    s=p.get('season_stats')
    if not s:return {k:None for k in (*FIELDS,'kd','killsPerHour','winRate')}
    d=dict(s['totals']);k=d['kills'];deaths=d['deaths'];hours=d['hoursPlayed'];games=d['wins']+d['losses']
    d.update(kd=k/deaths if deaths else float(k),killsPerHour=k/hours if hours else 0,winRate=100*d['wins']/games if games else 0)
    return d

def standings(state,guild):
    from progression import RANKS
    from rank_divisions import division
    seasons=[]
    records=[dict(season=state.get('season',1),players=state['players'],current=True)]+[dict(a,current=False) for a in state.get('season_archives',[])]
    for record in records:
        rows=[]
        for p in record['players'].values():
            member=guild.get_member(p['discord_id']);s=p.get('season_stats',{})
            rows.append(dict(id=str(p['discord_id']),name=p.get('season_name') or getattr(member,'display_name','Former member'),rating=p['points2']/2,rank_name=RANKS[p['rank']][0],division=division(p),stats=statistics(p),stats_updated=s.get('updated'),status=s.get('coverage','Season statistics not recorded'),wallet=None,week_movement=None))
        rows.sort(key=lambda p:(-p['rating'],p['id']));last=None;place=0
        for n,p in enumerate(rows,1):
            if p['rating']!=last:place=n
            p['position']=place;last=p['rating']
        seasons.append(dict(season=record['season'],current=record['current'],players=rows))
    return seasons
