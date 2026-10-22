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
from rank_divisions import thresholds, division

log = logging.getLogger("22a.ranks")
RANKS = [("Private", 0), ("Lance Corporal", 250), ("Corporal", 750),
         ("Sergeant", 1500), ("Staff Sergeant", 3000),
         ("Warrant Officer Class 2", 5000), ("Warrant Officer Class 1", 8000)]
COUNTERS = ("wins", "losses", "kills", "deaths")
SCORING = {"wins": 20, "losses": -10, "kills": 5, "deaths": -3}
RANK_BADGES = ["🪖", "🔰", "⚔️", "🛡️", "🎖️", "⭐", "👑"]
STATE_KEY = "progression_v1"
GUIDE_MARKER = "22A • Rank progression guide v1"


def rank_role_name(value, rank):
    """Accept only our exact rank suffix with no prefix or one badge token."""
    suffix = f"22A Rank • {rank}"
    if value == suffix:
        return True
    if not value.endswith(" " + suffix):
        return False
    prefix = value[:-(len(suffix)+1)]
    return bool(prefix) and not any(c.isspace() or c.isalnum() for c in prefix)


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
    embed.add_field(name="🪖 Season 1 promotion ladder", value="\n".join(f"{RANK_BADGES[i]} **{name}** — {points:,} points" for i, (name, points) in enumerate(RANKS)), inline=False)
    embed.add_field(name="↕️ Promotions and demotions", value="The bot awards your rank role automatically and announces rank changes.\n"
                    "Each rank has a **50-point demotion buffer**: Season 1 LCPL: 250 / below 200; Season 2: 313 / below 263.\n"
                    "Private is the lowest rank. Rating cannot fall below 0. **Inactivity costs no points.**", inline=False)
    embed.add_field(name="⏱️ Updates and fair play", value="Results are checked **every five minutes**, after the source publishes them.\n"
                    "Combat points use WDUK-tracked results. Level bonuses use your approved WARDOGS Tools profile. Relinking does not reset your rating.\n"
                    "Missing/stale data does not deduct points. Counter decreases pause scoring while automatic recovery checks three fresh snapshots over ten minutes. Large abnormal jumps still need admin review.\n"
                    "Recovery preserves rating and excludes uncertain results; restored old totals do not earn points twice. Use **/rank** to see your status.", inline=False)
    embed.add_field(name="🏆 Live ELO standings", value="The live board ranks the **top 20 linked server members** by their saved progression rating and refreshes **every five minutes**. "
                    "This is your current season rating, not just points earned today.", inline=False)
    embed.add_field(name="🌟 New level bonuses", value="**Wardog level +2** · **Role level +1**\n"
                    "Each newly gained level counts, across Assault, Medic, Recon, Support, Driver and Pilot.\n"
                    "Example: 3 Wardog levels + 2 Medic levels + 1 Pilot level = **+9 rating**.\n"
                    "Your current levels establish a baseline and award **no historical points**. Freshness checks apply; corrected levels cannot be counted twice.", inline=False)
    embed.add_field(name="🌐 Enable your level bonuses", value="1. Visit **https://wardogs.tools/account** and sign in with Discord, then link your WARDOGS account through Steam.\n"
                    "2. On the Player Hub, press **Connect Tools Profile** and paste your public player-profile URL.\n"
                    "3. Ask staff to check ownership and run **/approve-tools** for you.\n"
                    "The first fresh eligible snapshot becomes your baseline. The source normally syncs around every 15 minutes; bonuses may take longer to appear. Cash, worth and gold are display-only. WDUK cash-earned rewards start in Season 2; Tools cash is not used for scoring.", inline=False)
    embed.add_field(name="🏁 Seasons", value="At season end, staff use **End Season** on the admin panel and confirm. Final top-20 Season ELO standings are posted and full records archived.\n"
                    "Everyone starts the next season at **Private / 0 rating**, with fresh combat and level baselines. Steam links and history stay saved; manual pauses remain.\n"
                    "Resets are staff-triggered, not automatic by date. Season 2 activates the higher thresholds shown below; installation does not reset ratings.", inline=False)
    embed.add_field(name="👤 Your Player Hub", value="View your profile, compare players, inspect **Rating History**, choose team/play preferences and share your profile to **#wardogs-chat**. These preferences do not affect rating.", inline=False)
    embed.add_field(name="🥉 🥈 🥇 Season 2 divisions",value="Each military rank has Bronze, Silver and Gold milestones. Season 2 promotion thresholds: **313 / 938 / 1,875 / 3,750 / 6,250 / 10,000**. WO1 Silver: **11,250**, Gold: **12,500**. Roles and nickname abbreviations stay military ranks.",inline=False)
    embed.add_field(name="💰 Season 2 cash rewards",value="**+1 rating per $10,000 newly earned WDUK cash**, maximum **25/day (UTC)**. Fractions carry forward; whole rewards above the cap are discarded. First fresh snapshot sets your baseline. Spending does not deduct rating. Tools cash, wallet dollars and share sales do not count.",inline=False)
    embed.add_field(name="Black Market daily bonus", value="Every complete **$1,000 net realised daily profit earns +20 ELO**. Share-sale profit after fees and challenge wins count; realised losses reduce the daily total. Settles after **00:00 UTC**. No starting balances, refunds, unsold gains or historical profits. No losing-day ELO deduction or fractional carryover. Paused/reviewed players wait within the same season; unclaimed old-season bonuses expire.", inline=False)
    embed.add_field(name="Fantasy Squad", value="Pick three players and a captain for the next UTC day on the website. Daily Fantasy winners share **30 ELO**; the season champion shares **150 ELO**, applied before season standings are archived. Positive winning totals required. Each of three boosters can be used once per season. Missing-data rounds wait, then void without consuming boosters.", inline=False)
    embed.set_footer(text=GUIDE_MARKER)
    return embed


