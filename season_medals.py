"""Immutable season podium honours; ties use competition placing."""
def podium(players, season, closed):
    ordered=sorted(players.values(),key=lambda p:(-p['points2'],p['discord_id']))
    result=[];previous=None;place=0
    for n,p in enumerate(ordered,1):
        if p['points2']!=previous:place=n
        previous=p['points2']
        if place>3:break
        metal=('gold','silver','bronze')[place-1]
        result.append(dict(id=f'season-{season}-{metal}',uid=p['discord_id'],season=season,place=place,metal=metal,
            name=f'Season {season} {metal.title()} Medal',detail=f'Finished #{place} in Season {season} ELO standings',at=closed))
    return result

def awards(state,uid):
    result=[]
    for archive in state.get('season_archives',[]):
        saved=archive.get('podium')
        if saved is None:saved=podium(archive.get('players',{}),archive['season'],archive.get('closed'))
        result.extend(a for a in saved if a['uid']==uid)
    return result
