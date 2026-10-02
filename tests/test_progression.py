import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
from discord import app_commands

from progression import (COMMANDS, Progression, RANKS, STATE_KEY, advance, decode_stats,
                         new_player, rank_for, guide_embed, daily_due, daily_embed)
from state import Store

STEAM = "76561198000000001"
NOW = datetime.now(timezone.utc)
BASE = {"wins": 100, "losses": 100, "kills": 1000, "deaths": 1000}


def stamp(minutes=0):
    return (NOW + timedelta(minutes=minutes)).isoformat()


class RatingTests(unittest.TestCase):
    def test_waiting_link_baselines_without_awarding_history(self):
        player = new_player(1, None, None)
        advance(player, BASE.copy(), stamp())
        self.assertEqual(player["points2"], 0)
        self.assertEqual(player["baseline"], BASE)
        advance(player, dict(BASE, wins=101), stamp(5))
        self.assertEqual(player["points2"], 40)

    def test_daily_schedule_before_after_and_already_posted(self):
        now = NOW.replace(hour=17, minute=59)
        self.assertFalse(daily_due(now, "18:00"))
        now = now.replace(hour=18, minute=0)
        self.assertTrue(daily_due(now, "18:00"))
        self.assertFalse(daily_due(now, "18:00", now.date().isoformat()))
        self.assertTrue(daily_due(now, "18:00", (now-timedelta(days=1)).date().isoformat()))

    def test_daily_ranking_ties_and_embed_limits(self):
        players = [new_player(i, BASE.copy(), stamp()) for i in range(1, 26)]
        players[1]["points2"] = players[2]["points2"] = 600
        embed = daily_embed(players, NOW.date().isoformat(), NOW)
        self.assertLess(embed.description.index("<@2>"), embed.description.index("<@1>"))
        self.assertEqual(embed.description.count("🥇"), 2)
        self.assertIn("Showing 20 of 25", embed.description)
        self.assertLessEqual(len(embed.description), 4096)

    def test_everyone_starts_zero_with_existing_stats(self):
        player = new_player(1, BASE.copy(), stamp())
        self.assertEqual(player["points2"], 0)
        self.assertEqual(player["rank"], 0)
        self.assertEqual(player["baseline"], BASE)

    def test_updated_example_is_120_points(self):
        player = new_player(1, BASE.copy(), stamp())
        advance(player, {"wins": 102, "losses": 101, "kills": 1030, "deaths": 1020}, stamp(5))
        self.assertEqual(player["points2"], 240)

    def test_repeated_and_old_snapshots_never_rescore(self):
        player = new_player(1, BASE.copy(), stamp())
        row = dict(BASE, wins=101)
        advance(player, row, stamp(5))
        advance(player, row, stamp(5))
        advance(player, BASE.copy(), stamp())
        self.assertEqual(player["points2"], 40)

    def test_zero_floor_and_updated_kill_reward(self):
        player = new_player(1, BASE.copy(), stamp())
        advance(player, dict(BASE, deaths=1001), stamp(5))
        self.assertEqual(player["points2"], 0)
        advance(player, dict(BASE, deaths=1001, kills=1001), stamp(10))
        self.assertEqual(player["points2"], 10)

    def test_promotion_and_demotion_buffer(self):
        self.assertEqual(rank_for(500, 0), 1)
        self.assertEqual(rank_for(400, 1), 1)
        self.assertEqual(rank_for(399, 1), 0)
        self.assertEqual(rank_for(16000, 0), 6)
        self.assertEqual(rank_for(0, 6), 0)

    def test_transition_is_recorded_and_blocks_further_scoring_until_delivered(self):
        player = new_player(1, BASE.copy(), stamp())
        player["points2"] = 480
        advance(player, dict(BASE, wins=101), stamp(5))
        self.assertEqual(player["rank"], 1)
        self.assertEqual(player["pending"]["before"], 480)
        advance(player, dict(BASE, wins=102), stamp(10))
        self.assertEqual(player["points2"], 520)

    def test_reset_and_huge_jump_hold_without_penalty(self):
        for row in (dict(BASE, kills=1), dict(BASE, wins=10000)):
            player = new_player(1, BASE.copy(), stamp())
            player["points2"] = 480
            advance(player, row, stamp(5))
            self.assertTrue(player["hold"])
            self.assertEqual(player["points2"], 480)
            self.assertEqual(player["baseline"], BASE)

    def test_inactivity_and_pause_do_not_change_rating(self):
        player = new_player(1, BASE.copy(), stamp())
        player["points2"] = 10
        advance(player, BASE.copy(), stamp(5))
        player["active"] = False
        advance(player, dict(BASE, wins=110), stamp(10))
        self.assertEqual(player["points2"], 10)

    def test_feed_decode_stale_invalid_and_duplicate(self):
        payload = {"updatedAt": stamp(), "fields": ["steamId", *BASE], "players": [[STEAM, *BASE.values()]]}
        self.assertEqual(decode_stats(payload, NOW)[1][STEAM], BASE)
        with self.assertRaises(ValueError):
            decode_stats(payload, NOW + timedelta(hours=1))
        bad = copy.deepcopy(payload)
        bad["players"][0][1] = -1
        with self.assertRaises(ValueError):
            decode_stats(bad, NOW)
        payload["players"].append(payload["players"][0])
        with self.assertRaises(ValueError):
            decode_stats(payload, NOW)


