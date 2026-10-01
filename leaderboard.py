"""Optional WDUK public-feed leaderboard. Does not require a second bot token."""
import asyncio
import json
import logging
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
import discord
from discord.ext import tasks

log = logging.getLogger("22a.leaderboard")
PAGE_URL = "https://wardogs.uk/leaderboard.html"
METRICS = {
    "kills": ("Kills", "💀"),
    "kd": ("K/D", "🎯"),
    "deaths": ("Deaths", "☠️"),
    "hoursPlayed": ("Hours", "⏱️"),
    "cashEarned": ("Cash", "💰"),
}
PERIODS = {"all": "All time", "weekly": "This week", "daily": "Today"}
MARKER = "22A Leaderboard v1"


def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("The source timestamp must include its timezone.")
    return result


def decode_feed(payload):
    """Read the same fields/tuple format used by the website; fail closed on schema changes."""
    if not isinstance(payload, dict):
        raise ValueError("Unexpected leaderboard payload")
    timestamp(payload["updatedAt"])
    fields, tuples = payload.get("fields"), payload.get("players")
    required = {"steamId", "name", "online", *METRICS}
    if (not isinstance(fields, list) or not all(isinstance(f, str) for f in fields)
            or len(set(fields)) != len(fields) or not required.issubset(fields)
            or not isinstance(tuples, list)):
        raise ValueError("The leaderboard feed format has changed.")
    rows = []
    for values in tuples:
        if not isinstance(values, list) or len(values) != len(fields):
            raise ValueError("Invalid leaderboard row")
        row = dict(zip(fields, values))
        if not isinstance(row["steamId"], str) or not row["steamId"].isdigit():
            raise ValueError("Invalid Steam ID")
        if not isinstance(row["name"], str):
            raise ValueError("Invalid player name")
        for metric in METRICS:
            value = row[metric]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"Invalid {metric} value")
        rows.append(row)
    return rows


def make_snapshot(payload, query, limit):
    rows = [r for r in decode_feed(payload) if query.casefold() in r["name"].casefold()]
    # Save enough rows for every button, without storing the entire public player database.
    selected = {}
    for metric in METRICS:
        for row in sorted(rows, key=lambda r: (-r[metric], r["steamId"]))[:limit]:
            selected[row["steamId"]] = {k: row[k] for k in ("steamId", "name", "online", *METRICS)}
    return {"updatedAt": payload["updatedAt"], "checkedAt": datetime.now(timezone.utc).isoformat(),
            "count": len(rows), "rows": list(selected.values())}


def render_embed(snapshot, metric, query, period, limit, links, logo="", failed=False):
    label, icon = METRICS[metric]
    escaped_query = discord.utils.escape_markdown(discord.utils.escape_mentions(query[:60]))
    scope = f'Names containing “{escaped_query}”' if query else "All players"
    lines = [f"**{PERIODS[period]} · {label}**", scope, ""]
    if snapshot is None:
        lines.append("Waiting for the public leaderboard feed. The bot will retry every five minutes.")
    else:
        rows = sorted(snapshot["rows"], key=lambda r: (-r[metric], r["steamId"]))[:limit]
        rank, previous = 0, None
        shown = 0
        for position, row in enumerate(rows, 1):
            if row[metric] != previous:
                rank = position
            previous = row[metric]
            badge = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"**{rank}.**")
            name = " ".join(row["name"].split())[:48]
            name = discord.utils.escape_markdown(discord.utils.escape_mentions(name))
            name = name.replace("<", "‹").replace(">", "›")
            steam_id = row["steamId"]
            who = f"[{name}](https://steamcommunity.com/profiles/{steam_id})"
            if steam_id in links:
                who = f"<@{links[steam_id]}> — {name}"
            online = " 🟢" if row["online"] else ""
            value = row[metric]
            formatted = (f"{value:,.2f}" if metric == "kd" else
                         f"{value:,.1f} h" if metric == "hoursPlayed" else f"{value:,.0f}")
            entry = [f"{badge} {who}{online}", f"{icon} **{formatted}**"]
            if len("\n".join(lines + entry)) > 3300:
                break
            lines.extend(entry)
            shown += 1
        if not rows:
            lines.append("No players match this filter in the selected period.")
        source_time = int(timestamp(snapshot["updatedAt"]).timestamp())
        checked_time = int(timestamp(snapshot["checkedAt"]).timestamp())
        lines.extend(["", f"Showing {shown} of {snapshot['count']:,} matching players.",
                      f"Source updated <t:{source_time}:R> · Last fetched <t:{checked_time}:R>"])
        if (datetime.now(timezone.utc) - timestamp(snapshot["updatedAt"])).total_seconds() > 900:
            lines.append("⚠️ The source data is over 15 minutes old.")
    if failed:
        lines.append("⚠️ Latest fetch failed. Keeping the last successful data; retrying in five minutes.")
    embed = discord.Embed(title="🏆 22A — WarDogs Leaderboard", url=PAGE_URL,
                          description="\n".join(lines), color=0xC8102E)
    embed.set_footer(text=f"{MARKER} • Data: wardogs.uk • Refresh: 5 min • 🟢 Online in source snapshot")
    if logo:
        embed.set_thumbnail(url=logo)
    return embed


