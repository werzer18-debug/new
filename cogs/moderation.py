"""Moderation: classify messages, take a graduated action, and log it.

Actions, by severity (it never bans):
  - low / medium -> warn the user (DM)
  - high         -> mute the user (Discord timeout) + warn

Every action is also reported to a mod-only channel with the model's reasoning,
so a human can review and reverse it. Staff (anyone who can manage messages) are
never auto-actioned, only logged. Disabled unless MODERATION_ENABLED=true and
MOD_LOG_CHANNEL_ID is set.
"""

from datetime import timedelta

import discord
from discord.ext import commands

import claude_client
import config

SEVERITY_COLORS = {
    "low": 0xF1C40F,     # yellow
    "medium": 0xE67E22,  # orange
    "high": 0xE74C3C,    # red
}

# Categories that warrant a mute — threats and abuse. Anything else that gets
# flagged (spam/scams, mild toxicity) is warned instead of muted.
MUTE_CATEGORIES = {"threat", "harassment", "hate", "csam"}

# Discord's own timeout limit is 28 days; we cap mutes at 3 days by policy.
MAX_MUTE_MINUTES = 3 * 24 * 60  # 4320

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
            await self._handle(message, result)

    async def _handle(self, message: discord.Message, result: dict) -> None:
        category = result.get("category", "none")

        # Never auto-action staff — only log for their review.
        perms = getattr(message.author, "guild_permissions", None)
        if perms is not None and perms.manage_messages:
            action, detail = "none", "author is staff — logged only"
        elif category in MUTE_CATEGORIES:
            # Threats or abuse -> mute.
            action, detail = await self._mute(message, result)
        else:
            # Everything else flagged (spam, mild toxicity) -> warn.
            action, detail = await self._warn(message, result)

        await self._log(message, result, action, detail)

    async def _warn(self, message: discord.Message, result: dict) -> tuple[str, str]:
        reason = result.get("reason") or "Your message may violate the server rules."
        try:
            await message.author.send(
                f"⚠️ Heads up from **{message.guild.name}**: a recent message of "
                f"yours was flagged.\n> {reason}\nPlease review the server rules."
            )
            return "warned", "warning DM sent"
        except discord.Forbidden:
            return "warned", "warning DM failed (user has DMs closed)"

    async def _mute(self, message: discord.Message, result: dict) -> tuple[str, str]:
        reason = result.get("reason") or "Flagged content"
        severity = result.get("severity", "medium")
        # Scale the timeout by severity; fall back to the medium tier for an
        # unexpected value, and never exceed the 3-day cap.
        minutes = config.MUTE_MINUTES_BY_SEVERITY.get(
            severity, config.MUTE_MINUTES_BY_SEVERITY["medium"]
        )
        minutes = min(minutes, MAX_MUTE_MINUTES)
        try:
            await message.author.timeout(
                timedelta(minutes=minutes),
                reason=f"Auto-mute: {reason}",
            )
        except discord.Forbidden:
            return "mute failed", "missing 'Timeout Members' permission or role too low"
        except discord.HTTPException as exc:
            return "mute failed", str(exc)

        # Also try to let the user know why they were muted.
        await self._warn(message, result)
        return "muted", f"{minutes} min timeout"

    async def _log(
        self, message: discord.Message, result: dict, action: str, detail: str
    ) -> None:
        channel = self.bot.get_channel(config.MOD_LOG_CHANNEL_ID)
        if channel is None:
            print(
                "[moderation] MOD_LOG_CHANNEL_ID is set but the channel "
                "wasn't found — check the ID and the bot's access."
            )
            return

        severity = result.get("severity", "low")
        embed = discord.Embed(
            title="⚠️ Message flagged",
            description=message.content[:1024],
            color=SEVERITY_COLORS.get(severity, 0x95A5A6),
        )
        embed.add_field(name="Author", value=message.author.mention, inline=True)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.add_field(name="Category", value=result.get("category", "n/a"), inline=True)
        embed.add_field(name="Severity", value=severity, inline=True)
        embed.add_field(name="Action taken", value=f"{action} ({detail})", inline=True)
        embed.add_field(
            name="Reason", value=(result.get("reason") or "n/a")[:1024], inline=False
        )
        embed.add_field(
            name="Jump", value=f"[Go to message]({message.jump_url})", inline=False
        )
        await channel.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
