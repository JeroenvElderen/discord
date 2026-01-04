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

# -------------------------
# Helpers
# -------------------------

def parse_ticket_topic(topic: str | None) -> tuple[int | None, int | None]:
    """
    Expected topic: "member_id:role_id"
    """
    if not topic:
        return None, None
    if ":" not in topic:
        # Backward compatibility if you had only member_id in topic
        try:
            return int(topic), None
        except ValueError:
            return None, None
    a, b = topic.split(":", 1)
    try:
        return int(a), int(b)
    except ValueError:
        return None, None


# =========================
# Persistent Approval Handler View (works after restart)
# =========================
class ApprovalHandlerView(ui.View):
    """
    This view is registered ON STARTUP (timeout=None) and can handle
    approve/reject for ANY ticket, because member_id and role_id are
    encoded into the custom_id.
    """

    def __init__(self):
        super().__init__(timeout=None)

    async def _finalize_and_delete(self, interaction: discord.Interaction, result_text: str):
        # Disable buttons on the message that was clicked
        try:
            view = self
            # Disable all items in this handler view instance for this edit
            # (Discord will render them disabled for that message)
            for item in view.children:
                item.disabled = True

            if interaction.response.is_done():
                await interaction.message.edit(view=view)
            else:
                await interaction.response.edit_message(view=view)
        except Exception:
            pass

        # Notify staff user
        try:
            await interaction.followup.send(result_text, ephemeral=True)
            await interaction.followup.send("🧹 This channel will be deleted in **60 seconds**.", ephemeral=True)
        except Exception:
            pass

        await asyncio.sleep(60)

        try:
            await interaction.channel.delete(reason="Verification completed")
        except (discord.NotFound, discord.Forbidden):
            pass

    async def _handle_approve_reject(self, interaction: discord.Interaction, action: str, member_id: int, role_id: int):
        await interaction.response.defer(ephemeral=True)

        # Permission check
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.followup.send("❌ You do not have permission to do that.", ephemeral=True)
            return

        guild = interaction.guild
        if not guild:
            await interaction.followup.send("❌ Guild not found.", ephemeral=True)
            return

        member = guild.get_member(member_id)
        if not member:
            await interaction.followup.send("❌ Member not found.", ephemeral=True)
            return

        role = guild.get_role(role_id)
        if not role:
            await interaction.followup.send("❌ Role not found.", ephemeral=True)
            return

        if action == "approve":
            opposite_role = (
                guild.get_role(ROLE_VERIFIED_NUDIST)
                if role_id == ROLE_VERIFIED_NATURIST
                else guild.get_role(ROLE_VERIFIED_NATURIST)
            )

            try:
                if opposite_role and opposite_role in member.roles:
                    await member.remove_roles(opposite_role, reason="Switching verified identity")

                if role not in member.roles:
                    await member.add_roles(role, reason="Identity verification approved")
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ I cannot edit roles. Check my role position and permissions.",
                    ephemeral=True
                )
                return

            await interaction.channel.send(f"✅ {member.mention} has been **approved** as **{role.name}**.")
            await self._finalize_and_delete(interaction, "Approved and ticket completed.")
            return

        # action == "reject"
        await interaction.channel.send(
            "❌ Verification **rejected**.\n"
            "You may contact staff if you believe this was a mistake."
        )
        await self._finalize_and_delete(interaction, "Rejected and ticket completed.")

    # IMPORTANT: custom_id includes the IDs so it works after restart.
    @ui.button(label="✅ Approve", style=discord.ButtonStyle.success, custom_id="identity_approval:approve")
    async def approve_button(self, interaction: discord.Interaction, button: ui.Button):
        # Parse IDs from the message channel topic (fallback) OR from custom_id if present.
        # We will store member_id:role_id in channel.topic, so it always works.
        member_id, role_id = parse_ticket_topic(getattr(interaction.channel, "topic", None))
        if not member_id or not role_id:
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send(
                "❌ Ticket metadata missing. (Expected channel topic like `member_id:role_id`).",
                ephemeral=True
            )
            return
        await self._handle_approve_reject(interaction, "approve", member_id, role_id)

    @ui.button(label="❌ Reject", style=discord.ButtonStyle.danger, custom_id="identity_approval:reject")
    async def reject_button(self, interaction: discord.Interaction, button: ui.Button):
        member_id, role_id = parse_ticket_topic(getattr(interaction.channel, "topic", None))
        if not member_id or not role_id:
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send(
                "❌ Ticket metadata missing. (Expected channel topic like `member_id:role_id`).",
                ephemeral=True
            )
            return
        await self._handle_approve_reject(interaction, "reject", member_id, role_id)


# =========================
# Identity Questions Modal
# =========================
class IdentityQuestionsModal(ui.Modal):
    def __init__(self, parent_view: "IdentityPathView", identity: str, role_id: int):
        super().__init__(title=f"{identity.capitalize()} Verification Questions")
        self.parent_view = parent_view
        self.identity = identity
        self.role_id = role_id

        self.q_experience = ui.TextInput(
            label="How long have you identified this way?",
            style=discord.TextStyle.short,
            required=True,
            max_length=100,
            placeholder="e.g., 2 years / new / since 2020"
        )
        self.q_reason = ui.TextInput(
            label="Why are you requesting this identity role?",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=800,
            placeholder="Briefly explain your reason."
        )

        if identity == "nudist":
            self.q_specific = ui.TextInput(
                label="What does nudism mean to you?",
                style=discord.TextStyle.paragraph,
                required=True,
                max_length=800,
                placeholder="Your personal definition/approach."
            )
        else:
            self.q_specific = ui.TextInput(
                label="What does naturism mean to you?",
                style=discord.TextStyle.paragraph,
                required=True,
                max_length=800,
                placeholder="Your personal definition/approach."
            )

        self.add_item(self.q_experience)
        self.add_item(self.q_reason)
        self.add_item(self.q_specific)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        answers = {
            "experience": str(self.q_experience.value).strip(),
            "reason": str(self.q_reason.value).strip(),
            "specific": str(self.q_specific.value).strip(),
        }

        await self.parent_view._create_ticket(
            interaction=interaction,
            identity=self.identity,
            role_id=self.role_id,
            answers=answers,
        )

        await interaction.followup.send(
            "🛂 Verification started. A private ticket has been opened.",
            ephemeral=True
        )


