"""Members-only Hall of shame: every time a 22A member killed another 22A member on TF21."""
from aiohttp import web


class ShameActions:
    async def shame_status(self, request):
        session = self.session(request)
        await self.member(session['uid'])
        from kill_feed import service
        state = service(self.bot).state
        by_steam = {steam: p for steam, p in self.bot.progression.state['players'].items()}

        def who(steam, fallback):
            p = by_steam.get(steam)
            m = self.bot.guild.get_member(p['discord_id']) if p else None
            return {'id': str(p['discord_id']) if p else None, 'name': getattr(m, 'display_name', None) or fallback,
                    'avatar': str(getattr(getattr(m, 'display_avatar', None), 'url', '') or '')}

        events = [{**{k: e.get(k) for k in ('id', 'at', 'weapon', 'team_kill', 'headshot', 'distance', 'map', 'server')},
                   'killer': who(e['killer'], e['killer_name']), 'victim': who(e['victim'], e['victim_name'])}
                  for e in reversed(state['shame'])]
        offenders = {}
        for e in state['shame']:
            row = offenders.setdefault(e['killer'] or e['killer_name'], {'who': who(e['killer'], e['killer_name']), 'friendly': 0, 'blue': 0})
            row['friendly' if e['team_kill'] else 'blue'] += 1
        table = sorted(offenders.values(), key=lambda r: (-(r['friendly'] + r['blue']), -r['friendly'], r['who']['name'].lower()))
        return web.json_response({'enabled': bool(state['processed'] or state['cursor']), 'events': events[:200], 'offenders': table[:20]})


DECK_ID = r'\d{4}-\d{1,4}'


def deck_order(deck_id):
    year, _, number = deck_id.partition('-')
    return int(year), int(number or 0)


def deck_view(state, who):
    """Every deck of bounty cards, newest first: 54 slots each. Collected bounties are dealt
    in order; this hour's open bounty shows as the next card, up for grabs."""
    import time
    import playing_card
    from kill_feed import current_deck, hunter_of_deck
    decks = dict(state.get('deck', {}))
    b = state.get('bounty')
    if b and not b.get('claimed') and b.get('deck'):
        decks.setdefault(b['deck'], {})
    if not decks:
        deck_id, _ = current_deck(state, time.time())
        decks[deck_id] = {}
    out = []
    for deck_id in sorted(decks, key=deck_order, reverse=True):
        cards = decks[deck_id]
        slots = []
        for n in range(1, 55):
            card = cards.get(str(n))
            if n == 54:
                top = hunter_of_deck(state, deck_id)
                card = top and {'status': 'hunter', 'name': top['name'], 'count': top['count'], 'claimed': top['steam']}
            elif not card and b and not b.get('claimed') and b.get('deck') == deck_id and b.get('card') == n:
                card = {**b, 'status': 'open'}
            entry = {'n': n, 'label': playing_card.label(n), 'face': playing_card.face(n)}
            if card:
                entry.update(status=card['status'], name=card.get('name'), kills=card.get('kills'), hour=card.get('hour'),
                             count=card.get('count'), weapon=card.get('weapon'), distance=card.get('distance'),
                             headshot=card.get('headshot'),
                             claimed_by=who(card['claimed'], card.get('claimed_name')) if card.get('claimed') else None,
                             image=f'/api/reports/card/{deck_id}/{n}.png?v={card_version(card)}')
            slots.append(entry)
        out.append({'deck': deck_id, 'label': playing_card.deck_label(deck_id), 'slots': slots, 'collected': len(cards)})
    return out


def card_version(card):
    import hashlib
    import json
    return hashlib.sha1(json.dumps(card, sort_keys=True, default=str).encode()).hexdigest()[:10]


