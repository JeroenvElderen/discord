import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

from database import setup_database

# =========================
# Environment
# =========================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN or not TOKEN.strip():
    raise ValueError(
        "DISCORD_TOKEN environment variable is not set or empty."
    )

# =========================
# Intents
# =========================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

# =========================
# Bot
# =========================
bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# =========================
# Startup Logic (ONCE)
# =========================
async def load_cogs():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await bot.load_extension(f"cogs.{filename[:-3]}")
            print(f"Loaded cog: {filename}")


@bot.event
async def setup_hook():
    # Database init
    setup_database()

    # Load cogs ONCE
    await load_cogs()

    # Sync slash commands ONCE
    await bot.tree.sync()
    print("Slash commands synced.")


@bot.event
async def on_ready():
    # Presence / logging ONLY
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")


# =========================
# Example Slash Command
# =========================
@bot.tree.command(name="hello", description="Say hello to the bot")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message("Hello! I am alive.")


# =========================
# Example Prefix Command
# =========================
@bot.command()
async def ac(ctx):
    await ctx.send("Alive check: I'm running!")


# =========================
# Run
# =========================
bot.run(TOKEN)
