import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from config import database_location
from state import Store
from steam_link import link_command


class StorageTests(unittest.TestCase):
    def test_railway_requires_volume_and_database_inside_it(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            volume = root / "volume"
            volume.mkdir()
            env = {"RAILWAY_SERVICE_ID": "test"}
            with self.assertRaises(ValueError):
                database_location(env, root)
            env["RAILWAY_VOLUME_MOUNT_PATH"] = str(volume)
            with self.assertRaises(ValueError):
                database_location(env, root)
            env["DATABASE_PATH"] = str(volume / "22a.sqlite3")
            self.assertEqual(database_location(env, root), ((volume / "22a.sqlite3").resolve(), volume.resolve()))

    def test_link_rating_and_baseline_survive_reopen_and_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.db"
            store = Store(path, temp)
            data = {"players": {"76561198000000001": {"discord_id": 1, "steam_verified": True,
                    "points2": 2345, "rank": 2, "baseline": {"wins": 12}, "active": True}}, "roles": {"0": 11}}
            store.set("progression_v1", json.dumps(data))
            store.set("panel_id", "987")
            identity = store.database_id
            backup = store.backup()
            store.db.close()
            restored = Store(path, temp)
            self.assertEqual(json.loads(restored.get("progression_v1")), data)
            self.assertEqual(restored.database_id, identity)
            self.assertEqual(restored.get("panel_id"), "987")
            self.assertEqual(restored.backup(), backup)
            restored.db.close()
            import sqlite3
            db = sqlite3.connect(backup)
            self.assertEqual(json.loads(db.execute("SELECT value FROM settings WHERE key='progression_v1'").fetchone()[0]), data)
            db.close()

    def test_missing_or_changed_database_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.db"
            store = Store(path, temp)
            store.db.close()
            with self.assertRaises(ValueError):
                Store(Path(temp) / "other.db", temp)
            path.rename(Path(temp) / "preserved.db")
            with self.assertRaises(ValueError):
                Store(path, temp)
            self.assertFalse(path.exists())


class AlreadyLinkedTests(unittest.IsolatedAsyncioTestCase):
    async def test_link_skips_steam_for_saved_verified_identity(self):
        bot = MagicMock()
        bot.progression.find.return_value = ("76561198000000001", {"steam_verified": True, "points2": 1234})
        interaction = SimpleNamespace(client=bot, user=SimpleNamespace(id=1),
                                      response=SimpleNamespace(send_message=AsyncMock()))
        await link_command.callback(interaction)
        bot.steam_link.issue.assert_not_called()
        bot.progression.roles.assert_not_called()
        self.assertIn("already linked", interaction.response.send_message.call_args.args[0])
