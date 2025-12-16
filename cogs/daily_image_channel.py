# cogs/daily_image_channel.py

import discord
from discord.ext import commands

from config import DAILY_IMAGE_CHANNELS
from database import (
    has_posted_today,
    record_post,
    cleanup_old_daily_posts
)


class DailyImageChannel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Cleanup old daily records (restart-safe)
        cleanup_old_daily_posts()

        for channel_id in DAILY_IMAGE_CHANNELS:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                continue

            # Check if rules embed already exists in this channel
            rules_already_posted = False
            async for msg in channel.history(limit=25):
                if (
                    msg.author.id == self.bot.user.id
                    and msg.embeds
                    and msg.embeds[0].title == "📸 Channel Rules"
                ):
                    rules_already_posted = True
                    break

            if rules_already_posted:
                continue

            embed = discord.Embed(
                title="📸 Channel Rules",
                description=(
                    "• React with emoji\n"
                    "• Reply to images to say positive things\n"
                    "• **One image post per user per day**\n"
                    "• **New messages must contain an image**\n"
                    "• **Text-only posts are not allowed**\n\n"
                    "Replies without images **are allowed**."
                ),
                color=discord.Color.green()
            )

            rules_message = await channel.send(embed=embed)
            await rules_message.pin(reason="Image channel rules")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.channel.id not in DAILY_IMAGE_CHANNELS:
            return

        # Replies are always allowed
        if message.reference is not None:
            return

        images = [
            a for a in message.attachments
            if a.content_type and a.content_type.startswith("image/")
        ]

        # No image → delete
        if not images:
            await message.delete()
            return

        # Enforce restart-safe daily limit
        if has_posted_today(message.author.id, message.channel.id):
            await message.delete()
            return

        # Record valid post
        record_post(message.author.id, message.channel.id)


async def setup(bot: commands.Bot):
    await bot.add_cog(DailyImageChannel(bot))
