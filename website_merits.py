"""Armoury: members' Merits balance, how to earn them, and buying a booster (one a day)."""
import logging

import discord
from aiohttp import web

import merits
import patch_shop

log = logging.getLogger('22a.merits')


async def announce(bot, member, item_id, message):
    """A short Discord post when a booster goes on, in the field reports channel."""
    try:
        feed = getattr(bot, 'kill_feed', None)
        channel = feed.channel() if feed else None
        if channel is None:
            return
        item = merits.ITEMS[item_id]
        embed = discord.Embed(title=f"⚡ {item['name']} activated", colour=0xA6E35A,
                              description=f"<@{member.id}> spent {item['cost']} Merits. {message}")
        embed.set_footer(text='22A Armoury · Merits are earned in game, never bought')
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
    except Exception:
        log.exception('Could not post the booster notice')


class MeritActions:
    def armoury_view(self, member, feed):
        state = self.bot.progression.state
        return {**merits.view(state, member.id, feed), 'patches': patch_shop.view(state, member.id, member)}

    async def merits_status(self, request):
        session = self.session(request)
        member = await self.member(session['uid'])
        feed = getattr(getattr(self.bot, 'kill_feed', None), 'state', None)
        ranks = self.bot.progression
        async with ranks.lock:
            patch_shop.sync_originals(ranks.state, self.bot.guild)  # 22A Originals follows the Discord role.
            ranks.save()
        return web.json_response(self.armoury_view(member, feed))

    async def merits_buy(self, request):
        session = self.session(request, write=True)
        member = await self.member(session['uid'])
        body = await self.body(request)
        if body.get('confirm') is not True:
            raise web.HTTPBadRequest(reason='Confirm the purchase first.')
        ranks = self.bot.progression
        feed = getattr(getattr(self.bot, 'kill_feed', None), 'state', None)
        item, patch = body.get('item'), body.get('patch')
        async with ranks.lock:
            try:
                if isinstance(patch, str):
                    message = patch_shop.buy(ranks.state, member.id, patch)
                else:
                    message = merits.buy(ranks.state, member.id, item, feed)
            except ValueError as error:
                raise web.HTTPConflict(reason=str(error)) from None
            ranks.save()
        log.info('Member %s bought %s from the Armoury', member.id, patch or item)
        if not isinstance(patch, str):
            await announce(self.bot, member, item, message)
        return web.json_response({'message': message, **self.armoury_view(member, feed)})
