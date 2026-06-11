"""Memory features: index messages and answer questions about server history."""

from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

import claude_client
import config

MAX_DISCORD_LEN = 1900  # Discord hard limit is 2000; leave headroom


class Memory(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.purge_old_messages.start()

    def cog_unload(self) -> None:
        self.purge_old_messages.cancel()

    @tasks.loop(hours=6)
    async def purge_old_messages(self) -> None:
        """Delete stored messages older than the retention window.

        Runs on startup (cleaning up any old messages already saved) and every
        6 hours thereafter.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=config.RETENTION_DAYS)
        deleted = await self.bot.db.purge_older_than(int(cutoff.timestamp()))
        if deleted:
            print(
                f"[retention] purged {deleted} message(s) older than "
                f"{config.RETENTION_DAYS} day(s)"
            )

    @purge_old_messages.before_loop
    async def _before_purge(self) -> None:
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        # Index human messages in guild text channels only.
        if message.author.bot or message.guild is None or not message.content:
            return
        if await self.bot.db.is_opted_out(message.author.id):
            return
        await self.bot.db.store_message(
            message_id=message.id,
            guild_id=message.guild.id,
            channel_id=message.channel.id,
            channel_name=getattr(message.channel, "name", "unknown"),
            author_id=message.author.id,
            author_name=message.author.display_name,
            content=message.content,
            created_at=int(message.created_at.timestamp()),
        )

    @app_commands.command(
        name="ask", description="Ask anything about this server's history"
    )
    @app_commands.describe(question="What do you want to know?")
    async def ask(self, interaction: discord.Interaction, question: str) -> None:
        await interaction.response.defer(thinking=True)
        rows = await self.bot.db.search(interaction.guild_id, question)
        answer = await claude_client.answer_question(question, rows)
        if len(answer) > MAX_DISCORD_LEN:
            answer = answer[:MAX_DISCORD_LEN] + "…"
        await interaction.followup.send(answer or "I couldn't find anything about that.")

    @app_commands.command(
        name="forget_me",
        description="Delete your stored messages and stop indexing them",
    )
    async def forget_me(self, interaction: discord.Interaction) -> None:
        await self.bot.db.opt_out(interaction.user.id)
        await interaction.response.send_message(
            "Done — I deleted your stored messages and won't index new ones. "
            "Use /remember_me to opt back in.",
            ephemeral=True,
        )

    @app_commands.command(
        name="remember_me", description="Opt back in to message indexing"
    )
    async def remember_me(self, interaction: discord.Interaction) -> None:
        await self.bot.db.opt_in(interaction.user.id)
        await interaction.response.send_message(
            "You're opted back in.", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Memory(bot))
