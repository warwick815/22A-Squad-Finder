"""Cosmetic server nicknames; never changes Discord account usernames."""
import logging
import re

import discord

ABBREVIATIONS = ('PVT', 'LCPL', 'CPL', 'SGT', 'SSGT', 'WO2', 'WO1')
SUFFIX = re.compile(r'(?:\s*\[(?:PVT|LCPL|CPL|SGT|SSGT|WO2|WO1)\])+$', re.I)
log = logging.getLogger('22a.nicknames')


def ranked_name(base, rank):
    suffix = f' [{ABBREVIATIONS[rank]}]'
    return base[:32-len(suffix)].rstrip() + suffix


async def sync_nickname(ranks, member, player):
    # A paused account keeps its rank and nickname; scoring status is independent.
    current = member.display_name
    previous = player.get('rank_nickname', {})
    base = previous.get('base') if current == previous.get('applied') else None
    base = base or SUFFIX.sub('', current).rstrip() or member.name
    desired = ranked_name(base, player['rank'])
    if member.nick == desired:
        return
    guild = ranks.bot.guild
    if member.id == guild.owner_id:
        return  # Discord never allows bots to rename the server owner.
    if not guild.me.guild_permissions.manage_nicknames or member.top_role >= guild.me.top_role:
        log.warning('Cannot update rank nickname for %s: needs Manage Nicknames and a higher bot role', member.id)
        return
    try:
        await member.edit(nick=desired, reason='22A ELO rank nickname')
    except discord.HTTPException:
        log.exception('Rank nickname update failed for %s; role and scoring updates continue', member.id)
        return
    # Preserve the untruncated base so a later shorter suffix can restore it.
    player['rank_nickname'] = {'base': base, 'applied': desired}
    ranks.save()
