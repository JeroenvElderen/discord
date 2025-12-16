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
    # Attribution resolver
    # --------------------------------------------------

    def _extract_original_author(
        self, msg: discord.Message
    ) -> discord.abc.User | None:

        if not msg.author.bot:
            return msg.author

        if not msg.embeds or not msg.guild:
            return None

        for field in msg.embeds[0].fields:
            if field.name.lower() == "original poster":
                mention = field.value.strip("<@!>")
                return msg.guild.get_member(int(mention)) if mention.isdigit() else None

        return None

    # --------------------------------------------------
    # Info embed
    # --------------------------------------------------

    @commands.Cog.listener()
    async def on_ready(self):
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
                    await msg.pin()
                return

        embed = discord.Embed(
            title="🌟 Weekly Highlights",
            description=(
                "Each week one photo is featured from "
                "`#bare-life` or `#bare-nature`.\n\n"
                "Posted every **Friday at 18:00**."
            ),
            color=discord.Color.gold(),
        )
        embed.set_footer(text=FEATURED_INFO_TAG)
        msg = await channel.send(embed=embed)
        await msg.pin()

    # --------------------------------------------------
    # Candidate collection
    # --------------------------------------------------

    async def _collect(
        self,
        channel: discord.TextChannel,
        days: int | None,
    ) -> list[dict]:

        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=days)
            if days else None
        )

        results = []

        async for msg in channel.history(limit=5000):
            if cutoff and msg.created_at < cutoff:
                break

            author = self._extract_original_author(msg)

            for att in msg.attachments:
                if (
                    att.content_type
                    and att.content_type.startswith("image/")
                    and not is_image_already_featured(att.url)
                ):
                    results.append({
                        "image_url": att.url,
                        "jump_url": msg.jump_url,
                        "author": author,
                        "channel_id": channel.id,
                    })

        return results

    # --------------------------------------------------
    # Weekly task
    # --------------------------------------------------

    @tasks.loop(time=dt_time(hour=18, minute=0, tzinfo=ZoneInfo("Europe/Dublin")))
    async def _weekly_featured_task(self):
        featured = self.bot.get_channel(CHANNEL_FEATURED_PHOTOS)
        if not isinstance(featured, discord.TextChannel):
            return

        windows = [7, 30, None]
        sources = [CHANNEL_BARE_LIFE, CHANNEL_BARE_NATURE]
        chosen = None

        for window in windows:
            pool = []
            for cid in sources:
                ch = self.bot.get_channel(cid)
                if isinstance(ch, discord.TextChannel):
                    pool.extend(await self._collect(ch, window))
            if pool:
                chosen = random.choice(pool)
                break

        if not chosen:
            await featured.send("No eligible images found this week.")
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

        await featured.send(embed=embed)

    @_weekly_featured_task.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(FeaturedPhotos(bot))
