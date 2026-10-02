import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord

from player_panel import PlayerPanel, PlayerView, profile_embed
from progression import new_player, RANKS, RANK_BADGES
from state import Store

STEAM = "76561198000000001"
UPDATED = datetime.now(timezone.utc).isoformat()


class ProfileTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "state.db")
        self.bot = MagicMock()
        self.bot.tools_stats.add = AsyncMock()
        self.bot.store = self.store
        self.bot.cfg.guild_id = 1
        self.bot.cfg.logo_url = ""
        self.bot.progression.state = {"players": {STEAM: {}}}
        self.panel = PlayerPanel(self.bot)
        self.member = SimpleNamespace(id=1, display_avatar=SimpleNamespace(url="https://example.test/avatar.png"))
        self.player = new_player(1, dict(wins=0, losses=0, kills=0, deaths=0), UPDATED)

    async def asyncTearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    async def test_every_rank_profile_stays_within_discord_limits(self):
        row = dict(name="[22A] Example", kills=123, deaths=45, kd=2.73, wins=3, losses=2,
                   hoursPlayed=12.3, cashEarned=999, killsPerHour=10, teamKills=1, suicides=0,
                   online=True, lastSeenMinsAgo=0, favouriteServer="WDUK #4")
        for i in range(len(RANKS)):
            self.player.update(rank=i, points2=RANKS[i][1]*2, hold="Test review")
            embed = profile_embed(self.member, STEAM, self.player, row, UPDATED)
            self.assertEqual(embed.title, '22A Player Profile')
            self.assertLessEqual(len(embed.fields), 25)
            self.assertLessEqual(len(embed), 6000)
            values = {f.name: f.value for f in embed.fields}
            self.assertEqual(values["Win rate"], "60.0%")
            self.assertEqual(values["🎯 K/D"], "2.73")

    async def test_missing_stats_do_not_invent_zeroes(self):
        embed = profile_embed(self.member, STEAM, self.player, None, None)
        self.assertIn("Waiting", str(embed.to_dict()))
        embed = profile_embed(self.member, STEAM, self.player, {"name": "Test"}, UPDATED)
        self.assertEqual(next(f.value for f in embed.fields if f.name == "🎯 K/D"), "—")

    async def test_cache_persists_only_linked_accounts(self):
        payload = {"updatedAt": UPDATED, "fields": ["steamId", "name", "kills"],
                   "players": [[STEAM, "Example", 123], ["76561198000000002", "Other", 10]]}
        self.panel.record(payload)
        restored = PlayerPanel(self.bot)
        self.assertEqual(set(restored.rows), {STEAM})
        self.assertEqual(restored.updated, UPDATED)
        self.assertEqual(restored.rows[STEAM]["kills"], 123)

    async def test_persistent_buttons_and_private_profile(self):
        view = PlayerView(self.panel)
        self.assertTrue(view.is_persistent())
        self.assertEqual(len(view.children), 8)
        interaction = MagicMock(user=self.member)
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        self.bot.preferences = None
        self.bot.progression.find.return_value = (STEAM, self.player)
        await self.panel.show_profile(interaction)
        self.assertTrue(interaction.followup.send.call_args.kwargs["ephemeral"])
        self.bot.progression.find.assert_called_with(1)
        self.bot.preferences = None
        self.bot.progression.find.return_value = None
        await self.panel.show_profile(interaction)
        self.assertIn("Link Steam", interaction.response.send_message.call_args.args[0])

    async def test_other_member_profile_is_private_and_uses_selected_identity(self):
        other = SimpleNamespace(id=2, guild=SimpleNamespace(id=1), display_avatar=self.member.display_avatar)
        interaction = MagicMock(user=self.member)
        interaction.response.is_done.return_value = True
        interaction.followup.send = AsyncMock()
        self.bot.preferences = None
        self.bot.progression.find.return_value = (STEAM, self.player)
        await self.panel.show_profile(interaction, other)
        self.bot.progression.find.assert_any_call(2)
        sent = interaction.followup.send.call_args.kwargs
        self.assertTrue(sent["ephemeral"])
        self.assertIn("<@2>", sent["embeds"][0].description)
        self.bot.preferences = None
        self.bot.progression.find.return_value = None
        await self.panel.show_profile(interaction, other)
        self.assertIn("unavailable", interaction.followup.send.call_args.args[0])
        other.guild.id = 999
        with self.assertRaises(ValueError):
            await self.panel.show_profile(interaction, other)

    async def test_panel_reuses_message(self):
        channel = MagicMock(spec=discord.TextChannel)
        channel.id, channel.guild.id = 2, 1
        async def history(**kwargs):
            for item in []:
                yield item
        channel.history = history
        message = SimpleNamespace(id=123, embeds=[], edit=AsyncMock())
        channel.send = AsyncMock(return_value=message)
        channel.fetch_message = AsyncMock(return_value=message)
        await self.panel.ensure(channel)
        await self.panel.ensure(channel)
        channel.send.assert_awaited_once()
        message.edit.assert_awaited_once()
        self.assertEqual(self.store.get("player_panel_message:2"), "123")


if __name__ == "__main__":
    unittest.main()


class ComparisonTests(unittest.TestCase):
    def test_comparison_missing_data_and_correct_sides(self):
        from player_panel import comparison_embed
        e=comparison_embed(1,2,{'rank':0,'points2':40},{'rank':1,'points2':500},
            {'kills':10,'wins':1,'losses':2},{'kills':20,'wins':0,'losses':0},None)
        self.assertIn('10',e.fields[1].value)
        self.assertIn('20',e.fields[2].value)
        self.assertIn('33.3%',e.fields[1].value)
        self.assertIn('—',e.fields[2].value)
        self.assertIn('230.0 points behind',e.fields[3].value)
        self.assertLess(len(e),2000)

class ComparisonMarkers(unittest.TestCase):
    def test_lower_is_better_and_hours_neutral(self):
        from player_panel import comparison_embed
        e=comparison_embed(1,2,{'rank':0,'points2':0},{'rank':0,'points2':20},
            {'kills':20,'deaths':5,'hoursPlayed':100},{'kills':10,'deaths':10,'hoursPlayed':10},None)
        left=e.fields[1].value.splitlines();right=e.fields[2].value.splitlines()
        self.assertTrue(left[0].startswith('⚪'))
        self.assertTrue(left[1].startswith('🔴'))
        self.assertTrue(left[2].startswith('🟢'))
        self.assertTrue(left[3].startswith('🟢'))
        self.assertTrue(right[3].startswith('🔴'))
        self.assertTrue(left[7].startswith('⚪'))
