"""Community history, persistent standings, weekly reports and restricted admin UI."""
import os
from datetime import datetime, timezone, timedelta
import discord
from discord import app_commands
from progression import service, daily_embed, rank_for, RANKS, COUNTERS


def history_embed(player, page=1):
    events = list(reversed(player.get('history', [])))
    pages = max(1, (len(events)+4)//5)
    page = max(1, min(page, pages))
    embed = discord.Embed(title='📜 22A Rating History', color=0xC8102E,
        description=f"<@{player['discord_id']}> · Current rating **{player['points2']/2:,.1f}**\nRecorded from this update onward. Changes represent feed snapshots, not individual matches.")
    for event in events[(page-1)*5:page*5]:
        change = (event['after']-event['before'])/2
        detail = f"{event['before']/2:,.1f} → **{event['after']/2:,.1f}** ({change:+,.1f})"
        if event['kind'] == 'results':
            detail += '\n' + ' · '.join(f"{event['delta'][k]} {k} ({event['delta'][k]*event['weights'][k]:+g})" for k in COUNTERS)
            detail += '\nRating has a zero floor.'
        else:
            detail += (f"\nAdmin <@{event['actor']}>: " if event.get("actor") else f"\n{event['kind']}: ") + discord.utils.escape_markdown(discord.utils.escape_mentions(event['reason']))
        detail += f"\n{RANKS[event['from']][0]} → {RANKS[event['to']][0]}"
        embed.add_field(name=event['at'][:19].replace('T',' ')+' UTC', value=detail[:1024], inline=False)
    if not events:
        embed.add_field(name='No recorded changes yet', value='Your existing rating is preserved. New results will appear here.')
    embed.set_footer(text=f'Page {page}/{pages} • /rating-history page:2 for older entries')
    return embed


async def show_history(interaction, member=None, page=1):
    ranks = service(interaction)
    target = member or interaction.user
    if target.id != interaction.user.id:
        service(interaction, True)
    match = ranks.find(target.id)
    if not match:
        raise ValueError('No linked account found. Use /link first.')
    await interaction.response.send_message(embed=history_embed(match[1], page), ephemeral=True,
        allowed_mentions=discord.AllowedMentions.none())


def week_window(now):
    end = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return end-timedelta(days=7), end


def weekly_embed(players, start, end, tracking):
    totals = dict.fromkeys(COUNTERS, 0)
    gains = []
    promotions = demotions = corrections = 0
    for p in players:
        gain = 0
        for e in p.get('history', []):
            if not start <= datetime.fromisoformat(e['at']) < end:
                continue
            if e['kind'] != 'results':
                corrections += e['kind'] == 'Adjust rating'
                if e['kind'] == 'Level bonus':
                    gain += e['after']-e['before']
                    promotions += e['to'] > e['from']
                continue
            gain += e['after']-e['before']
            for k in COUNTERS:
                totals[k] += e['delta'][k]
            promotions += e['to'] > e['from']
            demotions += e['to'] < e['from']
        if gain:
            gains.append((gain, p['discord_id']))
    gains.sort(key=lambda x: (-x[0], x[1]))
    embed = discord.Embed(title='📣 22A Weekly Community Report', color=0xC8102E,
        description=f"**{start:%d %b} – {end-timedelta(days=1):%d %b %Y} (UTC)**\nLinked current server members • Results recorded during this week, including delayed feed updates.")
    embed.add_field(name='Team results', value=f"🏆 {totals['wins']:,} player-wins · {totals['losses']:,} player-losses\nThese are player totals, not unique matches.", inline=False)
    embed.add_field(name='Combat', value=f"{totals['kills']:,} kills · {totals['deaths']:,} deaths", inline=False)
    embed.add_field(name='Biggest rating gains', value='\n'.join(f"{i}. <@{uid}> **{gain/2:+,.1f}**" for i,(gain,uid) in enumerate([g for g in gains if g[0]>0][:10],1)) or 'No positive gains recorded.', inline=False)
    embed.add_field(name='Rank changes', value=f'{promotions} promotion events · {demotions} demotion events\n{corrections} admin corrections excluded from performance totals.', inline=False)
    if tracking > start:
        embed.add_field(name='Partial tracking period', value=f'History recording began {tracking:%d %b %Y %H:%M} UTC. Earlier results are unavailable.', inline=False)
    embed.set_footer(text=f'22A weekly {end.date()}')
    return embed


def channel_for(ranks, channel_id):
    channel = ranks.bot.get_channel(int(channel_id))
    if not isinstance(channel, discord.TextChannel) or channel.guild.id != ranks.bot.cfg.guild_id:
        raise ValueError('Choose a text channel in this server.')
    perms = channel.permissions_for(channel.guild.me)
    if not all(getattr(perms,p) for p in ('view_channel','send_messages','embed_links','read_message_history')):
        raise ValueError('Bot needs View Channel, Send Messages, Embed Links and Read Message History.')
    return channel


async def upsert(ranks, channel, key, embed, view=None):
    saved = ranks.bot.store.get(key)
    message = None
    if saved:
        try:
            message = await channel.fetch_message(int(saved))
        except discord.NotFound:
            pass
    if message is None:
        async for candidate in channel.history(limit=100):
            if candidate.author.id == ranks.bot.user.id and candidate.embeds and candidate.embeds[0].footer.text == embed.footer.text:
                message = candidate
                break
    if message:
        await message.edit(embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())
    else:
        message = await channel.send(embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())
    ranks.bot.store.set(key,message.id)
    return message


async def refresh(ranks):
    now = datetime.now(timezone.utc)
    store = ranks.bot.store
    tracking = store.get('community_tracking_start')
    if not tracking:
        tracking = now.isoformat()
        store.set('community_tracking_start', tracking)
    players = []
    for p in ranks.state['players'].values():
        member = ranks.bot.guild.get_member(p['discord_id'])
        if member is None:
            try:
                member = await ranks.bot.guild.fetch_member(p['discord_id'])
            except discord.NotFound:
                continue
        if not member.bot:
            players.append(p)
    raw = os.getenv('ELO_LEADERBOARD_CHANNEL_ID','').strip() or os.getenv('LEADERBOARD_CHANNEL_ID','').strip()
    if raw:
        try:
            channel = channel_for(ranks,raw)
            embed = daily_embed(players,now.date(),now)
            embed.title = f"🏆 22A Season {ranks.state.get('season', 1)} — ELO Player Standings"
            embed.set_footer(text='22A live ELO standings • Refreshes every 5 minutes • Community rating')
            await upsert(ranks,channel,f'elo_board:{channel.id}',embed)
        except Exception:
            import logging
            logging.getLogger('22a.community').exception('Live ELO board update failed')
    start,end = week_window(now)
    # Monday 18:00 UTC; if offline, publish on the next check that week.
    if now < end+timedelta(hours=18) or store.get('weekly_last') == end.isoformat():
        return
    if datetime.fromisoformat(tracking) >= end:
        return
    channel = channel_for(ranks,os.getenv('WEEKLY_REPORT_CHANNEL_ID','').strip() or ranks.channel_id)
    embed = weekly_embed(players,start,end,datetime.fromisoformat(tracking))
    await upsert(ranks,channel,f'weekly_report:{end.date()}:{channel.id}',embed)
    store.set('weekly_last',end.isoformat())


class AdminModal(discord.ui.Modal):
    member_id = discord.ui.TextInput(label='Discord member ID', min_length=1,max_length=20)
    reason = discord.ui.TextInput(label='Reason (recorded)', min_length=3,max_length=200)
    def __init__(self, action):
        super().__init__(title=f'22A Admin: {action}')
        self.action=action
        if action == 'Adjust rating':
            self.amount=discord.ui.TextInput(label='Points adjustment (e.g. 50 or -25)',max_length=8)
            self.add_item(self.amount)

    async def on_submit(self, interaction):
        ranks=service(interaction,True)
        await interaction.response.defer(ephemeral=True)
        async with ranks.lock:
            if not str(self.member_id).isdigit():
                raise ValueError('Enter a numeric Discord member ID.')
            match=ranks.find(int(str(self.member_id)))
            if not match:
                raise ValueError('Member is not linked.')
            steam,p=match
            before,old=p['points2'],p['rank']
            if p['pending']:
                raise ValueError('A rank announcement is pending. Try after the next successful update.')
            if self.action == 'Pause':
                p['active']=False
            elif self.action == 'Resume':
                if p['active'] and not p['hold']:
                    raise ValueError('Already active; no baseline changed.')
                updated,rows=await ranks.fetch()
                if steam not in rows:
                    raise ValueError('Player absent from feed; try later.')
                p.update(active=True,hold=None,baseline=rows[steam],updated=updated)
            else:
                try:
                    amount=int(str(self.amount))
                except ValueError:
                    raise ValueError('Enter whole points between -10000 and 10000.')
                if not -10000 <= amount <= 10000 or not amount:
                    raise ValueError('Enter a nonzero adjustment between -10000 and 10000.')
                p['points2']=max(0,before+2*amount)
                p['rank']=rank_for(p['points2'],old)
                if p['rank'] != old:
                    import uuid
                    p['pending']={'id':uuid.uuid4().hex,'from':old,'to':p['rank'],'before':before,'after':p['points2'],
                                  'delta':dict.fromkeys(COUNTERS,0),'reason':str(self.reason)}
            p.setdefault('history',[]).append({'at':datetime.now(timezone.utc).isoformat(),'kind':self.action,
                'before':before,'after':p['points2'],'from':old,'to':p['rank'],'actor':interaction.user.id,'reason':str(self.reason)})
            ranks.save()
            try:
                await ranks.sync_player(p)
            except Exception:
                await interaction.followup.send('Saved. Discord role/announcement update will retry on the next poll.',ephemeral=True)
                return
        await interaction.followup.send(f"Saved: {self.action}. Rating {p['points2']/2:,.1f}. Resume starts a fresh baseline; paused results are excluded.",ephemeral=True)

    async def on_error(self,interaction,error):
        from bot import handle_error
        await handle_error(interaction,error)


class AdminView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self,interaction):
        service(interaction,True)
        return True

    @discord.ui.button(label='Status',custom_id='22a:admin:status')
    async def status(self,interaction,button):
        ranks=service(interaction,True)
        players=list(ranks.state['players'].values())
        panel=getattr(ranks.bot,'player_panel',None)
        await interaction.response.send_message(f"Linked: {len(players)} · Paused: {sum(not p['active'] for p in players)} · Held: {sum(bool(p['hold']) for p in players)}\nLast successful feed: {getattr(panel,'updated',None) or 'Not yet received'}\nPending role announcements: {sum(bool(p['pending']) for p in players)}",ephemeral=True)

    @discord.ui.button(label='Pause player',custom_id='22a:admin:pause')
    async def pause(self,interaction,button):
        await interaction.response.send_modal(AdminModal('Pause'))

    @discord.ui.button(label='Resume player',custom_id='22a:admin:resume')
    async def resume(self,interaction,button):
        await interaction.response.send_modal(AdminModal('Resume'))

    @discord.ui.button(label='Adjust rating',custom_id='22a:admin:adjust')
    async def adjust(self,interaction,button):
        await interaction.response.send_modal(AdminModal('Adjust rating'))

    @discord.ui.button(label='End Season',emoji='🏁',style=discord.ButtonStyle.danger,custom_id='22a:admin:season-end:v1')
    async def end_season(self,interaction,button):
        from seasons import season_end
        await season_end.callback(interaction)

    async def on_error(self,interaction,error,item):
        from bot import handle_error
        await handle_error(interaction,error)


@app_commands.command(name='rating-history',description='View recorded rating changes; admins may inspect another member')
@app_commands.guild_only()
async def rating_history(interaction:discord.Interaction,member:discord.Member|None=None,page:app_commands.Range[int,1,100000]=1):
    await show_history(interaction,member,page)


@app_commands.command(name='admin-panel',description='Post the restricted 22A progression admin panel')
@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
async def admin_panel(interaction:discord.Interaction,channel:discord.TextChannel|None=None):
    ranks=service(interaction,True)
    await interaction.response.defer(ephemeral=True)
    channel=channel_for(ranks,(channel or interaction.channel).id)
    embed=discord.Embed(title='🛠️ 22A Admin Panel',description='Manage Server permission required for every action.\nPause/resume scoring or adjust a rating with an audit reason.\nUse /rating-history member: to inspect a player. Resume excludes paused results.',color=0xC8102E)
    embed.set_footer(text='22A admin panel v1')
    async with ranks.lock:
        message=await upsert(ranks,channel,f'admin_panel:{channel.id}',embed,AdminView())
    await interaction.followup.send(f'Admin panel ready: {message.jump_url}',ephemeral=True)

COMMANDS=(rating_history,admin_panel)
