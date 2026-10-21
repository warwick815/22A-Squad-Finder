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
