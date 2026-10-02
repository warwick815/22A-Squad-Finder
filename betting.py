"""Virtual-only peer challenges. Wallet and bet transitions commit together."""
import asyncio
import copy
import json
import logging
import time
import uuid
from collections import Counter
import discord
from discord import app_commands
from discord.ext import tasks
from leaderboard import timestamp

RULES = ('Virtual dollars only: no purchases, cash-out or ELO effect. Linked players receive $10,000 once. '
         'Stake $100–$1,000 each. Offers expire after 10 minutes; one open bet per player. '
         'Kills/limit: challenger bets the selected player FAILS the target; selected player bets they succeed. '
         'Race: whoever earns more kills wins. Both accept the terms before play starts. '
         'Measurement uses fresh cumulative source snapshots, not exact match events. '
         'The starting snapshot may precede acceptance by up to 5 minutes; the ending snapshot may follow the deadline by up to 5 minutes. '
         'Ties, observed resets/source changes, and unavailable ending data are refunded. '
         'Private replies disappear after 3 minutes.')


async def tell(i, text=None, **kwargs):
    if not i.response.is_done():
        await i.response.send_message(text, ephemeral=True, delete_after=180, **kwargs)
    else:
        message = await i.followup.send(text, ephemeral=True, wait=True, **kwargs)
        from response_cleanup import later
        later(message.delete)


class Book:
    def __init__(self, store):
        self.store = store
        self.data = json.loads(store.get('betting_v1') or '{"wallets":{},"bets":{}}')

    def save(self):
        self.store.set('betting_v1', json.dumps(self.data))

    def wallet(self, uid):
        return self.data['wallets'].setdefault(str(uid), 10000)

    def open_for(self, uid):
        return [b for b in self.data['bets'].values() if uid in (b['a'], b['b']) and b['status'] in ('offered','active')]

    def offer(self, a, b, stake, mode, target, hours, limit, now):
        if a == b or self.open_for(a) or self.open_for(b):
            raise ValueError('No self bets; each player can have only one open challenge.')
        if mode not in ('kills','race','limit') or not 100 <= stake <= 1000 or not 1 <= hours <= 6 or not 1 <= target <= 1000 or not 0 <= limit <= 1000:
            raise ValueError('Use kills/race/limit; stake 100–1000, hours 1–6, target 1–1000, death limit 0–1000.')
        if self.wallet(a) < stake:
            raise ValueError('Insufficient available dollars.')
        self.wallet(b)
        bet = dict(id=uuid.uuid4().hex[:12], a=a, b=b, stake=stake, mode=mode, target=target,
                   hours=hours, limit=limit, status='offered', expires=now+600, result='Awaiting acceptance')
        self.data['wallets'][str(a)] -= stake
        self.data['bets'][bet['id']] = bet
        self.save()
        return bet

    def finish(self, b, winner, reason):
        if b['status'] not in ('offered','active'):
            return False
        if b['status'] == 'offered':
            self.data['wallets'][str(b['a'])] += b['stake']
        elif winner is None:
            for uid in (b['a'],b['b']):
                self.data['wallets'][str(uid)] += b['stake']
        else:
            self.data['wallets'][str(winner)] += 2*b['stake']
        b.update(status='settled', winner=winner, result=reason)
        self.save()
        return True

    def accept(self, b, uid, snapshots, now):
        if b['status'] != 'offered' or uid != b['b']:
            raise ValueError('Only the invited player can accept an open offer.')
        if now >= b['expires']:
            self.finish(b,None,'Offer expired; stake returned')
            raise ValueError('Offer expired.')
        if self.wallet(uid) < b['stake']:
            raise ValueError('Insufficient available dollars to match the stake.')
        if any(not 0 <= now-s['time'] <= 300 for s in snapshots.values()):
            raise ValueError('Starting stats must be no more than five minutes old. Try again after the feed refreshes.')
        self.data['wallets'][str(uid)] -= b['stake']
        b.update(status='active', start=now, end=now+b['hours']*3600, baseline=copy.deepcopy(snapshots), last=copy.deepcopy(snapshots), finals={}, result='In progress')
        self.save()

    def observe(self, b, snapshots, now):
        if b['status'] != 'active':
            return
        for uid, initial in b['baseline'].items():
            s = snapshots.get(uid)
            if not s or s['time'] > now or s['time'] <= b['last'][uid]['time']:
                continue
            previous = b['last'][uid]
            if s['source'] != initial['source'] or any(s[k] < previous[k] for k in ('kills','deaths')):
                self.finish(b,None,'Counter reset or source changed; both stakes refunded')
                return
            b['last'][uid] = s
            if b['end'] <= s['time'] <= b['end']+300:
                b['finals'].setdefault(uid,s)
        if len(b['finals']) == len(b['baseline']):
            delta = {u:{k:b['finals'][u][k]-v[k] for k in ('kills','deaths')} for u,v in b['baseline'].items()}
            target = delta[str(b['b'])]
            if b['mode'] == 'race':
                own = delta[str(b['a'])]['kills']
                winner = None if own == target['kills'] else b['a'] if own > target['kills'] else b['b']
            else:
                success = target['kills'] >= b['target'] and (b['mode'] != 'limit' or target['deaths'] <= b['limit'])
                winner = b['b'] if success else b['a']
            details = '; '.join(f'<@{u}>: {v["kills"]} kills / {v["deaths"]} deaths (<t:{int(b["baseline"][u]["time"])}:t>–<t:{int(b["finals"][u]["time"])}:t>)' for u,v in delta.items())
            self.finish(b,winner,('Tie — refunded. ' if winner is None else f'<@{winner}> wins ${2*b["stake"]:,} pot. ')+details)
        elif now > b['end']+900:
            self.finish(b,None,'No reliable ending snapshot within the settlement window; refunded')
        else:
            self.save()


