"""22A / WarDogs squad finder. Run with Python 3.11+."""
import asyncio
import logging
import time
import uuid

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import Config
from state import Room, Store

log = logging.getLogger("22a")


def safe(value):
    return discord.utils.escape_markdown(discord.utils.escape_mentions(value))


async def reply(interaction, text, **kwargs):
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True, **kwargs)
    else:
        await interaction.response.send_message(text, ephemeral=True, **kwargs)


class SafeView(discord.ui.View):
    async def on_error(self, interaction, error, item):
        await handle_error(interaction, error)


class SafeModal(discord.ui.Modal):
    async def on_error(self, interaction, error):
        await handle_error(interaction, error)


async def handle_error(interaction, error):
    if isinstance(error, ValueError):
        await reply(interaction, str(error))
    else:
        log.error("Discord action failed", exc_info=(type(error), error, error.__traceback__))
        await reply(interaction, "Discord could not finish that action. Saved changes will be retried. "
                    "If it persists, ask an admin to check the bot permissions and log.")


class CreateModal(SafeModal):
    def __init__(self, bot, kind):
        super().__init__(title=f"22A • {kind}")
        self.bot, self.kind = bot, kind
        self.name_input = discord.ui.TextInput(label="Room / squad name", max_length=40,
                                              placeholder="Alpha Squad")
        self.size_input = discord.ui.TextInput(label=f"Maximum players (2–{bot.cfg.max_size})", default="6", max_length=2)
        self.add_item(self.name_input)
        self.add_item(self.size_input)
        self.game_input = None
        if kind == "Other Game Squad":
            self.game_input = discord.ui.TextInput(label="Game", max_length=40)
            self.add_item(self.game_input)
        self.notes_input = discord.ui.TextInput(label="Notes", style=discord.TextStyle.paragraph,
                                               required=False, max_length=500,
                                               placeholder="Teamwork / mic required / game mode")
        if kind != "Private Channel":
            self.add_item(self.notes_input)

    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            size = int(str(self.size_input))
        except ValueError:
            raise ValueError("Maximum players must be a number.") from None
        if not 2 <= size <= self.bot.cfg.max_size:
            raise ValueError(f"Choose between 2 and {self.bot.cfg.max_size} players.")
        name = str(self.name_input).strip()
        if not name:
            raise ValueError("Give your room a name.")
        private = self.kind == "Private Channel"
        game = str(self.game_input).strip() if self.game_input else "WarDogs"
        if not game:
            raise ValueError("Enter a game name.")
        async with self.bot.mutation:
            self.bot.validate_context(interaction)
            if len(self.bot.rooms) >= self.bot.cfg.max_rooms:
                raise ValueError("The server room limit has been reached. Try again after a room closes.")
            if any(r.owner == interaction.user.id for r in self.bot.rooms.values()):
                raise ValueError("You already own a room. Use /room to manage or disband it first.")
            room = Room(uuid.uuid4().hex[:12], interaction.user.id, name, game, size,
                        private=private, notes=str(self.notes_input) if not private else "",
                        members=[interaction.user.id])
            self.bot.rooms[room.id] = room
            self.bot.store.save(room)  # Intent persisted before creating a Discord channel.
            await self.bot.reconcile(room)
            voice = self.bot.guild.get_channel(room.voice_id)
            moved = await self.bot.move_if_connected(interaction.user, voice)
        await reply(interaction, f"Your {'private room' if private else 'squad'} is ready: {voice.mention}. "
                    + ("You have been moved into it. " if moved else "Click the channel to join voice. ")
                    + "Use /room for controls and invitations. Empty rooms expire automatically.")


class PanelView(SafeView):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    async def interaction_check(self, interaction):
        self.bot.validate_context(interaction)
        return True

    @discord.ui.button(label="Create WarDogs Squad", emoji="🐕", style=discord.ButtonStyle.primary, custom_id="22a:panel:wardogs:v1")
    async def wardogs(self, interaction, button):
        await interaction.response.send_modal(CreateModal(self.bot, "WarDogs Squad"))

    @discord.ui.button(label="Create Other Game Squad", emoji="🕹️", custom_id="22a:panel:other:v1")
    async def other(self, interaction, button):
        await interaction.response.send_modal(CreateModal(self.bot, "Other Game Squad"))

    @discord.ui.button(label="Create Private Channel", emoji="🔊", custom_id="22a:panel:private:v1")
    async def private(self, interaction, button):
        await interaction.response.send_modal(CreateModal(self.bot, "Private Channel"))


