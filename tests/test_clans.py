import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from leaderboard import ClanLeaderboard, Leaderboard, LeaderboardView, make_clan_snapshot, render_clan_embed
from state import Store


def feed():
    return {"updatedAt": datetime.now(timezone.utc).isoformat(), "clans": [
        {"tag": "22A" if i == 3 else f"Clan{i:02}", "memberCount": 10, "kills": 100 - i,
         "deaths": i + 1, "kd": i / 10, "hoursPlayed": i * 3.5, "cashEarned": i * 1000}
        for i in range(15)]}


class ClanTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "state.db")
        self.bot = MagicMock()
        self.bot.store = self.store
        self.bot.cfg = SimpleNamespace(guild_id=1, logo_url="")
        self.bot.user.id = 999
        self.players = Leaderboard(self.bot, 2)
        self.clans = ClanLeaderboard(self.bot, 2, query="", limit=10)

    async def asyncTearDown(self):
        self.players.stop()
        self.clans.stop()
        self.store.db.close()
        self.temp.cleanup()

    async def test_top_ten_and_all_clans_not_player_filter(self):
        snapshot = make_clan_snapshot(feed())
        self.assertEqual(snapshot["count"], 15)
        embed = render_clan_embed(snapshot)
        self.assertIn("Showing 10 of 15 clans", embed.description)
        self.assertIn("Clan00", embed.description)
        self.assertNotIn("Clan10", embed.description)
        self.assertIn("22A", embed.description)
        self.assertIn("⭐", embed.description)
        cash = render_clan_embed(snapshot, "cashEarned")
        self.assertIn("Clan14", cash.description)
        self.assertNotIn("Clan00", cash.description)
        self.assertLessEqual(len(embed.description), 4096)

    async def test_schema_errors_preserve_previous_snapshot(self):
        payload = feed()
        del payload["clans"][0]["memberCount"]
        with self.assertRaises(ValueError):
            make_clan_snapshot(payload)
        payload = feed()
        payload["clans"][0]["kills"] = float("nan")
        with self.assertRaises(ValueError):
            make_clan_snapshot(payload)

    async def test_separate_state_buttons_and_timers(self):
        self.assertNotEqual(self.players.message_key, self.clans.message_key)
        a = {b.custom_id for b in LeaderboardView(self.players).children}
        b = {b.custom_id for b in LeaderboardView(self.clans).children}
        self.assertFalse(a & b)
        self.assertTrue(LeaderboardView(self.clans).is_persistent())
        self.assertIsNot(self.players.refresh, self.clans.refresh)
        self.store.set("leaderboard_metric", "kd")
        self.store.set("clan_leaderboard_metric", "cashEarned")
        self.assertEqual(Leaderboard(self.bot, 2).metric, "kd")
        self.assertEqual(ClanLeaderboard(self.bot, 2).metric, "cashEarned")

    async def test_clan_cache_and_message_survive_restart(self):
        self.clans.fetch = AsyncMock(return_value=make_clan_snapshot(feed()))
        self.clans.publish = AsyncMock()
        await self.clans.refresh()
        self.store.set(self.clans.message_key, "123")
        restored = ClanLeaderboard(self.bot, 2, query="", limit=10)
        self.assertEqual(restored.snapshot, self.clans.snapshot)
        self.assertEqual(restored.message_id, 123)
        self.assertIsNone(self.store.get("leaderboard_cache"))

    async def test_clan_recovery_never_edits_player_message(self):
        channel = MagicMock(spec=discord.TextChannel)
        channel.guild.id = 1
        self.bot.get_channel.return_value = channel
        player_message = SimpleNamespace(id=42, author=SimpleNamespace(id=999),
                                         embeds=[discord.Embed().set_footer(text=self.players.marker)], edit=AsyncMock())
        async def history(**kwargs):
            yield player_message
        channel.history = history
        channel.send = AsyncMock(return_value=SimpleNamespace(id=43))
        await self.clans.publish()
        player_message.edit.assert_not_awaited()
        channel.send.assert_awaited_once()
        self.assertEqual(self.clans.message_id, 43)

    async def test_optional_config_and_period(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(ClanLeaderboard.from_env(self.bot))
        with patch.dict(os.environ, {"CLAN_LEADERBOARD_CHANNEL_ID": "2", "CLAN_LEADERBOARD_PERIOD": "weekly"}):
            service = ClanLeaderboard.from_env(self.bot)
            self.assertEqual(service.limit, 10)
            self.assertEqual(service.query, "")
            self.assertEqual(service.period, "weekly")

    async def test_failed_fetch_keeps_clans_and_empty_feed_is_clear(self):
        self.clans.snapshot = make_clan_snapshot(feed())
        original = self.clans.snapshot
        self.clans.fetch = AsyncMock(side_effect=ValueError("test unavailable"))
        self.clans.publish = AsyncMock()
        with self.assertLogs("22a.leaderboard", level="ERROR"):
            await self.clans.refresh()
        self.assertIs(self.clans.snapshot, original)
        self.assertIn("Latest fetch failed", self.clans.embed().description)
        payload = feed()
        payload["clans"] = []
        self.assertIn("No clans", render_clan_embed(make_clan_snapshot(payload)).description)


if __name__ == "__main__":
    unittest.main()
