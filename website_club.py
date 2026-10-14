"""Website adapter for the existing virtual-dollar book; no separate wallet."""
import time
from aiohttp import web


class ClubActions:
    async def club_context(self, request, write=False):
        session = self.session(request, write=write)
        member = await self.member(session['uid'])
        service = getattr(self.bot, 'betting', None)
        if not service:
            raise web.HTTPServiceUnavailable(reason='The Black Market is not ready yet.')
        channel = self.bot.guild.get_channel(service.book.data.get('channel', 0))
        if not channel:
            raise web.HTTPConflict(reason='Staff must set up /betting-panel in Discord first.')
        if not channel.permissions_for(member).view_channel:
            raise web.HTTPForbidden(reason='You need access to the Discord The Black Market channel.')
        return member, service, channel

    def club_bet(self, bet, uid):
        def name(who):
            return getattr(self.bot.guild.get_member(who), 'display_name', 'Former member')
        result = {k: bet.get(k) for k in ('id','mode','stake','hours','target','limit','status','expires','start','end','result')}
        result.update(a=str(bet['a']), b=str(bet['b']), challenger=name(bet['a']), opponent=name(bet['b']),
                      winner=str(bet['winner']) if bet.get('winner') is not None else None)
        # Only participants' own challenges are returned. Do not expose source identifiers.
        result['progress'] = []
        for who, initial in bet.get('baseline', {}).items():
            latest = bet.get('last', {}).get(who, initial)
            result['progress'].append({'name':name(int(who)), 'kills':max(0,latest['kills']-initial['kills']),
                'deaths':max(0,latest['deaths']-initial['deaths']), 'updated':latest['time']})
        result['can_accept'] = bet['status']=='offered' and bet['b']==uid and time.time()<bet['expires']
        result['can_cancel'] = bet['status']=='offered' and uid in (bet['a'],bet['b'])
        return result

    async def club_status(self, request):
        member, service, channel = await self.club_context(request)
        linked = bool(self.bot.progression.find(member.id))
        async with service.lock:
            book = service.book
            from player_exchange import Exchange
            Exchange(book).sync(self.bot.progression.state.get('season',1))
            mine = [b for b in book.data['bets'].values() if member.id in (b['a'],b['b'])]
            reserved = sum(b['stake'] for b in mine if b['status']=='active' or b['status']=='offered' and b['a']==member.id)
            # A GET does not grant or reset a wallet; new linked players see their initial entitlement.
            balance = book.data['wallets'].get(str(member.id),10000) if linked else None
            bets = [self.club_bet(b, member.id) for b in sorted(mine,key=lambda b:b['expires'],reverse=True)[:50]]
            opponents = [{'id':str(m.id),'name':m.display_name} for m in self.bot.guild.members
                         if not m.bot and m.id!=member.id and self.bot.progression.find(m.id)
                         and channel.permissions_for(m).view_channel and not book.open_for(m.id)]
        return web.json_response({'linked':linked,'balance':balance,'reserved':reserved,'bets':bets,
                                  'opponents':opponents,'can_offer':linked and not any(b['status'] in ('active','offered') for b in mine)})

    async def club_action(self, request):
        member, service, channel = await self.club_context(request, write=True)
        data = await self.body(request)
        if data.get('confirm') is not True:
            raise web.HTTPBadRequest(reason='Review and confirm the challenge terms first.')
        try:
            async with service.lock:
                service.linked(member.id)
                action = data.get('action')
                if action == 'offer':
                    target = data.get('opponent')
                    if not isinstance(target,str) or not target.isdecimal() or len(target)>20:
                        raise ValueError('Choose a linked opponent.')
                    opponent = await self.member(int(target))
                    service.linked(opponent.id)
                    if opponent.bot or not channel.permissions_for(opponent).view_channel:
                        raise web.HTTPForbidden(reason='Opponent cannot access The Black Market.')
                    perms = channel.permissions_for(self.bot.guild.me)
                    if not all(getattr(perms,p,False) for p in ('view_channel','send_messages','embed_links','read_message_history')):
                        raise ValueError('The bot needs permission to publish in the betting channel.')
                    for key in ('stake','hours','target','limit'):
                        if type(data.get(key)) is not int:
                            raise ValueError('Challenge amounts must be whole numbers.')
                    b = service.book.offer(member.id,opponent.id,data['stake'],data.get('mode'),data['target'],data['hours'],data['limit'],time.time())
                    b['channel']=channel.id
                    service.book.save()
                    message='Offer created. Your stake is reserved; your opponent can accept on the website or in Discord.'
                elif action in ('accept','cancel'):
                    bid=data.get('id')
                    b=service.book.data['bets'].get(bid) if isinstance(bid,str) else None
                    if not b or member.id not in (b['a'],b['b']):
                        raise web.HTTPForbidden(reason='This challenge is not yours.')
                    original=self.bot.guild.get_channel(b['channel'])
                    if not original or not original.permissions_for(member).view_channel:
                        raise web.HTTPForbidden(reason='You no longer have access to this challenge channel.')
                    if b['status']!='offered':
                        raise ValueError('This offer has already been handled. Refresh your challenges.')
                    if action=='accept':
                        if member.id!=b['b']:
                            raise web.HTTPForbidden(reason='Only the invited player can accept.')
                        other=await self.member(b['a'])
                        if not original.permissions_for(other).view_channel:
                            raise ValueError('The challenger no longer has channel access.')
                        if time.time()>=b['expires']:
                            service.book.finish(b,None,'Offer expired; stake returned')
                            raise ValueError('Offer expired; challenger refunded.')
                        snapshots=await service.snapshots(b)
                        expected={str(b['a']),str(b['b'])} if b['mode']=='race' else {str(b['b'])}
                        if set(snapshots)!=expected:
                            raise ValueError('Fresh player stats are unavailable. No stake deducted.')
                        service.book.accept(b,member.id,snapshots,time.time())
                        message='Accepted. Both stakes are reserved and the challenge has started.'
                    else:
                        service.book.finish(b,None,'Offer declined/cancelled; stake returned')
                        message='Offer closed. The challenger’s stake has been returned.'
                else:
                    raise ValueError('Choose a valid challenge action.')
        except ValueError as exc:
            raise web.HTTPBadRequest(reason=str(exc)) from None
        return web.json_response({'message':message})
