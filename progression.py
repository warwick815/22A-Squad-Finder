"""Persistent, team-weighted community ratings; not opponent-based Elo."""
import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone

import aiohttp
import discord
from discord import app_commands
from discord.ext import tasks

from leaderboard import timestamp

log = logging.getLogger("22a.ranks")
RANKS = [("Private", 0), ("Lance Corporal", 250), ("Corporal", 750),
         ("Sergeant", 1500), ("Staff Sergeant", 3000),
         ("Warrant Officer Class 2", 5000), ("Warrant Officer Class 1", 8000)]
COUNTERS = ("wins", "losses", "kills", "deaths")
SCORING = {"wins": 30, "losses": -10, "kills": 2, "deaths": -1}
RANK_BADGES = ["🪖", "🔰", "⚔️", "🛡️", "🎖️", "⭐", "👑"]
STATE_KEY = "progression_v1"
GUIDE_MARKER = "22A • Rank progression guide v1"


def daily_due(now, posting_time, last_date=None):
    now = now.astimezone(timezone.utc)
    hour, minute = map(int, posting_time.split(":"))
    return last_date != now.date().isoformat() and (now.hour, now.minute) >= (hour, minute)


def daily_embed(players, date, now):
    ordered = sorted(players, key=lambda p: (-p["points2"], p["discord_id"]))
    lines = ["**Top 20 linked members · Progression rating**", ""]
    rank, previous = 0, None
    for position, player in enumerate(ordered[:20], 1):
        if player["points2"] != previous:
            rank = position
        previous = player["points2"]
        badge = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"**{rank}.**")
        status = " · ⏸ Paused" if not player["active"] else " · ⚠️ Under review" if player["hold"] else " · Awaiting stats" if player.get("baseline") is None else ""
        lines.extend([f"{badge} <@{player['discord_id']}> — **{player['points2']/2:,.1f} pts**",
                      f"{RANK_BADGES[player['rank']]} {RANKS[player['rank']][0]}{status}"])
    lines.extend(["", f"Showing {min(20, len(ordered))} of {len(ordered)} linked server members.",
                  "Use **/rank** for your progress. New members: use **/link** to verify Steam.",
                  "Ratings are cumulative, not points earned today. Paused/reviewed accounts retain their saved rating."])
    active_dates = [timestamp(p["updated"]) for p in ordered if p["active"] and p.get("updated")]
    if active_dates:
        oldest = min(active_dates)
        lines.append(f"Oldest active scoring snapshot: <t:{int(oldest.timestamp())}:R>.")
        if (now - oldest).total_seconds() > 900:
            lines.append("⚠️ Some ratings use older saved data.")
    embed = discord.Embed(title=f"🏆 22A Daily Rank Standings — {date}", description="\n".join(lines),
                          color=0xC8102E, timestamp=now)
    embed.set_footer(text=f"22A daily ranks {date}")
    return embed


