import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from leaderboard import Leaderboard, LeaderboardView, MARKER, METRICS, decode_feed, make_snapshot, render_embed
from state import Store


def feed():
    return {"updatedAt": datetime.now(timezone.utc).isoformat(),
            "fields": ["steamId", "name", "kills", "kd", "deaths", "hoursPlayed", "cashEarned", "online"],
            "players": [["111", "[22A] Alpha", 10, 2.5, 4, 2.0, 1500, 1],
                        ["222", "[22a] Bravo", 20, 1.0, 20, 1.0, 1000, 0],
                        ["333", "Other", 900, 9.0, 100, 30.0, 50000, 0]]}


class FeedTests(unittest.TestCase):
    def test_tuple_decoding_matches_fields_not_fixed_positions(self):
        payload = feed()
        payload["fields"].reverse()
        for row in payload["players"]:
            row.reverse()
        self.assertEqual(decode_feed(payload)[0]["kills"], 10)

    def test_filter_and_per_metric_top_rows(self):
        snapshot = make_snapshot(feed(), "22A", 1)
        self.assertEqual(snapshot["count"], 2)
        self.assertEqual({r["steamId"] for r in snapshot["rows"]}, {"111", "222"})
        embed = render_embed(snapshot, "kills", "22A", "all", 1, {})
        self.assertIn("Bravo", embed.description)
        self.assertNotIn("Alpha", embed.description)
        self.assertIn("Showing 1 of 2", embed.description)

    def test_empty_filter_includes_everyone(self):
        self.assertEqual(make_snapshot(feed(), "", 20)["count"], 3)

    def test_reject_schema_drift_and_invalid_numbers(self):
        payload = feed()
        payload["fields"][2] = "new_kills_field"
        with self.assertRaises(ValueError):
            decode_feed(payload)
        for bad in (float("nan"), -1, "unknown", True):
            payload = feed()
            payload["players"][0][2] = bad
            with self.assertRaises(ValueError):
                decode_feed(payload)

    def test_all_metric_formats_and_links(self):
        snapshot = make_snapshot(feed(), "22A", 20)
        for metric in METRICS:
            embed = render_embed(snapshot, metric, "22A", "all", 20, {"111": "444"})
            self.assertIn("<@444>", embed.description)
            self.assertIn("steamcommunity.com/profiles/222", embed.description)
            self.assertIn("🟢", embed.description)

    def test_empty_and_failed_feed_states(self):
        snapshot = make_snapshot(feed(), "No match", 20)
        self.assertIn("No players match", render_embed(snapshot, "kills", "No match", "all", 20, {}).description)
        embed = render_embed(None, "kills", "22A", "all", 20, {}, failed=True)
        self.assertIn("Waiting", embed.description)
        self.assertIn("fetch failed", embed.description)

    def test_ties_and_embed_limits_with_hostile_names(self):
        payload = feed()
        payload["players"] = [[str(100 + i), "@everyone [22A] " + "*[]<>" * 100,
                               1e100, 1.0, 1, 1, 1, 1] for i in range(20)]
        snapshot = make_snapshot(payload, "22A", 20)
        embed = render_embed(snapshot, "kills", "22A", "all", 20, {})
        self.assertLessEqual(len(embed.description), 4096)
        self.assertLessEqual(len(embed), 6000)
        self.assertNotIn("@everyone", embed.description)
        self.assertGreater(embed.description.count("🥇"), 1)


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "state.db")
        self.bot = MagicMock()
        self.bot.store = self.store
        self.bot.cfg = SimpleNamespace(guild_id=1, logo_url="")
        self.bot.user.id = 999
        self.service = Leaderboard(self.bot, 2)
        self.channel = MagicMock(spec=discord.TextChannel)
        self.channel.guild.id = 1
        self.channel.fetch_message = AsyncMock()
        self.channel.send = AsyncMock(return_value=SimpleNamespace(id=123))
        self.bot.get_channel.return_value = self.channel
        async def history(**kwargs):
            for item in []:
                yield item
        self.channel.history = history

    async def asyncTearDown(self):
        self.service.stop()
        self.store.db.close()
        self.temp.cleanup()

    async def test_view_is_persistent(self):
        view = LeaderboardView(self.service)
        self.assertTrue(view.is_persistent())
        self.assertEqual(len(view.children), 5)

    async def test_same_message_is_edited_and_selection_restored(self):
        await self.service.publish()
        self.assertEqual(self.service.message_id, 123)
        message = SimpleNamespace(id=123, edit=AsyncMock())
        self.channel.fetch_message.return_value = message
        await self.service.publish()
        self.channel.send.assert_awaited_once()
        message.edit.assert_awaited_once()
        self.store.set("leaderboard_metric", "kd")
        restarted = Leaderboard(self.bot, 2)
        self.assertEqual(restarted.message_id, 123)
        self.assertEqual(restarted.metric, "kd")

    async def test_deleted_message_is_recreated(self):
        self.service.message_id = 77
        self.channel.fetch_message.side_effect = discord.NotFound(SimpleNamespace(status=404, reason="Not Found"), "missing")
        await self.service.publish()
        self.channel.send.assert_awaited_once()
        self.assertEqual(self.store.get(self.service.message_key), "123")

    async def test_recovery_finds_existing_message(self):
        embed = discord.Embed().set_footer(text=MARKER)
        message = SimpleNamespace(id=88, author=SimpleNamespace(id=999), embeds=[embed], edit=AsyncMock())
        async def history(**kwargs):
            yield message
        self.channel.history = history
        await self.service.publish()
        self.channel.send.assert_not_awaited()
        self.assertEqual(self.service.message_id, 88)

    async def test_failed_refresh_keeps_cache(self):
        self.service.snapshot = make_snapshot(feed(), "22A", 20)
        original = copy.deepcopy(self.service.snapshot)
        self.service.fetch = AsyncMock(side_effect=ValueError("bad feed"))
        self.service.publish = AsyncMock()
        with self.assertLogs("22a.leaderboard", level="ERROR"):
            await self.service.refresh()
        self.assertEqual(original, self.service.snapshot)
        self.assertTrue(self.service.failed)
        self.service.publish.assert_awaited_once()

    async def test_successful_fetch_persisted_and_restored(self):
        self.service.fetch = AsyncMock(return_value=make_snapshot(feed(), "22A", 20))
        self.service.publish = AsyncMock()
        await self.service.refresh()
        restarted = Leaderboard(self.bot, 2)
        self.assertEqual(restarted.snapshot, self.service.snapshot)
        changed_filter = Leaderboard(self.bot, 2, query="Other")
        self.assertIsNone(changed_filter.snapshot)

    async def test_buttons_use_cache_without_fetching(self):
        self.service.message_id = 123
        self.service.fetch = AsyncMock()
        self.service.publish = AsyncMock()
        interaction = MagicMock(guild_id=1, channel_id=2)
        interaction.message.id = 123
        interaction.response.defer = AsyncMock()
        await self.service.select(interaction, "kd")
        self.assertEqual(self.service.metric, "kd")
        self.service.fetch.assert_not_awaited()
        self.service.publish.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
