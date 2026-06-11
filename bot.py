"""Entry point for the Discord server-memory + moderation bot."""

import discord
from discord.ext import commands

import config
from db import Database

intents = discord.Intents.default()
intents.message_content = True  # required to read message text (enable in the Dev Portal)


class MemoryBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.db = Database(config.DATABASE_PATH)

    async def setup_hook(self) -> None:
        await self.db.connect()
        await self.load_extension("cogs.memory")
        await self.load_extension("cogs.moderation")
        await self.tree.sync()  # register slash commands

    async def on_ready(self) -> None:
        print(f"Logged in as {self.user} (id: {self.user.id})")
        print("Slash commands synced. The bot is ready.")

    async def close(self) -> None:
        await self.db.close()
        await super().close()


def main() -> None:
    bot = MemoryBot()
    bot.run(config.DISCORD_TOKEN)


if __name__ == "__main__":
    main()