# =========================
# Identity Selection View (persistent)
# =========================
class IdentityPathView(ui.View):
    def __init__(self, approval_view: ui.View):
        super().__init__(timeout=None)
        self.active_creations: set[int] = set()
        self.approval_view = approval_view  # persistent handler view

    async def _create_ticket(self, interaction: discord.Interaction, identity: str, role_id: int, answers: dict):
        guild = interaction.guild
        member = interaction.user

        if not guild:
            await interaction.followup.send("❌ This must be used in a server.", ephemeral=True)
            return

        if member.id in self.active_creations:
            await interaction.followup.send("ℹ️ You already have an active verification ticket.", ephemeral=True)
            return

        self.active_creations.add(member.id)

        try:
            category = guild.get_channel(CATEGORY_VERIFICATION)
            staff_role = guild.get_role(ROLE_STAFF)

            if not category or not staff_role:
                await interaction.followup.send("❌ Verification system misconfigured. Contact staff.", ephemeral=True)
                return

            for ch in category.channels:
                if ch.topic and ch.topic.startswith(str(member.id)):
                    await interaction.followup.send("ℹ️ You already have an active verification ticket.", ephemeral=True)
                    return

            # Store BOTH member_id and role_id so buttons can work after restart.
            topic_value = f"{member.id}:{role_id}"

            channel = await guild.create_text_channel(
                name=f"verify-{identity}-{member.name}".lower(),
                category=category,
                overwrites={
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    member: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                    staff_role: discord.PermissionOverwrite(view_channel=True, send_messages=True)
                },
                topic=topic_value,
                reason="Manual identity verification"
            )

            request_embed = discord.Embed(
                title="🛂 Identity Verification",
                description=(
                    f"**User:** {member.mention}\n"
                    f"**Requested identity:** {identity.capitalize()}\n\n"
                    "Staff must manually approve or reject this request."
                ),
                color=discord.Color.orange()
            )

            answers_embed = discord.Embed(
                title="🧾 Applicant Answers",
                description=(
                    f"**How long have you identified this way?**\n{answers.get('experience','')}\n\n"
                    f"**Why are you requesting this identity role?**\n{answers.get('reason','')}\n\n"
                    f"**What does {identity.capitalize()} mean to you?**\n{answers.get('specific','')}"
                ),
                color=discord.Color.blurple()
            )

            await channel.send(embed=request_embed)
            # Use the persistent approval handler view
            await channel.send(embed=answers_embed, view=self.approval_view)

        finally:
            self.active_creations.discard(member.id)

    @ui.button(label="🌿 Verified Naturist", style=discord.ButtonStyle.success, custom_id="identity_path:naturist")
    async def naturist(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(
            IdentityQuestionsModal(self, "naturist", ROLE_VERIFIED_NATURIST)
        )

    @ui.button(label="☀️ Verified Nudist", style=discord.ButtonStyle.primary, custom_id="identity_path:nudist")
    async def nudist(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(
            IdentityQuestionsModal(self, "nudist", ROLE_VERIFIED_NUDIST)
        )


# =========================
# Cog
# =========================
class IdentityPath(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Persistent approval handler (survives restarts)
        self.approval_handler_view = ApprovalHandlerView()

        # Persistent identity path view (survives restarts)
        self.identity_view = IdentityPathView(self.approval_handler_view)

        self.ensure_identity_embed.start()

    async def cog_load(self):
        # Register both persistent views so buttons work after restart
        self.bot.add_view(self.identity_view)
        self.bot.add_view(self.approval_handler_view)

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

    async def _post_identity_embed(self, channel: discord.abc.Messageable):
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

    # -------------------------
    # Slash-command fallback (works even if buttons are old)
    # -------------------------

    @discord.app_commands.command(name="approve_ticket", description="Approve the verification ticket in this channel (staff only).")
    async def approve_ticket(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.manage_roles:
            await interaction.followup.send("❌ You do not have permission to do that.", ephemeral=True)
            return

        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.followup.send("❌ This must be used in a ticket channel.", ephemeral=True)
            return

        member_id, role_id = parse_ticket_topic(interaction.channel.topic)
        if not member_id or not role_id:
            await interaction.followup.send("❌ Ticket metadata missing from channel topic.", ephemeral=True)
            return

        await self.approval_handler_view._handle_approve_reject(interaction, "approve", member_id, role_id)

    @discord.app_commands.command(name="reject_ticket", description="Reject the verification ticket in this channel (staff only).")
    async def reject_ticket(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.manage_roles:
            await interaction.followup.send("❌ You do not have permission to do that.", ephemeral=True)
            return

        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.followup.send("❌ This must be used in a ticket channel.", ephemeral=True)
            return

        member_id, role_id = parse_ticket_topic(interaction.channel.topic)
        if not member_id or not role_id:
            await interaction.followup.send("❌ Ticket metadata missing from channel topic.", ephemeral=True)
            return

        await self.approval_handler_view._handle_approve_reject(interaction, "reject", member_id, role_id)


async def setup(bot: commands.Bot):
    await bot.add_cog(IdentityPath(bot))
