# cogs/nature_router.py

import os
import cv2
import numpy as np
import aiohttp
import discord
from discord.ext import commands
from datetime import datetime, timezone

from config import (
    CHANNEL_BARE_LIFE,
    CHANNEL_BARE_NATURE,
)

TEMP_DIR = "/tmp/nature_router"
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
NATURE_THRESHOLD = 0.75
HISTORY_SCAN_LIMIT = 100


class NatureRouter(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        os.makedirs(TEMP_DIR, exist_ok=True)

    # --------------------------------------------------
    # Nature detection
    # --------------------------------------------------

    def _nature_score(self, image_path: str) -> float:
        img = cv2.imread(image_path)
        if img is None:
            return 0.0

        h, w, _ = img.shape
        total = h * w
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        green = cv2.inRange(hsv, (35, 40, 40), (85, 255, 255))
        blue = cv2.inRange(hsv, (90, 30, 30), (135, 255, 255))

        green_ratio = np.count_nonzero(green) / total
        blue_ratio = np.count_nonzero(blue) / total

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 100, 200)
        edge_density = np.count_nonzero(edges) / total

        score = (
            min(green_ratio * 2.5, 0.5) +
            min(blue_ratio * 2.0, 0.3) +
            min(edge_density * 1.5, 0.2)
        )

        return min(score, 1.0)

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------

    async def _download(self, url: str, filename: str) -> str:
        path = os.path.join(TEMP_DIR, filename)
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    with open(path, "wb") as f:
                        f.write(await resp.read())
        return path

    async def _already_posted_today(
        self,
        channel: discord.TextChannel,
        user: discord.Member,
    ) -> bool:
        today = datetime.now(timezone.utc).date()

        async for msg in channel.history(limit=HISTORY_SCAN_LIMIT):
            if (
                not msg.author.bot
                and msg.author.id == user.id
                and msg.attachments
                and msg.created_at.date() == today
            ):
                return True

        return False

    async def _repost(
        self,
        message: discord.Message,
        target: discord.TextChannel,
        score: float,
    ):
        embed = discord.Embed(
            description=message.content or "",
            color=discord.Color.green(),
        )

        embed.add_field(
            name="Original poster",
            value=message.author.mention,
            inline=False,
        )

        embed.set_footer(text=f"Auto-routed • Nature score {score:.2f}")

        files = [await a.to_file() for a in message.attachments]
        await target.send(embed=embed, files=files)

    # --------------------------------------------------
    # Listener
    # --------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.channel.id not in {
            CHANNEL_BARE_LIFE,
            CHANNEL_BARE_NATURE,
        }:
            return

        if not message.attachments:
            return

        att = message.attachments[0]
        if not att.filename.lower().endswith(IMAGE_EXTENSIONS):
            return

        img_path = await self._download(att.url, att.filename)
        score = self._nature_score(img_path)

        # LIFE → NATURE
        if message.channel.id == CHANNEL_BARE_LIFE and score >= NATURE_THRESHOLD:
            target = self.bot.get_channel(CHANNEL_BARE_NATURE)
            if target and not await self._already_posted_today(target, message.author):
                await self._repost(message, target, score)
                await message.reply(
                    "🌿 Detected outdoor nature — reposted to **#bare-nature**",
                    mention_author=False,
                )

        # NATURE → LIFE
        elif message.channel.id == CHANNEL_BARE_NATURE and score < NATURE_THRESHOLD:
            target = self.bot.get_channel(CHANNEL_BARE_LIFE)
            if target and not await self._already_posted_today(target, message.author):
                await self._repost(message, target, score)
                await message.reply(
                    "🏠 Detected daily life — reposted to **#bare-life**",
                    mention_author=False,
                )


async def setup(bot: commands.Bot):
    await bot.add_cog(NatureRouter(bot))
