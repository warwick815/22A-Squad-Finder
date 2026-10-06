"""Persistent cosmetic specialities and a live community roster."""
import asyncio
import json
import logging
import discord
from discord import app_commands
from discord.ext import tasks
from community import upsert, channel_for
from progression import service
from response_cleanup import clean_followup

GROUPS = {
 'cav':('🚙 Light Cavalry', [('recce','Recce'),('assault','Assault')]),
 'inf':('🪖 Infantry', [('at','Anti-Tank'),('aa','Anti-Air'),('recon','Recon / Sniper'),('lmg','LMG / Machine Gunner'),('rifle','Rifleman')]),
 'air':('🚁 Aviation', [('log','Logistics / Supply'),('transport','Transport / Reinforcements'),('attack','Attack'),('av','Anti-Vehicle'),('aa','Anti-Air / Close Support')]),
 'sup':('🛠️ Support & Logistics', [('medic','Medic'),('fob','FOB Builder / Engineer'),('driver','Ground Transport Driver'),('supply','Supply Driver')])}
OPTIONS={g+'_'+k:(g,label) for g,(_,items) in GROUPS.items() for k,label in items}

def validate(primary, secondary):
    if primary is not None and primary not in OPTIONS:raise ValueError('Choose a valid primary speciality.')
    if len(secondary)>3 or len(set(secondary))!=len(secondary) or not set(secondary)<=OPTIONS.keys():
        raise ValueError('Choose up to three different secondary specialities.')
    if secondary and primary is None:raise ValueError('Choose your primary speciality first.')
    if primary in secondary:raise ValueError('Your primary speciality cannot also be a secondary.')

def label(key):
    group,name=OPTIONS[key]
    return GROUPS[group][0]+' • '+name

def panel_embed():
    e=discord.Embed(title='🎖️ 22A — Choose Your Specialities',description='Show the community what you prefer to do.\nPick **one primary speciality** and up to **three secondary specialities**.\n⭐ marks your primary on the live roster.',color=0xC8102E)
    for _,(title,items) in GROUPS.items():e.add_field(name=title,value='\n'.join('• '+name for _,name in items),inline=False)
    e.add_field(name='How to use',value='**Choose Specialities** → select your primary, then any secondaries. Each selection saves immediately.\n**My Selections** shows your choices; **Clear Selections** removes your specialities.\nExisting team and general play-role preferences stay available.',inline=False)
    e.set_footer(text='22A • Cosmetic preferences, not ELO ranks or game unlocks • No squad slot limits')
    return e

class Specialities:
    def __init__(self,bot):
        self.bot=bot
        self.state=json.loads(bot.store.get('specialities_v1') or '{"roles":{},"members":{},"pages":{}}')
        self.lock=asyncio.Lock()
    def save(self):self.bot.store.set('specialities_v1',json.dumps(self.state))

    async def setup(self):
        guild=self.bot.guild
        if not guild.me.guild_permissions.manage_roles:raise ValueError('The bot needs Manage Roles.')
        roles=await guild.fetch_roles()
        for key in OPTIONS:
            name='22A Spec • '+label(key)
            role=next((r for r in roles if r.id==self.state['roles'].get(key)),None)
            if role is None:
                role=next((r for r in sorted(roles,key=lambda r:r.id) if r.name==name),None)
                if role is None:
                    role=await guild.create_role(name=name,permissions=discord.Permissions.none(),hoist=False,mentionable=False,reason='22A speciality setup')
                    roles.append(role)
                self.bot.preferences.safe(role)
                self.state['roles'][key]=role.id;self.save()
            self.bot.preferences.safe(role)

    async def sync_member(self,member):
        choice=self.state['members'][str(member.id)]
        selected=set(choice['secondary'])|({choice['primary']} if choice['primary'] else set())
        roles={k:self.bot.guild.get_role(rid) for k,rid in self.state['roles'].items()}
        if set(roles)!=set(OPTIONS) or any(r is None for r in roles.values()):
            raise ValueError('Staff must run /roles-panel to repair missing speciality roles.')
        for role in roles.values():self.bot.preferences.safe(role)
        remove=[r for k,r in roles.items() if k not in selected and r in member.roles]
        add=[r for k,r in roles.items() if k in selected and r not in member.roles]
        if remove:await member.remove_roles(*remove,atomic=True,reason='22A speciality selection')
        if add:await member.add_roles(*add,atomic=True,reason='22A speciality selection')
        choice['pending']=False;self.save()

    async def choose(self,i,kind,values):
        self.bot.validate_context(i)
        await i.response.defer(ephemeral=True,thinking=True)
        async with self.lock:
            old=self.state['members'].get(str(i.user.id),{'primary':None,'secondary':[]})
            primary=old['primary'];secondary=list(old['secondary'])
            if kind=='primary':
                primary=values[0] if values else None
                secondary=[k for k in secondary if k!=primary] if primary else []
            elif kind=='secondary':secondary=list(values)
            elif kind=='clear':primary=None;secondary=[]
            else:raise ValueError('Unknown selection.')
            validate(primary,secondary)
            self.state['members'][str(i.user.id)]={'primary':primary,'secondary':secondary,'pending':True}
            self.save()
            member=await self.bot.guild.fetch_member(i.user.id)
            try:await self.sync_member(member)
            except Exception:
                logging.getLogger('22a.specialities').exception('Speciality role sync pending for %s',member.id)
                await clean_followup(i,'Choices saved, but Discord roles could not update. Staff should check Manage Roles and role hierarchy. The bot will retry.',ephemeral=True)
                return
        await clean_followup(i,'Specialities updated. Your profile shows your choices; the roster refreshes within one minute.',ephemeral=True)

    def describe(self,member):
        choice=self.state['members'].get(str(member.id))
        if not choice or not choice['primary']:return ''
        return '\n**⭐ Primary speciality:** '+label(choice['primary'])+'\n**Secondary specialities:** '+(', '.join(label(k) for k in choice['secondary']) or 'None')+(' · role update pending' if choice.get('pending') else '')

    def roster(self,group):
        title,items=GROUPS[group]
        fields=[]
        for short,name in items:
            key=group+'_'+short;rid=self.state['roles'].get(key)
            members=sorted((m for m in self.bot.guild.members if not m.bot and any(r.id==rid for r in m.roles)),key=lambda m:(m.display_name.casefold(),m.id))
            lines=[('⭐ ' if self.state['members'].get(str(m.id),{}).get('primary')==key else '• ')+m.mention for m in members]
            chunks=[];part=''
            for line in lines:
                if len(part)+len(line)+1>900:chunks.append(part);part=''
                part+=line+'\n'
            chunks.append(part or 'No volunteers yet.')
            fields.extend((f'{name} ({len(members)})'+(' • continued' if n else ''),chunk) for n,chunk in enumerate(chunks))
        pages=[];e=discord.Embed(title=title+' — Community Roster',description='⭐ Primary speciality • Members may appear in several specialities.',color=0xC8102E)
        for name,value in fields:
            if len(e.fields)>=20 or len(e)+len(name)+len(value)>5500:
                pages.append(e);e=discord.Embed(title=title+' — Continued',color=0xC8102E)
            e.add_field(name=name,value=value,inline=False)
        pages.append(e)
        for n,e in enumerate(pages):e.set_footer(text=f'22A speciality roster {group} {n} • Refreshes every minute')
        return pages

    async def refresh(self):
        if not self.state.get('channel'):return
        channel=channel_for(self.bot.progression,self.state['channel'])
        for group in GROUPS:
            pages=self.roster(group)
            old=self.state['pages'].get(group,[]);ids=[]
            for n,e in enumerate(pages):
                message=await upsert(self.bot.progression,channel,f'speciality:{channel.id}:{group}:{n}',e)
                ids.append(message.id)
            for mid in old[len(pages):]:
                try:await channel.get_partial_message(mid).delete()
                except discord.NotFound:pass
            self.state['pages'][group]=ids;self.save()

    @tasks.loop(minutes=1)
    async def poll(self):
        if not self.bot.initialized or not self.bot.is_ready() or not self.state.get('channel'):return
        async with self.lock:
            for uid,choice in list(self.state['members'].items()):
                if not choice.get('pending'):continue
                try:await self.sync_member(await self.bot.guild.fetch_member(int(uid)))
                except discord.NotFound:
                    choice['pending']=False;self.save()
                except Exception:logging.getLogger('22a.specialities').exception('Speciality sync retry failed')
            try:await self.refresh()
            except Exception:logging.getLogger('22a.specialities').exception('Roster refresh failed')

