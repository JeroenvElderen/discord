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
        cleanup_old_daily_posts()

        for channel_id in DAILY_IMAGE_CHANNELS:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                continue

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
                    "• One image per user per day\n"
                    "• Respect consent and privacy\n"
                    "• No spam or reposts\n"
                    "• Follow community guidelines"
                ),
                color=0x2ECC71
            )

            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.channel.id not in DAILY_IMAGE_CHANNELS:
            return

        if not message.attachments:
            return

        if has_posted_today(message.author.id, message.channel.id):
            await message.delete()
            await message.channel.send(
                f"{message.author.mention} you already posted an image today.",
                delete_after=10
            )
            return

        record_post(message.author.id, message.channel.id)


async def setup(bot: commands.Bot):
    await bot.add_cog(DailyImageChannel(bot))
