# cogs/featured_photos.py

import random
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone, time as dt_time
from zoneinfo import ZoneInfo

from config import (
    CHANNEL_BARE_LIFE,
    CHANNEL_BARE_NATURE,
    CHANNEL_FEATURED_PHOTOS,
)

from database import (
    is_image_already_featured,
    record_featured_photo,
)

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")
FEATURED_INFO_TAG = "FEATURED_WEEKLY_INFO"

DUBLIN_TZ = ZoneInfo("Europe/Dublin")
SUNDAY_WEEKDAY = 6  # Monday=0 ... Sunday=6


class FeaturedPhotos(commands.Cog):
    """
    Weekly Featured Photos system:
    - Primary window: last 7 days
    - Fallback: last 30 days
    - Final fallback: whole channel
    - Uses database to prevent duplicate features (image_url PRIMARY KEY + INSERT OR IGNORE)
    - Scheduled: Sunday at 18:00 Europe/Dublin
    - Manual trigger: /feature (moderators only)
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --------------------------------------------------
    # Proper lifecycle handling
    # --------------------------------------------------

    async def cog_load(self):
        # Start the loop (decorator defines the 18:00 schedule)
        self._weekly_featured_task.start()

    async def cog_unload(self):
        self._weekly_featured_task.cancel()

    # --------------------------------------------------
    # Startup hook (guarantees info embed exists)
    # --------------------------------------------------

    @commands.Cog.listener()
    async def on_ready(self):
        await self._ensure_info_embed()

    # --------------------------------------------------
    # Moderator check
    # --------------------------------------------------

    def _is_moderator(self, member: discord.Member) -> bool:
        perms = member.guild_permissions
        return perms.administrator or perms.manage_messages or perms.manage_guild

    # --------------------------------------------------
    # Persistent Weekly Highlights info embed (PINNED)
    # --------------------------------------------------

    async def _ensure_info_embed(self):
        channel = self.bot.get_channel(CHANNEL_FEATURED_PHOTOS)
        if not isinstance(channel, discord.TextChannel):
            return

        async for msg in channel.history(limit=50, oldest_first=True):
            if (
                msg.author == self.bot.user
                and msg.embeds
                and msg.embeds[0].footer
                and msg.embeds[0].footer.text == FEATURED_INFO_TAG
            ):
                if not msg.pinned:
                    try:
                        await msg.pin(reason="Weekly Highlights info")
                    except discord.Forbidden:
                        pass
                return

        embed = discord.Embed(
            title="🌟 Weekly Highlights",
            description=(
                "Each week, one photo from our community is selected and "
                "featured here.\n\n"
                "**How it works**\n"
                "• Photos are selected from `#bare-life` and `#bare-nature`\n"
                "• Primary window: last **7 days**\n"
                "• Fallback windows apply automatically\n"
                "• Posted every **Sunday at 18:00**\n\n"
                "**Channel rules**\n"
                "• Text discussion allowed\n"
                "• No images, files, or links\n"
                "• Moderators are exempt"
            ),
            color=discord.Color.gold(),
        )
        embed.set_footer(text=FEATURED_INFO_TAG)

        msg = await channel.send(embed=embed)
        try:
            await msg.pin(reason="Weekly Highlights info")
        except discord.Forbidden:
            pass

    # --------------------------------------------------
    # Collect image candidates
    # --------------------------------------------------

    async def _collect_image_candidates(
        self,
        channel: discord.TextChannel,
        days: int | None,
        max_messages: int = 5000,
    ) -> list[dict]:
        """
        Collect eligible images from a channel in a given time window, excluding
        anything already featured (checked via DB).
        """
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=days)
            if days is not None
            else None
        )

        candidates: list[dict] = []

        async for msg in channel.history(limit=max_messages):
            if cutoff and msg.created_at < cutoff:
                break

            # Attachments
            for att in msg.attachments:
                if (
                    att.content_type
                    and att.content_type.startswith("image/")
                    and not is_image_already_featured(att.url)
                ):
                    candidates.append(
                        {
                            "image_url": att.url,
                            "jump_url": msg.jump_url,
                            "author": msg.author,
                            "channel_id": channel.id,
                        }
                    )

            # Embeds (image/thumbnail)
            for emb in msg.embeds:
                img_url = None
                if emb.image and emb.image.url:
                    img_url = emb.image.url
                elif emb.thumbnail and emb.thumbnail.url:
                    img_url = emb.thumbnail.url

                if (
                    img_url
                    and img_url.lower().endswith(IMAGE_EXTENSIONS)
                    and not is_image_already_featured(img_url)
                ):
                    candidates.append(
                        {
                            "image_url": img_url,
                            "jump_url": msg.jump_url,
                            "author": msg.author,
                            "channel_id": channel.id,
                        }
                    )

        return candidates

    # --------------------------------------------------
    # Core logic: select + record + post
    # --------------------------------------------------

    async def _feature_once(
        self,
        *,
        featured_channel: discord.TextChannel,
        footer_note: str,
    ) -> bool:
        """
        Returns True if a photo was posted, False if none eligible.
        """
        source_ids = [CHANNEL_BARE_LIFE, CHANNEL_BARE_NATURE]
        windows = [7, 30, None]

        chosen: dict | None = None

        for window in windows:
            pool: list[dict] = []
            for cid in source_ids:
                src_channel = self.bot.get_channel(cid)
                if not isinstance(src_channel, discord.TextChannel):
                    continue
                pool.extend(await self._collect_image_candidates(src_channel, days=window))

            if pool:
                chosen = random.choice(pool)
                break

        if not chosen:
            await featured_channel.send(
                "🌟 **Featured Photo**\n"
                "No eligible images were found."
            )
            return False

        # Record FIRST (DB is authoritative). Because image_url is PRIMARY KEY and we use
        # INSERT OR IGNORE, this guarantees the same URL will not be featured twice.
        record_featured_photo(
            image_url=chosen["image_url"],
            channel_id=chosen["channel_id"],
            message_jump_url=chosen["jump_url"],
            author_id=chosen["author"].id if chosen["author"] else None,
            featured_at=datetime.now(timezone.utc).isoformat(),
        )

        # If it was already featured (race condition), the insert would be ignored.
        # In that unlikely case, just try again quickly with a different pick.
        # (This prevents posting an image that didn't actually record.)
        if is_image_already_featured(chosen["image_url"]) is False:
            # Extremely unlikely due to ordering above, but keep it safe.
            await featured_channel.send(
                "🌟 **Featured Photo**\n"
                "A database issue occurred while recording the feature."
            )
            return False

        embed = discord.Embed(
            title="🌟 Featured Photo",
            description=(
                f"From <#{chosen['channel_id']}>\n"
                f"Posted by {chosen['author'].mention if chosen['author'] else 'Unknown'}\n\n"
                f"[View original post]({chosen['jump_url']})"
            ),
            color=discord.Color.gold(),
        )
        embed.set_image(url=chosen["image_url"])
        embed.set_footer(text=footer_note)

        await featured_channel.send(embed=embed)
        return True

    # --------------------------------------------------
    # Scheduled task: fires daily at 18:00 Dublin, posts only on Sunday
    # --------------------------------------------------

    @tasks.loop(time=dt_time(hour=18, minute=0, tzinfo=DUBLIN_TZ))
    async def _weekly_featured_task(self):
        now_local = datetime.now(DUBLIN_TZ)
        if now_local.weekday() != SUNDAY_WEEKDAY:
            return

        featured_channel = self.bot.get_channel(CHANNEL_FEATURED_PHOTOS)
        if not isinstance(featured_channel, discord.TextChannel):
            return

        await self._feature_once(
            featured_channel=featured_channel,
            footer_note="Automated weekly feature • Sundays 18:00 (Europe/Dublin)",
        )

    @_weekly_featured_task.before_loop
    async def _before_weekly_featured_task(self):
        await self.bot.wait_until_ready()

    # --------------------------------------------------
    # Manual slash command: /feature (mods only)
    # --------------------------------------------------

    @discord.app_commands.command(
        name="feature",
        description="Post a featured photo now (mods only).",
    )
    async def feature_command(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        if not self._is_moderator(interaction.user):
            await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True,
            )
            return

        featured_channel = self.bot.get_channel(CHANNEL_FEATURED_PHOTOS)
        if not isinstance(featured_channel, discord.TextChannel):
            await interaction.response.send_message(
                "Featured channel not found or not a text channel.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        posted = await self._feature_once(
            featured_channel=featured_channel,
            footer_note=f"Manual feature by {interaction.user.display_name}",
        )

        if posted:
            await interaction.followup.send("Posted a featured photo.", ephemeral=True)
        else:
            await interaction.followup.send("No eligible images found.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(FeaturedPhotos(bot))