class Betting:
    def __init__(self, bot):
        self.bot, self.book, self.lock = bot, Book(bot.store), asyncio.Lock()

    def linked(self, uid):
        result = self.bot.progression.find(uid)
        if not result:
            raise ValueError('Both players must /link their Steam accounts first.')
        return result[0]

    async def snapshots(self, b):
        ranks = self.bot.progression
        async with ranks.lock:
            updated, rows = await ranks.fetch()
            from wduk_api import source_id
            result = {}
            for uid in ([b['a'],b['b']] if b['mode'] == 'race' else [b['b']]):
                steam = self.linked(uid)
                if steam not in rows:
                    continue
                row = rows[steam]
                result[str(uid)] = dict(kills=row['kills'], deaths=row['deaths'],
                    time=timestamp(getattr(ranks,'source_times',{}).get(steam,updated)).timestamp(),
                    source=getattr(ranks,'source_overrides',{}).get(steam,source_id())+':'+steam)
            return result

    async def publish(self,b):
        channel = self.bot.guild.get_channel(b['channel'])
        if channel is None:
            return
        description = (f'<@{b["a"]}> vs <@{b["b"]}> · **${b["stake"]:,} each**\n'
            f'**{b["mode"].upper()}** · {b["hours"]} hour(s) · target {b["target"]} kills · death limit {b["limit"]}\n'
            + ('Challenger bets the selected player fails.\n' if b['mode'] != 'race' else 'Most additional kills wins; target/death limit unused.\n')
            + b['result'])
        if b['status']=='offered':
            description += f'\nExpires <t:{int(b["expires"])}:R>. Invited player: open **My Bets** to accept or decline.'
        elif b['status']=='active':
            description += f'\nNominal deadline <t:{int(b["end"])}:R>. Snapshot timing tolerance applies.'
        embed=discord.Embed(title='💵 22A Challenge • '+b['status'].title(),description=description,color=0xC8102E)
        marker='22A bet '+b['id']
        embed.set_footer(text=marker+' • Virtual dollars only')
        message=None
        if b.get('message'):
            try:
                message=await channel.fetch_message(b['message'])
            except discord.NotFound:
                pass
        if message is None:
            async for candidate in channel.history(limit=100):
                if candidate.author.id==self.bot.user.id and candidate.embeds and candidate.embeds[0].footer.text==embed.footer.text:
                    message=candidate
                    break
        if message:
            await message.edit(embed=embed)
        else:
            message=await channel.send(embed=embed,allowed_mentions=discord.AllowedMentions.none())
        b['message']=message.id
        b['published']=b['status']
        self.book.save()

    @tasks.loop(minutes=1)
    async def poll(self):
        if not self.bot.initialized or not self.bot.is_ready():
            return
        async with self.lock:
            for b in list(self.book.data['bets'].values()):
                try:
                    now=time.time()
                    if b['status']=='offered' and now>=b['expires']:
                        self.book.finish(b,None,'Offer expired; stake returned')
                    if b['status']=='active':
                        try:
                            data=await self.snapshots(b)
                        except Exception:
                            data={}
                        self.book.observe(b,data,time.time())
                    if b.get('published')!=b['status']:
                        await self.publish(b)
                except Exception:
                    logging.getLogger('22a.betting').exception('Bet processing failed; durable state retained')


