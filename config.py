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

# Models
ANSWER_MODEL = os.environ.get("ANSWER_MODEL", "claude-opus-4-8")
MODERATION_MODEL = os.environ.get("MODERATION_MODEL", "claude-opus-4-8")
