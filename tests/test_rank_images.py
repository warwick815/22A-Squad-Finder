import unittest
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock
import discord
from rank_images import badge, decorate, rank_images_setup, NAMES, INSTALLED


class RankImageTests(unittest.IsolatedAsyncioTestCase):
    def test_fallback_and_available_badge(self):
        self.assertEqual(badge(None, 1), '🔰')
        guild = Mock(spec=discord.Guild)
        guild.id = 123
        emoji = Mock(name='emoji')
        emoji.name = 'rank22a_lcpl'
        emoji.url = 'https://cdn.discordapp.com/emojis/123.png'
        emoji.is_usable.return_value = True
        guild.emojis = [emoji]
        embed = discord.Embed()
        decorate(embed, guild, 1)
        self.assertEqual(embed.thumbnail.url, emoji.url)
        self.assertEqual(badge(guild, 1), str(emoji))
        INSTALLED[guild.id] = [emoji]
        guild.emojis = []
        self.assertEqual(badge(guild, 1), str(emoji))
        INSTALLED.pop(guild.id)
        guild.emojis = [emoji]
        emoji.is_usable.return_value = False
        self.assertEqual(badge(guild, 1), '🔰')

    async def test_setup_reuses_existing_badges(self):
        interaction = Mock()
        interaction.user.guild_permissions.manage_guild = True
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.guild.fetch_emojis = AsyncMock(return_value=[SimpleNamespace(name='rank22a_'+n) for n in NAMES])
        interaction.guild.create_custom_emoji = AsyncMock()
        await rank_images_setup.callback(interaction)
        interaction.guild.create_custom_emoji.assert_not_awaited()
        interaction.user.guild_permissions.manage_guild = False
        with self.assertRaises(ValueError):
            await rank_images_setup.callback(interaction)
