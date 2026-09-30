"""Persistent player UI and private profiles, using the progression feed cache."""
import json
import math
import os
from datetime import datetime, timezone

import discord
from discord import app_commands

from progression import RANKS, RANK_BADGES, guide_embed
from leaderboard import timestamp

MARKER = "22A • Player panel v1"


def stat(row, key, decimals=0, suffix=""):
    value = row.get(key)
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        return "—"
    return f"{value:,.{decimals}f}{suffix}"


def profile_embed(member, steam, player, row, updated):
    index = player["rank"]
    rating = player["points2"] / 2
    embed = discord.Embed(title=f"{RANK_BADGES[index]} 22A Player Profile", color=0xC8102E,
        description=f"<@{member.id}> · [Steam profile](https://steamcommunity.com/profiles/{steam})\n"
                    f"**{RANK_BADGES[index]} {RANKS[index][0]}**")
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🎖️ Rating", value=f"**{rating:,.1f}**", inline=True)
    status = "Paused" if not player["active"] else "Under review" if player["hold"] else "Waiting for fresh leaderboard baseline" if player.get("baseline") is None else "Active"
    embed.add_field(name="Status", value=status + (" · role/announcement pending" if player["pending"] else ""), inline=True)
    embed.add_field(name="Steam link", value="Steam verified" if player.get("steam_verified") else "Admin confirmed", inline=True)
    if index < len(RANKS) - 1:
        target = RANKS[index + 1][1]
        lower = RANKS[index][1]
        fraction = max(0, min(1, (rating - lower) / (target - lower)))
        filled = int(fraction * 10)
        embed.add_field(name=f"Next: {RANK_BADGES[index+1]} {RANKS[index+1][0]}",
            value=f"{'▰'*filled}{'▱'*(10-filled)}\n**{max(0, target-rating):,.1f} points to go** · target {target:,}", inline=False)
    else:
        embed.add_field(name="Progression", value="👑 Highest rank achieved", inline=False)
    if index:
        embed.add_field(name="Demotion boundary", value=f"Below **{RANKS[index][1]-50:,}** rating", inline=False)
    if player["hold"]:
        embed.add_field(name="Review needed", value=player["hold"][:1000], inline=False)
    if not row:
        embed.add_field(name="Game stats", value="Waiting for the next successful five-minute feed update. Your saved rating is shown above.", inline=False)
    else:
        name = discord.utils.escape_markdown(discord.utils.escape_mentions(str(row.get("name", "Unknown"))[:100]))
        embed.add_field(name="All-time WDUK game stats", value=name + "\nThese are lifetime source stats; rating only counts results after enrollment.", inline=False)
        for key, label, decimals, suffix in [
            ("kills", "💀 Kills", 0, ""), ("deaths", "☠️ Deaths", 0, ""), ("kd", "🎯 K/D", 2, ""),
            ("wins", "🏆 Wins", 0, ""), ("losses", "❌ Losses", 0, ""),
            ("hoursPlayed", "⏱️ Hours", 1, " h"), ("cashEarned", "💰 Cash earned", 0, ""),
            ("killsPerHour", "Kills / hour", 2, ""), ("teamKills", "Team kills", 0, ""),
            ("suicides", "Suicides", 0, "")]:
            embed.add_field(name=label, value=stat(row, key, decimals, suffix), inline=True)
        wins, losses = row.get("wins"), row.get("losses")
        win_rate = f"{100*wins/(wins+losses):.1f}%" if type(wins) is int and type(losses) is int and wins+losses > 0 else "—"
        embed.add_field(name="Win rate", value=win_rate, inline=True)
        embed.add_field(name="Presence at source update", value="🟢 Online" if row.get("online") else "Offline", inline=True)
        server = discord.utils.escape_markdown(discord.utils.escape_mentions(str(row.get("favouriteServer") or "—")[:100]))
        embed.add_field(name="Most played server", value=server, inline=True)
        if updated:
            source = timestamp(updated)
            age = (datetime.now(timezone.utc) - source).total_seconds()
            embed.add_field(name="Game data updated", value=f"<t:{int(source.timestamp())}:R>" + (" · ⚠️ cached data is over 15 minutes old" if age > 900 else ""), inline=False)
            minutes = row.get("lastSeenMinsAgo")
            if type(minutes) in (int, float) and math.isfinite(minutes) and minutes >= 0:
                embed.add_field(name="Last seen in game", value=f"<t:{int(source.timestamp()-minutes*60)}:R>", inline=True)
    embed.add_field(name="Rating last checked", value=f"<t:{int(timestamp(player['updated']).timestamp())}:R>" if player.get("updated") else "Awaiting first fresh snapshot; historical stats will not award points.", inline=False)
    embed.set_footer(text="22A • Private profile • Game stats: wardogs.uk • Reopen to refresh")
    return embed


