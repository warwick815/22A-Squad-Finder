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
    seasons=sum(steam in a.get('players',{}) for a in bot.progression.state.get('season_archives',[]))
    kills,kd,kph,hours=row.get('kills'),row.get('kd'),row.get('killsPerHour'),row.get('hoursPlayed')
    # Ratio awards only count once a player has enough play for the ratio to mean something.
    kd_value=None if kd is None or kills is None else (kd if kills>=500 else 0)
    kph_value=None if kph is None or hours is None else (kph if hours>=50 else 0)
    box=bot.progression.state.get('community_hq',{}).get('lockers',{}).get(str(player['discord_id']),{})
    patches=len(box.get('earned',{}))
    definitions=[('linked','Enlisted','Linked Steam account','service',1,1),
        ('stripes','First stripes','Reach Lance Corporal','service',rank,1),
        ('nco','Non-commissioned','Reach Corporal','service',rank,2),
        ('veteran','Season veteran','Complete a season','service',seasons,1),
        ('kills100','First hundred','Record 100 lifetime kills','combat',row.get('kills'),100),
        ('kills1000','Frontline veteran','Record 1,000 lifetime kills','combat',row.get('kills'),1000),
        ('kills5000','Combat distinction','Record 5,000 lifetime kills','combat',row.get('kills'),5000),
        ('wins10','Victory ribbon','Record 10 lifetime wins','combat',row.get('wins'),10),
        ('wins50','Campaign medal','Record 50 lifetime wins','combat',row.get('wins'),50),
        ('hours100','Long service','Record 100 lifetime hours','service',row.get('hoursPlayed'),100),
        ('club1','First payout','Win a The Black Market challenge','club',wins,1),
        ('club10','Challenge champion','Win 10 The Black Market challenges','club',wins,10),
        # Added challenges: more rank milestones, deeper combat tiers, service and community.
        ('sergeant','Three stripes','Reach Sergeant','service',rank,3),
        ('staffsgt','Crown and stripes','Reach Staff Sergeant','service',rank,4),
        ('warrant','Warrant','Reach Warrant Officer Class 2','service',rank,5),
        ('veteran2','Old campaigner','Complete two seasons','service',seasons,2),
        ('hours250','Old sweat','Record 250 lifetime hours','service',row.get('hoursPlayed'),250),
        ('hours500','Lifer','Record 500 lifetime hours','service',row.get('hoursPlayed'),500),
        ('kills10000','Legend of the line','Record 10,000 lifetime kills','combat',row.get('kills'),10000),
        ('wins100','Campaign star','Record 100 lifetime wins','combat',row.get('wins'),100),
        ('wins250','Battle honours','Record 250 lifetime wins','combat',row.get('wins'),250),
        ('sharpshooter','Sharpshooter','Hold a 2.0 lifetime K/D with at least 500 kills','combat',kd_value,2),
        ('rapidfire','Rapid fire','Average 20 kills an hour across at least 50 hours','combat',kph_value,20),
        ('cash10m','Paymaster','Earn $10 million in-game cash','service',row.get('cashEarned'),10_000_000),
        ('cash50m','Treasury','Earn $50 million in-game cash','service',row.get('cashEarned'),50_000_000),
        ('club25','Bookies\' nightmare','Win 25 The Black Market challenges','club',wins,25),
        ('patches3','Patch collector','Earn 3 morale patches from community operations','club',patches,3),
        ('patches6','Kit bag','Earn 6 morale patches from community operations','club',patches,6)]
    changed=False
    result=[]
    for code,name,detail,group,value,goal in definitions:
        if value is not None and value>=goal and code not in earned:
            earned[code]=datetime.now(timezone.utc).isoformat();changed=True
        result.append(dict(id=code,name=name,detail=detail,group=group,earned=code in earned,
                           first_observed=earned.get(code),value=value,target=goal))
    if changed and store:store.set(key,json.dumps(earned))
    from season_medals import awards
    for award in awards(bot.progression.state,player['discord_id']):
        result.append(dict(id=award['id'],name=award['name'],detail=award['detail'],group='season podium',metal=award['metal'],earned=True,first_observed=award['at'],value=1,target=1))
    return result
