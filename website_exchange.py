"""Authenticated, reviewed virtual-share trades using the betting lock."""
import time
import secrets
from aiohttp import web
from player_exchange import Exchange, price, fee, available, HOLDING_LIMIT, ORDER_LIMIT
from market_pricing import quote_state


class ExchangeActions:
    def instrument(self, uid):
        m=self.bot.guild.get_member(uid)
        found=self.bot.progression.find(uid)
        if not m or m.bot or not found:return None
        steam,p=found
        market=quote_state(self.bot,steam)
        return dict(id=str(uid),name=m.display_name,steam=steam,rating=p['points2']/2,
                    price=market['price'] if market else price(p['points2']),tradable=bool(market and market['market_ready'] and available(p)),updated=p.get('updated'),market=market)

    async def exchange_status(self, request):
        member,service,channel=await self.club_context(request)
        async with service.lock:
            ex=Exchange(service.book);ex.sync(self.bot.progression.state.get('season',1))
            holdings=ex.state['holdings'].get(str(member.id),{})
            market=[]
            for m in self.bot.guild.members:
                if m.bot or not channel.permissions_for(m).view_channel:continue
                item=self.instrument(m.id)
                if item:
                    item['supply']=ex.supply(m.id)
                    item['self']=m.id==member.id
                    item.pop('steam');market.append(item)
            portfolio=[]
            for target,p in holdings.items():
                item=self.instrument(int(target))
                valid=item and item['steam']==p['steam']
                gross=item['price']*p['quantity'] if valid else None
                portfolio.append(dict(id=target,name=item['name'] if valid else p['name'],quantity=p['quantity'],cost=p['cost'],
                    price=item['price'] if valid else None,value=gross,net=gross-fee(gross) if gross is not None else None,
                    profit=gross-fee(gross)-p['cost'] if gross is not None else None,
                    tradable=bool(valid and item['tradable'] and channel.permissions_for(self.bot.guild.get_member(int(target))).view_channel)))
            own=self.instrument(member.id)
            if own:
                own.pop('steam')
                own['supply']=ex.supply(member.id)
                own['holders']=sum(1 for uid,positions in ex.state['holdings'].items() if uid!=str(member.id) and positions.get(str(member.id),{}).get('quantity',0)>0)
            from market_rewards import reward_status
            return web.json_response(dict(own_stock=own,rewards=reward_status(service.book,member.id,ex.state['season']),balance=service.book.data['wallets'].get(str(member.id),10000),
                linked=bool(self.bot.progression.find(member.id)),season=ex.state['season'],
                market=sorted(market,key=lambda p:(-p['rating'],p['name'])),portfolio=portfolio,
                history=[{k:v for k,v in e.items() if k!='uid'} for e in reversed(ex.state['history']) if e['uid']==str(member.id)][:50]))

    async def exchange_quote(self, request):
        member,service,channel=await self.club_context(request,write=True)
        d=await self.body(request)
        try:
            target=d.get('target');qty=d.get('quantity');side=d.get('side')
            if not isinstance(target,str) or not target.isdecimal() or len(target)>20 or type(qty) is not int or not 1<=qty<=ORDER_LIMIT or side not in ('buy','sell'):
                raise ValueError('Choose a player, buy/sell and 1–20 whole shares per order.')
            async with service.lock:
                service.linked(member.id)
                ex=Exchange(service.book);ex.sync(self.bot.progression.state.get('season',1))
                other=await self.member(int(target))
                ex.sync(self.bot.progression.state.get('season',1))
                if other.id==member.id or not channel.permissions_for(other).view_channel:
                    raise ValueError('Choose another member with access to The Black Market.')
                item=self.instrument(other.id)
                if not item or not item['tradable']:raise ValueError('Player trading is paused. A fresh, active rating is required.')
                pos=ex.state['holdings'].get(str(member.id),{}).get(target)
                if pos and pos['steam']!=item['steam']:raise ValueError('Player identity changed; position frozen until season settlement.')
                if side=='sell' and (pos or {}).get('quantity',0)<qty:raise ValueError('You do not own that many shares.')
                if side=='buy' and (pos or {}).get('quantity',0)+qty>HOLDING_LIMIT:raise ValueError('Maximum 20 shares per player.')
                if side=='buy' and qty>ex.supply(other.id)['remaining']:raise ValueError('Not enough shares available. Wait for another member to sell.')
                gross=item['price']*qty;charge=fee(gross) if side=='sell' else 0
                if side=='buy' and service.book.data['wallets'].get(str(member.id),10000)<gross:raise ValueError('Not enough available betting dollars.')
                token=secrets.token_urlsafe(24)
                self.session(request)['exchange_quote']=dict(token=token,expires=time.monotonic()+60,target=target,steam=item['steam'],price=item['price'],rating=item['rating'],side=side,quantity=qty,season=ex.state['season'],revision=ex.state['revision'],reset=service.book.data.get('reset_version',0))
                return web.json_response(dict(token=token,name=item['name'],side=side,quantity=qty,price=item['price'],fee=charge,total=gross-charge,expires_in=60))
        except ValueError as exc:raise web.HTTPBadRequest(reason=str(exc)) from None

    async def exchange_trade(self, request):
        member,service,channel=await self.club_context(request,write=True)
        d=await self.body(request);session=self.session(request)
        q=session.get('exchange_quote')
        if not q or not isinstance(d.get('token'),str) or not secrets.compare_digest(q['token'],d['token']):
            raise web.HTTPConflict(reason='Get a new quote before confirming this trade.')
        session.pop('exchange_quote',None)
        try:
            async with service.lock:
                service.linked(member.id)
                ex=Exchange(service.book);ex.sync(self.bot.progression.state.get('season',1))
                other=await self.member(int(q['target']))
                ex.sync(self.bot.progression.state.get('season',1))
                item=self.instrument(other.id)
                if (time.monotonic()>q['expires'] or q['season']!=ex.state['season'] or q['revision']!=ex.state['revision']
                    or q['reset']!=service.book.data.get('reset_version',0) or not item or not item['tradable']
                    or item['price']!=q['price'] or item['rating']!=q['rating'] or item['steam']!=q['steam']
                    or not channel.permissions_for(other).view_channel):
                    raise web.HTTPConflict(reason='Quote expired or player/market changed. Review a fresh quote; no trade made.')
                total=ex.execute(member.id,other.id,item['steam'],item['name'],q['side'],q['quantity'],q['price'])
                return web.json_response(dict(message=f"{'Bought' if q['side']=='buy' else 'Sold'} {q['quantity']} shares in {item['name']}. ${total:,} {'spent' if q['side']=='buy' else 'credited — no trading fee'}."))
        except ValueError as exc:raise web.HTTPBadRequest(reason=str(exc)) from None
