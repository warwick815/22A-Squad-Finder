"""Member-only HQ features with staff-only operation/schedule controls."""
import time,math
from aiohttp import web
import community_hq as hq
import fantasy

class CommunityActions:
    async def community_status(self,request):
        session=self.session(request);member=await self.member(session['uid']);ranks=self.bot.progression
        async with ranks.lock:
            h=hq.state(ranks.state);hq.expire(ranks.state,time.time());hq.locker(ranks.state,member.id);ranks.save()
            season=ranks.state.get('season',1);players=[]
            selection=max((r for r in ranks.state.get('fantasy',{}).get('rounds',{}).values() if r['season']==season and r['status']=='selection' and r['start']>time.time()),key=lambda r:r['start'],default=None)
            for p in ranks.state['players'].values():
                m=self.bot.guild.get_member(p['discord_id'])
                if not m or m.bot:continue
                uid=str(m.id);scout=hq.scouting(ranks.state,uid);cost=selection['players'].get(uid,{}).get('cost') if selection else None
                players.append(dict(id=uid,name=m.display_name,avatar=str(getattr(getattr(m,'display_avatar',None),'url','')),rating=p['points2']/2,cost=cost,confidence=hq.confidence(self.bot,uid),**scout,value=scout['average']/cost if cost and scout['average'] is not None else None))
            ops=[]
            for o in sorted(h['operations'].values(),key=lambda o:o['start'],reverse=True):
                ops.append({**{k:v for k,v in o.items() if k not in ('members','actor')},'progress':sum(m['total'] for m in o['members'].values()),'participants':len(o['members']),'joined':str(member.id) in o['members'],'contribution':o['members'].get(str(member.id),{}).get('total',0)})
            totals=fantasy.totals(ranks.state,season)
            return web.json_response(dict(season=season,staff=bool(getattr(getattr(member,'guild_permissions',None),'manage_guild',False)),players=players,operations=ops,patches=hq.PATCHES,locker=hq.locker(ranks.state,member.id),finale=h['finales'].get(str(season)),fantasy=sorted([dict(id=uid,points=value) for uid,value in totals.items()],key=lambda p:-p['points'])))

    async def community_action(self,request):
        session=self.session(request,write=True);member=await self.member(session['uid']);body=await self.body(request);ranks=self.bot.progression
        action=body.get('action')
        if action in ('create','schedule'):
            await self.staff_member(request,write=True)
            if body.get('confirm') is not True:raise web.HTTPBadRequest(reason='Review and confirm the staff action.')
        async with ranks.lock:
            try:
                if action=='display':hq.select_patches(ranks.state,member.id,body.get('patches'))
                elif action=='join':
                    found=ranks.find(member.id)
                    if not found or not found[1].get('active') or found[1].get('hold'):raise ValueError('An active linked profile is required.')
                    if not isinstance(body.get('operation'),str):raise ValueError('Choose an operation.')
                    hq.join_operation(ranks.state,body['operation'],member.id)
                elif action=='create':hq.create_operation(ranks.state,body.get('patch'),member.id)
                elif action=='schedule':
                    end=body.get('end')
                    if type(end) not in (float,int) or not math.isfinite(end) or not time.time()<end<=time.time()+366*86400:raise ValueError('Choose a future date within the next year.')
                    hq.state(ranks.state)['finales'][str(ranks.state.get('season',1))]=dict(end=end,actor=str(member.id),updated=time.time())
                else:raise ValueError('Unknown action.')
            except (ValueError,TypeError) as e:raise web.HTTPBadRequest(reason=str(e)) from None
            ranks.save()
        return web.json_response(dict(message='Saved.'))