class Role:
    def __init__(self, role_id, position=1):
        self.id, self.position = role_id, position
        self.permissions = SimpleNamespace(value=0)
        self.managed = False

    def is_default(self):
        return False

    def __ge__(self, other):
        return self.position >= other.position


class ProgressionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "db")
        self.bot = MagicMock()
        self.bot.store = self.store
        self.bot.cfg.guild_id = 1
        self.bot.cfg.logo_url = ""
        self.bot.guild.me.guild_permissions.manage_roles = True
        self.bot.guild.me.top_role = Role(99, 100)
        self.roles = [Role(i + 10) for i in range(7)]
        self.bot.guild.get_role.side_effect = lambda rid: next((r for r in self.roles if r.id == rid), None)
        self.member = SimpleNamespace(id=1, bot=False, roles=[Role(777)], add_roles=AsyncMock(), remove_roles=AsyncMock())
        self.member.display_name = 'Test Player'
        self.member.name = 'Test Player'
        self.member.nick = None
        self.member.top_role = Role(777)
        self.member.edit = AsyncMock()
        self.bot.guild.fetch_member = AsyncMock(return_value=self.member)
        self.bot.user.id = 999
        self.service = Progression(self.bot, 2)
        self.service.state["roles"] = {str(i): r.id for i, r in enumerate(self.roles)}
        self.channel = MagicMock(spec=discord.TextChannel)
        self.channel.guild.id = 1
        self.channel.send = AsyncMock()
        async def history(**kwargs):
            for x in []:
                yield x
        self.channel.history = history
        self.bot.get_channel.return_value = self.channel

    async def asyncTearDown(self):
        self.service.stop()
        self.store.db.close()
        self.temp.cleanup()

    async def test_link_baseline_is_persisted_before_role_failure(self):
        self.service.fetch = AsyncMock(return_value=(stamp(), {STEAM: BASE.copy()}))
        self.member.add_roles.side_effect = RuntimeError("API down")
        with self.assertRaises(RuntimeError):
            await self.service.link(self.member, STEAM)
        restarted = Progression(self.bot, 2)
        self.assertEqual(restarted.state["players"][STEAM]["points2"], 0)
        self.assertEqual(restarted.state["players"][STEAM]["baseline"], BASE)
        with self.assertRaisesRegex(ValueError, "Already linked"):
            await self.service.link(self.member, STEAM)

    async def test_verified_enrollment_does_not_need_stats_and_survives_restart(self):
        self.service.fetch = AsyncMock(side_effect=ValueError("stale feed"))
        await self.service.enroll_verified(self.member, STEAM)
        self.service.fetch.assert_not_awaited()
        player = Progression(self.bot, 2).state["players"][STEAM]
        self.assertIsNone(player["baseline"])
        self.assertTrue(player["steam_verified"])
        self.assertEqual(player["points2"], 0)
        daily_embed([player], NOW.date().isoformat(), NOW)

    async def test_one_to_one_identity_and_no_relink_reset(self):
        self.service.state["players"][STEAM] = new_player(1, BASE, stamp())
        with self.assertRaises(ValueError):
            await self.service.link(self.member, "76561198000000002")
        with self.assertRaises(ValueError):
            await self.service.link(SimpleNamespace(id=2, bot=False), STEAM)

    async def test_website_override_supplies_missing_member(self):
        from unittest.mock import patch
        steam = "76561197988807107"
        self.service.state["players"][steam] = new_player(1, BASE.copy(), stamp())
        fields = ["steamId", "wins", "losses", "kills", "deaths"]
        public = {"updatedAt": stamp(), "fields": fields, "players": [[steam, 100, 100, 1000, 1000]]}
        api = {"updatedAt": stamp(), "fields": fields, "players": []}
        self.bot.player_panel = None
        self.service.fetch_public_payload = AsyncMock(return_value=public)
        with patch("wduk_api.enabled", return_value=True), patch("wduk_api.fetch_clan", new=AsyncMock(return_value=api)):
            updated, rows = await self.service.fetch()
        self.assertEqual(rows[steam], BASE)
        self.assertEqual(self.service.source_overrides[steam], "wardogs-public-all-v1")
        self.assertEqual(self.service.state["players"][steam]["points2"], 0)

    async def test_setup_recovers_existing_roles_and_is_idempotent(self):
        from progression import RANK_BADGES
        for i, role in enumerate(self.roles):
            role.name = f"{RANK_BADGES[i]} 22A Rank • {RANKS[i][0]}"
        duplicate = Role(1000)
        duplicate.name = self.roles[0].name
        self.bot.guild.fetch_roles = AsyncMock(return_value=self.roles + [duplicate])
        self.bot.guild.create_role = AsyncMock()
        self.service.state["roles"] = {}
        await self.service.setup_roles()
        await self.service.setup_roles()
        self.bot.guild.create_role.assert_not_awaited()
        self.assertEqual(self.service.state["roles"]["0"], self.roles[0].id)

    async def test_setup_preserves_saved_choice_over_older_duplicate(self):
        for i, role in enumerate(self.roles):
            role.name = f"🪖 22A Rank • {RANKS[i][0]}"
        duplicate = Role(1)
        duplicate.name = self.roles[0].name
        self.bot.guild.fetch_roles = AsyncMock(return_value=self.roles + [duplicate])
        self.bot.guild.create_role = AsyncMock()
        await self.service.setup_roles()
        self.assertEqual(self.service.state["roles"]["0"], self.roles[0].id)
        self.bot.guild.create_role.assert_not_awaited()

    async def test_sync_only_managed_roles_and_announcement_retry(self):
        player = new_player(1, BASE.copy(), stamp())
        player["points2"] = 480
        advance(player, dict(BASE, wins=101), stamp(5))
        self.service.state["players"][STEAM] = player
        self.member.roles.append(self.roles[0])
        self.channel.send.side_effect = RuntimeError("network down")
        with self.assertRaises(RuntimeError):
            await self.service.sync_player(player)
        self.assertIsNotNone(player["pending"])
        self.member.remove_roles.assert_awaited_with(self.roles[0], reason="22A progression rank update", atomic=True)
        self.member.add_roles.assert_awaited_with(self.roles[1], reason="22A progression rank", atomic=True)
        self.channel.send.side_effect = None
        await self.service.sync_player(player)
        self.assertIsNone(player["pending"])
        self.assertIsNone(json.loads(self.store.get(STATE_KEY))["players"][STEAM]["pending"])

    async def test_announcement_crash_recovery_finds_existing_event(self):
        player = new_player(1, BASE.copy(), stamp())
        player["points2"] = 480
        advance(player, dict(BASE, wins=101), stamp(5))
        embed = discord.Embed().set_footer(text=f"22A rank event {player['pending']['id']}")
        async def history(**kwargs):
            yield SimpleNamespace(author=SimpleNamespace(id=999), embeds=[embed])
        self.channel.history = history
        await self.service.sync_player(player)
        self.channel.send.assert_not_awaited()
        self.assertIsNone(player["pending"])

    async def test_refuse_roles_with_permissions_or_above_bot(self):
        self.roles[0].permissions.value = 8
        with self.assertRaises(ValueError):
            self.service.roles()
        self.roles[0].permissions.value = 0
        self.roles[0].position = 101
        with self.assertRaises(ValueError):
            self.service.roles()

    async def test_failed_feed_never_mutates_rating(self):
        player = new_player(1, BASE.copy(), stamp())
        self.service.state["players"][STEAM] = player
        original = copy.deepcopy(player)
        self.service.fetch = AsyncMock(side_effect=ValueError("bad source"))
        with self.assertLogs("22a.ranks", level="ERROR"):
            await self.service.poll()
        self.assertEqual({k:v for k,v in player.items() if k != 'rank_nickname'}, original)
        self.member.edit.assert_awaited_with(nick='Test Player [PVT]', reason='22A ELO rank nickname')

    async def test_commands_register_with_expected_admin_permissions(self):
        tree = app_commands.CommandTree(discord.Client(intents=discord.Intents.none()))
        for command in COMMANDS:
            tree.add_command(command)
            if command.name != "rank":
                self.assertTrue(command.default_permissions.manage_guild)
        self.assertEqual(len(tree.get_commands()), 8)
        self.assertNotIn("rank-link", {command.name for command in tree.get_commands()})

    async def test_guide_content_matches_scoring_and_link_availability(self):
        embed = guide_embed(True)
        text = str(embed.to_dict())
        self.assertIn("/link", text)
        self.assertIn("Win +20", text)
        self.assertIn("Loss −10", text)
        self.assertIn("Kill +5", text)
        self.assertIn("Death −3", text)
        self.assertIn("+120 points", text)
        for name, points in RANKS:
            self.assertIn(f"{name}** — {points:,}", text)
        self.assertLess(len(embed), 6000)
        for field in embed.fields:
            self.assertLessEqual(len(field.value), 1024)
        self.assertIn("enable **/link**", str(guide_embed(False).to_dict()))
        self.assertNotIn("/rank-link", str(guide_embed(False).to_dict()))

    async def test_guide_reuses_saved_message_and_repairs_deletion(self):
        self.channel.id = 2
        message = SimpleNamespace(id=444, embeds=[guide_embed(True)], edit=AsyncMock())
        self.channel.send.return_value = message
        await self.service.ensure_guide(self.channel)
        self.channel.fetch_message = AsyncMock(return_value=message)
        await self.service.ensure_guide(self.channel)
        self.channel.send.assert_awaited_once()
        self.assertEqual(self.store.get("rank_guide_message:2"), "444")
        self.channel.fetch_message.side_effect = discord.NotFound(SimpleNamespace(status=404, reason="Not Found"), "missing")
        await self.service.ensure_guide(self.channel)
        self.assertEqual(self.channel.send.await_count, 2)

    async def test_daily_post_once_across_restart_and_retry_failure(self):
        self.service.daily_time = "00:00"
        self.bot.guild.get_member.return_value = self.member
        self.service.state["players"][STEAM] = new_player(1, BASE.copy(), stamp())
        self.service.save()
        self.channel.send.side_effect = RuntimeError("API down")
        with self.assertRaises(RuntimeError):
            await self.service.post_daily(NOW)
        self.assertIsNone(self.store.get("rank_daily_last_date"))
        self.channel.send.side_effect = None
        await self.service.post_daily(NOW)
        self.assertEqual(self.store.get("rank_daily_last_date"), NOW.date().isoformat())
        restarted = Progression(self.bot, 2)
        restarted.daily_time = "00:00"
        await restarted.post_daily(NOW)
        self.assertEqual(self.channel.send.await_count, 2)

    async def test_daily_crash_recovery_and_no_empty_post(self):
        self.service.daily_time = "00:00"
        await self.service.post_daily(NOW)
        self.channel.send.assert_not_awaited()
        embed = discord.Embed().set_footer(text=f"22A daily ranks {NOW.date().isoformat()}")
        async def history(**kwargs):
            yield SimpleNamespace(author=SimpleNamespace(id=999), embeds=[embed])
        self.channel.history = history
        await self.service.post_daily(NOW)
        self.assertEqual(self.store.get("rank_daily_last_date"), NOW.date().isoformat())
        self.channel.send.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()