def service(i):
    i.client.validate_context(i)
    return i.client.betting


class SafeView(discord.ui.View):
    async def on_error(self,i,error,item):
        await tell(i,str(error) if isinstance(error,ValueError) else 'Action failed. Check Railway logs; reopen My Bets before retrying.')
        if not isinstance(error,ValueError):
            logging.getLogger('22a.betting').error('Bet UI failed',exc_info=(type(error),error,error.__traceback__))


class OfferModal(discord.ui.Modal,title='Challenge terms — virtual dollars'):
    mode=discord.ui.TextInput(label='Mode: kills, race, or limit',default='kills')
    stake=discord.ui.TextInput(label='Stake per player ($100–$1,000)',default='500')
    target=discord.ui.TextInput(label='Kills target (race ignores this)',default='20')
    hours=discord.ui.TextInput(label='Duration in hours (1–6)',default='1')
    limit=discord.ui.TextInput(label='Maximum deaths (limit mode only)',default='10')

    def __init__(self,opponent):
        super().__init__()
        self.opponent=opponent

    async def on_submit(self,i):
        s=service(i)
        s.linked(i.user.id);s.linked(self.opponent)
        try:
            stake,target,hours,limit=map(int,(str(self.stake),str(self.target),str(self.hours),str(self.limit)))
        except ValueError:
            raise ValueError('Stake, target, hours and death limit must be whole numbers.')
        await i.response.defer(ephemeral=True,thinking=True)
        async with s.lock:
            channel_id=s.book.data.get('channel')
            channel=i.guild.get_channel(channel_id) if channel_id else None
            if channel is None:
                raise ValueError('Staff must post /betting-panel first.')
            perms=channel.permissions_for(i.guild.me)
            if not all(getattr(perms,p) for p in ('view_channel','send_messages','embed_links','read_message_history')):
                raise ValueError('The bot needs View Channel, Send Messages, Embed Links and Read Message History in the betting channel.')
            other=await i.guild.fetch_member(self.opponent)
            if other.bot or not channel.permissions_for(other).view_channel or not channel.permissions_for(i.user).view_channel:
                raise ValueError('Choose a human member who can access the betting channel.')
            b=s.book.offer(i.user.id,self.opponent,stake,str(self.mode).strip().lower(),target,hours,limit,time.time())
            b['channel']=channel.id;s.book.save()
        await tell(i,'Offer created and your stake reserved. The invited player can open My Bets to accept. Offers expire after ten minutes.')

    async def on_error(self,i,error):
        await tell(i,str(error) if isinstance(error,ValueError) else 'Could not create offer. Check My Bets before retrying.')


class OpponentView(SafeView):
    @discord.ui.select(cls=discord.ui.UserSelect,placeholder='Choose your opponent',min_values=1,max_values=1)
    async def choose(self,i,select):
        service(i).linked(i.user.id)
        await i.response.send_modal(OfferModal(select.values[0].id))


class DecisionView(SafeView):
    def __init__(self,bid):
        super().__init__(timeout=180)
        self.bid=bid

    @discord.ui.button(label='Accept & match stake',style=discord.ButtonStyle.success)
    async def accept(self,i,button):
        s=service(i)
        await i.response.defer(ephemeral=True,thinking=True)
        async with s.lock:
            b=s.book.data['bets'][self.bid]
            if i.user.id!=b['b'] or b['status']!='offered':
                raise ValueError('Only the invited player may accept an open challenge.')
            snapshots=await s.snapshots(b)
            expected=2 if b['mode']=='race' else 1
            if len(snapshots)!=expected:
                raise ValueError('Required player stats are unavailable. No stake deducted.')
            s.book.accept(b,i.user.id,snapshots,time.time())
        await tell(i,'Accepted. Both stakes are reserved and the challenge has started.')

    @discord.ui.button(label='Decline / cancel offer',style=discord.ButtonStyle.danger)
    async def decline(self,i,button):
        s=service(i)
        async with s.lock:
            b=s.book.data['bets'][self.bid]
            if i.user.id not in (b['a'],b['b']) or b['status']!='offered':
                raise ValueError('Only participants may cancel an unaccepted offer.')
            s.book.finish(b,None,'Offer declined/cancelled; stake returned')
        await tell(i,'Offer closed; reserved stake returned.')


