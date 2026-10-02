"""Scheduled fictional drill-corporal banter; no generated personal attacks."""
import json
import logging
import os
import random
import time
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import tasks

LINES = [
    "Your aim is so fucking dreadful the enemy have started using you as cover. Sort it out, you walking ammunition shortage!",
    "I've seen shopping trolleys advance with more purpose. Stop wandering about like a lost bollock and get on the objective!",
    "That wasn't suppressing fire. That was an expensive fucking weather report. Try aiming at something wearing the OTHER uniform!",
    "You call that reconnaissance? You couldn't spot a bloody tank in a phone box. Open your eyes!",
    "Your tactical contribution so far is turning perfectly good ammunition into fucking noise. Improve!",
    "I've seen better formations in a bowl of alphabet soup. Stop flapping about and find your bloody squad!",
    "If missing shots were a trade, you'd be a fucking master craftsman. Unfortunately, we're trying to WIN!",
    "You're not holding the flank, you're giving the enemy a fucking guided tour. Close the door!",
    "Your grenade landed closer to your career prospects than the enemy. Throw the bloody thing FORWARD!",
    "That landing was less helicopter pilot and more angry bastard throwing a wardrobe down the stairs!",
    "Your route to the objective has more detours than a fucking council roadworks scheme. Get there before the war ends!",
    "Stop polishing that rifle with your eyeballs and fucking use it. The enemy aren't going to admire themselves to death!",
    "You've spent so long on that hill they're putting you on the fucking tourist map. MOVE!",
    "Your battle plan appears to be run in, fall over, repeat. Brilliant. A fucking revolving door with boots!",
    "That reload had an interval and a fucking souvenir programme. Pick up the pace!",
    "You're meant to deliver supplies, not take them on a bloody sightseeing holiday. Get that wagon moving!",
    "The objective isn't a fucking rumour. It's marked on your map. Go and introduce yourself!",
    "Your camouflage is excellent. Nobody's seen a useful contribution from you all fucking evening!",
    "Stop arguing with the map, you magnificent bloody navigational disaster. North hasn't moved!",
    "I've seen more controlled bursts from a knackered garden hose. Finger off the trigger until your sights catch up!",
    "Your crosshair and the enemy are in a long-distance fucking relationship. Bring them together!",
    "That magazine cost money, sunshine. The clouds can buy their own fucking ammunition!",
    "You couldn't hit the sea from a sinking frigate. Stop blaming the bloody scope!",
    "That's a rifle, not a fucking metal detector. Lift the muzzle out of the dirt!",
    "Your trigger discipline is a drum solo performed by a startled bastard. Short bursts!",
    "You've outlined that enemy beautifully. Now colour the fucking middle in!",
    "Stop shooting the doorway after they've left. This isn't a bloody historical reenactment!",
    "Your bullet grouping needs its own fucking postcode. Tighten it up!",
    "You've emptied three magazines into the scenery. Congratulations, the shrubbery has surrendered!",
    "The recoil isn't dragging you about. You're escorting it round the fucking countryside!",
    "You've brought a sniper rifle to a broom cupboard. Outstanding fucking equipment selection!",
    "Your pistol work resembles somebody angrily ringing a tiny bloody doorbell. AIM!",
    "You changed attachments six times and still missed. Perhaps the loose fitting is behind the fucking stock!",
    "That warning shot had nineteen equally useless fucking friends. Make the next one count!",
    "You're leading the target by a fucking calendar month. Adjust your sights, not the laws of physics!",
    "The only thing your scope has acquired is a lovely view. This is combat, not fucking birdwatching!",
    "You crouched in the middle of the road and called it cover. That's a fucking speed bump!",
    "Your flanking manoeuvre has returned to spawn. Excellent, you've successfully surrounded yourself!",
    "Stop silhouetting yourself on that ridge. You're a soldier, not a fucking church steeple!",
    "You sprinted past three walls to reload in the open. Have you got a bloody sponsorship deal with the enemy?",
    "Your idea of tactical spacing is climbing inside the squad leader's fucking backpack!",
    "You cleared that room by leaving it. A bold fucking interpretation of the order!",
    "The smoke is there to conceal movement, not provide atmosphere for your bloody picnic!",
    "You've been checking the same empty corner for five minutes. Charge it fucking rent or move on!",
    "You're guarding an objective we lost ten minutes ago. Read the bloody map, museum security!",
    "That retreat was so enthusiastic you've nearly joined a different fucking server!",
    "Stop peeking the same window. Even the enemy's kettle knows where you're appearing next!",
    "You're prone behind a fucking traffic cone. That isn't fortification, it's optimism!",
    "Your entry technique is announcing yourself and getting stuck in the bloody doorframe!",
    "We said hold position, not become a fucking archaeological site. Watch your sector!",
    "That ambush had all the subtlety of a brass band falling down bloody stairs!",
    "Stop chasing one bloke across the map. The objective hasn't agreed to wait for your fucking side quest!",
    "Medic, you're standing on a casualty like a bloody bus stop. Put the kit to work!",
    "Your bedside manner consists of running past at full fucking speed. Come back and revive the squad!",
    "You've got smoke grenades, medic. Use them before opening your surgery in the middle of a bloody firing lane!",
    "Stop admiring that revive timer. It's a treatment, not a fucking cooking programme!",
    "You patched yourself up while the squad queued behind you. This isn't a bloody private clinic!",
    "That rescue route crossed every enemy sightline available. Are you collecting fucking loyalty stamps?",
    "You brought medical gear and contributed a stern look. The wounded need help, not a bloody performance review!",
    "You've revived him facing the same machine gun. Give the poor bastard a fighting chance this time!",
    "Recon, your last useful spot was the stain on your fucking trousers. Mark an actual target!",
    "Those binoculars aren't for checking the property market. Tell us where the bloody enemy are!",
    "Your intelligence report was 'over there'. Excellent, we've narrowed it down to the fucking planet!",
    "You spent ten minutes finding a nest and forgot the objective. Lovely bloody holiday home, though!",
    "That ghillie suit won't disguise you sprinting across a fucking car park!",
    "You've spotted a friendly truck three times. We're delighted it's still fucking ours!",
    "Stop ranging that stationary rock. It hasn't moved since the last bloody ice age!",
    "Your overwatch overlooks everything except the fucking approach we asked you to cover!",
    "Support, that FOB placement has all the defensive value of a bloody lemonade stand!",
    "You've parked the repair kit beside the broken vehicle and hoped for the fucking best. Use it!",
    "That machine gun position covers a wall. Unless the bricks attack, you're fucking redundant there!",
    "Your rocket hit the branch above you. The tree is now fully aware of our bloody position!",
    "You built that emplacement facing our spawn. Planning ahead for a fucking defeat, are we?",
    "Stop feeding one shell at a time into a problem that requires a bloody plan!",
    "Your resupply point is somewhere nobody can reach. Brilliant, a fucking military escape room!",
    "You've carried that toolbox across the map without fixing anything. You're a bloody mobile hardware display!",
    "Driver, the gearbox has requested a transfer. Pick a fucking gear and commit!",
    "You've reversed into the only tree in the field. That's precision fucking incompetence!",
    "This supply run has become a three-point turn with a bloody transport budget!",
    "The squad asked for a lift, not a fucking suspension test!",
    "You parked broadside to the enemy and left the engine running. Shall we wrap the bloody keys as well?",
    "That bridge was wider than the truck. Explain the fucking river!",
    "You're navigating by collision. Every bloody fence on the map knows our destination!",
    "Stop honking at the barricade. It hasn't got a fucking driving licence!",
    "The supplies are still at base and you've arrived empty. Outstanding, a bloody delivery of fresh air!",
    "You found a shortcut that takes twice as long. Put that fucking miracle in the after-action report!",
    "Pilot, we're requesting a landing zone, not a fucking impact site!",
    "Your hover has the stability of a shopping bag in a bloody hurricane!",
    "That approach gave every enemy on the map a fucking viewing appointment!",
    "The passengers asked to deploy, not inspect the underside of a bloody bridge!",
    "Stop arguing with gravity. It's won every fucking appeal so far!",
    "You dropped the supplies on a roof nobody can reach. Wonderful, airborne fucking interior design!",
    "That take-off trimmed every tree in the landing zone. Join the bloody parks department!",
    "Your flight path looks like a spilled bowl of fucking spaghetti. Straighten it out!",
    "Your radio call lasted longer than the engagement. Send coordinates, not your fucking memoirs!",
    "We asked for enemy numbers and got 'loads'. Splendid, another bloody graduate of advanced counting!",
    "Stop narrating every footstep. The radio isn't your fucking podcast!",
    "Your squad coordination is six shopping lists in a bloody trench coat. Agree on a plan!",
    "You've spent more time choosing a loadout than using it. This isn't fucking military dress-up!",
    "Debrief complete: tremendous enthusiasm, catastrophic execution. Now get back out there and be less fucking decorative!",
]