class LeaderboardView(discord.ui.View):
    def __init__(self, service):
        super().__init__(timeout=None)
        for metric, (label, _) in METRICS.items():
            button = discord.ui.Button(label=label, custom_id=f"22a:{service.namespace}:{metric}:v1",
                style=discord.ButtonStyle.primary if metric == service.metric else discord.ButtonStyle.secondary)
            async def callback(interaction, selected=metric):
                await service.select(interaction, selected)
            button.callback = callback
            self.add_item(button)

    async def on_error(self, interaction, error, item):
        log.error("Leaderboard button failed", exc_info=(type(error), error, error.__traceback__))
        message = "Could not update the leaderboard. Check the bot's channel permissions and log."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


class Leaderboard:
    namespace = "leaderboard"
    marker = MARKER
    feed_prefix = "leaderboard"

    def __init__(self, bot, channel_id, query="22A", period="all", limit=20, links=None):
        self.bot, self.channel_id = bot, channel_id
        self.query, self.period, self.limit = query, period, limit
        self.links = links or {}
        self.lock = asyncio.Lock()
        self.last_click = 0.0
        self.failed = False
        self.message_id = None
        self.metric = bot.store.get(f"{self.namespace}_metric") or "kills"
        if self.metric not in METRICS:
            self.metric = "kills"
        self.snapshot = None
        raw = bot.store.get(f"{self.namespace}_cache")
        if raw:
            try:
                cached = json.loads(raw)
                if cached["query"] == query and cached["period"] == period and cached["limit"] == limit:
                    self.snapshot = cached["snapshot"]
            except (ValueError, KeyError, TypeError):
                log.warning("Ignoring invalid leaderboard cache")
        self.message_key = f"{self.namespace}_message:{channel_id}"
        saved = bot.store.get(self.message_key)
        if saved:
            self.message_id = int(saved)

    @classmethod
    def from_env(cls, bot):
        raw_id = os.getenv("LEADERBOARD_CHANNEL_ID", "").strip()
        if not raw_id:
            return None
        if not raw_id.isdigit() or int(raw_id) <= 0:
            raise ValueError("LEADERBOARD_CHANNEL_ID must be a text-channel ID or empty.")
        period = os.getenv("LEADERBOARD_PERIOD", "all").strip()
        if period not in PERIODS:
            raise ValueError("LEADERBOARD_PERIOD must be all, weekly, or daily.")
        limit = int(os.getenv("LEADERBOARD_TOP", "20"))
        if not 1 <= limit <= 20:
            raise ValueError("LEADERBOARD_TOP must be between 1 and 20.")
        links = {}
        path = Path(__file__).resolve().parent / "leaderboard-links.json"
        if path.exists():
            links = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(links, dict) or any(not str(k).isdigit() or not str(v).isdigit() for k, v in links.items()):
                raise ValueError("leaderboard-links.json must map Steam IDs to Discord user IDs.")
        return cls(bot, int(raw_id), os.getenv("LEADERBOARD_FILTER", "22A").strip(),
                   period, limit, {str(k): str(v) for k, v in links.items()})

    async def fetch(self):
        from wduk_api import enabled, fetch_clan
        if self.namespace == "leaderboard" and enabled() and self.period == "all":
            payload = await fetch_clan(self.bot)
            return make_snapshot(payload, "", self.limit)
        url = f"https://wardogs.uk/{self.feed_prefix}-{self.period}.json"
        timeout = aiohttp.ClientTimeout(total=40)
        async with aiohttp.ClientSession(timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0 (compatible; 22A-Discord-Leaderboard/1.0)",
            "Accept": "application/json"}) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    body.extend(chunk)
                    if len(body) > 20 * 1024 * 1024:
                        raise ValueError("Leaderboard feed exceeds the 20 MB safety limit")
                return self.make_snapshot(json.loads(body))

    def make_snapshot(self, payload):
        return make_snapshot(payload, self.query, self.limit)

    def embed(self):
        links = dict(self.links)
        progression = getattr(self.bot, "progression", None)
        if progression is not None:
            for steam, player in progression.state["players"].items():
                if player.get("steam_verified") and player.get("active"):
                    links[steam] = str(player["discord_id"])
        embed = render_embed(self.snapshot, self.metric, self.query, self.period, self.limit,
                            links, self.bot.cfg.logo_url, self.failed)
        from wduk_api import enabled
        if enabled() and self.period == "all":
            embed.description = embed.description.replace(f'Names containing “{discord.utils.escape_markdown(discord.utils.escape_mentions(self.query[:60]))}”', '22A clan members')
            embed.set_footer(text=f"{MARKER} • Data: WDUK clan API • Refresh: 5 min • 🟢 Online in source snapshot")
        return embed

    async def publish(self):
        channel = self.bot.get_channel(self.channel_id)
        if not isinstance(channel, discord.TextChannel) or channel.guild.id != self.bot.cfg.guild_id:
            raise ValueError(f"{self.namespace.upper()}_CHANNEL_ID must be a text channel in the configured server.")
        permissions = channel.permissions_for(channel.guild.me)
        missing = [p for p in ("view_channel", "send_messages", "embed_links", "read_message_history")
                   if not getattr(permissions, p)]
        if missing:
            raise ValueError("Leaderboard channel missing permissions: " + ", ".join(missing))
        message = None
        if self.message_id:
            try:
                message = await channel.fetch_message(self.message_id)
            except discord.NotFound:
                self.message_id = None
        if message is None:
            # Recover a send/save crash or an existing matching post after a lost message ID.
            async for candidate in channel.history(limit=100):
                if (candidate.author.id == self.bot.user.id and candidate.embeds
                        and (candidate.embeds[0].footer.text or "").startswith(self.marker)):
                    message = candidate
                    break
        view = LeaderboardView(self)
        if message:
            await message.edit(embed=self.embed(), view=view, allowed_mentions=discord.AllowedMentions.none())
        else:
            message = await channel.send(embed=self.embed(), view=view, allowed_mentions=discord.AllowedMentions.none())
        self.message_id = message.id
        self.bot.store.set(self.message_key, message.id)

    async def select(self, interaction, metric):
        if (interaction.guild_id != self.bot.cfg.guild_id or interaction.channel_id != self.channel_id
                or not interaction.message or interaction.message.id != self.message_id):
            await interaction.response.send_message("Use the current leaderboard message in its configured channel.", ephemeral=True)
            return
        await interaction.response.defer()
        async with self.lock:
            if time.monotonic() - self.last_click < 3:
                await interaction.followup.send("Please wait a few seconds between changes.", ephemeral=True)
                return
            self.last_click = time.monotonic()
            self.metric = metric
            self.bot.store.set(f"{self.namespace}_metric", metric)
            await self.publish()

    @tasks.loop(minutes=5)
    async def refresh(self):
        if not self.bot.is_ready():
            return
        async with self.lock:
            try:
                snapshot = await self.fetch()
                self.bot.store.set(f"{self.namespace}_cache", json.dumps({"query": self.query, "period": self.period,
                                    "limit": self.limit, "snapshot": snapshot}))
                self.snapshot, self.failed = snapshot, False
            except Exception:
                self.failed = True
                log.exception("Public leaderboard fetch failed; retaining last data and retrying in five minutes")
            try:
                await self.publish()
            except Exception:
                log.exception("Leaderboard message update failed; retrying in five minutes")

    def start(self):
        if not self.refresh.is_running():
            self.refresh.start()

    def stop(self):
        self.refresh.cancel()