def guide_embed(steam_enabled=False):
    embed = discord.Embed(title="🎖️ 22A — Rank Progression", color=0xC8102E,
        description="**Start as Private. Win as a team. Earn your stripes.**\n"
        "Everyone starts at **Private with 0 rating** when enrolled. Your existing stats become your starting baseline—"
        "only new results count.")
    instructions = ("1. Run **/link** and select **Sign in through Steam**.\n"
                    "2. Complete sign-in on Steam’s website.\n"
                    "3. Return to Discord → **Review Steam account** → **Confirm link**.\n"
                    "4. Use **/rank** to check your rating and next promotion."
                    if steam_enabled else
                    "Steam linking is not configured yet. Ask an admin to enable **/link**.\n"
                    "Then use **/rank** to check your rating and next promotion.")
    embed.add_field(name="🔗 Get started", value=instructions + "\nYour Steam account must appear on the WDUK leaderboard.", inline=False)
    score_text = "\n".join(" · ".join(
        f"**{label} {SCORING[key]:+g}**".replace("-", "−") for key, label in pair)
        for pair in ((("wins", "Win"), ("losses", "Loss")), (("kills", "Kill"), ("deaths", "Death"))))
    example = sum(SCORING[key] * count for key, count in zip(COUNTERS, (2, 1, 30, 20)))
    embed.add_field(name="📊 How points work", value=score_text + "\n"
                    "Kills and deaths contribute directly; there is no separate lifetime K/D bonus.\n"
                    f"Example: 2 wins, 1 loss, 30 kills, 20 deaths = **{example:+g} points**.", inline=False)
    embed.add_field(name="🪖 Promotion ladder", value="\n".join(f"{RANK_BADGES[i]} **{name}** — {points:,} points" for i, (name, points) in enumerate(RANKS)), inline=False)
    embed.add_field(name="↕️ Promotions and demotions", value="The bot awards your rank role automatically and announces rank changes.\n"
                    "Each rank has a **50-point demotion buffer**: Lance Corporal promotes at 250 and demotes below 200.\n"
                    "Private is the lowest rank. Rating cannot fall below 0. **Inactivity costs no points.**", inline=False)
    embed.add_field(name="⏱️ Updates and fair play", value="Results are checked **every five minutes**, after the source publishes them.\n"
                    "Only WDUK-tracked results count. Relinking does not reset your rating.\n"
                    "Missing/stale data does not deduct points. Suspicious counter changes pause scoring for admin review.\n"
                    "Use **/rank** to see your status, or ask an admin if you need help.", inline=False)
    embed.add_field(name="🏆 Daily standings", value="A daily post ranks the **top 20 linked server members** by their saved progression rating. "
                    "This is your cumulative rating, not just points earned that day. Use **/rank** to check yourself at any time.", inline=False)
    embed.set_footer(text=GUIDE_MARKER)
    return embed


def decode_stats(payload, now=None):
    updated = timestamp(payload["updatedAt"])
    age = ((now or datetime.now(timezone.utc)) - updated).total_seconds()
    if age > 900 or age < -300:
        raise ValueError("Progression feed is stale or has a future timestamp; no rating changes made.")
    fields = payload.get("fields")
    if not isinstance(fields, list) or not {"steamId", *COUNTERS}.issubset(fields) or len(fields) != len(set(fields)):
        raise ValueError("Progression feed fields changed.")
    if not isinstance(payload.get("players"), list):
        raise ValueError("Invalid progression feed")
    result = {}
    for values in payload["players"]:
        if not isinstance(values, list) or len(values) != len(fields):
            raise ValueError("Invalid progression row")
        row = dict(zip(fields, values))
        steam = row["steamId"]
        if not isinstance(steam, str) or not re.fullmatch(r"\d{17}", steam) or steam in result:
            raise ValueError("Invalid or duplicate Steam ID")
        if any(type(row[k]) is not int or not 0 <= row[k] <= 10**10 for k in COUNTERS):
            raise ValueError("Invalid progression counters")
        result[steam] = {k: row[k] for k in COUNTERS}
    return updated.isoformat(), result


def rank_for(points2, current):
    """Integer half-points avoid rounding; 50-point demotion buffer."""
    while current < len(RANKS) - 1 and points2 >= RANKS[current + 1][1] * 2:
        current += 1
    while current > 0 and points2 < (RANKS[current][1] - 50) * 2:
        current -= 1
    return current


def new_player(discord_id, counters, updated):
    return {"discord_id": discord_id, "points2": 0, "rank": 0, "active": True,
            "baseline": counters, "updated": updated, "hold": None, "pending": None}


def advance(player, counters, updated):
    if not player["active"] or player["hold"] or player["pending"]:
        return
    if player.get("baseline") is None:
        # The first valid feed establishes a baseline, never awards historical results.
        player.update(baseline=counters.copy(), updated=updated)
        return
    if timestamp(updated) <= timestamp(player["updated"]):
        return
    delta = {k: counters[k] - player["baseline"][k] for k in COUNTERS}
    if any(v < 0 for v in delta.values()):
        player["hold"] = "Source counters decreased. Admin review and /rank-resume required."
        return
    # A generous bound catches obvious corrupt jumps, scaled to elapsed time (including downtime).
    hours = max(1, (timestamp(updated) - timestamp(player["updated"])).total_seconds() / 3600)
    if delta["wins"] + delta["losses"] > 60 * hours or delta["kills"] + delta["deaths"] > 10000 * hours:
        player["hold"] = "Unusually large source change. Admin review and /rank-resume required."
        return
    old_points, old_rank = player["points2"], player["rank"]
    points = max(0, old_points + 2 * sum(SCORING[key] * delta[key] for key in COUNTERS))
    rank = rank_for(points, old_rank)
    player.update(points2=points, rank=rank, baseline=counters, updated=updated)
    if rank != old_rank:
        player["pending"] = {"id": uuid.uuid4().hex, "from": old_rank, "to": rank,
                             "before": old_points, "after": points, "delta": delta}