def decode_stats(payload, now=None, *, check_fresh=True):
    updated = timestamp(payload["updatedAt"])
    age = ((now or datetime.now(timezone.utc)) - updated).total_seconds()
    if check_fresh and (age > 900 or age < -300):
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
        if 'cashEarned' in row:result[steam]['cashEarned']=row['cashEarned']
    return updated.isoformat(), result


def rank_for(points2, current, floors=None):
    floors = floors or [r[1] for r in RANKS]
    """Integer half-points avoid rounding; 50-point demotion buffer."""
    while current < len(RANKS) - 1 and points2 >= floors[current + 1] * 2:
        current += 1
    while current > 0 and points2 < (floors[current] - 50) * 2:
        current -= 1
    return current


def new_player(discord_id, counters, updated):
    from season_stats import fresh_state
    return {"discord_id": discord_id, "season_stats": fresh_state(), "points2": 0, "rank": 0, "active": True,
            "baseline": counters, "updated": updated, "hold": None, "pending": None}


def recover_counters(player, counters, updated):
    """Confirm a persistent correction, without rescoring restored old totals."""
    if (not player["active"] or player["pending"] or
            not (player.get("hold") or "").startswith("Source counters decreased")):
        return False
    if timestamp(updated) <= timestamp(player["updated"]):
        return True
    candidate = player.get("recovery")
    if candidate and timestamp(updated) <= timestamp(candidate["last"]):
        return True
    if candidate:
        elapsed = max(1, (timestamp(updated)-timestamp(candidate["last"])).total_seconds()/3600)
        delta = {k: counters[k]-candidate["counters"][k] for k in COUNTERS}
        if (any(v < 0 for v in delta.values()) or delta["wins"]+delta["losses"] > 60*elapsed
                or delta["kills"]+delta["deaths"] > 10000*elapsed):
            candidate = None
    if candidate is None:
        player["recovery"] = {"first": updated, "last": updated, "count": 1, "counters": counters.copy()}
        return True
    candidate.update(last=updated, count=candidate["count"]+1, counters=counters.copy())
    if candidate["count"] < 3 or (timestamp(updated)-timestamp(candidate["first"])).total_seconds() < 600:
        return True
    previous = player.get("counter_floor", player["baseline"])
    player["counter_floor"] = {k: max(previous[k], player["baseline"][k], counters[k]) for k in COUNTERS}
    player.update(baseline=counters.copy(), updated=updated, hold=None)
    player.pop("recovery", None)
    player.setdefault("history", []).append({"at": datetime.now(timezone.utc).isoformat(),
        "kind": "Automatic recovery", "before": player["points2"], "after": player["points2"],
        "from": player["rank"], "to": player["rank"], "actor": None,
        "reason": "Counter correction confirmed across three snapshots over at least ten minutes. Rating preserved; uncertain results excluded. Restored old totals will not earn points again."})
    return True


