"""Small durable state store; no Discord or credentials in this module."""
import json
import sqlite3
import time
import os
import uuid
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import asdict, dataclass, field


@dataclass
class Room:
    id: str
    owner: int
    name: str
    game: str
    limit: int
    private: bool = False
    notes: str = ""
    members: list[int] = field(default_factory=list)
    locked: bool = False
    voice_id: int | None = None
    message_id: int | None = None
    status: str = "creating"
    empty_since: float | None = field(default_factory=time.time)
    ever_used: bool = False

    def join(self, user_id: int):
        if user_id in self.members:
            return
        if self.status != "active":
            raise ValueError("This room is closing or is not ready yet.")
        if self.locked:
            raise ValueError("This room is locked to new members.")
        if len(self.members) >= self.limit:
            raise ValueError("This room is full.")
        self.members.append(user_id)

    def leave(self, user_id: int):
        if user_id not in self.members:
            raise ValueError("That person is not a member of this room.")
        self.members.remove(user_id)
        if not self.members:
            self.status = "deleting"
        elif self.owner == user_id:
            self.owner = self.members[0]

    def expired(self, now: float, initial: int, empty: int) -> bool:
        grace = empty if self.ever_used else initial
        return self.empty_since is not None and now - self.empty_since >= grace


class Store:
    def __init__(self, path, storage_root=None):
        self.path = Path(path).resolve()
        self.marker = Path(storage_root) / ".22a-storage.json" if storage_root else self.path.with_suffix(self.path.suffix + ".identity.json")
        identity = json.loads(self.marker.read_text(encoding="utf-8")) if self.marker.exists() else None
        if identity and (identity["database_path"] != str(self.path) or not self.path.is_file() or self.path.stat().st_size == 0):
            raise ValueError("Saved database is missing or DATABASE_PATH changed. Refusing to create an empty replacement. "
                             "Restore the recorded database or a verified backup before starting.")
        self.db = sqlite3.connect(self.path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS rooms (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self.db.commit()
        self.database_id = self.get("database_id")
        if identity and self.database_id != identity["database_id"]:
            self.db.close()
            raise ValueError("Database identity does not match this storage volume. Restore the correct database; ratings were not reset.")
        if self.db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            self.db.close()
            raise ValueError("Database integrity check failed. Restore a verified backup.")
        if not self.database_id:
            self.database_id = uuid.uuid4().hex
            self.set("database_id", self.database_id)
        if identity is None:
            temporary = self.marker.with_suffix(".tmp")
            temporary.write_text(json.dumps({"database_id": self.database_id, "database_path": str(self.path)}), encoding="utf-8")
            os.replace(temporary, self.marker)

    def backup(self):
        """One consistent SQLite snapshot per UTC day; keep seven on the same storage."""
        directory = self.path.parent / "backups"
        directory.mkdir(exist_ok=True)
        date = datetime.now(timezone.utc).date().isoformat()
        target = directory / f"22a-{self.database_id}-{date}.sqlite3"
        if target.exists():
            return target
        temporary = target.with_suffix(".tmp")
        destination = sqlite3.connect(temporary)
        try:
            self.db.backup(destination)
            if destination.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Database backup verification failed")
        finally:
            destination.close()
        os.replace(temporary, target)
        for old in sorted(directory.glob(f"22a-{self.database_id}-*.sqlite3"), reverse=True)[7:]:
            old.unlink()
        return target

    def rooms(self):
        return {row[0]: Room(**json.loads(row[1])) for row in self.db.execute("SELECT id, body FROM rooms")}

    def save(self, room):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO rooms VALUES (?, ?)", (room.id, json.dumps(asdict(room))))

    def delete(self, room_id):
        with self.db:
            self.db.execute("DELETE FROM rooms WHERE id = ?", (room_id,))

    def get(self, key):
        row = self.db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set(self, key, value):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, str(value)))