class PlayerView(discord.ui.View):
    def __init__(self, service):
        super().__init__(timeout=None)
        self.service = service

    async def interaction_check(self, interaction):
        self.service.bot.validate_context(interaction)
        return True

    @discord.ui.button(label="My Profile", emoji="👤", style=discord.ButtonStyle.primary, custom_id="22a:player:profile:v1")
    async def profile(self, interaction, button):
        await self.service.show_profile(interaction)

    @discord.ui.button(label="Link Steam", emoji="🔗", custom_id="22a:player:link:v1")
    async def link(self, interaction, button):
        from steam_link import link_command
        await link_command.callback(interaction)

    @discord.ui.button(label="Rank Guide", emoji="🎖️", custom_id="22a:player:guide:v1")
    async def guide(self, interaction, button):
        await interaction.response.send_message(embed=guide_embed(bool(self.service.bot.steam_link)), ephemeral=True)

    async def on_error(self, interaction, error, item):
        from bot import handle_error
        await handle_error(interaction, error)


class PlayerPanel:
    def __init__(self, bot):
        self.bot = bot
        self.rows = {}
        self.updated = None
        raw = bot.store.get("player_profile_cache")
        if raw:
            try:
                cached = json.loads(raw)
                self.rows, self.updated = cached["rows"], cached["updated"]
            except (ValueError, KeyError, TypeError):
                pass

    def record(self, payload):
        fields = payload["fields"]
        self.rows = {str(values[fields.index("steamId")]): dict(zip(fields, values)) for values in payload["players"]}
        self.updated = payload["updatedAt"]
        linked = self.bot.progression.state["players"]
        self.bot.store.set("player_profile_cache", json.dumps({"updated": self.updated,
                            "rows": {steam: row for steam, row in self.rows.items() if steam in linked}}))

    async def show_profile(self, interaction):
        match = self.bot.progression.find(interaction.user.id)
        if not match:
            await interaction.response.send_message("You haven’t linked an account yet. Press **Link Steam** on the player panel, "
                "or ask an admin to enroll you if Steam sign-in is not configured.", ephemeral=True)
            return
        steam, player = match
        await interaction.response.send_message(embed=profile_embed(interaction.user, steam, player,
            self.rows.get(steam), self.updated), ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    async def ensure(self, channel=None):
        if channel is None:
            raw = os.getenv("PLAYER_PANEL_CHANNEL_ID", "").strip() or self.bot.store.get("player_panel_channel")
            channel = self.bot.get_channel(int(raw or self.bot.progression.channel_id))
        if not isinstance(channel, discord.TextChannel) or channel.guild.id != self.bot.cfg.guild_id:
            raise ValueError("Choose a text channel in this server for the player panel.")
        perms = channel.permissions_for(channel.guild.me)
        if not all(getattr(perms, p) for p in ("view_channel", "send_messages", "embed_links", "read_message_history")):
            raise ValueError("Player panel needs View Channel, Send Messages, Embed Links and Read Message History.")
        embed = discord.Embed(title="🪖 22A — Player Hub", color=0xC8102E,
            description="**Your service record. Your progress. Your next promotion.**\n\n"
            "👤 **My Profile** — privately view your rank, rating, next promotion and game stats.\n"
            "🔗 **Link Steam** — sign in through Steam and confirm your account in Discord.\n"
            "🎖️ **Rank Guide** — see how points, promotions and demotions work.\n\n"
            "Start at Private. Earn your stripes together. Game data refreshes every five minutes.")
        embed.set_footer(text=MARKER)
        if self.bot.cfg.logo_url:
            embed.set_thumbnail(url=self.bot.cfg.logo_url)
        key = f"player_panel_message:{channel.id}"
        saved = self.bot.store.get(key)
        message = None
        if saved:
            try:
                message = await channel.fetch_message(int(saved))
            except discord.NotFound:
                pass
        if not message:
            async for candidate in channel.history(limit=100):
                if candidate.author.id == self.bot.user.id and candidate.embeds and candidate.embeds[0].footer.text == MARKER:
                    message = candidate
                    break
        view = PlayerView(self)
        if message is None:
            message = await channel.send(embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())
        elif not message.embeds or message.embeds[0].to_dict() != embed.to_dict():
            await message.edit(embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())
        self.bot.store.set(key, message.id)
        self.bot.store.set("player_panel_channel", channel.id)
        return message


@app_commands.command(name="player-panel", description="Post or repair the permanent player profile and Steam-link panel")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
async def player_panel_command(interaction: discord.Interaction, channel: discord.TextChannel | None = None):
    interaction.client.validate_context(interaction)
    if not interaction.user.guild_permissions.manage_guild:
        raise ValueError("Manage Server permission is required.")
    await interaction.response.defer(ephemeral=True, thinking=True)
    async with interaction.client.progression.lock:
        message = await interaction.client.player_panel.ensure(channel)
    await interaction.followup.send(f"Player hub ready: {message.jump_url}", ephemeral=True)