class AdvertView(SafeView):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    def room(self, interaction):
        self.bot.validate_context(interaction)
        return self.bot.lookup(next((r.id for r in self.bot.rooms.values()
                                    if r.message_id == interaction.message.id), ""))

    @discord.ui.button(label="Join Squad", emoji="➕", style=discord.ButtonStyle.success, custom_id="22a:advert:join:v1")
    async def join(self, interaction, button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        async with self.bot.mutation:
            room = self.room(interaction)
            room.join(interaction.user.id)
            self.bot.store.save(room)
            await self.bot.reconcile(room)
            voice = self.bot.guild.get_channel(room.voice_id)
            moved = await self.bot.move_if_connected(interaction.user, voice)
        await reply(interaction, f"Joined **{safe(room.name)}**. " +
                    ("You have been moved to voice." if moved else f"Join voice here: {voice.mention}"))

    @discord.ui.button(label="Leave Squad", emoji="➖", custom_id="22a:advert:leave:v1")
    async def leave(self, interaction, button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        async with self.bot.mutation:
            room = self.room(interaction)
            await self.bot.remove_member(room, interaction.user.id)
        await reply(interaction, "You left the squad. Leadership passes to the next member if needed.")

    @discord.ui.button(label="Join Voice", emoji="🔊", custom_id="22a:advert:voice:v1")
    async def voice(self, interaction, button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        async with self.bot.mutation:
            room = self.room(interaction)
            if interaction.user.id not in room.members:
                raise ValueError("Join the squad first to unlock its voice channel.")
            voice = self.bot.guild.get_channel(room.voice_id)
            if voice is None:
                raise ValueError("The voice channel is unavailable; cleanup is in progress.")
            moved = await self.bot.move_if_connected(interaction.user, voice)
        await reply(interaction, "Moved you into voice." if moved else f"Click {voice.mention} to connect. "
                    "Discord only lets bots move you when you are already in a voice channel.")

    @discord.ui.button(label="Leader Controls", emoji="⚙️", custom_id="22a:advert:controls:v1")
    async def controls(self, interaction, button):
        room = self.room(interaction)
        self.bot.check_owner(room, interaction.user)
        await reply(interaction, f"Controls for **{safe(room.name)}**", view=Controls(self.bot, room.id))


class RenameModal(SafeModal, title="22A • Rename room"):
    name_input = discord.ui.TextInput(label="New name", max_length=40)

    def __init__(self, bot, room_id):
        super().__init__()
        self.bot, self.room_id = bot, room_id

    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        async with self.bot.mutation:
            room = self.bot.lookup(self.room_id)
            self.bot.check_owner(room, interaction.user)
            name = str(self.name_input).strip()
            if not name:
                raise ValueError("Enter a name.")
            room.name = name
            self.bot.store.save(room)
            await self.bot.reconcile(room)
        await reply(interaction, "Room renamed.")


class PickMember(SafeView):
    def __init__(self, bot, room_id, action):
        super().__init__(timeout=180)
        self.bot, self.room_id, self.action = bot, room_id, action
        picker = discord.ui.UserSelect(placeholder=f"Choose someone to {action}", min_values=1, max_values=1)
        picker.callback = self.choose
        self.add_item(picker)
        self.picker = picker

    async def choose(self, interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        async with self.bot.mutation:
            room = self.bot.lookup(self.room_id)
            self.bot.check_owner(room, interaction.user)
            target = await self.bot.guild.fetch_member(self.picker.values[0].id)
            if target.bot:
                raise ValueError("Choose a human member of this server.")
            if self.action == "invite":
                room.join(target.id)
                self.bot.store.save(room)
                await self.bot.reconcile(room)
            elif self.action == "kick":
                if target.id == room.owner:
                    raise ValueError("Transfer leadership first, or disband the room.")
                await self.bot.remove_member(room, target.id)
            else:
                if target.id not in room.members:
                    raise ValueError("The new leader must already belong to this room.")
                if any(r.id != room.id and r.owner == target.id for r in self.bot.rooms.values()):
                    raise ValueError("That person already owns another room.")
                room.owner = target.id
                self.bot.store.save(room)
                await self.bot.reconcile(room)
        await reply(interaction, f"{self.action.title()} complete. " +
                    ("They can now see the room; let them know to join it. No DM was sent." if self.action == "invite" else ""))


class ConfirmDisband(SafeView):
    def __init__(self, bot, room_id):
        super().__init__(timeout=60)
        self.bot, self.room_id = bot, room_id

    @discord.ui.button(label="Confirm disband", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction, button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        async with self.bot.mutation:
            room = self.bot.lookup(self.room_id)
            self.bot.check_owner(room, interaction.user)
            room.status = "deleting"
            self.bot.store.save(room)
            await self.bot.reconcile(room)
        self.stop()
        await reply(interaction, "Room disbanded and advert removed.")


class Controls(SafeView):
    def __init__(self, bot, room_id):
        super().__init__(timeout=300)
        self.bot, self.room_id = bot, room_id

    async def interaction_check(self, interaction):
        self.bot.validate_context(interaction)
        self.bot.check_owner(self.bot.lookup(self.room_id), interaction.user)
        return True

    @discord.ui.button(label="Rename", emoji="✏️")
    async def rename(self, interaction, button):
        await interaction.response.send_modal(RenameModal(self.bot, self.room_id))

    @discord.ui.button(label="Lock / Unlock", emoji="🔒")
    async def lock(self, interaction, button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        async with self.bot.mutation:
            room = self.bot.lookup(self.room_id)
            self.bot.check_owner(room, interaction.user)
            room.locked = not room.locked
            self.bot.store.save(room)
            await self.bot.reconcile(room)
        await reply(interaction, "Locked to new members. Existing members can still reconnect." if room.locked else "Unlocked.")

    @discord.ui.button(label="Invite member", emoji="➕")
    async def invite(self, interaction, button):
        await reply(interaction, "Choose a server member to grant access. Unlock first if locked.",
                    view=PickMember(self.bot, self.room_id, "invite"))

    @discord.ui.button(label="Kick member", emoji="➖")
    async def kick(self, interaction, button):
        await reply(interaction, "Choose a member to remove and disconnect.", view=PickMember(self.bot, self.room_id, "kick"))

    @discord.ui.button(label="Transfer leader", emoji="👑")
    async def transfer(self, interaction, button):
        await reply(interaction, "Choose an existing room member.", view=PickMember(self.bot, self.room_id, "transfer"))

    @discord.ui.button(label="Disband", emoji="🗑️", style=discord.ButtonStyle.danger)
    async def disband(self, interaction, button):
        await reply(interaction, "Delete this voice room and its advert? Connected members will be disconnected.",
                    view=ConfirmDisband(self.bot, self.room_id))


class SquadBot(commands.Bot):
    def __init__(self, cfg):
        intents = discord.Intents.none()
        intents.guilds = intents.members = intents.voice_states = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents,
                         allowed_mentions=discord.AllowedMentions.none(), help_command=None)
        self.cfg = cfg
        self.store = Store(cfg.database)
        identity = f"{cfg.guild_id}:{cfg.lfg_id}:{cfg.category_id}"
        previous = self.store.get("server_channels")
        if previous and previous != identity:
            self.store.db.close()
            raise ValueError("This database belongs to different server/channel IDs. Restore the original IDs, "
                             "or disband existing rooms and use a new DATABASE_PATH for the new setup.")
        self.store.set("server_channels", identity)
        self.rooms = self.store.rooms()
        self.mutation = asyncio.Lock()
        self.initialized = False
        self.guild = self.lfg = self.category = None
        self.leaderboard = None
        self.clan_leaderboard = None
        self.progression = None
        self.steam_link = None

    async def setup_hook(self):
        from progression import Progression, COMMANDS as rank_commands
        self.progression = Progression.from_env(self)
        if self.progression:
            for command in rank_commands:
                self.tree.add_command(command, guild=discord.Object(self.cfg.guild_id))
        from steam_link import SteamLink, link_command
        self.steam_link = SteamLink.from_env(self)
        if self.steam_link:
            self.tree.add_command(link_command, guild=discord.Object(self.cfg.guild_id))
            await self.steam_link.start()
        from leaderboard import Leaderboard, ClanLeaderboard, LeaderboardView
        self.leaderboard = Leaderboard.from_env(self)
        if self.leaderboard:
            self.add_view(LeaderboardView(self.leaderboard))
        self.clan_leaderboard = ClanLeaderboard.from_env(self)
        if self.clan_leaderboard:
            self.add_view(LeaderboardView(self.clan_leaderboard))
        self.add_view(PanelView(self))
        self.add_view(AdvertView(self))
        self.tree.add_command(panel, guild=discord.Object(self.cfg.guild_id))
        self.tree.add_command(room_command, guild=discord.Object(self.cfg.guild_id))
        self.tree.add_command(leave_command, guild=discord.Object(self.cfg.guild_id))
        self.tree.on_error = self.command_error
        await self.tree.sync(guild=discord.Object(self.cfg.guild_id))

    async def command_error(self, interaction, error):
        await handle_error(interaction, getattr(error, "original", error))

    def validate_context(self, interaction):
        if not self.initialized or interaction.guild_id != self.cfg.guild_id:
            raise ValueError("The 22A bot is starting up or this is the wrong server. Try again shortly.")

    def lookup(self, room_id):
        room = self.rooms.get(room_id)
        if not room or room.status != "active":
            raise ValueError("This room has closed or is still being prepared. Use the panel to create a new one.")
        return room

    def check_owner(self, room, member):
        if member.id != room.owner and not member.guild_permissions.manage_guild:
            raise ValueError("Only the room leader or a member with Manage Server can do that.")

    async def on_ready(self):
        if self.initialized:
            return
        try:
            self.guild = self.get_guild(self.cfg.guild_id)
            if self.guild is None:
                raise ValueError("GUILD_ID does not match a server the bot has joined.")
            self.lfg = self.guild.get_channel(self.cfg.lfg_id)
            self.category = self.guild.get_channel(self.cfg.category_id)
            if not isinstance(self.lfg, discord.TextChannel) or not isinstance(self.category, discord.CategoryChannel):
                raise ValueError("LFG_CHANNEL_ID must be a text channel and VOICE_CATEGORY_ID a category in this server.")
            required_guild = ["view_channel", "manage_channels", "manage_roles", "connect",
                              "move_members", "speak", "stream", "use_voice_activation"]
            missing_guild = [p for p in required_guild if not getattr(self.guild.me.guild_permissions, p)]
            if missing_guild:
                raise ValueError("Enable these permissions in Server Settings > Roles > the bot's role: "
                                 + ", ".join(missing_guild) + ". Category overrides alone are insufficient.")
            for channel, required in [(self.lfg, ["view_channel", "send_messages", "embed_links", "read_message_history"]),
                                      (self.category, ["view_channel", "manage_channels", "manage_roles", "connect", "move_members",
                                                       "speak", "stream", "use_voice_activation"])]:
                permissions = channel.permissions_for(self.guild.me)
                missing = [p for p in required if not getattr(permissions, p)]
                if missing:
                    raise ValueError(f"Missing permissions in {channel.name}: {', '.join(missing)}")
            async with self.mutation:
                # A fresh grace period on restart avoids deleting rooms based on stale occupancy.
                for room in self.rooms.values():
                    room.empty_since = time.time()
                    self.store.save(room)
                await self.ensure_panel()
            self.initialized = True
            if self.progression:
                self.progression.start()
            if self.leaderboard:
                self.leaderboard.start()
            if self.clan_leaderboard:
                self.clan_leaderboard.start()
            if not self.sweep.is_running():
                self.sweep.start()
            log.info("22A ready in %s with %d saved rooms", self.guild.name, len(self.rooms))
        except Exception:
            log.exception("Startup failed; correct .env/permissions and restart")
            await self.close()

    def panel_embed(self):
        embed = discord.Embed(title="🎮 Looking For Squad", color=0xC8102E,
            description="**Starting a squad?**\nHit **Create WarDogs Squad** for a WARDOGS match, "
            "or **Create Other Game Squad** for anything else. Pick the details in the popup and "
            "I'll post an advert and set up a private voice channel for it.\n\n"
            "**Joining one?**\nFind an active advert below and click **Join Squad**. "
            "Already in voice? I'll move you straight in. Otherwise click **Join Voice** for the channel.\n\n"
            "**Just want a voice channel, no advert?**\nHit **Create Private Channel** for your own room. "
            "Use **/room** to invite friends and manage it.\n\n"
            "**Lead your squad. Find your team. Roll out with 22A.**")
        embed.set_footer(text="[22A] — WARDOGS COMMUNITY • Temporary rooms clean up automatically")
        if self.cfg.logo_url:
            embed.set_thumbnail(url=self.cfg.logo_url)
        return embed

    async def close(self):
        if self.steam_link:
            await self.steam_link.close()
        if self.progression:
            self.progression.stop()
        self.sweep.cancel()
        if self.leaderboard:
            self.leaderboard.stop()
        if self.clan_leaderboard:
            self.clan_leaderboard.stop()
        await super().close()

    async def ensure_panel(self):
        message_id = self.store.get("panel_id")
        if message_id:
            try:
                message = await self.lfg.fetch_message(int(message_id))
                await message.edit(embed=self.panel_embed(), view=PanelView(self))
                return message
            except discord.NotFound:
                pass
        message = await self.lfg.send(embed=self.panel_embed(), view=PanelView(self))
        self.store.set("panel_id", message.id)
        return message

    def advert_embed(self, room):
        embed = discord.Embed(title=f"{'🐕' if room.game == 'WarDogs' else '🕹️'} {safe(room.game)} SQUAD",
                              color=0xC8102E, description=safe(room.notes) or "Squad up with 22A.")
        embed.add_field(name="Squad", value=safe(room.name))
        embed.add_field(name="Leader", value=f"<@{room.owner}>")
        embed.add_field(name="Players", value=f"{len(room.members)} / {room.limit}")
        embed.add_field(name="Status", value="🔒 Locked" if room.locked else ("🔴 Full" if len(room.members) >= room.limit else "🟢 Recruiting"))
        embed.add_field(name="Private voice", value=f"<#{room.voice_id}>")
        embed.add_field(name="Members", value="\n".join(f"<@{uid}>" for uid in room.members) or "None", inline=False)
        embed.set_footer(text=f"[22A] — WARDOGS • Room {room.id} • Empty voice rooms expire")
        return embed

    async def move_if_connected(self, member, voice):
        if member.voice and member.voice.channel and member.voice.channel.id != voice.id:
            try:
                await member.move_to(voice, reason="22A member requested squad voice")
                return True
            except discord.HTTPException:
                log.warning("Could not move member %s; they can join manually", member.id)
        return False

    async def remove_member(self, room, user_id):
        room.leave(user_id)
        self.store.save(room)
        await self.reconcile(room)

    async def reconcile(self, room):
        """Reapply desired state. Failed operations retain their records for the next sweep."""
        voice = self.guild.get_channel(room.voice_id) if room.voice_id else None
        marker = f"22a-{room.id}-"
        if voice is None and room.status == "creating":
            # Recover a create that succeeded at Discord just before the process stopped.
            voice = next((c for c in self.category.voice_channels if c.name.startswith(marker)), None)
            if voice:
                room.voice_id = voice.id
                self.store.save(room)
        if voice is None and room.status == "active":
            room.status = "deleting"  # An admin manually removed the channel.
            self.store.save(room)
        if room.status == "deleting":
            if voice:
                try:
                    await voice.delete(reason="22A temporary room closed")
                except discord.NotFound:
                    pass
            if room.message_id:
                try:
                    await self.lfg.get_partial_message(room.message_id).delete()
                except discord.NotFound:
                    pass
            self.store.delete(room.id)
            self.rooms.pop(room.id, None)
            return

        members = []
        for uid in list(room.members):
            member = self.guild.get_member(uid)
            if member is None:
                try:
                    member = await self.guild.fetch_member(uid)
                except discord.NotFound:
                    room.leave(uid)
                    self.store.save(room)
                    continue
            members.append(member)
        if room.status == "deleting":
            await self.reconcile(room)
            return
        overwrites = {self.guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
                      # Management rights come from the server role. Setting a MANAGE_ROLES
                      # channel overwrite during creation requires Administrator at Discord.
                      self.guild.me: discord.PermissionOverwrite(view_channel=True, connect=True)}
        for member in members:
            overwrites[member] = discord.PermissionOverwrite(view_channel=True, connect=True, speak=True,
                                                             stream=True, use_voice_activation=True)
        name = room.name[:100]
        if voice is None:
            # Use a recovery marker only until the Discord channel ID is durably saved.
            voice = await self.guild.create_voice_channel((marker + room.name)[:100], category=self.category, overwrites=overwrites,
                                                          user_limit=room.limit, reason="22A temporary squad room")
            room.voice_id = voice.id
            self.store.save(room)
        if voice.name != name or voice.user_limit != room.limit or voice.overwrites != overwrites:
            await voice.edit(name=name, user_limit=room.limit, overwrites=overwrites, reason="22A room membership updated")
        # Revoking Connect does not disconnect someone already in voice.
        for member in list(voice.members):
            if member.id not in room.members and not member.bot and not member.guild_permissions.administrator:
                await member.move_to(None, reason="22A room access removed")
        room.status = "active"
        self.store.save(room)
        if not room.private:
            embed = self.advert_embed(room)
            message = None
            if room.message_id:
                try:
                    message = await self.lfg.fetch_message(room.message_id)
                except discord.NotFound:
                    pass
            else:
                # Recover an advert sent just before a crash (bounded recent history).
                async for candidate in self.lfg.history(limit=200):
                    if candidate.author.id == self.user.id and candidate.embeds and f"Room {room.id} •" in (candidate.embeds[0].footer.text or ""):
                        message = candidate
                        break
            if message is None:
                message = await self.lfg.send(embed=embed, view=AdvertView(self))
            elif not message.embeds or message.embeds[0].to_dict() != embed.to_dict():
                await message.edit(embed=embed, view=AdvertView(self))
            room.message_id = message.id
            self.store.save(room)

    @tasks.loop(seconds=30)
    async def sweep(self):
        if not self.is_ready() or self.guild.unavailable:
            return  # Do not make cleanup decisions from a disconnected gateway cache.
        async with self.mutation:
            for room in list(self.rooms.values()):
                try:
                    voice = self.guild.get_channel(room.voice_id) if room.voice_id else None
                    now = time.time()
                    if voice and voice.members:
                        room.empty_since = None
                        room.ever_used = True
                    elif room.empty_since is None:
                        room.empty_since = now
                    if room.status == "active" and room.expired(now, self.cfg.initial_seconds, self.cfg.empty_seconds):
                        room.status = "deleting"
                    self.store.save(room)
                    await self.reconcile(room)
                except Exception:
                    log.exception("Room %s reconciliation failed; retry in 30 seconds", room.id)

    @sweep.before_loop
    async def before_sweep(self):
        await self.wait_until_ready()

    async def on_voice_state_update(self, member, before, after):
        if not self.initialized or before.channel == after.channel:
            return
        async with self.mutation:
            changed_ids = {c.id for c in (before.channel, after.channel) if c}
            for room in self.rooms.values():
                if room.voice_id in changed_ids:
                    voice = self.guild.get_channel(room.voice_id)
                    if voice and voice.members:
                        room.ever_used = True
                        room.empty_since = None
                    elif room.empty_since is None:
                        room.empty_since = time.time()
                    self.store.save(room)

    async def on_member_remove(self, member):
        if not self.initialized or member.guild.id != self.cfg.guild_id:
            return
        async with self.mutation:
            for room in list(self.rooms.values()):
                if member.id in room.members:
                    try:
                        await self.remove_member(room, member.id)
                    except Exception:
                        log.exception("Member departure cleanup failed; sweep will retry")


@app_commands.command(name="panel", description="Post or repair the permanent 22A squad panel")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
async def panel(interaction: discord.Interaction):
    bot = interaction.client
    bot.validate_context(interaction)
    if not interaction.user.guild_permissions.manage_guild:
        raise ValueError("Manage Server permission is required.")
    await interaction.response.defer(ephemeral=True, thinking=True)
    async with bot.mutation:
        message = await bot.ensure_panel()
    await reply(interaction, f"22A panel ready: {message.jump_url}")


@app_commands.command(name="room", description="Manage your 22A room; admins may supply a room ID from an advert/channel")
@app_commands.guild_only()
async def room_command(interaction: discord.Interaction, room_id: str | None = None):
    bot = interaction.client
    bot.validate_context(interaction)
    if room_id:
        room = bot.lookup(room_id)
    else:
        room = next((r for r in bot.rooms.values() if r.owner == interaction.user.id and r.status == "active"), None)
        if room is None:
            raise ValueError("You do not own an active room. Create one from the 22A panel.")
    bot.check_owner(room, interaction.user)
    await reply(interaction, f"**{safe(room.name)}** • <#{room.voice_id}> • "
                f"{len(room.members)}/{room.limit} members • {'Locked' if room.locked else 'Unlocked'} • Room ID: `{room.id}`",
                view=Controls(bot, room.id))


@app_commands.command(name="leave-room", description="Leave a room by its ID (also works for private rooms)")
@app_commands.guild_only()
async def leave_command(interaction: discord.Interaction, room_id: str):
    bot = interaction.client
    bot.validate_context(interaction)
    await interaction.response.defer(ephemeral=True, thinking=True)
    async with bot.mutation:
        await bot.remove_member(bot.lookup(room_id), interaction.user.id)
    await reply(interaction, "You left the room.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        config = Config.load()
        bot = SquadBot(config)
    except ValueError as error:
        raise SystemExit(f"Configuration error: {error}") from None
    bot.run(config.token, log_handler=None)