class Progression:
    def __init__(self, bot, channel_id):
        self.bot, self.channel_id = bot, channel_id
        raw = bot.store.get(STATE_KEY)
        self.state = json.loads(raw) if raw else {"roles": {}, "players": {}}
        self.lock = asyncio.Lock()
        self.daily_time = os.getenv("RANK_DAILY_TIME_UTC", "18:00").strip()
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", self.daily_time):
            raise ValueError("RANK_DAILY_TIME_UTC must use HH:MM, e.g. 18:00 (UTC).")
        daily_channel = os.getenv("RANK_DAILY_CHANNEL_ID", "").strip()
        if daily_channel and (not daily_channel.isdigit() or int(daily_channel) <= 0):
            raise ValueError("RANK_DAILY_CHANNEL_ID must be a text channel ID or empty.")
        self.daily_channel_id = int(daily_channel) if daily_channel else channel_id

    @classmethod
    def from_env(cls, bot):
        channel = os.getenv("RANK_ANNOUNCEMENT_CHANNEL_ID", "").strip()
        if not channel:
            return None
        if not channel.isdigit() or int(channel) <= 0:
            raise ValueError("RANK_ANNOUNCEMENT_CHANNEL_ID must be a text channel ID.")
        return cls(bot, int(channel))

    def save(self):
        self.bot.store.set(STATE_KEY, json.dumps(self.state))

    async def post_daily(self, now=None):
        now = now or datetime.now(timezone.utc)
        date = now.astimezone(timezone.utc).date().isoformat()
        if not daily_due(now, self.daily_time, self.bot.store.get("rank_daily_last_date")):
            return
        channel = self.bot.get_channel(self.daily_channel_id)
        if not isinstance(channel, discord.TextChannel) or channel.guild.id != self.bot.cfg.guild_id:
            raise ValueError("Rank daily channel must be a text channel in this server.")
        perms = channel.permissions_for(channel.guild.me)
        if not all(getattr(perms, p) for p in ("view_channel", "send_messages", "embed_links", "read_message_history")):
            raise ValueError("Daily channel needs View Channel, Send Messages, Embed Links and Read Message History.")
        marker = f"22A daily ranks {date}"
        async for message in channel.history(limit=100):
            if message.author.id == self.bot.user.id and message.embeds and message.embeds[0].footer.text == marker:
                self.bot.store.set("rank_daily_last_date", date)
                return
        players = []
        for player in self.state["players"].values():
            member = self.bot.guild.get_member(player["discord_id"])
            if member is None:
                try:
                    member = await self.bot.guild.fetch_member(player["discord_id"])
                except discord.NotFound:
                    continue
            if not member.bot:
                players.append(player)
        if not players:
            return  # Wait until someone is linked; do not post an empty daily message.
        embed = daily_embed(players, date, now)
        if self.bot.cfg.logo_url:
            embed.set_thumbnail(url=self.bot.cfg.logo_url)
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        self.bot.store.set("rank_daily_last_date", date)

    async def ensure_guide(self, channel=None):
        if channel is None:
            configured = os.getenv("RANK_GUIDE_CHANNEL_ID", "").strip()
            saved = self.bot.store.get("rank_guide_channel")
            channel = self.bot.get_channel(int(configured or saved or self.channel_id))
        if not isinstance(channel, discord.TextChannel) or channel.guild.id != self.bot.cfg.guild_id:
            raise ValueError("Choose a normal text channel in this server for the rank guide.")
        perms = channel.permissions_for(channel.guild.me)
        if not all(getattr(perms, p) for p in ("view_channel", "send_messages", "embed_links", "read_message_history")):
            raise ValueError("Guide channel needs View Channel, Send Messages, Embed Links and Read Message History.")
        key = f"rank_guide_message:{channel.id}"
        saved = self.bot.store.get(key)
        message = None
        if saved:
            try:
                message = await channel.fetch_message(int(saved))
            except discord.NotFound:
                pass
        if message is None:
            async for candidate in channel.history(limit=100):
                if (candidate.author.id == self.bot.user.id and candidate.embeds
                        and candidate.embeds[0].footer.text == GUIDE_MARKER):
                    message = candidate
                    break
        embed = guide_embed(bool(getattr(self.bot, "steam_link", None)))
        logo = self.bot.cfg.logo_url
        if logo:
            embed.set_thumbnail(url=logo)
        if message is None:
            message = await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        elif not message.embeds or message.embeds[0].to_dict() != embed.to_dict():
            await message.edit(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        self.bot.store.set(key, message.id)
        self.bot.store.set("rank_guide_channel", channel.id)
        return message

    def channel(self):
        channel = self.bot.get_channel(self.channel_id)
        if not isinstance(channel, discord.TextChannel) or channel.guild.id != self.bot.cfg.guild_id:
            raise ValueError("Set RANK_ANNOUNCEMENT_CHANNEL_ID to a text channel in this server.")
        perms = channel.permissions_for(channel.guild.me)
        if not all(getattr(perms, p) for p in ("view_channel", "send_messages", "embed_links", "read_message_history")):
            raise ValueError("Rank channel needs View Channel, Send Messages, Embed Links and Read Message History.")
        return channel

    def roles(self):
        guild = self.bot.guild
        if not guild.me.guild_permissions.manage_roles:
            raise ValueError("The bot needs Manage Roles.")
        roles = []
        for index, (name, _) in enumerate(RANKS):
            role_id = self.state["roles"].get(str(index))
            role = guild.get_role(role_id) if role_id else None
            if role is None:
                raise ValueError("Run /ranks-setup to create or repair the progression roles.")
            if role.managed or role.is_default() or role >= guild.me.top_role or role.permissions.value:
                raise ValueError(f"Keep {name} below the bot's role, with no server permissions. Rank roles are cosmetic.")
            roles.append(role)
        return roles

    async def setup_roles(self):
        self.channel()
        if not self.bot.guild.me.guild_permissions.manage_roles:
            raise ValueError("Give the bot Manage Roles first.")
        for index, (name, _) in enumerate(RANKS):
            saved = self.state["roles"].get(str(index))
            if saved and self.bot.guild.get_role(saved):
                role = self.bot.guild.get_role(saved)
                if role.name == f"22A Rank • {name}":
                    await role.edit(name=f"{RANK_BADGES[index]} 22A Rank • {name}", reason="22A rank badge update")
                continue
            role = await self.bot.guild.create_role(name=f"{RANK_BADGES[index]} 22A Rank • {name}", permissions=discord.Permissions.none(),
                    hoist=False, mentionable=False, reason="22A progression setup requested by admin")
            self.state["roles"][str(index)] = role.id
            self.save()
        self.roles()

    async def fetch(self):
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=40), headers={
                "User-Agent": "Mozilla/5.0 (compatible; 22A-Discord-Progression/1.0)", "Accept": "application/json"}) as session:
            async with session.get("https://wardogs.uk/leaderboard-all.json") as response:
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    body.extend(chunk)
                    if len(body) > 20 * 1024 * 1024:
                        raise ValueError("Progression feed too large")
                payload = json.loads(body)
                result = decode_stats(payload)
                panel = getattr(self.bot, "player_panel", None)
                if panel is not None:
                    panel.record(payload)
                return result

    def find(self, discord_id):
        return next(((steam, p) for steam, p in self.state["players"].items() if p["discord_id"] == discord_id), None)

    async def link(self, member, steam):
        if member.bot or not re.fullmatch(r"\d{17}", steam):
            raise ValueError("Choose a human member and a 17-digit SteamID64.")
        self.roles()
        self.channel()
        existing = self.find(member.id)
        stored = self.state["players"].get(steam)
        if (existing and existing[0] != steam) or (stored and stored["discord_id"] != member.id):
            raise ValueError("That Discord or Steam identity is already registered. Existing ratings cannot be reset by relinking.")
        if stored:
            raise ValueError("Already linked. Use /rank to inspect or /rank-resume to resume; rating is preserved.")
        updated, rows = await self.fetch()
        if steam not in rows:
            raise ValueError("Steam ID not present in the public all-time feed. No account was created.")
        player = new_player(member.id, rows[steam], updated)
        self.state["players"][steam] = player
        self.save()  # Baseline and rating recorded before role assignment; loop can retry.
        await self.sync_player(player)

    async def enroll_verified(self, member, steam):
        """Save verified identity independently of the third-party stats service."""
        if member.bot or not re.fullmatch(r"\d{17}", steam):
            raise ValueError("Choose a human member and a valid SteamID64.")
        existing = self.find(member.id)
        stored = self.state["players"].get(steam)
        if (existing and existing[0] != steam) or (stored and stored["discord_id"] != member.id):
            raise ValueError("That Discord or Steam identity already has a different registration.")
        if stored:
            return
        player = new_player(member.id, None, None)
        player["steam_verified"] = True
        self.state["players"][steam] = player
        self.save()
        try:
            await self.sync_player(player)
        except Exception:
            log.exception("Verified Steam link saved; Private role assignment will retry")

    async def sync_player(self, player):
        roles = self.roles()
        try:
            member = await self.bot.guild.fetch_member(player["discord_id"])
        except discord.NotFound:
            return
        target = roles[player["rank"]] if player["active"] else None
        if target and target not in member.roles:
            await member.add_roles(target, reason="22A progression rank", atomic=True)
        obsolete = [r for r in member.roles if r in roles and r != target]
        if obsolete:
            await member.remove_roles(*obsolete, reason="22A progression rank update", atomic=True)
        event = player["pending"]
        if event and player["active"]:
            channel = self.channel()
            marker = f"22A rank event {event['id']}"
            found = False
            async for message in channel.history(limit=100):
                if message.author.id == self.bot.user.id and message.embeds and message.embeds[0].footer.text == marker:
                    found = True
                    break
            if not found:
                promoted = event["to"] > event["from"]
                delta = event["delta"]
                embed = discord.Embed(title="🎖️ PROMOTION" if promoted else "📉 DEMOTION",
                    description=f"<@{player['discord_id']}>\n**{RANKS[event['from']][0]} → {RANKS[event['to']][0]}**\n"
                    f"{RANK_BADGES[event['to']]} Rating: **{event['before']/2:,.1f} → {event['after']/2:,.1f}**\n"
                    f"Since last snapshot: {delta['wins']} wins · {delta['losses']} losses · "
                    f"{delta['kills']} kills · {delta['deaths']} deaths", color=0x2ECC71 if promoted else 0xC8102E)
                embed.set_footer(text=marker)
                await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            player["pending"] = None
            self.save()

    @tasks.loop(minutes=5)
    async def poll(self):
        if not self.bot.is_ready() or not self.bot.initialized:
            return
        async with self.lock:
            try:
                if getattr(self.bot, "player_panel", None) is not None:
                    await self.bot.player_panel.ensure()
            except Exception:
                log.exception("Could not update player panel; progression will continue independently")
            try:
                await self.ensure_guide()
            except Exception:
                log.exception("Could not update rank guide; progression will continue independently")
            try:
                if not self.state["players"]:
                    return
                self.roles()
                self.channel()
                updated, rows = await self.fetch()
                for steam, player in self.state["players"].items():
                    try:
                        # Deliver an outstanding transition before scoring another one.
                        if player["pending"]:
                            await self.sync_player(player)
                        if steam in rows:
                            was_held = player["hold"]
                            advance(player, rows[steam], updated)
                            self.save()
                            if player["hold"] and not was_held:
                                log.warning("Rank scoring held for Discord member %s: %s", player["discord_id"], player["hold"])
                        await self.sync_player(player)
                    except Exception:
                        log.exception("Rank update failed for member %s; will retry", player["discord_id"])
            except Exception:
                log.exception("Progression update unavailable; existing ratings preserved, retry in five minutes")
            finally:
                try:
                    await self.post_daily()
                except Exception:
                    log.exception("Daily rank standings failed; retry on next five-minute check")

    def start(self):
        if not self.poll.is_running():
            self.poll.start()

    def stop(self):
        self.poll.cancel()


