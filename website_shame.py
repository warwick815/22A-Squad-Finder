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


class ReportActions:
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
                                  'history': [bounty(b) for b in reversed(state.get('bounties', []))][:10],
                                  'streak': streak, 'sessions': [session_view(s) for s in reversed(state.get('sessions', []))][:12],
                                  'live': live})
