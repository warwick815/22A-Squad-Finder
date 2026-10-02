"""Cosmetic server nicknames; never changes Discord account usernames."""
import logging
import re

import discord
from discord import app_commands

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
        return 'Already correct'
    guild = ranks.bot.guild
    if member.id == guild.owner_id:
        return 'Server owner: Discord does not allow bots to rename this member'
    if not guild.me.guild_permissions.manage_nicknames or member.top_role >= guild.me.top_role:
        log.warning('Cannot update rank nickname for %s: needs Manage Nicknames and a higher bot role', member.id)
        return 'Blocked: grant Manage Nicknames and move the bot role above this member’s highest role'
    try:
        await member.edit(nick=desired, reason='22A ELO rank nickname')
    except discord.HTTPException:
        log.exception('Rank nickname update failed for %s; role and scoring updates continue', member.id)
        return 'Discord rejected nickname update; check Railway logs'
    # Preserve the untruncated base so a later shorter suffix can restore it.
    player['rank_nickname'] = {'base': base, 'applied': desired}
    ranks.save()
    return 'Updated'


async def sync_all(ranks):
    results = []
    for player in list(ranks.state['players'].values()):
        try:
            member = await ranks.bot.guild.fetch_member(player['discord_id'])
            result = await sync_nickname(ranks, member, player)
        except discord.NotFound:
            result = 'Member has left the server'
        except Exception:
            log.exception('Nickname sync failed for %s', player['discord_id'])
            result = 'Update failed; check Railway logs'
        results.append((player['discord_id'], result))
    return results


@app_commands.command(name='rank-nicknames-sync', description='Staff: update rank nicknames and report any blockers')
@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
async def nickname_sync(interaction: discord.Interaction):
    from progression import service
    ranks = service(interaction, True)
    await interaction.response.defer(ephemeral=True, thinking=True)
    async with ranks.lock:
        results = await sync_all(ranks)
    lines = [f'<@{uid}> — {result}' for uid, result in results]
    if not lines:
        lines = ['No linked players found.']
    page = ''
    for line in lines:
        if len(page) + len(line) > 1800:
            await interaction.followup.send(page, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
            page = ''
        page += line + '\n'
    if page:
        await interaction.followup.send(page, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