def make_clan_snapshot(payload, limit=10):
    if not isinstance(payload, dict) or not isinstance(payload.get("clans"), list):
        raise ValueError("The clan leaderboard feed format has changed.")
    timestamp(payload["updatedAt"])
    rows = []
    tags = set()
    for row in payload["clans"]:
        if not isinstance(row, dict) or not isinstance(row.get("tag"), str) or not row["tag"].strip():
            raise ValueError("Invalid clan tag")
        if row["tag"] in tags:
            raise ValueError("Duplicate clan tag")
        tags.add(row["tag"])
        for metric in (*METRICS, "memberCount"):
            value = row.get(metric)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"Invalid clan {metric}")
        rows.append({k: row[k] for k in ("tag", "memberCount", *METRICS)})
    selected = {}
    for metric in METRICS:
        for row in sorted(rows, key=lambda r: (-r[metric], r["tag"]))[:limit]:
            selected[row["tag"]] = row
    return {"updatedAt": payload["updatedAt"], "checkedAt": datetime.now(timezone.utc).isoformat(),
            "count": len(rows), "rows": list(selected.values())}


def render_clan_embed(snapshot, metric="kills", period="all", logo="", failed=False):
    label, icon = METRICS[metric]
    lines = [f"**{PERIODS[period]} · Ranked by {label}**", "All clans / communities on WDUK servers", ""]
    if snapshot is None:
        lines.append("Waiting for the public clan feed. Retrying every five minutes.")
    else:
        rows = sorted(snapshot["rows"], key=lambda r: (-r[metric], r["tag"]))[:10]
        rank, previous, shown = 0, None, 0
        for position, row in enumerate(rows, 1):
            if row[metric] != previous:
                rank = position
            previous = row[metric]
            badge = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"**{rank}.**")
            tag = " ".join(row["tag"].split())[:40]
            tag = discord.utils.escape_markdown(discord.utils.escape_mentions(tag))
            tag = tag.replace("<", "‹").replace(">", "›")
            star = " ⭐" if row["tag"].strip("[] ").casefold() == "22a" else ""
            value = row[metric]
            formatted = (f"{value:,.2f}" if metric == "kd" else
                         f"{value:,.1f} h" if metric == "hoursPlayed" else f"{value:,.0f}")
            entry = [f"{badge} **[{tag}]**{star} · {row['memberCount']:,.0f} members",
                     f"{icon} **{formatted} {label if metric != 'hoursPlayed' else ''}**",
                     f"Kills {row['kills']:,.0f} · Deaths {row['deaths']:,.0f} · K/D {row['kd']:,.2f}",
                     f"Hours {row['hoursPlayed']:,.1f} · Cash {row['cashEarned']:,.0f}", ""]
            if len("\n".join(lines + entry)) > 3300:
                break
            lines.extend(entry)
            shown += 1
        if not rows:
            lines.append("No clans published for this period yet.")
        source_time = int(timestamp(snapshot["updatedAt"]).timestamp())
        checked_time = int(timestamp(snapshot["checkedAt"]).timestamp())
        lines.extend([f"Showing {shown} of {snapshot['count']:,} clans.",
                      f"Source updated <t:{source_time}:R> · Last fetched <t:{checked_time}:R>"])
        if (datetime.now(timezone.utc) - timestamp(snapshot["updatedAt"])).total_seconds() > 900:
            lines.append("⚠️ The source data is over 15 minutes old.")
    if failed:
        lines.append("⚠️ Latest fetch failed. Keeping the last successful data; retrying in five minutes.")
    embed = discord.Embed(title="🏆 Top 10 WarDogs Clans", url=PAGE_URL,
                          description="\n".join(lines), color=0xC8102E)
    embed.set_footer(text="22A Clan Leaderboard v1 • Data: wardogs.uk • Refresh: 5 min")
    if logo:
        embed.set_thumbnail(url=logo)
    return embed


class ClanLeaderboard(Leaderboard):
    namespace = "clan_leaderboard"
    marker = "22A Clan Leaderboard v1"
    feed_prefix = "leaderboard-clans"

    @classmethod
    def from_env(cls, bot):
        raw_id = os.getenv("CLAN_LEADERBOARD_CHANNEL_ID", "").strip()
        if not raw_id:
            return None
        if not raw_id.isdigit() or int(raw_id) <= 0:
            raise ValueError("CLAN_LEADERBOARD_CHANNEL_ID must be a text-channel ID or empty.")
        period = os.getenv("CLAN_LEADERBOARD_PERIOD", "all").strip()
        if period not in PERIODS:
            raise ValueError("CLAN_LEADERBOARD_PERIOD must be all, weekly, or daily.")
        return cls(bot, int(raw_id), query="", period=period, limit=10)

    def make_snapshot(self, payload):
        return make_clan_snapshot(payload, self.limit)

    def embed(self):
        return render_clan_embed(self.snapshot, self.metric, self.period, self.bot.cfg.logo_url, self.failed)
