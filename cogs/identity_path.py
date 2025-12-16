import discord
import asyncio
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

    async def _finalize_and_delete(self, interaction: discord.Interaction, result_text: str):
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)

        await interaction.followup.send(result_text, ephemeral=True)
        await interaction.followup.send(
            "🧹 This channel will be deleted in **60 seconds**.",
            ephemeral=True
        )
        await asyncio.sleep(60)

        try:
            await interaction.channel.delete(reason="Verification completed")
        except discord.NotFound:
            pass
        except discord.Forbidden:
            pass


    @ui.button(
        label="✅ Approve",
        style=discord.ButtonStyle.success,
        custom_id="identity_approval:approve"
    )
    async def approve(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.manage_roles:
            await interaction.followup.send(
                "❌ You do not have permission to approve verifications.",
                ephemeral=True
            )
            return

        guild = interaction.guild
        member = guild.get_member(self.member_id)
        if not member:
            await interaction.followup.send("❌ Member not found.", ephemeral=True)
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

        await self._finalize_and_delete(interaction, "Approved and ticket completed.")

    @ui.button(
        label="❌ Reject",
        style=discord.ButtonStyle.danger,
        custom_id="identity_approval:reject"
    )
    async def reject(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.manage_roles:
            await interaction.followup.send(
                "❌ You do not have permission to reject verifications.",
                ephemeral=True
            )
            return

        await interaction.channel.send(
            "❌ Verification **rejected**.\n"
            "You may contact staff if you believe this was a mistake."
        )

        await self._finalize_and_delete(interaction, "Rejected and ticket completed.")


# =========================
# Identity Selection View
# =========================
class IdentityPathView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.active_creations: set[int] = set()  # 🔒 atomic user lock

    async def _create_ticket(self, interaction, identity: str, role_id: int):
        guild = interaction.guild
        member = interaction.user

        # 🔒 HARD ATOMIC LOCK (prevents race conditions)
        if member.id in self.active_creations:
            await interaction.followup.send(
                "ℹ️ You already have an active verification ticket.",
                ephemeral=True
            )
            return

        self.active_creations.add(member.id)

        try:
            category = guild.get_channel(CATEGORY_VERIFICATION)
            staff_role = guild.get_role(ROLE_STAFF)

            if not category or not staff_role:
                await interaction.followup.send(
                    "❌ Verification system misconfigured. Contact staff.",
                    ephemeral=True
                )
                return

            # Secondary safety check (existing channels)
            for ch in category.channels:
                if ch.topic == str(member.id):
                    await interaction.followup.send(
                        "ℹ️ You already have an active verification ticket.",
                        ephemeral=True
                    )
                    return

            channel = await guild.create_text_channel(
                name=f"verify-{identity}-{member.name}".lower(),
                category=category,
                overwrites={
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    member: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                    staff_role: discord.PermissionOverwrite(view_channel=True, send_messages=True)
                },
                topic=str(member.id),
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

            await interaction.followup.send(
                "🛂 Verification started. A private ticket has been opened.",
                ephemeral=True
            )

        finally:
            # 🔓 RELEASE LOCK
            self.active_creations.discard(member.id)

    @ui.button(
        label="🌿 Verified Naturist",
        style=discord.ButtonStyle.success,
        custom_id="identity_path:naturist"
    )
    async def naturist(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self._create_ticket(interaction, "naturist", ROLE_VERIFIED_NATURIST)

    @ui.button(
        label="☀️ Verified Nudist",
        style=discord.ButtonStyle.primary,
        custom_id="identity_path:nudist"
    )
    async def nudist(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self._create_ticket(interaction, "nudist", ROLE_VERIFIED_NUDIST)


# =========================
# Cog (SINGLE persistent view)
# =========================
class IdentityPath(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.identity_view = IdentityPathView()  # SINGLE instance
        self.ensure_identity_embed.start()

    async def cog_load(self):
        self.bot.add_view(self.identity_view)

    async def cog_unload(self):
        self.ensure_identity_embed.cancel()

    async def _get_identity_channel(self):
        channel = self.bot.get_channel(CHANNEL_IDENTITY_PATH)
        if channel:
            return channel
        try:
            return await self.bot.fetch_channel(CHANNEL_IDENTITY_PATH)
        except (discord.NotFound, discord.Forbidden):
            return None

    async def _post_identity_embed(self, channel):
        embed = discord.Embed(
            title="🧭 Choose Your Identity Path",
            description=(
                "Choose the identity path that best reflects how you relate "
                "to social nudity or naturism.\n\n"
                "• Only one identity may be approved\n"
                "• Manual staff verification required"
            ),
            color=discord.Color.green()
        )

        await channel.send(embed=embed, view=self.identity_view)
        print("✅ Identity Path embed posted.")

    @tasks.loop(minutes=2)
    async def ensure_identity_embed(self):
        await self.bot.wait_until_ready()
        channel = await self._get_identity_channel()
        if not channel:
            return

        async for msg in channel.history(limit=20):
            if msg.author == self.bot.user and msg.embeds:
                return

        await self._post_identity_embed(channel)

    @ensure_identity_embed.before_loop
    async def before_ensure(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(IdentityPath(bot))
