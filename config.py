import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Config:
    token: str
    guild_id: int
    lfg_id: int
    category_id: int
    database: Path
    empty_seconds: int
    initial_seconds: int
    max_size: int
    max_rooms: int
    logo_url: str

    @classmethod
    def load(cls):
        load_dotenv(ROOT / ".env")
        def integer(key, default=None, minimum=1, maximum=10**20):
            raw = os.getenv(key, str(default) if default is not None else "")
            try:
                value = int(raw)
                if not minimum <= value <= maximum:
                    raise ValueError()
                return value
            except ValueError:
                raise ValueError(f"Set {key} to an integer between {minimum} and {maximum} in .env") from None
        token = os.getenv("DISCORD_TOKEN", "").strip()
        if not token or token == "paste_your_bot_token_here":
            raise ValueError("Set DISCORD_TOKEN in your local .env file.")
        path = Path(os.getenv("DATABASE_PATH", "data/22a.sqlite3"))
        if not path.is_absolute():
            path = ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        logo = os.getenv("BRAND_LOGO_URL", "").strip()
        if logo and not logo.startswith("https://"):
            raise ValueError("BRAND_LOGO_URL must be an https:// image URL or empty.")
        return cls(token, integer("GUILD_ID"), integer("LFG_CHANNEL_ID"),
                   integer("VOICE_CATEGORY_ID"), path,
                   integer("EMPTY_TIMEOUT_SECONDS", 120, 30),
                   integer("INITIAL_TIMEOUT_SECONDS", 600, 60),
                   integer("MAX_SQUAD_SIZE", 16, 2, 25),
                   integer("MAX_ACTIVE_ROOMS", 30, 1, 45), logo)
