"""Display-only achievements. Earned medals survive rank/season changes."""
import json
from datetime import datetime, timezone


def medals(bot, steam, player, row):
    store=getattr(bot,'store',None)
    key='website_medals_v1:'+steam
    earned=json.loads(store.get(key) or '{}') if store else {}
    rank=max([player['rank']]+[e.get('to',0) for e in player.get('history',[]) if isinstance(e.get('to'),int)])
    book=getattr(getattr(bot,'betting',None),'book',None)
    wins=sum(1 for b in book.data['bets'].values() if b.get('winner')==player['discord_id'] and b['status']=='settled') if book else 0
    definitions=[('linked','Enlisted','Linked Steam account','service',1,1),
        ('stripes','First stripes','Reach Lance Corporal','service',rank,1),
        ('nco','Non-commissioned','Reach Corporal','service',rank,2),
        ('veteran','Season veteran','Complete a season','service',sum(steam in a.get('players',{}) for a in bot.progression.state.get('season_archives',[])),1),
        ('kills100','First hundred','Record 100 lifetime kills','combat',row.get('kills'),100),
        ('kills1000','Frontline veteran','Record 1,000 lifetime kills','combat',row.get('kills'),1000),
        ('kills5000','Combat distinction','Record 5,000 lifetime kills','combat',row.get('kills'),5000),
        ('wins10','Victory ribbon','Record 10 lifetime wins','combat',row.get('wins'),10),
        ('wins50','Campaign medal','Record 50 lifetime wins','combat',row.get('wins'),50),
        ('hours100','Long service','Record 100 lifetime hours','service',row.get('hoursPlayed'),100),
        ('club1','First payout','Win a The Black Market challenge','club',wins,1),
        ('club10','Challenge champion','Win 10 The Black Market challenges','club',wins,10)]
    changed=False
    result=[]
    for code,name,detail,group,value,goal in definitions:
        if value is not None and value>=goal and code not in earned:
            earned[code]=datetime.now(timezone.utc).isoformat();changed=True
        result.append(dict(id=code,name=name,detail=detail,group=group,earned=code in earned,
                           first_observed=earned.get(code),value=value,target=goal))
    if changed and store:store.set(key,json.dumps(earned))
    return result
