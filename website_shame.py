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


def deck_view(state, who):
    """Every year's deck of bounty cards: 54 slots each, with the cards collected so far."""
    import playing_card
    from kill_feed import hunter_of_year
    years = {}
    for year, cards in sorted(state.get('deck', {}).items(), reverse=True):
        slots = []
        for n in range(1, 55):
            card = cards.get(str(n))
            if n == 54:
                top = hunter_of_year(state, year)
                card = top and {'status': 'hunter', 'name': top['name'], 'count': top['count'], 'claimed': top['steam']}
            entry = {'n': n, 'label': playing_card.label(n), 'face': playing_card.face(n)}
            if card:
                entry.update(status=card['status'], name=card.get('name'), kills=card.get('kills'), week=card.get('week'),
                             count=card.get('count'), weapon=card.get('weapon'), distance=card.get('distance'),
                             headshot=card.get('headshot'),
                             claimed_by=who(card['claimed'], card.get('claimed_name')) if card.get('claimed') else None,
                             image=f'/api/reports/card/{year}/{n}.png?v={card_version(card)}')
            slots.append(entry)
        years[year] = {'year': year, 'slots': slots, 'collected': sum(1 for c in cards.values() if c.get('status') == 'claimed'),
                       'escaped': sum(1 for c in cards.values() if c.get('status') == 'escaped')}
    return list(years.values())


def card_version(card):
    import hashlib
    import json
    return hashlib.sha1(json.dumps(card, sort_keys=True, default=str).encode()).hexdigest()[:10]


class ReportActions:
    async def report_card(self, request):
        """One playing card from a year's bounty deck, drawn on request and cached."""
        session = self.session(request)
        await self.member(session['uid'])
        year, n = request.match_info['year'], request.match_info['n']
        if not (year.isdecimal() and len(year) == 4 and n.isdecimal() and 1 <= int(n) <= 54):
            raise web.HTTPNotFound()
        from kill_feed import hunter_of_year, service
        state = service(self.bot).state
        card = state.get('deck', {}).get(year, {}).get(n)
        photo = None
        if n == '54':
            top = hunter_of_year(state, year)
            card = top and {'n': 54, 'name': top['name'], 'count': top['count'], 'status': 'hunter'}
            if top:
                # The year's top hunter gets their Discord picture on the Red Joker.
                p = self.bot.progression.state['players'].get(str(top['steam']))
                member = self.bot.guild.get_member(p['discord_id']) if p else None
                if member:
                    from card_send import avatar
                    photo = await avatar(member)
                    card['name'] = member.display_name
        if not card:
            raise web.HTTPNotFound()
        cache = self.__dict__.setdefault('_card_cache', {})
        key = (year, n, card_version(card), bool(photo))
        if key not in cache:
            import asyncio
            import playing_card
            if len(cache) > 120:
                cache.clear()
            cache[key] = await asyncio.to_thread(playing_card.render, {**card, 'n': int(n)}, year, photo)
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
            return {'week': b['week'], 'name': b['name'], 'kills': b['kills'], 'set_at': b['set_at'],
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
