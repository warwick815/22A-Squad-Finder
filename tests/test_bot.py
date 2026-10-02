import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord

from bot import AdvertView, Controls, CreateModal, PanelView, SquadBot
from config import Config
from state import Room, Store


def active(**kwargs):
    values = dict(id="abc123", owner=1, name="Alpha", game="WarDogs", limit=2,
                  members=[1], status="active")
    values.update(kwargs)
    return Room(**values)


class StateTests(unittest.TestCase):
    def test_full_and_idempotent_join(self):
        room = active()
        room.join(2)
        room.join(2)
        self.assertEqual(room.members, [1, 2])
        with self.assertRaisesRegex(ValueError, "full"):
            room.join(3)

    def test_lock_allows_existing_members_only(self):
        room = active(locked=True)
        room.join(1)
        with self.assertRaisesRegex(ValueError, "locked"):
            room.join(2)

    def test_leader_departure_and_last_member_cleanup(self):
        room = active(members=[1, 2])
        room.leave(1)
        self.assertEqual(room.owner, 2)
        room.leave(2)
        self.assertEqual(room.status, "deleting")

    def test_grace_periods(self):
        room = active(empty_since=100)
        self.assertFalse(room.expired(699, 600, 120))
        self.assertTrue(room.expired(700, 600, 120))
        room.ever_used = True
        self.assertTrue(room.expired(220, 600, 120))
        room.empty_since = None
        self.assertFalse(room.expired(99999, 600, 120))

    def test_restart_roundtrip_and_tombstone(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.db"
            store = Store(path)
            room = active(voice_id=10, message_id=20, locked=True, members=[1, 2])
            store.save(room)
            store.set("panel_id", 30)
            store.db.close()
            reopened = Store(path)
            self.assertEqual(reopened.rooms()[room.id], room)
            self.assertEqual(reopened.get("panel_id"), "30")
            room.status = "deleting"
            reopened.save(room)
            self.assertEqual(reopened.rooms()[room.id].status, "deleting")
            reopened.delete(room.id)
            self.assertEqual(reopened.rooms(), {})
            reopened.db.close()


class BotTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.bot = SquadBot(Config("not-a-real-token", 100, 200, 300,
                                  Path(self.temp.name) / "test.db", 120, 600, 16, 30, ""))
        self.bot.guild = MagicMock()
        self.bot.guild.unavailable = False
        self.bot.is_ready = MagicMock(return_value=True)
        self.bot.lfg = MagicMock()
        self.bot.category = MagicMock()
        self.bot.category.voice_channels = []
        self.bot.guild.get_channel.return_value = None
        self.owner = MagicMock()
        self.owner.id = 1
        self.bot.guild.get_member.return_value = self.owner
        self.bot.guild.create_voice_channel = AsyncMock()
        self.bot.lfg.get_partial_message.return_value.delete = AsyncMock()

    async def asyncTearDown(self):
        self.bot.sweep.cancel()
        await self.bot.close()
        self.bot.store.db.close()
        self.temp.cleanup()

    def remember(self, room):
        self.bot.rooms[room.id] = room
        self.bot.store.save(room)
        return room

    async def test_persistent_components_and_modals(self):
        self.assertTrue(PanelView(self.bot).is_persistent())
        self.assertTrue(AdvertView(self.bot).is_persistent())
        ids = [c.custom_id for v in (PanelView(self.bot), AdvertView(self.bot)) for c in v.children]
        self.assertEqual(len(ids), len(set(ids)))
        for kind in ["WarDogs Squad", "Other Game Squad", "Private Channel"]:
            self.assertLessEqual(len(CreateModal(self.bot, kind).children), 5)
        self.assertEqual(len(Controls(self.bot, "abc").children), 6)

    async def test_commands_register(self):
        self.bot.tree.sync = AsyncMock()
        await self.bot.setup_hook()
        commands = self.bot.tree.get_commands(guild=discord.Object(100))
        self.assertEqual({c.name for c in commands}, {"panel", "room", "leave-room", "roasts"})

    async def test_unauthorized_controls_rejected(self):
        stranger = SimpleNamespace(id=2, guild_permissions=SimpleNamespace(manage_guild=False))
        with self.assertRaisesRegex(ValueError, "Only"):
            self.bot.check_owner(active(), stranger)

    async def test_create_private_and_permission_isolation(self):
        room = self.remember(active(status="creating", private=True))
        voice = MagicMock(id=55, members=[])
        voice.edit = AsyncMock()
        self.bot.guild.create_voice_channel.return_value = voice
        await self.bot.reconcile(room)
        args = self.bot.guild.create_voice_channel.call_args.kwargs
        self.assertFalse(args["overwrites"][self.bot.guild.default_role].view_channel)
        self.assertFalse(args["overwrites"][self.bot.guild.default_role].connect)
        self.assertTrue(args["overwrites"][self.owner].connect)
        # Discord rejects MANAGE_ROLES overwrites on create for non-admin bots.
        for overwrite in args["overwrites"].values():
            self.assertIsNone(overwrite.manage_roles)
        self.assertTrue(args["overwrites"][self.bot.guild.me].view_channel)
        self.assertEqual(args["user_limit"], 2)
        self.assertEqual(room.voice_id, 55)
        self.assertEqual(voice.edit.call_args.kwargs["name"], "Alpha")
        self.assertEqual(self.bot.store.rooms()[room.id].status, "active")
        self.bot.lfg.send.assert_not_called()

    async def test_recover_channel_created_before_crash(self):
        room = self.remember(active(status="creating", private=True))
        voice = MagicMock(id=55, members=[], user_limit=2)
        voice.name = "22a-abc123-Alpha"
        voice.edit = AsyncMock()
        self.bot.category.voice_channels = [voice]
        await self.bot.reconcile(room)
        self.bot.guild.create_voice_channel.assert_not_called()
        self.assertEqual(room.voice_id, 55)
        self.assertEqual(voice.edit.call_args.kwargs["name"], "Alpha")

    async def test_delete_failure_retains_record_then_retries(self):
        room = self.remember(active(status="deleting", voice_id=55, message_id=66))
        voice = MagicMock()
        voice.delete = AsyncMock(side_effect=RuntimeError("temporary API failure"))
        self.bot.guild.get_channel.return_value = voice
        with self.assertRaises(RuntimeError):
            await self.bot.reconcile(room)
        self.assertIn(room.id, self.bot.store.rooms())
        voice.delete.side_effect = None
        await self.bot.reconcile(room)
        self.assertNotIn(room.id, self.bot.rooms)
        self.assertNotIn(room.id, self.bot.store.rooms())
        self.bot.lfg.get_partial_message.assert_called_with(66)

    async def test_manually_deleted_voice_removes_advert(self):
        room = self.remember(active(voice_id=55, message_id=66))
        await self.bot.reconcile(room)
        self.bot.lfg.get_partial_message.return_value.delete.assert_awaited_once()
        self.assertNotIn(room.id, self.bot.rooms)

    async def test_kicked_member_is_disconnected(self):
        room = self.remember(active(private=True, voice_id=55))
        kicked = MagicMock(id=2)
        kicked.bot = False
        kicked.guild_permissions.administrator = False
        kicked.move_to = AsyncMock()
        voice = MagicMock(id=55, members=[kicked])
        voice.edit = AsyncMock()
        self.bot.guild.get_channel.return_value = voice
        await self.bot.reconcile(room)
        kicked.move_to.assert_awaited_once_with(None, reason="22A room access removed")

    async def test_sweep_keeps_occupied_room(self):
        room = self.remember(active(private=True, voice_id=55, empty_since=0))
        voice = MagicMock(id=55, members=[self.owner])
        self.bot.guild.get_channel.return_value = voice
        self.bot.reconcile = AsyncMock()
        await self.bot.sweep()
        self.assertEqual(room.status, "active")
        self.assertIsNone(room.empty_since)
        self.assertTrue(room.ever_used)

    async def test_sweep_expires_unused_room(self):
        room = self.remember(active(private=True, voice_id=55, empty_since=time.time() - 601))
        self.bot.guild.get_channel.return_value = MagicMock(id=55, members=[])
        self.bot.reconcile = AsyncMock()
        await self.bot.sweep()
        self.assertEqual(room.status, "deleting")

    async def test_no_cleanup_while_disconnected(self):
        room = self.remember(active(private=True, voice_id=55, empty_since=0))
        self.bot.is_ready.return_value = False
        self.bot.reconcile = AsyncMock()
        await self.bot.sweep()
        self.bot.reconcile.assert_not_awaited()
        self.assertEqual(room.status, "active")


if __name__ == "__main__":
    unittest.main()
