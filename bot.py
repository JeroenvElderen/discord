import discord
import config

from discord.ext import commands
from database import setup_database, get_connection
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN or not TOKEN.strip():
    raise ValueError(
        "DISCORD_TOKEN environment variable is not set or is empty. "
        "Please create a .env file with DISCORD_TOKEN=your_token_here or set the environment variable."
    )

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    setup_database()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

    # Load all cogs from /cogs automatically
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await bot.load_extension(f"cogs.{filename[:-3]}")
            print(f"Loaded cog: {filename}")

    await bot.tree.sync()
    print("Slash commands synced.")
    print("------")


# Example Slash Command
@bot.tree.command(name="hello", description="Say hello to the bot")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message("Hello! I am alive.")


# Example Prefix Command
@bot.command()
async def ac(ctx):
    await ctx.send("Alive check: I'm running!")


bot.run(TOKEN)