class ReportActions:
    async def report_card(self, request):
        """One playing card from a bounty deck, drawn on request and cached."""
        import re
        session = self.session(request)
        await self.member(session['uid'])
        deck_id, n = request.match_info['deck'], request.match_info['n']
        if not (re.fullmatch(DECK_ID, deck_id) and n.isdecimal() and 1 <= int(n) <= 54):
            raise web.HTTPNotFound()
        from kill_feed import hunter_of_deck, service
        state = service(self.bot).state
        card = state.get('deck', {}).get(deck_id, {}).get(n)
        b = state.get('bounty')
        if not card and b and not b.get('claimed') and b.get('deck') == deck_id and str(b.get('card')) == n:
            card = {**b, 'status': 'open'}  # This hour's card, still up for grabs.
        photo = None
        if n == '54':
            top = hunter_of_deck(state, deck_id)
            card = top and {'n': 54, 'name': top['name'], 'count': top['count'], 'status': 'hunter'}
            if top:
                # The deck's top hunter gets their Discord picture on the Red Joker.
                p = self.bot.progression.state['players'].get(str(top['steam']))
                member = self.bot.guild.get_member(p['discord_id']) if p else None
                if member:
                    from card_send import avatar
                    photo = await avatar(member)
                    card['name'] = member.display_name
        if not card:
            raise web.HTTPNotFound()
        cache = self.__dict__.setdefault('_card_cache', {})
        key = (deck_id, n, card_version(card), bool(photo))
        if key not in cache:
            import asyncio
            import playing_card
            if len(cache) > 120:
                cache.clear()
            cache[key] = await asyncio.to_thread(playing_card.render, {**card, 'n': int(n)}, deck_id, photo)
        return web.Response(body=cache[key], content_type='image/png',
                            headers={'Cache-Control': 'private, max-age=86400'})

    async def reports_status(self, request):
        """Field reports: Most Wanted, past bounties, this week's best streak and squad sessions."""
        session = self.session(request)
        await self.member(session['uid'])
        import time
        from kill_feed import service, week_key
        state = service(self.bot).state
        players = self.bot.progression.state['players']

        def who(steam, fallback):
            p = players.get(str(steam)) if steam else None
            m = self.bot.guild.get_member(p['discord_id']) if p else None
            return {'id': str(p['discord_id']) if p else None, 'name': getattr(m, 'display_name', None) or fallback,
                    'avatar': str(getattr(getattr(m, 'display_avatar', None), 'url', '') or '')}

        def bounty(b):
            if not b:
                return None
            return {'hour': b.get('hour'), 'week': b.get('week'), 'expires': b.get('expires'), 'deck': b.get('deck'), 'card': b.get('card'),
                    'name': b['name'], 'kills': b['kills'], 'set_at': b['set_at'],
                    'status': b.get('status') or ('claimed' if b.get('claimed') else 'open'),
                    'claimed_by': who(b['claimed'], b.get('claimed_name')) if b.get('claimed') else None,
                    'claimed_at': b.get('claimed_at'), 'weapon': b.get('weapon'), 'distance': b.get('distance'), 'headshot': b.get('headshot')}

        def session_view(s):
            return {**{k: s.get(k) for k in ('server', 'map', 'start', 'end', 'kills', 'headshots', 'longest', 'weapon')},
                    'members': [{**who(m['steam'], m['name']), 'kills': m['kills'], 'headshots': m['headshots']} for m in s['members']],
                    'top': {**who(s['top']['steam'], s['top']['name']), 'kills': s['top']['kills']}}

        sw = state.get('streak_week') or {}
        streak = ({**sw, 'who': who(sw.get('steam'), sw.get('name'))} if sw.get('week') == week_key(time.time()) else None)
        live = [{'server': server, 'members': [who(k, v['name']) for k, v in o['members'].items()], 'kills': o['kills'], 'since': o['start']}
                for server, o in state.get('open', {}).items() if time.time() - o['last'] <= 3600]
        return web.json_response({'enabled': bool(state['processed'] or state['cursor']), 'bounty': bounty(state.get('bounty')),
                                  'deck': deck_view(state, who),
                                  'history': [bounty(b) for b in reversed(state.get('bounties', []))][:10],
                                  'streak': streak, 'sessions': [session_view(s) for s in reversed(state.get('sessions', []))][:12],
                                  'live': live})