class SafeView(discord.ui.View):
    async def interaction_check(self,i):
        i.client.validate_context(i);return True
    async def on_error(self,i,error,item):
        from bot import handle_error
        await handle_error(i,error)

class SelectionView(SafeView):
    @discord.ui.select(placeholder='Primary speciality — choose one',min_values=1,max_values=1,
        options=[discord.SelectOption(label=label(k),value=k) for k in OPTIONS])
    async def primary(self,i,select):await i.client.specialities.choose(i,'primary',select.values)
    @discord.ui.select(placeholder='Secondary specialities — up to three',min_values=0,max_values=3,
        options=[discord.SelectOption(label=label(k),value=k) for k in OPTIONS])
    async def secondary(self,i,select):await i.client.specialities.choose(i,'secondary',select.values)

class SpecialityPanel(SafeView):
    def __init__(self):super().__init__(timeout=None)
    @discord.ui.button(label='Choose Specialities',custom_id='22a:spec:choose:v1',style=discord.ButtonStyle.success)
    async def choose(self,i,button):
        await i.response.send_message('Select your primary first, then up to three secondaries. Each menu saves immediately. Category names are included in every option.',view=SelectionView(timeout=180),ephemeral=True,delete_after=180)
    @discord.ui.button(label='My Selections',custom_id='22a:spec:mine:v1')
    async def mine(self,i,button):
        await i.response.send_message(i.client.specialities.describe(i.user) or 'No specialities selected yet.',ephemeral=True,delete_after=180)
    @discord.ui.button(label='Clear Selections',custom_id='22a:spec:clear:v1',style=discord.ButtonStyle.secondary)
    async def clear(self,i,button):await i.client.specialities.choose(i,'clear',[])
    @discord.ui.button(label='Role Guide',custom_id='22a:spec:guide:v1')
    async def guide(self,i,button):await i.response.send_message(embed=panel_embed(),ephemeral=True,delete_after=180)

@app_commands.command(name='roles-panel',description='Staff: create speciality roles and publish the live roster')
@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
async def roles_panel(i:discord.Interaction,channel:discord.TextChannel):
    ranks=service(i,True)
    channel=channel_for(ranks,channel.id)
    await i.response.defer(ephemeral=True,thinking=True)
    s=i.client.specialities
    async with s.lock:
        if s.state.get('channel') and s.state['channel']!=channel.id:
            raise ValueError('The roster is already configured in another channel. Reuse that channel to refresh it.')
        await s.setup()
        s.state['channel']=channel.id;s.save()
        await s.refresh()
        await upsert(ranks,channel,f'speciality-panel:{channel.id}',panel_embed(),SpecialityPanel())
    await clean_followup(i,'Speciality roles and live roster ready in '+channel.mention,ephemeral=True)
