"""Moderation: classify messages and report genuinely problematic ones.

This never auto-bans or deletes. It surfaces flagged messages to a mod-only
channel with the model's reasoning, so a human always makes the final call.
Disabled unless MODERATION_ENABLED=true and MOD_LOG_CHANNEL_ID is set.
"""

import discord
from discord.ext import commands

import claude_client
import config

SEVERITY_COLORS = {
    "low": 0xF1C40F,     # yellow
    "medium": 0xE67E22,  # orange
    "high": 0xE74C3C,    # red
}

MIN_LENGTH = 4  # skip trivially short messages to save API calls


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not config.MODERATION_ENABLED or config.MOD_LOG_CHANNEL_ID is None:
            return
        if message.author.bot or message.guild is None or not message.content:
            return
        if len(message.content) < MIN_LENGTH:
            return

        try:
            result = await claude_client.moderate_message(message.content)
        except Exception as exc:  # noqa: BLE001 — never let moderation crash the bot
            print(f"[moderation] classification error: {exc}")
            return

        if result.get("flagged"):
            await self._report(message, result)

    async def _report(self, message: discord.Message, result: dict) -> None:
        channel = self.bot.get_channel(config.MOD_LOG_CHANNEL_ID)
        if channel is None:
            print(
                "[moderation] MOD_LOG_CHANNEL_ID is set but the channel "
                "wasn't found — check the ID and the bot's access."
            )
            return

        severity = result.get("severity", "low")
        embed = discord.Embed(
            title="⚠️ Message flagged for review",
            description=message.content[:1024],
            color=SEVERITY_COLORS.get(severity, 0x95A5A6),
        )
        embed.add_field(name="Author", value=message.author.mention, inline=True)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.add_field(name="Category", value=result.get("category", "n/a"), inline=True)
        embed.add_field(name="Severity", value=severity, inline=True)
        embed.add_field(
            name="Reason", value=(result.get("reason") or "n/a")[:1024], inline=False
        )
        embed.add_field(
            name="Jump", value=f"[Go to message]({message.jump_url})", inline=False
        )
        await channel.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
