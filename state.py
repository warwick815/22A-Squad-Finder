"""Small durable state store; no Discord or credentials in this module."""
import json
import sqlite3
import time
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
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS rooms (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self.db.commit()

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
