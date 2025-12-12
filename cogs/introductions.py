import discord
from discord.ext import commands
from config import CHANNEL_INTRODUCTIONS

INTRO_EMOJIS = ["👋", "🌿", "❤️"]


class Introductions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.channel.id != CHANNEL_INTRODUCTIONS:
            return

        # Enforce one introduction per user
        async for msg in message.channel.history(
            limit=50,
            before=message.created_at
        ):
            if msg.author.id == message.author.id:
                try:
                    await message.delete()
                except discord.Forbidden:
                    print("❌ Missing permissions to delete introduction message.")
                except discord.HTTPException:
                    pass
                return

        # Add predefined reactions to the valid introduction
        for emoji in INTRO_EMOJIS:
            try:
                await message.add_reaction(emoji)
            except discord.HTTPException:
                pass

        await self.bot.process_commands(message)

    @commands.Cog.listener()
    async def on_reaction_add(
        self,
        reaction: discord.Reaction,
        user: discord.User
    ):
        if user.bot:
            return

        message = reaction.message

        if message.channel.id != CHANNEL_INTRODUCTIONS:
            return

        # Remove reactions not in allowed list
        if str(reaction.emoji) not in INTRO_EMOJIS:
            try:
                await reaction.remove(user)
            except discord.Forbidden:
                pass
            return

        # Enforce ONE reaction per user
        for emoji in INTRO_EMOJIS:
            if emoji == str(reaction.emoji):
                continue

            for react in message.reactions:
                if str(react.emoji) == emoji:
                    try:
                        await react.remove(user)
                    except discord.Forbidden:
                        pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Introductions(bot))
