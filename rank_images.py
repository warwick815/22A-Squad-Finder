"""Rank artwork installed as server emojis, reused by profiles and announcements."""
import asyncio
from pathlib import Path
import discord
from discord import app_commands

NAMES = ('pte', 'lcpl', 'cpl', 'sgt', 'ssgt', 'wo2', 'wo1')
FALLBACK = ('🪖', '🔰', '⚔️', '🛡️', '🎖️', '⭐', '👑')
LOCK = asyncio.Lock()


def emoji_for(guild, rank):
    if not isinstance(guild, discord.Guild):
        return None
    return next((e for e in guild.emojis if e.name == 'rank22a_' + NAMES[rank] and e.is_usable()), None)


def badge(guild, rank):
    emoji = emoji_for(guild, rank)
    return str(emoji) if emoji else FALLBACK[rank]


def decorate(embed, guild, rank):
    emoji = emoji_for(guild, rank)
    if emoji:
        embed.set_thumbnail(url=str(emoji.url))


@app_commands.command(name='rank-images-setup', description='Staff: install the seven rank badge images')
@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
async def rank_images_setup(interaction: discord.Interaction):
    interaction.client.validate_context(interaction)
    if not interaction.user.guild_permissions.manage_guild:
        raise ValueError('Manage Server permission required.')
    await interaction.response.defer(ephemeral=True, thinking=True)
    async with LOCK:
        existing = await interaction.guild.fetch_emojis()
        missing = [name for name in NAMES if not any(e.name == 'rank22a_' + name for e in existing)]
        root = Path(__file__).parent / 'rank_badges'
        for name in missing:
            if not (root / (name + '.png')).is_file():
                raise ValueError('Upload the rank_badges folder alongside the bot files first.')
        for name in missing:
            try:
                await interaction.guild.create_custom_emoji(name='rank22a_' + name,
                    image=(root / (name + '.png')).read_bytes(), reason='22A rank artwork setup')
            except discord.HTTPException as error:
                await interaction.followup.send(f'Could not install {name.upper()} (Discord code {error.code}). Check Create Expressions permission and free emoji slots. Already installed badges are kept; rerun this command after fixing it.', ephemeral=True)
                return
    await interaction.followup.send('Rank images installed. Reopen player profiles to see them. Future promotion and demotion announcements will use the badges. If images do not appear immediately, wait a few seconds for Discord to update its emoji cache.', ephemeral=True)
