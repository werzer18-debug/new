"""Configuration loaded from environment variables (see .env.example)."""

import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Copy .env.example to .env and fill it in."
        )
    return value


DISCORD_TOKEN = _require("DISCORD_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")  # SDK also reads this from env

DATABASE_PATH = os.environ.get("DATABASE_PATH", "server_memory.db")

# Moderation
MODERATION_ENABLED = os.environ.get("MODERATION_ENABLED", "false").lower() == "true"
_mod_channel = os.environ.get("MOD_LOG_CHANNEL_ID")
MOD_LOG_CHANNEL_ID = int(_mod_channel) if _mod_channel else None

# Mute duration (Discord timeout, in minutes) scaled by the flag's severity.
# All values are capped at 3 days (4320 min) by the moderation cog.
MUTE_MINUTES_BY_SEVERITY = {
    "low": int(os.environ.get("MUTE_MINUTES_LOW", "30")),       # 30 minutes
    "medium": int(os.environ.get("MUTE_MINUTES_MEDIUM", "360")),  # 6 hours
    "high": int(os.environ.get("MUTE_MINUTES_HIGH", "4320")),    # 3 days
}

# Data retention: automatically delete stored messages older than this many days.
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "3"))

# Models
ANSWER_MODEL = os.environ.get("ANSWER_MODEL", "claude-opus-4-8")
MODERATION_MODEL = os.environ.get("MODERATION_MODEL", "claude-opus-4-8")