def service(interaction, admin=False):
    interaction.client.validate_context(interaction)
    if admin and not interaction.user.guild_permissions.manage_guild:
        raise ValueError("Manage Server permission is required.")
    result = interaction.client.progression
    if result is None:
        raise ValueError("Set RANK_ANNOUNCEMENT_CHANNEL_ID and restart to enable progression.")
    return result


@app_commands.command(name="ranks-setup", description="Create or repair the seven cosmetic 22A progression roles")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
async def ranks_setup(interaction: discord.Interaction):
    ranks = service(interaction, True)
    await interaction.response.defer(ephemeral=True, thinking=True)
    async with ranks.lock:
        await ranks.setup_roles()
    await interaction.followup.send("Rank roles ready. Members should use /link to verify their Steam account. "
                                   "Keep all rank roles below the bot's role.", ephemeral=True)


@app_commands.command(name="rank", description="See your or another member's community progression rating")
@app_commands.guild_only()
async def rank_status(interaction: discord.Interaction, member: discord.Member | None = None):
    ranks = service(interaction)
    target = member or interaction.user
    match = ranks.find(target.id)
    if not match:
        raise ValueError("Not linked yet. Use /link or press Link Steam on the player panel.")
    _, player = match
    index = player["rank"]
    next_rank = f"Next: {RANKS[index+1][0]} at {RANKS[index+1][1]:,} points." if index < len(RANKS)-1 else "Highest rank achieved."
    status = player["hold"] or ("Paused" if not player["active"] else "Waiting for fresh leaderboard baseline" if player.get("baseline") is None else "Active")
    await interaction.response.send_message(f"<@{target.id}> — **{RANK_BADGES[index]} {RANKS[index][0]}**\nRating: **{player['points2']/2:,.1f}**\n"
        f"{next_rank}\nStatus: {status}\nLast scored source snapshot: {player['updated'] or 'Awaiting first fresh snapshot'}"
        + ("\nRole/announcement update pending." if player["pending"] else ""), ephemeral=True)


