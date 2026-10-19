"""Members-only Clips page data: Medal clips collected from the Discord clips channel."""
from aiohttp import web

from clips import medal_id


def _staff(member):
    return bool(getattr(getattr(member, 'guild_permissions', None), 'manage_guild', False))


class ClipActions:
    async def clips_status(self, request):
        session = self.session(request)
        member = await self.member(session['uid'])
        service = getattr(self.bot, 'clips', None)
        if not service:
            return web.json_response({'enabled': False, 'clips': [], 'staff': _staff(member)})
        staff = _staff(member)
        rows = []
        for clip in sorted(service.state['clips'].values(), key=lambda c: c['posted'], reverse=True):
            if clip.get('hidden') and not staff:
                continue
            author = self.bot.guild.get_member(int(clip['author']))
            rows.append({'id': clip['id'], 'url': clip['url'], 'medal': clip.get('medal') or medal_id(clip['url']),
                         'title': clip.get('title'), 'thumb': clip.get('thumb'), 'player': clip.get('player'),
                         'posted': clip['posted'], 'votes': clip.get('votes', 0), 'hidden': bool(clip.get('hidden')),
                         'author': {'id': clip['author'], 'name': getattr(author, 'display_name', None) or clip.get('author_name') or 'Former member',
                                    'avatar': str(getattr(getattr(author, 'display_avatar', None), 'url', '') or '')}})
        return web.json_response({'enabled': True, 'staff': staff, 'clips': rows[:300]})

    async def clips_action(self, request):
        session = self.session(request, write=True)
        member = await self.member(session['uid'])
        if not _staff(member):
            raise web.HTTPForbidden(reason='Only staff can hide or show clips.')
        service = getattr(self.bot, 'clips', None)
        if not service:
            raise web.HTTPBadRequest(reason='Clips are not switched on.')
        body = await self.body(request)
        if body.get('action') not in ('hide', 'show') or not isinstance(body.get('id'), str):
            raise web.HTTPBadRequest(reason='Choose a clip to hide or show.')
        try:
            service.set_hidden(body['id'], body['action'] == 'hide')
        except ValueError as e:
            raise web.HTTPBadRequest(reason=str(e)) from None
        return web.json_response({'message': 'Clip hidden from the website.' if body['action'] == 'hide' else 'Clip visible again.'})
