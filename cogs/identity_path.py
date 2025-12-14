import discord
from discord.ext import commands, tasks
from discord import ui

from config import (
    CHANNEL_IDENTITY_PATH,
    ROLE_VERIFIED_NATURIST,
    ROLE_VERIFIED_NUDIST,
    ROLE_STAFF,
    CATEGORY_VERIFICATION
)

# =========================
# Staff Approval View
# =========================
class ApprovalView(ui.View):
    def __init__(self, member_id: int, role_id: int):
        super().__init__(timeout=None)
        self.member_id = member_id
        self.role_id = role_id

    async def _lock_channel(self, channel: discord.TextChannel):
        await channel.edit(
            overwrites={
                channel.guild.default_role: discord.PermissionOverwrite(view_channel=False)
            }
        )

    @ui.button(
        label="✅ Approve",
        style=discord.ButtonStyle.success,
        custom_id="identity_approval:approve"
    )
    async def approve(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "❌ You do not have permission to approve verifications.",
                ephemeral=True
            )
            return

        guild = interaction.guild
        member = guild.get_member(self.member_id)

        if not member:
            await interaction.response.send_message(
                "❌ Member not found.",
                ephemeral=True
            )
            return

        role = guild.get_role(self.role_id)
        opposite_role = (
            guild.get_role(ROLE_VERIFIED_NUDIST)
            if self.role_id == ROLE_VERIFIED_NATURIST
            else guild.get_role(ROLE_VERIFIED_NATURIST)
        )

        if opposite_role and opposite_role in member.roles:
            await member.remove_roles(opposite_role)

        if role and role not in member.roles:
            await member.add_roles(role)

        await interaction.channel.send(
            f"✅ {member.mention} has been **approved** as **{role.name}**."
        )

        await self._lock_channel(interaction.channel)
        await interaction.response.send_message(
            "Approved and ticket locked.",
            ephemeral=True
        )

    @ui.button(
        label="❌ Reject",
        style=discord.ButtonStyle.danger,
        custom_id="identity_approval:reject"
    )
    async def reject(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "❌ You do not have permission to reject verifications.",
                ephemeral=True
            )
            return

        await interaction.channel.send(
            "❌ Verification **rejected**.\n"
            "You may contact staff if you believe this was a mistake."
        )

        await self._lock_channel(interaction.channel)
        await interaction.response.send_message(
            "Rejected and ticket locked.",
            ephemeral=True
        )


# =========================
# Identity Selection View
# =========================
class IdentityPathView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _create_ticket(self, interaction, identity: str, role_id: int):
        guild = interaction.guild
        member = interaction.user
        category = guild.get_channel(CATEGORY_VERIFICATION)
        staff_role = guild.get_role(ROLE_STAFF)

        if not category or not staff_role:
            await interaction.response.send_message(
                "❌ Verification system misconfigured. Contact staff.",
                ephemeral=True
            )
            return

        channel_name = f"verify-{identity}-{member.name}".lower()

        for ch in category.channels:
            if ch.name == channel_name:
                await interaction.response.send_message(
                    "ℹ️ You already have an open verification ticket.",
                    ephemeral=True
                )
                return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            staff_role: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            reason="Manual identity verification"
        )

        embed = discord.Embed(
            title="🛂 Identity Verification",
            description=(
                f"**User:** {member.mention}\n"
                f"**Requested identity:** {identity.capitalize()}\n\n"
                "Staff must manually approve or reject this request."
            ),
            color=discord.Color.orange()
        )

        await channel.send(embed=embed, view=ApprovalView(member.id, role_id))

        await interaction.response.send_message(
            "🛂 Verification started. A private ticket has been opened.",
            ephemeral=True
        )

    @ui.button(
        label="🌿 Verified Naturist",
        style=discord.ButtonStyle.success,
        custom_id="identity_path:naturist"
    )
    async def naturist(self, interaction: discord.Interaction, button: ui.Button):
        await self._create_ticket(interaction, "naturist", ROLE_VERIFIED_NATURIST)

    @ui.button(
        label="☀️ Verified Nudist",
        style=discord.ButtonStyle.primary,
        custom_id="identity_path:nudist"
    )
    async def nudist(self, interaction: discord.Interaction, button: ui.Button):
        await self._create_ticket(interaction, "nudist", ROLE_VERIFIED_NUDIST)


# =========================
# Cog (Self-Healing)
# =========================
class IdentityPath(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ensure_identity_embed.start()

    async def cog_load(self):
        # Register persistent view ONCE
        self.bot.add_view(IdentityPathView())

    async def cog_unload(self):
        self.ensure_identity_embed.cancel()

    async def _get_identity_channel(self) -> discord.TextChannel | None:
        channel = self.bot.get_channel(CHANNEL_IDENTITY_PATH)
        if channel:
            return channel

        try:
            return await self.bot.fetch_channel(CHANNEL_IDENTITY_PATH)
        except (discord.NotFound, discord.Forbidden):
            return None

    async def _post_identity_embed(self, channel: discord.TextChannel):
        embed = discord.Embed(
            title="🧭 Choose Your Identity Path",
            description=(
            "This community brings together people who value body freedom, "
            "respect, and authenticity.\n\n"
            "Please choose the identity path that best reflects **how you personally "
            "relate to social nudity or naturism**.\n\n"
            "• This choice represents **identity**, not status or hierarchy\n"
            "• Only **one** identity path may be approved\n"
            "• All requests require **manual staff verification**"
            ),
            color=discord.Color.green()
        )

        embed.add_field(
            name="🌿 Verified Naturist",
            value=(
            "For members who practice or support **naturism** as a lifestyle or philosophy.\n\n"
            "Naturism emphasizes:\n"
            "• Comfort with social nudity in appropriate settings\n"
            "• Body acceptance and non-sexualized nudity\n"
            "• Respect for others, nature, and community values"
            ),
            inline=False
        )

        embed.add_field(
            name="☀️ Verified Nudist",
            value=(
            "For members who identify with **nudism** as a personal or social expression.\n\n"
            "Nudism often focuses on:\n"
            "• Personal freedom and body autonomy\n"
            "• Being nude as a natural state of being\n"
            "• Comfort with nudity independent of environment or philosophy"
        ),
            inline=False
        )

        await channel.send(embed=embed, view=IdentityPathView())
        print("✅ Identity Path embed posted (self-healed).")


    @tasks.loop(minutes=2)
    async def ensure_identity_embed(self):
        await self.bot.wait_until_ready()

        channel = await self._get_identity_channel()
        if not channel:
            return

        async for msg in channel.history(limit=20):
            if msg.author == self.bot.user and msg.embeds:
                return  # Embed exists

        # Missing → heal
        await self._post_identity_embed(channel)

    @ensure_identity_embed.before_loop
    async def before_ensure(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(IdentityPath(bot))