class BettingPanel(SafeView):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Create Bet',custom_id='22a:bet:create:v1',style=discord.ButtonStyle.success)
    async def create(self,i,button):
        service(i).linked(i.user.id)
        await tell(i,'Choose a linked player. Creating an offer reserves your stake; they must accept and match it. '+RULES,view=OpponentView(timeout=180))

    @discord.ui.button(label='My Wallet',custom_id='22a:bet:wallet:v1')
    async def wallet(self,i,button):
        s=service(i);s.linked(i.user.id)
        async with s.lock:
            balance=s.book.wallet(i.user.id);s.book.save()
            reserved=sum(b['stake'] for b in s.book.open_for(i.user.id) if b['a']==i.user.id or b['status']=='active')
        await tell(i,f'💵 Available: **${balance:,}** · Reserved: **${reserved:,}**\nVirtual dollars only. Your $10,000 starting grant is one-time.')

    @discord.ui.button(label='My Bets',custom_id='22a:bet:mine:v1')
    async def mine(self,i,button):
        s=service(i);s.linked(i.user.id)
        bets=[b for b in s.book.data['bets'].values() if i.user.id in (b['a'],b['b'])]
        opened=s.book.open_for(i.user.id)
        if opened:
            b=opened[0]
            text=f'**{b["mode"].upper()}** · <@{b["a"]}> vs <@{b["b"]}> · ${b["stake"]} each\nTarget {b["target"]} kills; max {b["limit"]} deaths (limit only); {b["hours"]} hours.\n'+b['result']+'\n'+RULES
            await tell(i,text,view=DecisionView(b['id']) if b['status']=='offered' else None)
        else:
            await tell(i,'No open bets.\n'+'\n'.join(b['result'] for b in bets[-3:]))

    @discord.ui.button(label='Leaderboard',custom_id='22a:bet:board:v1')
    async def board(self,i,button):
        s=service(i)
        totals={u:v for u,v in s.book.data['wallets'].items()}
        for b in s.book.data['bets'].values():
            if b['status'] in ('offered','active'):
                totals[str(b['a'])]+=b['stake']
                if b['status']=='active':totals[str(b['b'])]+=b['stake']
        entries=sorted(totals.items(),key=lambda p:(-p[1],p[0]))[:20]
        await tell(i,embed=discord.Embed(title='💵 22A Virtual Dollar Standings',description='Available + reserved dollars\n'+'\n'.join(f'{n}. <@{u}> — ${v:,}' for n,(u,v) in enumerate(entries,1))))

    @discord.ui.button(label='How It Works',custom_id='22a:bet:help:v1')
    async def help(self,i,button):
        service(i)
        await tell(i,RULES)


@app_commands.command(name='betting-panel',description='Staff: post or refresh the virtual betting panel')
@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
async def betting_panel(i:discord.Interaction,channel:discord.TextChannel):
    s=service(i)
    if not i.user.guild_permissions.manage_guild:raise ValueError('Manage Server required.')
    perms=channel.permissions_for(i.guild.me)
    if not all(getattr(perms,p) for p in ('view_channel','send_messages','embed_links','read_message_history')):
        raise ValueError('Grant View Channel, Send Messages, Embed Links and Read Message History in that channel.')
    await i.response.defer(ephemeral=True,thinking=True)
    async with s.lock:
        embed=discord.Embed(title='💵 22A Challenge Club',description=RULES,color=0xC8102E)
        old=s.book.data.get('panel')
        message=None
        if old and s.book.data.get('channel')==channel.id:
            try:message=await channel.fetch_message(old)
            except discord.NotFound:pass
        if message:await message.edit(embed=embed,view=BettingPanel())
        else:message=await channel.send(embed=embed,view=BettingPanel())
        s.book.data.update(panel=message.id,channel=channel.id);s.book.save()
    await tell(i,'Betting panel ready: '+message.jump_url)


@app_commands.command(name='bet-refund',description='Staff: refund an unresolved challenge with a recorded reason')
@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
async def bet_refund(i:discord.Interaction,bet_id:str,reason:str):
    s=service(i)
    if not i.user.guild_permissions.manage_guild:raise ValueError('Manage Server required.')
    async with s.lock:
        b=s.book.data['bets'].get(bet_id)
        if not b or b['status']=='settled':raise ValueError('No unresolved bet with that ID.')
        s.book.finish(b,None,f'Staff refund by {i.user.id}: '+discord.utils.escape_mentions(reason[:300]))
    await tell(i,'Stakes refunded; result retained in history.')
