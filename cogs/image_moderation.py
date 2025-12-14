import os
import discord
from discord.ext import commands
from nudenet import NudeDetector

from config import PROTECTED_IMAGE_CHANNELS, NO_IMAGE_CHANNELS

TEMP_DIR = "/tmp/nudenet"
NUDITY_THRESHOLD = 0.3
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


class ImageModeration(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.detector = NudeDetector()
        os.makedirs(TEMP_DIR, exist_ok=True)

    def is_nude(self, image_path: str) -> bool:
        detections = self.detector.detect(image_path)
        print("NUDENET DETECTIONS:", detections)

        for item in detections:
            if item.get("score", 0) >= NUDITY_THRESHOLD:
                return True
        return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # HARD RULE: no images at all
        if message.channel.id in NO_IMAGE_CHANNELS and message.attachments:
            await message.delete()
            await message.channel.send(
                f"{message.author.mention} ❌ Images are not allowed in this channel.",
                delete_after=10
            )
            return

        # Only scan nudity in protected channels
        if message.channel.id not in PROTECTED_IMAGE_CHANNELS:
            return

        if not message.attachments:
            return

        for attachment in message.attachments:
            if not attachment.filename.lower().endswith(IMAGE_EXTENSIONS):
                continue

            image_path = f"{TEMP_DIR}/{attachment.id}.jpg"
            await attachment.save(image_path)

            try:
                if self.is_nude(image_path):
                    await message.delete()
                    await message.channel.send(
                        f"{message.author.mention} ❌ Images containing nudity are not allowed here.",
                        delete_after=10
                    )
                    return
            finally:
                if os.path.exists(image_path):
                    os.remove(image_path)


async def setup(bot: commands.Bot):
    await bot.add_cog(ImageModeration(bot))
