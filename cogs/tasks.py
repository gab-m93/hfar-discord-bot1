import discord
from discord import app_commands
from discord.ext import commands

import config
from ui.embeds import parse_task_embed, STATUS_OPEN, STATUS_COMPLETED
from ui.modals import TaskCreateModal
from ui.views import TaskDashboardView


class Tasks(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Register the context menu command on the tree
        self.ctx_menu = app_commands.ContextMenu(
            name="Create Task",
            callback=self.create_task_from_message,
        )
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    async def create_task_from_message(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        """Right-click a message → Apps → Create Task."""
        if interaction.channel_id == config.TASK_DASHBOARD_CHANNEL_ID:
            await interaction.response.send_message(
                "Tasks cannot be created from inside the task dashboard.", ephemeral=True
            )
            return

        source_content = message.content or (
            message.embeds[0].title if message.embeds else ""
        )
        modal = TaskCreateModal(
            source_content=source_content,
            source_url=message.jump_url,
        )
        await interaction.response.send_modal(modal)

    # ── Slash commands ──────────────────────────────────────────────────────

    task_group = app_commands.Group(name="task", description="Task management commands")

    @task_group.command(name="list", description="List all open tasks in the dashboard")
    async def task_list(self, interaction: discord.Interaction) -> None:
        channel = self.bot.get_channel(config.TASK_DASHBOARD_CHANNEL_ID)
        if channel is None:
            await interaction.response.send_message(
                "Task dashboard channel not configured.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        open_tasks: list[str] = []

        async for msg in channel.history(limit=200):
            if not msg.embeds or msg.author != self.bot.user:
                continue
            data = parse_task_embed(msg.embeds[0])
            if data["status"] == STATUS_OPEN:
                deadline = data["deadline"]
                dl_str = f" — due {deadline}" if deadline != "No deadline" else ""
                assignee = data["assigned_to"]
                assign_str = f" → {assignee}" if assignee != "Unassigned" else ""
                open_tasks.append(
                    f"• [{data['title']}]({msg.jump_url}){assign_str}{dl_str}"
                )

        if not open_tasks:
            await interaction.followup.send("No open tasks found.", ephemeral=True)
            return

        # Discord message limit: split into chunks of 10
        chunks = [open_tasks[i:i+10] for i in range(0, len(open_tasks), 10)]
        for i, chunk in enumerate(chunks):
            header = f"**Open tasks ({len(open_tasks)} total):**\n" if i == 0 else ""
            await interaction.followup.send(header + "\n".join(chunk), ephemeral=True)

    @task_group.command(
        name="setup",
        description="[Admin] Post a header embed in the task dashboard channel",
    )
    @app_commands.default_permissions(manage_channels=True)
    async def task_setup(self, interaction: discord.Interaction) -> None:
        channel = self.bot.get_channel(config.TASK_DASHBOARD_CHANNEL_ID)
        if channel is None:
            await interaction.response.send_message(
                "Dashboard channel not found. Check TASK_DASHBOARD_CHANNEL_ID.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="📋 Task Dashboard",
            description=(
                "All tasks are listed here.\n\n"
                "**To create a task:** right-click any message in another channel → "
                "**Apps → Create Task**.\n"
                "Use the buttons on each task to complete, edit, reassign, or delete it."
            ),
            color=0x5865F2,
        )
        await channel.send(embed=embed)
        await interaction.response.send_message(
            "Dashboard header posted.", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    cog = Tasks(bot)
    await bot.add_cog(cog)
    bot.tree.add_command(cog.task_group)
