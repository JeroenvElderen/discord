import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
import re

from config import CHANNEL_DAILY_UPDATES, MODERATOR_ROLE_ID
from database import (
    has_personal_update_today,
    insert_personal_update,
    get_personal_updates,
    get_personal_update_by_date,
    get_user_updates_for_mod_view
)


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _is_moderator(member: discord.Member) -> bool:
    return any(role.id == MODERATOR_ROLE_ID for role in getattr(member, "roles", []))


class DailyPersonalUpdates(commands.Cog):
    """
    One-message-per-day personal update channel + database-backed personal logbook.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ----------------------------
    # Listener: enforce 1 per day + save to logbook
    # ----------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.channel.id != CHANNEL_DAILY_UPDATES:
            return

        # Use UTC to avoid server/user timezone drift.
        today = datetime.now(timezone.utc).date().isoformat()
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

        # If they try posting an attachment-only update, store a safe placeholder.
        content = (message.content or "").strip()
        if not content and message.attachments:
            content = "[Attachment-only update]"
        elif not content:
            content = "[No text provided]"

        # Fast check (DB)
        if has_personal_update_today(message.author.id, message.channel.id, today):
            try:
                await message.delete()
            except discord.Forbidden:
                pass

            try:
                await message.author.send(
                    "You can only post **one personal update per day** in that channel.\n"
                    "Your extra message was removed and not saved."
                )
            except discord.Forbidden:
                pass
            return

        inserted = insert_personal_update(
            user_id=message.author.id,
            channel_id=message.channel.id,
            message_id=message.id,
            log_date=today,
            content=content,
            created_at=created_at
        )

        # In the rare case of a race condition (double post at the same time)
        if not inserted:
            try:
                await message.delete()
            except discord.Forbidden:
                pass

            try:
                await message.author.send(
                    "You can only post **one personal update per day** in that channel.\n"
                    "Your extra message was removed and not saved."
                )
            except discord.Forbidden:
                pass

    # ----------------------------
    # Slash command: /mylog
    # ----------------------------
    @app_commands.command(name="mylog", description="Read your personal logbook entries.")
    @app_commands.describe(limit="How many entries to show (1-20). Default: 5")
    async def mylog(self, interaction: discord.Interaction, limit: int = 5):
        limit = max(1, min(limit, 20))
        rows = get_personal_updates(interaction.user.id, limit=limit)

        if not rows:
            await interaction.response.send_message(
                "No logbook entries found yet. Post in the daily updates channel first.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="📓 Your Personal Logbook",
            color=discord.Color.green()
        )

        # Keep embed readable: add up to 10 fields, otherwise compress into description
        for row in rows[:10]:
            log_date = row["log_date"]
            content = row["content"]
            content = content if len(content) <= 900 else (content[:900] + "…")
            embed.add_field(name=log_date, value=content, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ----------------------------
    # Slash command: /mylogday
    # ----------------------------
    @app_commands.command(name="mylogday", description="Read your logbook entry for a specific date (YYYY-MM-DD).")
    @app_commands.describe(date="Date in format YYYY-MM-DD")
    async def mylogday(self, interaction: discord.Interaction, date: str):
        date = (date or "").strip()
        if not DATE_RE.match(date):
            await interaction.response.send_message(
                "Invalid date format. Use **YYYY-MM-DD** (example: 2025-12-16).",
                ephemeral=True
            )
            return

        row = get_personal_update_by_date(interaction.user.id, date)
        if not row:
            await interaction.response.send_message(
                f"No entry found for **{date}**.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"📓 Your Logbook — {row['log_date']}",
            description=row["content"] if len(row["content"]) <= 3900 else (row["content"][:3900] + "…"),
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ----------------------------
    # Optional moderator command: /userlog
    # ----------------------------
    @app_commands.command(name="userlog", description="(Moderator) Read a member’s recent logbook entries.")
    @app_commands.describe(member="Member to view", limit="How many entries to show (1-20). Default: 5")
    async def userlog(self, interaction: discord.Interaction, member: discord.Member, limit: int = 5):
        if not isinstance(interaction.user, discord.Member) or not _is_moderator(interaction.user):
            await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True
            )
            return

        limit = max(1, min(limit, 20))
        rows = get_user_updates_for_mod_view(member.id, limit=limit)

        if not rows:
            await interaction.response.send_message(
                f"No logbook entries found for {member.mention}.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"📓 Logbook — {member.display_name}",
            color=discord.Color.orange()
        )

        for row in rows[:10]:
            log_date = row["log_date"]
            content = row["content"]
            content = content if len(content) <= 900 else (content[:900] + "…")
            embed.add_field(name=log_date, value=content, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(DailyPersonalUpdates(bot))
