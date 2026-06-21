import discord
from discord import app_commands
from discord.ext import commands

import config
from ui.embeds import (
    build_overview_embed,
    parse_task_data_embed,
    OVERVIEW_TITLE_PREFIX,
    STATUS_OPEN,
)
from ui.modals import TaskCreateModal
from ui.views import OverviewView, find_overview, get_task_thread


class Tasks(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
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
        await interaction.response.send_modal(
            TaskCreateModal(source_content=source_content, source_url=message.jump_url)
        )

    task_group = app_commands.Group(name="task", description="Task management commands")

    @task_group.command(name="list", description="List all open tasks")
    async def task_list(self, interaction: discord.Interaction) -> None:
        channel = self.bot.get_channel(config.TASK_DASHBOARD_CHANNEL_ID)
        if channel is None:
            await interaction.response.send_message(
                "Task dashboard channel not configured.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        overview_msg = await find_overview(channel)
        if overview_msg is None:
            await interaction.followup.send("No overview found. Run `/task setup`.", ephemeral=True)
            return

        thread = await get_task_thread(overview_msg)
        if thread is None:
            await interaction.followup.send("Task data thread not found.", ephemeral=True)
            return

        messages = []
        async for msg in thread.history(limit=100):
            if msg.embeds and msg.author == self.bot.user:
                messages.append(msg)
        messages.reverse()

        open_tasks = []
        for msg in messages:
            data = parse_task_data_embed(msg.embeds[0])
            if data["status"] == STATUS_OPEN:
                dl_str = f" — due {data['deadline']}" if data["deadline"] != "No deadline" else ""
                a_str = f" → {data['assignee']}" if data["assignee"] != "Unassigned" else ""
                open_tasks.append(f"• [{data['title']}]({data['source_url']}){a_str}{dl_str}")

        if not open_tasks:
            await interaction.followup.send("No open tasks.", ephemeral=True)
            return

        chunks = [open_tasks[i:i + 10] for i in range(0, len(open_tasks), 10)]
        for i, chunk in enumerate(chunks):
            header = f"**Open tasks ({len(open_tasks)} total):**\n" if i == 0 else ""
            await interaction.followup.send(header + "\n".join(chunk), ephemeral=True)

    @task_group.command(
        name="setup",
        description="[Admin] Create or reset the overview message and task data thread",
    )
    @app_commands.default_permissions(manage_channels=True)
    async def task_setup(self, interaction: discord.Interaction) -> None:
        channel = self.bot.get_channel(config.TASK_DASHBOARD_CHANNEL_ID)
        if channel is None:
            await interaction.response.send_message(
                "Dashboard channel not found. Check TASK_DASHBOARD_CHANNEL_ID.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Remove any existing overview (pinned or oldest)
        try:
            pins = await channel.pins()
            for pin in pins:
                if (
                    pin.author == self.bot.user
                    and pin.embeds
                    and (pin.embeds[0].title or "").startswith(OVERVIEW_TITLE_PREFIX)
                ):
                    await pin.unpin()
                    await pin.delete()
        except discord.HTTPException:
            pass

        async for msg in channel.history(limit=50, oldest_first=True):
            if (
                msg.author == self.bot.user
                and msg.embeds
                and (msg.embeds[0].title or "").startswith(OVERVIEW_TITLE_PREFIX)
            ):
                try:
                    await msg.delete()
                except discord.HTTPException:
                    pass
                break

        # Post the overview message
        overview_msg = await channel.send(
            embed=build_overview_embed([]), view=OverviewView(None)
        )

        # Create the task data thread
        try:
            thread = await overview_msg.create_thread(
                name="Task Data",
                auto_archive_duration=60,
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "Overview created but could not create the task data thread.\n"
                "Grant the bot **Create Public Threads** and **Send Messages in Threads** "
                "permissions in the channel and run `/task setup` again.",
                ephemeral=True,
            )
            return
        except discord.HTTPException as e:
            await interaction.followup.send(f"Failed to create thread: {e}", ephemeral=True)
            return

        # Update footer with thread ID
        await overview_msg.edit(embed=build_overview_embed([], thread_id=thread.id))

        # Try to pin
        try:
            await overview_msg.pin()
            pin_note = ""
        except discord.Forbidden:
            pin_note = (
                "\n⚠️ Could not pin — grant **Manage Messages** permission or pin manually."
            )

        await interaction.followup.send(
            f"Overview message and task data thread created.{pin_note}", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tasks(bot))