@app_commands.command(name="rank-pause", description="Admin: pause scoring and remove only this bot's progression roles; keep rating")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
async def rank_pause(interaction: discord.Interaction, member: discord.Member):
    ranks = service(interaction, True)
    await interaction.response.defer(ephemeral=True, thinking=True)
    async with ranks.lock:
        match = ranks.find(member.id)
        if not match:
            raise ValueError("Member is not registered.")
        player = match[1]
        if player["pending"]:
            await ranks.sync_player(player)
        player["active"] = False
        ranks.save()
        await ranks.sync_player(player)
    await interaction.followup.send("Paused. Rating and identity are preserved; rank roles removed.", ephemeral=True)


@app_commands.command(name="rank-resume", description="Admin: preserve rating and reset baseline after a pause or reviewed feed reset")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
async def rank_resume(interaction: discord.Interaction, member: discord.Member):
    ranks = service(interaction, True)
    await interaction.response.defer(ephemeral=True, thinking=True)
    async with ranks.lock:
        match = ranks.find(member.id)
        if not match:
            raise ValueError("Member is not registered.")
        steam, player = match
        if player["active"] and not player["hold"]:
            raise ValueError("Already active; the baseline has not been changed.")
        updated, rows = await ranks.fetch()
        if steam not in rows:
            raise ValueError("Player is absent from the feed; try again later.")
        player.update(active=True, hold=None, baseline=rows[steam], updated=updated)
        ranks.save()
        await ranks.sync_player(player)
    await interaction.followup.send("Resumed with the same rating and a fresh baseline. Paused/unreviewed results are not awarded.", ephemeral=True)


@app_commands.command(name="rank-guide", description="Post or repair the permanent rank progression guide")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
async def rank_guide(interaction: discord.Interaction, channel: discord.TextChannel | None = None):
    ranks = service(interaction, True)
    await interaction.response.defer(ephemeral=True, thinking=True)
    async with ranks.lock:
        message = await ranks.ensure_guide(channel)
    await interaction.followup.send(f"Rank progression guide ready: {message.jump_url}", ephemeral=True)


COMMANDS = (ranks_setup, rank_status, rank_pause, rank_resume, rank_guide)