def advance(player, counters, updated):
    if player.get('season_started') and timestamp(updated) <= timestamp(player['season_started']):
        return
    if recover_counters(player, counters, updated):
        return
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
        player["hold"] = "Source counters decreased. Automatic checks are waiting for three consistent fresh snapshots over ten minutes."
        return
    # A generous bound catches obvious corrupt jumps, scaled to elapsed time (including downtime).
    hours = max(1, (timestamp(updated) - timestamp(player["updated"])).total_seconds() / 3600)
    if delta["wins"] + delta["losses"] > 60 * hours or delta["kills"] + delta["deaths"] > 10000 * hours:
        player["hold"] = "Unusually large source change. Admin review and /rank-resume required."
        return
    if player.get("counter_floor"):
        floor = player["counter_floor"]
        delta = {k: max(0, counters[k]-max(player["baseline"][k], floor[k])) for k in COUNTERS}
        if all(counters[k] >= floor[k] for k in COUNTERS):
            player.pop("counter_floor", None)
    old_points, old_rank = player["points2"], player["rank"]
    points = max(0, old_points + 2 * sum(SCORING[key] * delta[key] for key in COUNTERS))
    rank = rank_for(points, old_rank, thresholds(player))
    player.update(points2=points, rank=rank, baseline=counters, updated=updated)
    if any(delta.values()):
        player.setdefault("history", []).append({"at": datetime.now(timezone.utc).isoformat(),
            "source": updated, "kind": "results", "before": old_points, "after": points,
            "from": old_rank, "to": rank, "delta": delta, "weights": SCORING.copy()})
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
        from card_send import safely, standings_message, standings_rows
        card = lambda: {'kicker': '22A DAILY STANDINGS', 'tail': now.strftime('%-d %b').upper(), 'title': 'WHO LEADS THE PACK',
                        'sub': f"Season {self.state.get('season', 1)} ELO · {len(players)} linked members", 'rows': standings_rows(self.bot, players)}
        sent = await safely(embed, lambda: standings_message(self.bot, embed, card()))
        await channel.send(**sent, allowed_mentions=discord.AllowedMentions.none())
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
        from web_links import web_view, components_changed
        view=web_view("standings")
        if message is None:
            message = await channel.send(embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())
        elif not message.embeds or message.embeds[0].to_dict() != embed.to_dict() or components_changed(message,view):
            await message.edit(embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())
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
        guild = self.bot.guild
        if not guild.me.guild_permissions.manage_roles:
            raise ValueError("Give the bot Manage Roles first.")
        # Fetch fresh roles: a previous create/save failure may have left a real role
        # behind even though its ID was never committed to the database.
        existing = await guild.fetch_roles()
        for index, (name, _) in enumerate(RANKS):
            saved = self.state["roles"].get(str(index))
            role = next((r for r in existing if r.id == saved), None)
            if role is None:
                matches = [r for r in existing if rank_role_name(r.name, name)]
                if matches:
                    safe = [r for r in matches if not r.managed and not r.is_default()
                            and not r >= guild.me.top_role and not r.permissions.value]
                    if not safe:
                        raise ValueError(f"Existing {name} roles cannot be managed safely. Remove server permissions and place one below the bot, then retry.")
                    role = min(safe, key=lambda r: r.id)  # Deterministic oldest role.
                else:
                    role = await guild.create_role(name=f"{RANK_BADGES[index]} 22A Rank • {name}",
                        permissions=discord.Permissions.none(), hoist=False, mentionable=False,
                        reason="22A progression setup requested by admin")
                    existing.append(role)
                self.state["roles"][str(index)] = role.id
                self.save()
            if role.name == f"22A Rank • {name}":
                await role.edit(name=f"{RANK_BADGES[index]} 22A Rank • {name}", reason="22A rank badge update")
        # Validate the freshly fetched selection, without waiting for gateway cache updates.
        for role_id in self.state["roles"].values():
            role = next(r for r in existing if r.id == role_id)
            if role.managed or role.is_default() or role >= guild.me.top_role or role.permissions.value:
                raise ValueError("Rank roles must be cosmetic and below the bot role.")

    async def fetch(self):
        from progression_sources import fetch_progression
        return await fetch_progression(self)

    async def fetch_public_payload(self):
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=40), headers={"User-Agent": "22A-Discord-Bot/1.0", "Accept": "application/json"}) as session:
            async with session.get("https://wardogs.uk/leaderboard-all.json") as response:
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    body.extend(chunk)
                    if len(body) > 20*1024*1024:
                        raise ValueError("Public feed too large")
                return json.loads(body)

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
        from rank_nicknames import sync_nickname
        await sync_nickname(self, member, player)
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
                if event.get("reason"):
                    embed.description += "\nRating adjustment: " + discord.utils.escape_markdown(discord.utils.escape_mentions(event["reason"]))
                from rank_images import badge, decorate
                embed.description = f"{badge(self.bot.guild, event['to'])} **{RANKS[event['to']][0]}**\n" + embed.description
                decorate(embed, self.bot.guild, event['to'])
                embed.set_footer(text=marker)
                import cards
                from card_send import avatar, display, safely, with_card

                async def build():
                    data = {'name': display(member), 'from': event['from'], 'to': event['to'], 'to_name': RANKS[event['to']][0],
                            'before': event['before'] / 2, 'after': event['after'] / 2,
                            'delta': None if event.get('reason') else delta, 'reason': event.get('reason')}
                    return await with_card(embed, cards.rank_change, (data, await avatar(member)), 'rank-update.png',
                                           description=f"<@{player['discord_id']}> · **{RANKS[event['from']][0]} → {RANKS[event['to']][0]}**")
                await channel.send(**await safely(embed, build), allowed_mentions=discord.AllowedMentions.none())
            player["pending"] = None
            self.save()

    @tasks.loop(minutes=5)
    async def poll(self):
        if not self.bot.is_ready() or not self.bot.initialized:
            return
        async with self.lock:
            try:
                from fantasy import tick, ensure_round
                betting = getattr(self.bot, 'betting', None)
                if betting:
                    from website_fantasy import catalog
                    channel = self.bot.guild.get_channel(betting.book.data.get('channel', 0))
                    if channel:ensure_round(self.state, catalog(self.bot, channel))
                tick(self.state)
                self.save()
                from market_rewards import settle_rewards
                if getattr(self.bot, "betting", None):
                    settle_rewards(self, self.bot.betting.book)
            except Exception:
                log.exception("Market reward settlement failed; retry next poll")
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
                # TF21 community servers: scored on its own baseline; a TF21 outage never blocks this update.
                tf21_time, tf21_rows = None, {}
                from tf21_api import enabled as tf21_enabled, fetch as fetch_tf21
                if tf21_enabled():
                    try:
                        tf21_time, tf21_rows = await fetch_tf21(self.bot)
                    except Exception as exc:
                        log.warning("TF21 feed unavailable (%s); WarDogs UK scoring continues", exc)
                for steam, player in self.state["players"].items():
                    try:
                        # Deliver an outstanding transition before scoring another one.
                        if player["pending"]:
                            await self.sync_player(player)
                        if self.state.get('season',1)>=2:player['rank_rules']=2
                        if steam in rows:
                            was_held = player["hold"]
                            from wduk_api import apply_source, source_id
                            player_time = getattr(self, "source_times", {}).get(steam, updated)
                            player_source = getattr(self, "source_overrides", {}).get(steam, source_id())
                            if not apply_source(player, rows[steam], player_time, player_source):
                                advance(player, rows[steam], player_time)
                            from cash_rewards import apply_cash
                            apply_cash(player, rows[steam].get('cashEarned'), player_time, player_source)
                            self.save()
                            if player["hold"] and not was_held:
                                log.warning("Rank scoring held for Discord member %s: %s", player["discord_id"], player["hold"])
                        if steam in tf21_rows:
                            from tf21_progress import advance_tf21
                            advance_tf21(player, tf21_rows[steam], tf21_time)
                            self.save()
                        await self.sync_player(player)
                    except Exception:
                        log.exception("Rank update failed for member %s; will retry", player["discord_id"])
            except Exception:
                log.exception("Progression update unavailable; existing ratings preserved, retry in five minutes")
            finally:
                try:
                    from rank_nicknames import sync_all
                    await sync_all(self)
                except Exception:
                    log.exception("Nickname sync failed; retry on next five-minute check")
                try:
                    from kill_feed import service as kill_feed
                    await kill_feed(self.bot).refresh(set(self.state["players"]))
                except Exception as exc:
                    log.warning("TF21 kill feed unavailable (%s); dog tags update next time", exc)
                try:
                    from seasons import refresh_seasons
                    await refresh_seasons(self)
                except Exception:
                    log.exception("Season/level checks failed; saved ratings retained")
                try:
                    from community import refresh
                    await refresh(self)
                except Exception:
                    log.exception("Community boards/report update failed; retry in five minutes")
                try:
                    self.bot.store.backup()
                except Exception:
                    log.exception("Database backup failed; check persistent storage")

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
    next_rank = f"Next: {RANKS[index+1][0]} at {thresholds(player)[index+1]:,} points." if index < len(RANKS)-1 else "Highest rank achieved."
    status = player["hold"] or ("Paused" if not player["active"] else "Waiting for fresh leaderboard baseline" if player.get("baseline") is None else "Active")
    await interaction.response.send_message(f"<@{target.id}> — **{RANK_BADGES[index]} {RANKS[index][0]} · {division(player)['name']}**\nRating: **{player['points2']/2:,.1f}**\n"
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
async def rank_resume(interaction: discord.Interaction, member: discord.Member, keep_baseline: bool = False):
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
        from wduk_api import source_id
        if keep_baseline:
            from resume_baseline import validate_preserved_resume
            validate_preserved_resume(player, rows[steam], getattr(ranks, "source_times", {}).get(steam, updated), getattr(ranks, "source_overrides", {}).get(steam, source_id()))
            player.update(active=True, hold=None)
        else:
            player.update(active=True, hold=None, baseline=rows[steam],
                          updated=getattr(ranks, "source_times", {}).get(steam, updated),
                          rating_source=getattr(ranks, "source_overrides", {}).get(steam, source_id()))
        player.pop('recovery', None)
        player.setdefault('history', []).append(dict(at=datetime.now(timezone.utc).isoformat(),kind='Resume keeping baseline' if keep_baseline else 'Resume',before=player['points2'],after=player['points2'],actor=interaction.user.id,reason='Staff slash-command resume'))
        ranks.save()
        await ranks.sync_player(player)
    await interaction.followup.send("Resumed keeping the original baseline. Consistent paused gains may score on the next poll." if keep_baseline else "Resumed with the same rating and a fresh baseline. Paused/unreviewed results are not awarded.", ephemeral=True)


@app_commands.command(name="rank-guide", description="Post or repair the permanent rank progression guide")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
async def rank_guide(interaction: discord.Interaction, channel: discord.TextChannel | None = None):
    ranks = service(interaction, True)
    await interaction.response.defer(ephemeral=True, thinking=True)
    async with ranks.lock:
        message = await ranks.ensure_guide(channel)
    await interaction.followup.send(f"Rank progression guide ready: {message.jump_url}", ephemeral=True)


@app_commands.command(name="rank-roles", description="Admin: identify saved rank roles and duplicate role IDs without deleting anything")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
async def rank_roles(interaction: discord.Interaction):
    ranks = service(interaction, True)
    await interaction.response.defer(ephemeral=True)
    roles = await ranks.bot.guild.fetch_roles()
    embed = discord.Embed(title="22A Rank Role Audit", color=0xC8102E,
        description="KEEP = role ID saved by this bot. Other matches are duplicate candidates. "
        "Before deleting a candidate in Server Settings, check its members and channel permissions. "
        "Run /ranks-setup first if KEEP is missing. Only run one bot instance.")
    for index, (name, _) in enumerate(RANKS):
        saved = ranks.state["roles"].get(str(index))
        matches = [r for r in roles if r.id == saved or rank_role_name(r.name, name)]
        lines = [f"{'KEEP' if r.id == saved else 'Candidate'}: <@&{r.id}> — `{r.id}`" for r in matches]
        embed.add_field(name=name, value=("\n".join(lines) or "No matching roles found.")[:1024], inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


from rank_images import rank_images_setup
from rank_nicknames import nickname_sync
COMMANDS = (ranks_setup, rank_status, rank_pause, rank_resume, rank_guide, rank_roles, rank_images_setup, nickname_sync)
