from rank_divisions import thresholds
"""Prospective level bonuses and explicitly confirmed season changes."""
import copy
import os
import uuid
from datetime import datetime, timezone
import discord
from discord import app_commands
from progression import service, rank_for, COUNTERS
from tools_stats import get_service, ROLES


def apply_levels(p, stats, pid, now=None):
    now = now or datetime.now(timezone.utc)
    if not stats or stats.get('failed') or not p['active'] or p['hold'] or p['pending']:
        return 0
    date = datetime.fromisoformat(stats['updated'].replace('Z', '+00:00'))
    if p.get('season_started') and date <= datetime.fromisoformat(p['season_started']):
        return 0
    if not -300 <= (now-date).total_seconds() <= 1800:
        return 0
    levels = {'wardog': stats['values']['wardogLevel'], **stats['levels']}
    if set(levels) != {'wardog', *ROLES} or any(type(v) is not int or v < 0 for v in levels.values()):
        return 0
    old = p.get('level_baseline')
    if not old or old['pid'] != pid:
        p['level_baseline'] = {'pid': pid, 'updated': stats['updated'], 'levels': levels.copy()}
        return 0
    if date <= datetime.fromisoformat(old['updated'].replace('Z', '+00:00')):
        return 0
    gains = {k: max(0, levels[k]-old['levels'][k]) for k in levels}
    old.update(updated=stats['updated'], levels={k: max(old['levels'][k], levels[k]) for k in levels})
    points = 2*gains['wardog'] + sum(gains[k] for k in ROLES)
    if not points:
        return 0
    before, rank = p['points2'], p['rank']
    p['points2'] += 2*points
    p['rank'] = rank_for(p['points2'], rank, thresholds(p))
    reason = f"Wardog +{gains['wardog']} levels x 2; role levels +{sum(gains[k] for k in ROLES)} x 1."
    p.setdefault('history', []).append({'at': now.isoformat(), 'kind': 'Level bonus', 'before': before,
        'after': p['points2'], 'from': rank, 'to': p['rank'], 'actor': None, 'reason': reason})
    if rank != p['rank']:
        p['pending'] = {'id': uuid.uuid4().hex, 'from': rank, 'to': p['rank'], 'before': before,
            'after': p['points2'], 'delta': dict.fromkeys(COUNTERS, 0), 'reason': reason}
    return points


def close_season(state, expected):
    if state.get('season', 1) != expected:
        raise ValueError('Season already changed; open a new confirmation.')
    archive = {'season': expected, 'closed': datetime.now(timezone.utc).isoformat(),
               'players': copy.deepcopy(state['players']), 'posted': False}
    from season_medals import podium
    archive['podium']=podium(archive['players'],expected,archive['closed'])
    state.setdefault('season_archives', []).append(archive)
    state['season'] = expected+1
    for p in state['players'].values():
        p.update(rank_rules=2, points2=0, rank=0, baseline=None, updated=None, pending=None, hold=None, season_started=archive['closed'])
        for key in ('level_baseline', 'counter_floor', 'recovery', 'cash_reward'):
            p.pop(key, None)
    return archive


def linked_pid(tools, steam, p):
    return tools.state['links'].get(str(p['discord_id'])) or (
        'd8f9bef7-7dc6-4017-8228-0fd1ce527c93' if steam == '76561197988807107' else None)


