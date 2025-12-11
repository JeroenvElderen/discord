import discord
import config
import sys

from discord.ext import commands
from database import setup_database, get_connection
from dotenv import load_dotenv
from validators import startup_validation_check
import os

# Load environment variables from .env file
load_dotenv()

# Validate configuration before proceeding
if not startup_validation_check(config):
    print("❌ Bot startup aborted due to configuration errors.")
    sys.exit(1)

TOKEN = os.getenv("DISCORD_TOKEN")

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


# Start the bot with proper error handling
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("\n" + "="*60)
        print("❌ LOGIN FAILED")
        print("="*60)
        print("The provided Discord token is invalid.")
        print("\nPlease verify that:")
        print("  1. Your DISCORD_TOKEN in .env is correct")
        print("  2. The token hasn't been regenerated in Discord Developer Portal")
        print("  3. The bot application still exists")
        print("\nGet a new token from:")
        print("  https://discord.com/developers/applications")
        print("="*60 + "\n")
        sys.exit(1)
    except discord.PrivilegedIntentsRequired:
        print("\n" + "="*60)
        print("❌ PRIVILEGED INTENTS REQUIRED")
        print("="*60)
        print("Your bot requires privileged intents that aren't enabled.")
        print("\nTo fix this:")
        print("  1. Go to https://discord.com/developers/applications")
        print("  2. Select your bot application")
        print("  3. Go to the 'Bot' section")
        print("  4. Enable 'SERVER MEMBERS INTENT' and 'MESSAGE CONTENT INTENT'")
        print("  5. Save changes and restart the bot")
        print("="*60 + "\n")
        sys.exit(1)
    except Exception as e:
        print("\n" + "="*60)
        print("❌ UNEXPECTED ERROR")
        print("="*60)
        print(f"An unexpected error occurred: {type(e).__name__}")
        print(f"Details: {str(e)}")
        print("\nPlease check your configuration and try again.")
        print("="*60 + "\n")
        sys.exit(1)

