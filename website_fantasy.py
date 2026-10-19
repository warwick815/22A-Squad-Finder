"""Authenticated Fantasy Squad endpoints; selection never spends wallet funds."""
import time
from aiohttp import web
import fantasy


def catalog(bot,channel):
    from market_pricing import quote_state
    from player_exchange import price
    rows=[]
    for steam,p in bot.progression.state['players'].items():
        m=bot.guild.get_member(p['discord_id'])
        if not m or m.bot or not channel.permissions_for(m).view_channel or not p.get('active') or p.get('hold'):continue
        q=quote_state(bot,steam)
        rows.append(dict(id=str(m.id),name=m.display_name,steam=steam,price=q['price'] if q else price(p['points2'])))
    return rows


def avatar(bot,uid):
    member=bot.guild.get_member(int(uid))
    return str(getattr(getattr(member,'display_avatar',None),'url',''))


class FantasyActions:
    async def exchange_retired(self,request):
        self.session(request,write=request.method=='POST')
        raise web.HTTPGone(reason='Player Exchange has been replaced by Fantasy Squad. Existing shares are refunded at purchase cost. Reload the website.')

    async def fantasy_status(self,request):
        member,service,channel=await self.club_context(request)
        async with service.lock:fantasy.migrate(service.book)
        ranks=self.bot.progression
        async with ranks.lock:
            tomorrow=fantasy.ensure_round(ranks.state,catalog(self.bot,channel))
            fantasy.tick(ranks.state);ranks.save()
            f=fantasy.state(ranks.state);season=ranks.state.get('season',1);now=time.time()
            public=[]
            for r in sorted(f['rounds'].values(),key=lambda r:r['start'],reverse=True):
                entries=[]
                if r['start']<=now:
                    for uid,e in r['entries'].items():
                        details=[]
                        for target in e['players']:
                            multiplier=2 if target==e['captain'] and e['booster']=='captain' else 1.5 if target==e['captain'] else 1
                            if e['booster']=='team':multiplier*=1.5
                            info=fantasy.player_status(r,target,now)
                            base=info['base']
                            details.append(dict(id=target,name=r['players'][target]['name'],avatar=avatar(self.bot,target),cost=r['players'][target]['cost'],base_points=base,tracked_from=info['tracked_from'],recovered=info['tracked_from'] is not None,data_status=info['status'],updated=info['updated'],multiplier=multiplier,points=base*multiplier if base is not None else None,partial=info['partial']))
                        covered=sum(p['points'] is not None for p in details)
                        recovered_count=sum(p['recovered'] for p in details)
                        provisional=fantasy.score_entry(e,{p['id']:p['base_points'] or 0 for p in details}) if covered else None
                        entries.append(dict(covered=covered,recovered_count=recovered_count,total_players=len(details),partial=any(p['partial'] for p in details),id=uid,avatar=avatar(self.bot,uid),details=details,name=getattr(self.bot.guild.get_member(int(uid)),'display_name','Former member'),players=e['players'],lineup=[r['players'][i]['name']+(' (C)' if i==e['captain'] else '') for i in e['players']],captain=e['captain'],booster=e['booster'],points=r.get('results',{}).get(uid,provisional)))
                public.append(dict(id=r['id'],season=r['season'],start=r['start'],end=r['end'],status=r['status'],reason=r.get('reason'),entries=entries,entrants=len(r['entries']),award=f['awards'].get(r['id'])))
            names=lambda uid:getattr(self.bot.guild.get_member(int(uid)),'display_name','Former member')
            boards=[dict(season=s,rows=[dict(id=uid,name=names(uid),avatar=avatar(self.bot,uid),points=points) for uid,points in sorted(fantasy.totals(ranks.state,s).items(),key=lambda x:(-x[1],x[0]))],champion=f['champions'].get(str(s))) for s in sorted({r['season'] for r in f['rounds'].values()}|{season},reverse=True)]
            player_points={}
            for rd in f['rounds'].values():
                if rd['season']==season and rd['status']=='completed':
                    for uid,score in rd.get('scores',{}).items():player_points[uid]=player_points.get(uid,0)+score
            locked=[rd for rd in f['rounds'].values() if rd['season']==season and rd['start']<=now and rd['status'] in ('live','awaiting data','completed')]
            latest=max(locked,key=lambda rd:rd['start']) if locked else None
            market=[]
            if tomorrow:
                from market_pricing import quote_state
                for item in tomorrow['players'].values():
                    q=quote_state(self.bot,item['steam']) or {}
                    picked=sum(item['id'] in entry['players'] for entry in latest['entries'].values()) if latest else 0
                    entrants=len(latest['entries']) if latest else 0
                    market.append({'avatar':avatar(self.bot,item['id']),'season_points':player_points.get(item['id']),'picked_pct':round(100*picked/entrants,1) if entrants else None,**{k:v for k,v in item.items() if k!='steam'},'history':q.get('price_history',[]),'current_price':q.get('price',item['price'])})
            return web.json_response(dict(season=season,budget=tomorrow.get('budget',fantasy.BUDGET) if tomorrow else fantasy.BUDGET,linked=bool(ranks.find(member.id)),selection=dict(id=tomorrow['id'],start=tomorrow['start']) if tomorrow else None,players=market,entry=(tomorrow['entries'].get(str(member.id)) or tomorrow.get('drafts',{}).get(str(member.id))) if tomorrow else None,needs_resave=bool(tomorrow and str(member.id) in tomorrow.get('drafts',{})),squad_size=tomorrow.get('squad_size',fantasy.SQUAD_SIZE) if tomorrow else fantasy.SQUAD_SIZE,used=sorted(fantasy.used_boosters(ranks.state,str(member.id),season)),rounds=public,standings=boards))

    async def fantasy_submit(self,request):
        member,service,channel=await self.club_context(request,write=True)
        ranks=self.bot.progression
        if not ranks.find(member.id):raise web.HTTPBadRequest(reason='Link Steam before joining Fantasy Squad.')
        body=await self.body(request)
        async with ranks.lock:
            try:
                r=fantasy.state(ranks.state)['rounds'].get(body.get('round')) if isinstance(body.get('round'),str) else None
                if r:
                    for uid in body.get('players',[]):
                        if not isinstance(uid,str) or not uid.isdecimal():raise ValueError('Choose valid squad members.')
                        m=self.bot.guild.get_member(int(uid))
                        if not m or m.bot or not channel.permissions_for(m).view_channel:raise ValueError('One of these members is no longer eligible.')
                fantasy.submit(ranks.state,str(member.id),body)
            except (ValueError,TypeError) as e:raise web.HTTPBadRequest(reason=str(e) or 'Invalid squad.') from None
            ranks.save()
        return web.json_response(dict(message='Squad saved for the next 18:00 UK-time round. You can edit it until lock.'))