async def refresh_seasons(ranks):
    from community import channel_for, upsert
    destination = os.getenv('ELO_LEADERBOARD_CHANNEL_ID', '').strip() or os.getenv('LEADERBOARD_CHANNEL_ID', '').strip() or ranks.daily_channel_id
    for archive in ranks.state.get('season_archives', []):
        if archive['posted']:
            continue
        channel = channel_for(ranks, destination)
        players = sorted(archive['players'].values(), key=lambda p: (-p['points2'], p['discord_id']))
        lines = [f"{i}. <@{p['discord_id']}> — **{p['points2']/2:,.1f} pts**" for i, p in enumerate(players[:20], 1)]
        embed = discord.Embed(title=f"🏁 Season {archive['season']} — Final ELO Standings",
            description='\n'.join(lines) or 'No linked players.', color=0xC8102E)
        embed.set_footer(text=f"22A season archive {archive['season']}")
        embed.add_field(name='Closed', value=archive['closed'][:19]+' UTC', inline=False)
        await upsert(ranks, channel, f"season_final:{archive['season']}:{channel.id}", embed)
        archive['posted'] = True
        ranks.save()
    tools = get_service(ranks.bot)
    for steam, p in ranks.state['players'].items():
        pid = p.get('approved_tools_profile')
        if not pid or pid != linked_pid(tools, steam, p):
            continue
        stats = await tools.fetch(pid)
        apply_levels(p, stats, pid)
        ranks.save()
        try:
            await ranks.sync_player(p)
        except Exception:
            import logging
            logging.getLogger('22a.seasons').exception('Saved level update; Discord roles will retry')


class SeasonConfirm(discord.ui.View):
    def __init__(self, owner, season):
        super().__init__(timeout=120)
        self.owner, self.season = owner, season

    @discord.ui.button(label='Archive season and reset ratings', style=discord.ButtonStyle.danger)
    async def confirm(self, interaction, button):
        ranks = service(interaction, True)
        if interaction.user.id != self.owner:
            raise ValueError('Only the requesting admin can confirm.')
        await interaction.response.defer(ephemeral=True)
        async with ranks.lock:
            close_season(ranks.state, self.season)
            ranks.save()
            for p in ranks.state['players'].values():
                try:
                    await ranks.sync_player(p)
                except Exception:
                    pass
        await interaction.followup.send('Season archived. New season: Private / 0. Final standings post on the next check. Links and historical records preserved.', ephemeral=True)
        self.stop()

    async def on_error(self, interaction, error, item):
        from bot import handle_error
        await handle_error(interaction, error)


@app_commands.command(name='season-end', description='Admin: preview archiving this season and resetting ratings')
@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
async def season_end(interaction: discord.Interaction):
    ranks = service(interaction, True)
    season = ranks.state.get('season', 1)
    await interaction.response.send_message(f'Close Season {season} and start Season {season+1}? All ratings reset to 0 / Private. Full prior records are archived; top 20 final standings are posted. Fresh baselines exclude old results. Links and manual pauses stay saved. Season 2 rules use 25% higher thresholds and future cash-earned bonuses.', view=SeasonConfirm(interaction.user.id, season), ephemeral=True)


@app_commands.command(name='approve-tools', description='Admin: approve a public profile after checking ownership; enable future level bonuses')
@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
async def approve_tools(interaction: discord.Interaction, member: discord.Member):
    ranks = service(interaction, True)
    await interaction.response.defer(ephemeral=True)
    async with ranks.lock:
        match = ranks.find(member.id)
        if not match:
            raise ValueError('Member must link Steam first.')
        steam, p = match
        tools = get_service(ranks.bot)
        pid = linked_pid(tools, steam, p)
        if not pid:
            raise ValueError('Member must Connect Tools Profile first.')
        if p.get('approved_tools_profile'):
            if p['approved_tools_profile'] != pid:
                raise ValueError('Different profile previously approved; identity needs manual review.')
            await interaction.followup.send('Already approved; baseline preserved.', ephemeral=True)
            return
        if any(x.get('approved_tools_profile') == pid for x in ranks.state['players'].values() if x is not p):
            raise ValueError('Profile already approved for another member.')
        stats = await tools.fetch(pid)
        if not stats or stats.get('failed'):
            raise ValueError('Public stats unavailable; try later.')
        p['approved_tools_profile'] = pid
        apply_levels(p, stats, pid)
        ranks.save()
    await interaction.followup.send(f'Approved https://wardogs.tools/player/{pid}. First fresh eligible snapshot is baseline only; future gains earn +2 per Wardog level and +1 per role level. Approval relies on your ownership check.', ephemeral=True)


COMMANDS = (season_end, approve_tools)
