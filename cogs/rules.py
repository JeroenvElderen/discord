import discord
from discord.ext import commands
from config import ROLE_MEMBER, CHANNEL_RULES
from database import add_member, remove_member
from datetime import datetime

CHECKMARK = "✅"


class Rules(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rules_message_id = None

    async def initialize_rules(self):
        await self.bot.wait_until_ready()

        channel = self.bot.get_channel(CHANNEL_RULES)
        if channel is None:
            print("❌ ERROR: Rules channel not found. Check CHANNEL_RULES ID.")
            return

        print("🔍 Searching for existing rules message...")

        # Look for existing valid message
        async for msg in channel.history(limit=50):
            if msg.author.id == self.bot.user.id and msg.embeds:
                self.rules_message_id = msg.id
                print(f"📌 Found existing rules message: {self.rules_message_id}")
                return

        print("➕ No rules message found. Creating a new one...")

        embed = discord.Embed(
            title="🌿 Welcome to PlanetNaturists!",
            description=(
                "A warm, respectful space for genuine naturists and nudists. We celebrate comfort, "
                "body-positivity, and the freedom of simple nudity — always **non-sexual** and respectful. 🌞\n\n"
                "**Please read and agree to these before joining the community 👇**\n\n"

                "1️⃣ **Real Naturism Only**\n"
                "This is a naturist space — not for fetish or exhibitionist content. Keep all discussions and posts "
                "genuine, non-sexual, and body-positive.\n\n"

                "2️⃣ **Respect Consent & Privacy**\n"
                "Never share or repost anyone’s photos without clear permission. Everything shared here stays private — "
                "respect others’ comfort and boundaries.\n\n"

                "3️⃣ **Nudity ≠ Sexuality**\n"
                "Nudity is natural. Posts or photos must remain non-sexual, without poses or erotic tone.\n\n"

                "4️⃣ **Adults Only (18+)**\n"
                "No exceptions. Do not post or discuss nudity involving minors — ever.\n\n"

                "5️⃣ **Be Kind & Body-Positive**\n"
                "No shaming, judgment, or hate. Every body deserves respect and dignity. 🌿\n\n"

                "6️⃣ **Stay On-Topic**\n"
                "Keep chats related to naturism, social nudity, travel, or lifestyle. Off-topic or spam posts may be removed.\n\n"

                "7️⃣ **Tag Nudity as NSFW**\n"
                "Even when natural and non-sexual, always tag NSFW to keep things respectful.\n\n"

                "8️⃣ **No Creepy or Flirty Behavior**\n"
                "No unsolicited DMs, flirting, sexual comments, or hookup-seeking. This is not a dating space — keep it safe and friendly.\n\n"

                "9️⃣ **No Promotions**\n"
                "No self-promotion or advertising without moderator approval.\n\n"

                "🔟 **Think Before You Post**\n"
                "Be mindful of what you share — once online, it can spread. Share only what feels right to you. 🌺\n\n"

                "✅ **Click the checkmark reaction below to agree and become a Member.**\n\n"
                "🌿 *PlanetNaturists – Respect. Nature. Freedom.*"
            ),
            color=0x57F287
        )

        msg = await channel.send(embed=embed)
        await msg.add_reaction(CHECKMARK)

        self.rules_message_id = msg.id
        print(f"📌 New rules message posted and tracked: {self.rules_message_id}")

    # -----------------------------------
    # Reaction ADD → Give role + store DB
    # -----------------------------------
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.channel_id != CHANNEL_RULES:
            return
        if str(payload.emoji) != CHECKMARK:
            return
        if payload.user_id == self.bot.user.id:
            return
        if payload.message_id != self.rules_message_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        member = guild.get_member(payload.user_id)
        if member is None:
            print("⚠️ Member not found during reaction add.")
            return

        role = guild.get_role(ROLE_MEMBER)
        if role is None:
            print("❌ ERROR: ROLE_MEMBER ID is invalid.")
            return

        # Give role
        await member.add_roles(role)
        print(f"✅ Added Member role to: {member}")

        # Store in database
        now = datetime.utcnow().isoformat()
        add_member(member.id, str(member), now)
        print(f"🗄️ Stored in database: {member} at {now}")

    # ---------------------------------------
    # Reaction REMOVE → Remove role + DB entry
    # ---------------------------------------
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.channel_id != CHANNEL_RULES:
            return
        if str(payload.emoji) != CHECKMARK:
            return
        if payload.message_id != self.rules_message_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        member = guild.get_member(payload.user_id)
        if member is None:
            print("⚠️ Member not found during reaction removal.")
            return

        role = guild.get_role(ROLE_MEMBER)
        if role is None:
            print("❌ ERROR: ROLE_MEMBER ID is invalid.")
            return

        # Remove role
        await member.remove_roles(role)
        print(f"❌ Removed Member role from: {member}")

        # Remove from DB
        remove_member(member.id)
        print(f"🗄️ Removed from database: {member.id}")


async def setup(bot):
    cog = Rules(bot)
    await bot.add_cog(cog)
    bot.loop.create_task(cog.initialize_rules())
