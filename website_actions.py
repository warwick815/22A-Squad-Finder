"""Authenticated website actions, sharing bot locks and durable state."""
import asyncio
import hashlib
import json
import os
import secrets
import time
import uuid
from datetime import datetime, timezone

from aiohttp import web
import discord
from progression import rank_for, COUNTERS
from seasons import close_season
from tools_stats import get_service, profile_id


class HQActions:
    async def body(self, request):
        try:
            data = await request.json()
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except (ValueError, TypeError):
            raise web.HTTPBadRequest(reason='Invalid request. Please reopen the form.') from None

    async def staff_member(self, request, write=False):
        session = self.session(request, write=write)
        member = await self.member(session['uid'])
        if not member.guild_permissions.manage_guild:
            raise web.HTTPForbidden(reason='Manage Server permission is required for staff tools.')
        return session, member

    def audit(self, actor, action, target, reason):
        entries = json.loads(self.bot.store.get('website_audit_v1') or '[]')
        entries.append({'at': datetime.now(timezone.utc).isoformat(), 'actor': str(actor),
                        'action': action, 'target': str(target), 'reason': reason})
        self.bot.store.set('website_audit_v1', json.dumps(entries[-500:]))

    async def staff_status(self, request):
        await self.staff_member(request)
        tools = get_service(self.bot)
        players = []
        for steam, p in self.bot.progression.state['players'].items():
            member = self.bot.guild.get_member(p['discord_id'])
            players.append({'id': str(p['discord_id']), 'name': member.display_name if member else 'Former member',
                'steam': steam, 'verified': bool(p.get('steam_verified')), 'rating': p['points2']/2,
                'active': p['active'], 'hold': p.get('hold'), 'pending': bool(p.get('pending')),
                'updated': p.get('updated'), 'tools': tools.state['links'].get(str(p['discord_id'])) or
                    p.get('approved_tools_profile'), 'approved': bool(p.get('approved_tools_profile'))})
        api = getattr(self.bot, 'clan_api', None)
        return web.json_response({'players': players, 'season': self.bot.progression.state.get('season', 1),
            'api_issue': bool(getattr(api, 'error', None)),
            'updated': self.bot.player_panel.updated,
            'audit': json.loads(self.bot.store.get('website_audit_v1') or '[]')[-100:][::-1]})

    def fingerprint(self, command):
        ranks = self.bot.progression
        if command['action'] == 'end-season':
            value = {'season': ranks.state.get('season', 1)}
        else:
            found = ranks.find(int(command['target']))
            value = {'player': found[1], 'tools_link': get_service(self.bot).state['links'].get(command['target'])} if found else None
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    async def staff_prepare(self, request):
        session, actor = await self.staff_member(request, write=True)
        command = await self.body(request)
        action = command.get('action')
        if action not in ('pause', 'resume', 'adjust', 'tools-link', 'end-season'):
            raise web.HTTPBadRequest(reason='Unknown staff action.')
        reason = command.get('reason', '')
        if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 200:
            raise web.HTTPBadRequest(reason='Enter a reason between 3 and 200 characters.')
        clean = {'action': action, 'reason': reason.strip()}
        if action == 'end-season':
            season = self.bot.progression.state.get('season', 1)
            clean['season'] = season
            summary = f'Archive Season {season} and start Season {season+1}. All ratings become 0 / Private. Steam links and history remain. Manual pauses remain. This cannot be undone from the website.'
        else:
            target = str(command.get('target', ''))
            if not target.isdecimal() or len(target) > 20 or not self.bot.progression.find(int(target)):
                raise web.HTTPBadRequest(reason='Select a linked member.')
            target_member = await self.member(int(target))
            clean['target'] = target
            summary = f'{action.replace("-", " ").title()} for {target_member.display_name}.'
            if action == 'adjust':
                amount = command.get('amount')
                if type(amount) is not int or not -10000 <= amount <= 10000 or not amount:
                    raise web.HTTPBadRequest(reason='Enter a nonzero whole-point adjustment from -10000 to 10000.')
                clean['amount'] = amount
                summary += f' Change rating by {amount:+d} points (zero floor). Rank roles and announcements may change.'
            if action == 'resume':
                summary += ' Requires a fresh source snapshot. Paused results are excluded by starting a new baseline.'
            if action == 'tools-link':
                try:
                    clean['pid'] = profile_id(command.get('url', ''))
                except (ValueError, AttributeError):
                    raise web.HTTPBadRequest(reason='Enter a valid public WARDOGS Tools player URL.') from None
                if command.get('ownership_checked') is not True:
                    raise web.HTTPBadRequest(reason='Verify the player owns this Tools profile before approving it.')
                summary += ' Replace the Tools link and approve future level gains. Existing levels are a new baseline, with no retroactive points.'
        token = secrets.token_urlsafe(32)
        # One outstanding confirmation per session, bound to the exact reviewed command.
        session['confirmation'] = {'token': token, 'command': clean, 'fingerprint': self.fingerprint(clean),
                                   'expires': time.monotonic()+120}
        return web.json_response({'token': token, 'summary': summary, 'reason': reason})

    async def staff_confirm(self, request):
        session, actor = await self.staff_member(request, write=True)
        body = await self.body(request)
        pending = session.get('confirmation')
        if not pending or pending['expires'] <= time.monotonic() or not secrets.compare_digest(
                str(body.get('token', '')), pending['token']):
            raise web.HTTPBadRequest(reason='Confirmation expired. Review the action again.')
        del session['confirmation']
        command = pending['command']; action = command['action']
        ranks = self.bot.progression
        async with ranks.lock:
            if pending['fingerprint'] != self.fingerprint(command):
                raise web.HTTPConflict(reason='The player or season changed since your preview. Review again.')
            if action == 'end-season':
                close_season(ranks.state, command['season'])
                ranks.save()
                self.audit(actor.id, action, command['season'], command['reason'])
                # Normal poll retries role/nickname sync and posts the archived standings.
                return web.json_response({'message': 'Season archived; ratings reset. Discord roles and final standings will update on the next poll.'})
            steam, p = ranks.find(int(command['target']))
            if p.get('pending'):
                raise web.HTTPConflict(reason='A rank update is pending. Wait for the next bot update.')
            before, rank = p['points2'], p['rank']
            if action == 'pause':
                p['active'] = False
            elif action == 'resume':
                if p['active'] and not p.get('hold'):
                    raise web.HTTPConflict(reason='Player is already active. No baseline changed.')
                updated, rows = await ranks.fetch()
                if steam not in rows:
                    raise web.HTTPConflict(reason='Player is missing from fresh source data. Rating and review status preserved.')
                from wduk_api import apply_source
                source_time = getattr(ranks, 'source_times', {}).get(steam, updated)
                source = getattr(ranks, 'source_overrides', {}).get(steam, p.get('rating_source'))
                apply_source(p, rows[steam], source_time, source)
                p.update(active=True, hold=None, baseline=rows[steam], updated=source_time)
                p.pop('recovery', None)
            elif action == 'adjust':
                p['points2'] = max(0, before+2*command['amount'])
                p['rank'] = rank_for(p['points2'], rank)
                if p['rank'] != rank:
                    p['pending'] = {'id': uuid.uuid4().hex, 'from': rank, 'to': p['rank'],
                        'before': before, 'after': p['points2'], 'delta': dict.fromkeys(COUNTERS, 0), 'reason': command['reason']}
            elif action == 'tools-link':
                tools = get_service(self.bot); pid = command['pid']
                if any(x.get('approved_tools_profile') == pid for x in ranks.state['players'].values() if x is not p):
                    raise web.HTTPConflict(reason='That Tools profile is already approved for another player.')
                stats = await tools.fetch(pid)
                if not stats or stats.get('failed'):
                    raise web.HTTPConflict(reason='Could not fetch this Tools profile. Link unchanged.')
                tools.state['links'][str(p['discord_id'])] = pid; tools.save()
                p['approved_tools_profile'] = pid
                p.pop('level_baseline', None)
            p.setdefault('history', []).append({'at': datetime.now(timezone.utc).isoformat(),
                'kind': {'adjust':'Adjust rating','pause':'Pause','resume':'Resume','tools-link':'Tools link'}[action],
                'before': before, 'after': p['points2'], 'from': rank, 'to': p['rank'],
                'actor': actor.id, 'reason': command['reason']})
            ranks.save()
            self.audit(actor.id, action, p['discord_id'], command['reason'])
        return web.json_response({'message': 'Saved. Discord rank roles and announcements will synchronise on the next bot update.'})

    def squad_list(self, member):
        result = []
        for room in getattr(self.bot, 'rooms', {}).values():
            if room.status != 'active' or (room.private and member.id not in room.members):
                continue
            if not room.private and getattr(self.bot, 'lfg', None) and not self.bot.lfg.permissions_for(member).view_channel:
                continue
            members = [self.bot.guild.get_member(uid) for uid in room.members]
            present = set()
            for m in members:
                if m:
                    pref = self.bot.specialities.state['members'].get(str(m.id), {})
                    present.update(pref.get('secondary', []))
                    if pref.get('primary'): present.add(pref['primary'])
            result.append({'id':room.id, 'name':room.name, 'game':room.game, 'count':len(room.members),
                'limit':room.limit, 'locked':room.locked, 'joined':member.id in room.members,
                'members':[m.display_name if m else 'Member unavailable' for m in members],
                'suggested_roles':[name for key, name in [('sup_medic','Medic'),('inf_at','Anti-Tank'),('sup_driver','Driver')] if key not in present],
                'voice_url':f'https://discord.com/channels/{self.bot.cfg.guild_id}/{room.voice_id}' if member.id in room.members and room.voice_id else None})
        return result

    async def squad_action(self, request):
        session = self.session(request, write=True)
        member = await self.member(session['uid']); data = await self.body(request)
        action = data.get('action')
        if action not in ('join', 'leave'):
            raise web.HTTPBadRequest(reason='Choose join or leave.')
        async with self.bot.mutation:
            room = self.bot.rooms.get(str(data.get('room', '')))
            if not room or room.status != 'active' or (room.private and member.id not in room.members):
                raise web.HTTPNotFound(reason='Squad unavailable.')
            if not room.private and not self.bot.lfg.permissions_for(member).view_channel:
                raise web.HTTPForbidden(reason='You need access to the squad channel.')
            try:
                if action == 'join': room.join(member.id)
                else: room.leave(member.id)
            except ValueError as error:
                raise web.HTTPConflict(reason=str(error)) from None
            self.bot.store.save(room)
            try:
                await self.bot.reconcile(room)
            except discord.HTTPException:
                return web.json_response({'message':'Squad membership saved; Discord channel access is pending and will retry.'})
        return web.json_response({'message':'Squad membership updated. Use Open voice to connect in Discord.'})

    async def share_profile(self, request):
        session = self.session(request, write=True)
        member = await self.member(session['uid'])
        data = await self.body(request)
        if data.get('confirm') is not True:
            raise web.HTTPBadRequest(reason='Confirm sharing your profile to #wardogs-chat.')
        panel = self.bot.player_panel
        if not hasattr(panel, 'share_lock'): panel.share_lock = asyncio.Lock()
        async with panel.share_lock:
            raw = os.getenv('PROFILE_SHARE_CHANNEL_ID', '').strip()
            matches = [c for c in self.bot.guild.text_channels if c.name == 'wardogs-chat']
            channel = self.bot.guild.get_channel(int(raw)) if raw.isdecimal() else (matches[0] if len(matches)==1 else None)
            if not isinstance(channel, discord.TextChannel) or channel.guild.id != self.bot.cfg.guild_id:
                raise web.HTTPConflict(reason='Staff must configure the wardogs-chat sharing channel.')
            for subject in (member, self.bot.guild.me):
                perms = channel.permissions_for(subject)
                if not perms.view_channel or not perms.send_messages:
                    raise web.HTTPForbidden(reason='You and the bot need access to post in wardogs-chat.')
            if not channel.permissions_for(self.bot.guild.me).embed_links:
                raise web.HTTPForbidden(reason='The bot needs Embed Links in wardogs-chat.')
            key = f'profile_share_last:{member.id}'; now = time.time()
            if now-float(self.bot.store.get(key) or 0) < 300:
                raise web.HTTPTooManyRequests(reason='Profiles can be shared once every five minutes across the website and Discord.')
            match = self.bot.progression.find(member.id)
            if not match: raise web.HTTPConflict(reason='Link Steam in Discord first.')
            from player_panel import profile_embed
            steam, player = match
            embed = profile_embed(member, steam, player, panel.rows.get(steam), panel.updated)
            embed.description += '\n\n' + self.bot.preferences.describe(member)
            tools = self.player(member).get('tools')
            if tools:
                values = tools['values']
                embed.add_field(name='WARDOGS Tools — cached snapshot', inline=False,
                    value=f"Level {values['wardogLevel']} · XP {values['xp']:,} · Cash ${values['cash']:,}\n"
                          f"Source updated: {tools['updated']}\nMember-provided profile; ownership not independently verified.")
            embed.set_footer(text='22A • Shared by the player via Member HQ • Snapshot at time of sharing')
            self.bot.store.set(key, str(now))
            message = await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        return web.json_response({'message':'Profile shared to #wardogs-chat.', 'url':message.jump_url})