def enabled():
    return os.getenv('ROASTS_ENABLED', '').lower().strip() in ('1', 'true', 'yes')


def eligible(member, channel, last, now):
    return (not member.bot and member.status != discord.Status.offline
            and member.voice is not None and member.voice.channel is not None
            and channel.permissions_for(member).view_channel
            and now-float(last.get(str(member.id), 0)) >= 86400)


class Roasts:
    def __init__(self, bot):
        self.bot = bot
        self.state = json.loads(bot.store.get('roasts_v1') or '{}')
        self.state.setdefault('last', {})
        if 'next' not in self.state:
            self.schedule()

    def save(self):
        self.bot.store.set('roasts_v1', json.dumps(self.state))

    def schedule(self):
        self.state['next'] = time.time()+random.uniform(3600, 10800)
        self.save()

    @tasks.loop(seconds=60)
    async def poll(self):
        if not self.bot.initialized or not self.bot.is_ready() or self.state.get('paused'):
            return
        now = time.time()
        if now < self.state['next']:
            return
        # Reserve the next slot before sending: restarts never trigger catch-up spam.
        self.schedule()
        try:
            guild = self.bot.guild
            raw = os.getenv('ROAST_CHANNEL_ID', '').strip()
            matches = [c for c in guild.text_channels if c.name == 'wardogs-chat']
            channel = guild.get_channel(int(raw)) if raw else (matches[0] if len(matches) == 1 else None)
            if not isinstance(channel, discord.TextChannel):
                raise ValueError('Set ROAST_CHANNEL_ID to wardogs-chat.')
            perms = channel.permissions_for(guild.me)
            if not all(getattr(perms, p) for p in ('view_channel', 'send_messages', 'embed_links', 'attach_files')):
                raise ValueError('Roast channel needs View Channel, Send Messages, Embed Links and Attach Files.')
            candidates = [m for m in guild.members if eligible(m, channel, self.state['last'], now)]
            if not candidates:
                return
            member = random.choice(candidates)
            index = random.choice([i for i in range(len(LINES)) if i != self.state.get('line')])
            embed = discord.Embed(title='🪖 Corporal Nauyokas — Barracks Inspection',
                description=f'{member.mention}, LISTEN IN!\n\n{LINES[index]}', color=0x4B5320)
            embed.set_image(url='attachment://corporal.png')
            embed.set_footer(text='22A • Unofficial fictional parody • Not written or endorsed by Nauyokas')
            self.state['last'][str(member.id)] = now
            self.state['line'] = index
            self.save()
            with discord.File(Path(__file__).parent/'corporal.png', filename='corporal.png') as picture:
                await channel.send(content=member.mention, embed=embed, file=picture,
                    allowed_mentions=discord.AllowedMentions(users=[member], roles=False, everyone=False))
        except Exception:
            logging.getLogger('22a.roasts').exception('Roast skipped; next scheduled slot retained')


@app_commands.command(name='roasts', description='Staff: pause or resume scheduled barracks banter')
@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
async def roast_control(interaction: discord.Interaction, paused: bool):
    interaction.client.validate_context(interaction)
    if not interaction.user.guild_permissions.manage_guild:
        raise ValueError('Manage Server permission required.')
    roasts = getattr(interaction.client, 'roasts', None)
    if roasts is None:
        raise ValueError('Enable ROASTS_ENABLED and Presence Intent, then restart.')
    roasts.state['paused'] = paused
    roasts.schedule()
    await interaction.response.send_message('Roasts paused.' if paused else 'Roasts resumed. Next post in 1–3 hours if an eligible member is online in voice.', ephemeral=True)
