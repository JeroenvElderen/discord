import discord
from discord.ext import commands, tasks
from discord import app_commands, Interaction
from datetime import datetime, timedelta, time, timezone

from config import CHANNEL_WIND_DOWN, MODERATOR_ROLE_ID


class WeeklyWindDown(commands.Cog):
    """
    Weekly wind-down ritual:
    - Posts a calm reflection prompt
    - Enables slow mode
    - Locks channel after 24 hours
    - Posts a summary message for reflection
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session_message_id: int | None = None
        self.start_time: datetime | None = None
        self.weekly_wind_down.start()

    # --------------------------------------------------
    # Startup safety
    # --------------------------------------------------
    @commands.Cog.listener()
    async def on_ready(self):
        await self.bot.wait_until_ready()

        now = datetime.now(timezone.utc)

        # Friday = 4 (Monday = 0)
        if now.weekday() != 4:
            return

        channel = self.bot.get_channel(CHANNEL_WIND_DOWN)
        if not isinstance(channel, discord.TextChannel):
            return

        # Prevent duplicate session
        async for msg in channel.history(limit=5):
            if (
                msg.author.id == self.bot.user.id
                and msg.embeds
                and msg.embeds[0].title == "🌿 Weekly Wind-Down"
            ):
                return

        await self._start_wind_down(channel)

    # --------------------------------------------------
    # Scheduled weekly task
    # --------------------------------------------------
    @tasks.loop(time=time(hour=18, minute=0, tzinfo=timezone.utc))
    async def weekly_wind_down(self):
        """Runs every Friday at 18:00 UTC."""
        if datetime.now(timezone.utc).weekday() != 4:
            return

        channel = self.bot.get_channel(CHANNEL_WIND_DOWN)
        if not isinstance(channel, discord.TextChannel):
            return

        # Prevent duplicate session
        async for msg in channel.history(limit=5):
            if (
                msg.author.id == self.bot.user.id
                and msg.embeds
                and msg.embeds[0].title == "🌿 Weekly Wind-Down"
            ):
                return

        await self._start_wind_down(channel)

    # --------------------------------------------------
    # Moderator slash command (ROLE-BASED)
    # --------------------------------------------------
    @app_commands.command(
        name="start_winddown",
        description="Manually start the weekly wind-down session."
    )
    async def start_winddown(self, interaction: Interaction):

        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True
            )
            return

        # Role-based moderator check (from config.py)
        if not any(role.id == MODERATOR_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message(
                "You do not have permission to start the wind-down session.",
                ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(CHANNEL_WIND_DOWN)
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "Wind-down channel not found or misconfigured.",
                ephemeral=True
            )
            return

        # Prevent duplicate session
        async for msg in channel.history(limit=5):
            if (
                msg.author.id == self.bot.user.id
                and msg.embeds
                and msg.embeds[0].title == "🌿 Weekly Wind-Down"
            ):
                await interaction.response.send_message(
                    "A wind-down session is already active.",
                    ephemeral=True
                )
                return

        await self._start_wind_down(channel)

        await interaction.response.send_message(
            "🌿 Weekly wind-down started successfully.",
            ephemeral=True
        )

    # --------------------------------------------------
    # Core logic
    # --------------------------------------------------
    async def _start_wind_down(self, channel: discord.TextChannel):
        # Unlock channel
        await channel.set_permissions(
            channel.guild.default_role,
            send_messages=True,
            reason="Weekly wind-down started"
        )

        await channel.edit(slowmode_delay=60)

        embed = discord.Embed(
            title="🌿 Weekly Wind-Down",
            description=(
                "Take a moment to slow down with the community.\n\n"
                "• What felt good this week?\n"
                "• What are you grateful for right now?\n"
                "• What would you like to leave behind before the new week begins?\n\n"
                "No debates. No judging. Just presence."
            ),
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )

        message = await channel.send(embed=embed)

        self.session_message_id = message.id
        self.start_time = datetime.now(timezone.utc)

        self.bot.loop.create_task(self._lock_and_summarize(channel))

    async def _lock_and_summarize(self, channel: discord.TextChannel):
        await discord.utils.sleep_until(self.start_time + timedelta(hours=24))

        # Lock channel
        await channel.set_permissions(
            channel.guild.default_role,
            send_messages=False,
            reason="Weekly wind-down concluded"
        )

        await channel.edit(slowmode_delay=0)

        participants: dict[str, int] = {}

        theme_keywords = {
            "Slowing down & rest": ["rest", "slow", "tired", "sleep", "calm", "quiet"],
            "Gratitude & appreciation": ["grateful", "thankful", "gratitude", "appreciate"],
            "Nature & outdoors": ["nature", "sun", "outdoors", "weather", "forest", "sea"],
            "Letting go of stress": ["stress", "busy", "pressure", "overwhelmed", "release"],
            "Community & connection": ["together", "community", "here", "space", "sharing"],
        }

        theme_hits = {key: 0 for key in theme_keywords}

        async for msg in channel.history(limit=500):
            if msg.author.bot or not msg.content:
                continue

            participants[msg.author.display_name] = (
                participants.get(msg.author.display_name, 0) + 1
            )

            content_lower = msg.content.lower()
            for theme, keywords in theme_keywords.items():
                if any(word in content_lower for word in keywords):
                    theme_hits[theme] += 1

        theme_lines = [
            f"• {theme}" for theme, count in theme_hits.items() if count > 0
        ]

        if participants:
            summary_text = (
                f"This week’s wind-down brought together "
                f"{len(participants)} community member(s)."
            )
        else:
            summary_text = "This session was quiet, but the space was held."

        if theme_lines:
            summary_text += "\n\nCommon themes included:\n" + "\n".join(theme_lines)

        summary_embed = discord.Embed(
            title="🕯️ Wind-Down Reflection",
            description=summary_text,
            color=discord.Color.dark_green(),
            timestamp=datetime.now(timezone.utc)
        )

        await channel.send(embed=summary_embed)

    # --------------------------------------------------
    # Task lifecycle
    # --------------------------------------------------
    @weekly_wind_down.before_loop
    async def before_weekly_wind_down(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(WeeklyWindDown(bot))