class AutoRecoveryTests(unittest.TestCase):
    def test_recovery_preserves_rating_and_prevents_rebound_reward(self):
        p=new_player(1,BASE.copy(),stamp(-30));p['points2']=80
        lower=dict(BASE,kills=900)
        advance(p,lower,stamp(-25))
        self.assertTrue(p['hold'])
        for minute in (-20,-15,-10):advance(p,lower,stamp(minute))
        self.assertIsNone(p['hold'])
        self.assertEqual(p['points2'],80)
        advance(p,BASE.copy(),stamp(-5))
        self.assertEqual(p['points2'],80)
        advance(p,dict(BASE,kills=1001),stamp())
        self.assertEqual(p['points2'],90)
    def test_repeated_snapshots_do_not_recover(self):
        p=new_player(1,BASE.copy(),stamp(-30))
        lower=dict(BASE,kills=900)
        advance(p,lower,stamp(-25))
        for _ in range(5):advance(p,lower,stamp(-20))
        self.assertTrue(p['hold'])
        self.assertEqual(p['recovery']['count'],1)
    def test_manual_pause_not_resumed(self):
        p=new_player(1,BASE.copy(),stamp(-30));p.update(active=False,hold='Source counters decreased.')
        for minute in (-20,-15,-10):advance(p,dict(BASE,kills=900),stamp(minute))
        self.assertFalse(p['active'])
        self.assertTrue(p['hold'])
