"""Display-only importer for public wardogs.tools profiles; never awards rating."""
import asyncio
import json
import re
import time
import logging
from datetime import datetime, timezone
from html.parser import HTMLParser
import aiohttp
import discord

URL_PATTERN=r'https://wardogs\.tools/player/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})/?'
ROLES={'infantry':'Assault','medic':'Medic','recon':'Recon','support':'Support','driver':'Driver','pilot':'Pilot'}
class Scripts(HTMLParser):
    def __init__(self):
        super().__init__();self.inside=False;self.scripts=[]
    def handle_starttag(self,tag,attrs):
        if tag=='script':self.inside=True
    def handle_endtag(self,tag):
        if tag=='script':self.inside=False
    def handle_data(self,data):
        if self.inside:self.scripts.append(data)

def profile_id(url):
    m=re.fullmatch(URL_PATTERN,url.strip())
    if not m:raise ValueError('Paste a public https://wardogs.tools/player/… profile link, not the stats-card link.')
    return m[1].lower()

def parse_profile(html):
    parser=Scripts();parser.feed(html)
    chunks=[]
    for script in parser.scripts:
        m=re.fullmatch(r'self\.__next_f\.push\((.*)\)',script.strip(),re.S)
        if m:
            try:
                part=json.loads(m[1])
                if len(part)==2 and part[0]==1 and isinstance(part[1],str):chunks.append(part[1])
            except (ValueError,TypeError):pass
    text=''.join(chunks)
    def extract(key):
        m=re.search('"'+key+r'"\s*:\s*',text)
        if not m:raise ValueError('Public profile format changed or stats are unavailable.')
        return json.JSONDecoder().raw_decode(text[m.end():])[0]
    values=extract('currentValues');levels=extract('currentLevels');updated=extract('lastPolledAt')
    for key in ('wardogLevel','xp','cash','gold','worth'):
        if type(values.get(key)) is not int or not 0<=values[key]<=10**15:raise ValueError('Invalid public stats.')
    for key in ROLES:
        if type(levels.get(key)) is not int or not 0<=levels[key]<=100:raise ValueError('Invalid role levels.')
    date=datetime.fromisoformat(updated.replace('Z','+00:00'))
    if date.tzinfo is None:raise ValueError('Missing source timezone.')
    return {'values':values,'levels':levels,'updated':updated}

class ToolsStats:
    def __init__(self,bot):
        self.bot=bot;self.lock=asyncio.Lock();self.until={}
        self.state=json.loads(bot.store.get('wardogs_tools_v1') or '{"links":{},"cache":{}}')
    def save(self):self.bot.store.set('wardogs_tools_v1',json.dumps(self.state))
    async def fetch(self,pid):
        async with self.lock:
            if time.monotonic()<self.until.get(pid,0):return self.state['cache'].get(pid)
            self.until[pid]=time.monotonic()+900
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
                    async with session.get('https://wardogs.tools/player/'+pid,headers={'User-Agent':'Mozilla/5.0 (compatible; 22A-Profile/1.0)'},allow_redirects=False) as response:
                        if response.status!=200:raise ValueError(f'Website returned HTTP {response.status}.')
                        data=bytearray()
                        async for chunk in response.content.iter_chunked(65536):
                            data.extend(chunk)
                            if len(data)>2*1024*1024:raise ValueError('Profile exceeds size limit.')
                        parsed=parse_profile(data.decode('utf-8'))
                parsed['failed']=False
                parsed['fetched_at']=int(time.time())
                self.state['cache'][pid]=parsed;self.save()
            except Exception as error:
                cached=self.state['cache'].get(pid)
                reason=str(error) if isinstance(error,ValueError) else type(error).__name__
                logging.getLogger('22a.tools').warning('Tools profile %s fetch failed: %s',pid,reason)
                if cached:
                    cached['failed']=True
                    cached['fetch_error']=reason[:160]
                    self.save()
                self.until[pid]=time.monotonic()+300
            return self.state['cache'].get(pid)
    async def add(self,embed,member_id,steam):
        pid=self.state['links'].get(str(member_id))
        # Explicit mapping supplied by Warwick in this conversation.
        if not pid and steam=='76561197988807107':pid='d8f9bef7-7dc6-4017-8228-0fd1ce527c93'
        if not pid:
            embed.description+='\n\n🌐 **WARDOGS Tools**\nUse **Connect Tools Profile** on the Player Hub after signing up at https://wardogs.tools/account.'
            return
        stats=await self.fetch(pid)
        text=f'\n\n🌐 **WARDOGS Tools** · [Public profile](https://wardogs.tools/player/{pid})\nMember-provided profile · ownership not independently verified\n'
        if not stats:
            embed.description+=text+'Stats unavailable. Reopen later to retry; your rating is unchanged.'
            return
        v=stats['values']
        text+=f"**Wardog level {v['wardogLevel']}** · XP {v['xp']:,}\nCash **${v['cash']:,}** · Worth **${v['worth']:,}** · Gold {v['gold']:,}\n"
        text+=' · '.join(f"{label} **{stats['levels'][key]}**" for key,label in ROLES.items())
        date=datetime.fromisoformat(stats['updated'].replace('Z','+00:00'))
        match = self.bot.progression.find(member_id)
        approved = bool(match and match[1].get('approved_tools_profile') == pid)
        status = ('Level bonuses approved' + (' · fresh baseline required before rewards' if not match[1].get('level_baseline') else ' · baseline saved')) if approved else 'Display only · ask an admin to approve ownership for level bonuses'
        text+=f'\nSource synced <t:{int(date.timestamp())}:R> · {status}'
        if stats.get('fetched_at'):text+=f'\nBot last read website <t:{stats["fetched_at"]}:R>.'
        if stats.get('failed'):
            text+='\n⚠️ Bot could not fetch the latest website data; showing saved stats. Retrying in five minutes.'
        elif (datetime.now(timezone.utc)-date).total_seconds()>1800:
            text+='\n⚠️ The website returned an old snapshot. Open your public profile to check whether tracking is paused. The bot cannot force a game sync.'
        embed.description+=text

class ToolsLinkModal(discord.ui.Modal,title='Connect your public WARDOGS Tools profile'):
    url=discord.ui.TextInput(label='Your public player profile URL',max_length=150)
    async def on_submit(self,interaction):
        interaction.client.validate_context(interaction)
        pid=profile_id(str(self.url))
        await interaction.response.defer(ephemeral=True)
        tools=get_service(interaction.client)
        stats=await tools.fetch(pid)
        if not stats:raise ValueError('Could not read stats from this profile. Check the link and try later.')
        tools.state['links'][str(interaction.user.id)]=pid;tools.save()
        await interaction.followup.send('Public profile connected for display. Reopen My Profile to see levels and money. Ask an admin to verify ownership and use /approve-tools to enable future level bonuses. Existing levels do not award points.',ephemeral=True)
    async def on_error(self,interaction,error):
        from bot import handle_error
        await handle_error(interaction,error)

def get_service(bot):
    if not hasattr(bot,'tools_stats'):bot.tools_stats=ToolsStats(bot)
    return bot.tools_stats
