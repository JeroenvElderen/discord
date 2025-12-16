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


class FeaturedPhotos(commands.Cog):
    """
    Weekly Featured Photos system:
    - Primary window: last 7 days
    - Fallback: last 30 days
    - Final fallback: whole channel
    - Uses database to prevent duplicate features
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        dublin = ZoneInfo("Europe/Dublin")
        self._weekly_featured_task.change_interval(
            time=dt_time(hour=18, minute=0, tzinfo=dublin)
        )
        self._weekly_featured_task.start()

    def cog_unload(self):
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
        return (
            perms.administrator
            or perms.manage_messages
            or perms.manage_guild
        )

    # --------------------------------------------------
    # Persistent Weekly Highlights info embed (PINNED)
    # --------------------------------------------------
    async def _ensure_info_embed(self):
        channel = self.bot.get_channel(CHANNEL_FEATURED_PHOTOS)
        if not isinstance(channel, discord.TextChannel):
            return

        # Look for existing embed (pinned or not)
        async for msg in channel.history(limit=50, oldest_first=True):
            if (
                msg.author == self.bot.user
                and msg.embeds
                and msg.embeds[0].footer
                and msg.embeds[0].footer.text == FEATURED_INFO_TAG
            ):
                # Ensure it is pinned
                if not msg.pinned:
                    try:
                        await msg.pin(reason="Weekly Highlights info")
                    except discord.Forbidden:
                        pass
                return

        # Create embed if not found
        embed = discord.Embed(
            title="🌟 Weekly Highlights",
            description=(
                "Each week, one photo from our community is selected and "
                "featured here.\n\n"
                "**How it works**\n"
                "• Photos are selected from `#bare-life` and `#bare-nature`\n"
                "• Primary window: last **7 days**\n"
                "• Fallback windows apply automatically\n"
                "• Posted every **Friday at 18:00**\n\n"
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

        cutoff = None
        if days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        candidates: list[dict] = []

        async for msg in channel.history(limit=max_messages):
            if cutoff and msg.created_at < cutoff:
                break

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
    # Weekly featured task
    # --------------------------------------------------
    @tasks.loop(time=dt_time(hour=18, minute=0, tzinfo=ZoneInfo("Europe/Dublin")))
    async def _weekly_featured_task(self):
        featured_channel = self.bot.get_channel(CHANNEL_FEATURED_PHOTOS)
        if not isinstance(featured_channel, discord.TextChannel):
            return

        source_ids = [CHANNEL_BARE_LIFE, CHANNEL_BARE_NATURE]
        windows = [7, 30, None]

        chosen = None

        for window in windows:
            pool: list[dict] = []

            for cid in source_ids:
                channel = self.bot.get_channel(cid)
                if not isinstance(channel, discord.TextChannel):
                    continue

                try:
                    pool.extend(
                        await self._collect_image_candidates(channel, days=window)
                    )
                except Exception as e:
                    print(f"❌ FeaturedPhotos: error scanning #{channel.name}: {e}")

            if pool:
                chosen = random.choice(pool)
                break

        if not chosen:
            await featured_channel.send(
                "🌟 **Featured Photo of the Week**\n"
                "No eligible images were found."
            )
            return

        record_featured_photo(
            image_url=chosen["image_url"],
            channel_id=chosen["channel_id"],
            message_jump_url=chosen["jump_url"],
            author_id=chosen["author"].id if chosen["author"] else None,
            featured_at=datetime.now(timezone.utc).isoformat(),
        )

        embed = discord.Embed(
            title="🌟 Featured Photo of the Week",
            description=(
                f"From <#{chosen['channel_id']}>\n"
                f"Posted by {chosen['author'].mention if chosen['author'] else 'Unknown'}\n\n"
                f"[View original post]({chosen['jump_url']})"
            ),
            color=discord.Color.gold(),
        )
        embed.set_image(url=chosen["image_url"])
        embed.set_footer(text="Automated weekly feature • Fridays 18:00")

        await featured_channel.send(embed=embed)

    @_weekly_featured_task.before_loop
    async def _before_weekly_featured_task(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(FeaturedPhotos(bot))
