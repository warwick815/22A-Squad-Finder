"""Season 2 rank thresholds and presentation, preserving Season 1."""
import math
BASE=(0,250,750,1500,3000,5000,8000)
NEW=(0,313,938,1875,3750,6250,10000)
def thresholds(player):return NEW if player.get('rank_rules',1)>=2 else BASE
def division(player):
    floors=thresholds(player);rank=player['rank'];points=player['points2']/2
    floor=floors[rank];end=floors[rank+1] if rank<6 else floor+(floors[6]-floors[5])
    bounds=[floor,math.ceil(floor+(end-floor)/3),math.ceil(floor+2*(end-floor)/3)]
    index=max(i for i,v in enumerate(bounds) if points>=v) if points>=floor else 0
    target=bounds[index+1] if index<2 else (end if rank<6 else None)
    return dict(name=('Bronze','Silver','Gold')[index],index=index,color=('#cd8c52','#bdc9d4','#efc65a')[index],floor=bounds[index],target=target,
        progress=max(0,min(100,100*(points-bounds[index])/(target-bounds[index]))) if target else 100)
