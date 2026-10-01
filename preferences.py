"""Cosmetic, self-assigned team and play-role preferences."""
import asyncio
import json
import discord
from discord import app_commands
from community import upsert, channel_for
from progression import service

TEAMS={'lonestar':('🔵 Lonestar (Blue)',0x3498DB),'valkyra':('🔴 Valkyra (Red)',0xE74C3C),'manticore':('🟢 Manticore (Green)',0x2ECC71)}
CLASSES={'assault':('Assault','Frontline infantry: assault rifles, pistols and grenades.'),
'medic':('Medic','Healing, revives and close-range SMG support.'),
'recon':('Recon','Spotting, intelligence and sniper/DMR engagements.'),
'support':('Support','Heavy weapons, repairs and building or destroying FOBs.'),
'driver':('Driver','Ground transport, supply deliveries and vehicle combat.'),
'pilot':('Pilot','Helicopter transport, reinforcements and aerial logistics.')}
NAMES={**{k:'22A Team • '+v[0][2:] for k,v in TEAMS.items()},**{k:'22A Play • '+v[0] for k,v in CLASSES.items()}}
KEY='preferences_v1'

class Preferences:
    def __init__(self,bot):
        self.bot=bot
        raw=bot.store.get(KEY)
        self.state=json.loads(raw) if raw else {'roles':{},'members':{}}
        self.lock=asyncio.Lock()
    def save(self):
        self.bot.store.set(KEY,json.dumps(self.state))
    def safe(self,role):
        guild=self.bot.guild
        if role.managed or role.is_default() or role.permissions.value or role >= guild.me.top_role:
            raise ValueError('Preference roles must have no server permissions and be below the bot role.')
        if any(role in channel.overwrites for channel in guild.channels):
            raise ValueError('Preference roles must not have channel permission overrides. Use separate access roles.')
    async def setup(self):
        if not self.bot.guild.me.guild_permissions.manage_roles:
            raise ValueError('The bot needs Manage Roles.')
        roles=await self.bot.guild.fetch_roles()
        for key,name in NAMES.items():
            saved=self.state['roles'].get(key)
            role=next((r for r in roles if r.id==saved),None)
            if role is None:
                matches=[r for r in roles if r.name==name]
                if matches:
                    role=min(matches,key=lambda r:r.id)
                    self.safe(role)
                else:
                    role=await self.bot.guild.create_role(name=name,permissions=discord.Permissions.none(),
                        colour=discord.Colour(TEAMS[key][1] if key in TEAMS else 0),
                        hoist=False,mentionable=False,reason='22A preference panel setup')
                    roles.append(role)
                self.state['roles'][key]=role.id
                self.save()
            self.safe(role)
    async def choose(self,interaction,group,values):
        self.bot.validate_context(interaction)
        allowed=TEAMS if group=='team' else CLASSES
        if len(values)!=len(set(values)) or not set(values)<=set(allowed) or (group=='team' and len(values)>1):
            raise ValueError('Invalid preference selection.')
        await interaction.response.defer(ephemeral=True)
        async with self.lock:
            roles=await self.bot.guild.fetch_roles()
            selected={}
            for key in allowed:
                role=next((r for r in roles if r.id==self.state['roles'].get(key)),None)
                if role is None:
                    raise ValueError('An admin must run /preferences-panel to create or repair preference roles.')
                self.safe(role)
                selected[key]=role
            member=await self.bot.guild.fetch_member(interaction.user.id)
            remove=[r for k,r in selected.items() if k not in values and r in member.roles]
            add=[r for k,r in selected.items() if k in values and r not in member.roles]
            if remove:
                await member.remove_roles(*remove,atomic=True,reason='Member updated 22A preferences')
            if add:
                await member.add_roles(*add,atomic=True,reason='Member updated 22A preferences')
            self.state['members'].setdefault(str(member.id),{})[group]=list(values)
            self.save()
        await interaction.followup.send('Preferences updated. Reopen your profile to see them.',ephemeral=True)
    def describe(self,member):
        ids={r.id for r in member.roles}
        team=[v[0] for k,v in TEAMS.items() if self.state['roles'].get(k) in ids]
        classes=[v[0] for k,v in CLASSES.items() if self.state['roles'].get(k) in ids]
        return '**Preferred team:** '+(', '.join(team) or 'Not selected')+'\n**Play roles:** '+(', '.join(classes) or 'Not selected')

class PreferenceView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    async def interaction_check(self,interaction):
        interaction.client.validate_context(interaction)
        return True
    @discord.ui.select(placeholder='Preferred team — choose one (or clear)',min_values=0,max_values=1,
        custom_id='22a:preferences:team:v1',options=[discord.SelectOption(label=v[0],value=k) for k,v in TEAMS.items()])
    async def team(self,interaction,select):
        await interaction.client.preferences.choose(interaction,'team',select.values)
    @discord.ui.select(placeholder='Preferred play roles — choose any (or clear)',min_values=0,max_values=6,
        custom_id='22a:preferences:classes:v1',options=[discord.SelectOption(label=v[0],value=k,description=v[1]) for k,v in CLASSES.items()])
    async def classes(self,interaction,select):
        await interaction.client.preferences.choose(interaction,'classes',select.values)
    async def on_error(self,interaction,error,item):
        from bot import handle_error
        await handle_error(interaction,error)


def preference_embed():
    embed=discord.Embed(title='🎮 22A — Team & Play Preferences',color=0xC8102E,
        description='Choose **one preferred team** and **as many play roles as you like** below.\n'
        'Selections assign cosmetic Discord roles and appear on your player profile. Steam linking is not required to choose.\n'
        'Clear a selection to remove it. These preferences do not change your in-game team, unlocks or progression rating.')
    embed.add_field(name='Preferred team',value='\n'.join(v[0] for v in TEAMS.values()),inline=False)
    for name,description in CLASSES.values():
        embed.add_field(name=name,value=description,inline=False)
    embed.set_footer(text='22A preferences panel v1')
    return embed

@app_commands.command(name='preferences-panel',description='Admin: create cosmetic preference roles and post the member selection panel')
@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
async def preferences_panel(interaction:discord.Interaction,channel:discord.TextChannel|None=None):
    ranks=service(interaction,True)
    await interaction.response.defer(ephemeral=True)
    dest=channel_for(ranks,(channel or interaction.channel).id)
    prefs=interaction.client.preferences
    async with prefs.lock:
        await prefs.setup()
        message=await upsert(ranks,dest,f'preferences_panel:{dest.id}',preference_embed(),PreferenceView())
    await interaction.followup.send(f'Preferences panel ready: {message.jump_url}',ephemeral=True)
