import discord
import config
from ui.embeds import (
    build_compact_task_embed,
    build_overview_embed,
    parse_task_embed,
    is_completed,
    is_task_embed,
    OVERVIEW_TITLE_PREFIX,
    STATUS_OPEN,
    STATUS_COMPLETED,
)


async def rebuild_overview(channel: discord.TextChannel) -> None:
    """Scan the dashboard channel and update the overview message."""
    # Find the overview: check pins first, then fall back to oldest message in channel
    overview_msg: discord.Message | None = None
    try:
        pins = await channel.pins()
        overview_msg = next(
            (
                p for p in pins
                if p.author == channel.guild.me
                and p.embeds
                and (p.embeds[0].title or "").startswith(OVERVIEW_TITLE_PREFIX)
            ),
            None,
        )
    except discord.HTTPException:
        pass

    if overview_msg is None:
        async for msg in channel.history(limit=50, oldest_first=True):
            if (
                msg.author == channel.guild.me
                and msg.embeds
                and (msg.embeds[0].title or "").startswith(OVERVIEW_TITLE_PREFIX)
            ):
                overview_msg = msg
                break

    if overview_msg is None:
        return

    # Collect open tasks from channel history (oldest first)
    open_tasks: list[dict] = []
    messages: list[discord.Message] = []
    async for msg in channel.history(limit=200):
        if msg.author == channel.guild.me and msg.embeds and is_task_embed(msg.embeds[0]):
            messages.append(msg)
    messages.reverse()  # oldest first
    for msg in messages:
        data = parse_task_embed(msg.embeds[0])
        if data["status"] == STATUS_OPEN:
            open_tasks.append({"data": data, "url": msg.jump_url})

    await overview_msg.edit(embed=build_overview_embed(open_tasks))


class TaskCreationView(discord.ui.View):
    """Ephemeral view shown after TaskCreateModal; lets the user assign someone then post."""

    def __init__(
        self,
        title: str,
        description: str,
        deadline: str,
        creator: discord.Member | discord.User,
        source_url: str,
    ) -> None:
        super().__init__(timeout=300)
        self.title = title
        self.description = description
        self.deadline = deadline
        self.creator = creator
        self.source_url = source_url
        self.assignee: discord.Member | discord.User | None = None

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        placeholder="Assign to someone (optional)",
        min_values=0,
        max_values=1,
    )
    async def select_assignee(
        self, interaction: discord.Interaction, select: discord.ui.UserSelect
    ) -> None:
        self.assignee = select.values[0] if select.values else None
        name = self.assignee.display_name if self.assignee else "nobody"
        await interaction.response.send_message(
            f"Assignee set to **{name}**. Click **Create Task** when ready.",
            ephemeral=True,
        )

    @discord.ui.button(label="✅ Create Task", style=discord.ButtonStyle.success)
    async def create_task(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        channel = interaction.client.get_channel(config.TASK_DASHBOARD_CHANNEL_ID)
        if channel is None:
            await interaction.edit_original_response(
                content="Task dashboard channel not found. Check TASK_DASHBOARD_CHANNEL_ID.",
            )
            return

        embed = build_compact_task_embed(
            title=self.title,
            description=self.description,
            creator=self.creator.mention,
            assignee=self.assignee.mention if self.assignee else "Unassigned",
            deadline=self.deadline,
            status=STATUS_OPEN,
            source_url=self.source_url or None,
        )
        try:
            await channel.send(embed=embed, view=TaskDashboardView())
        except discord.HTTPException as e:
            await interaction.edit_original_response(content=f"Failed to post task: {e}")
            return

        await rebuild_overview(channel)
        self.stop()
        await interaction.edit_original_response(
            content="✅ Task created in the dashboard!", view=None
        )


class TaskDashboardView(discord.ui.View):
    """Persistent view attached to every compact task embed."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="⚙️ Manage",
        style=discord.ButtonStyle.secondary,
        custom_id="task_manage",
    )
    async def manage_callback(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not interaction.message.embeds:
            await interaction.response.send_message("Could not read task data.", ephemeral=True)
            return
        data = parse_task_embed(interaction.message.embeds[0])
        summary = discord.Embed(
            title=data["title"],
            description=f"**Status:** {data['status']}  |  **Assigned to:** {data['assigned_to']}  |  **Deadline:** {data['deadline']}",
            color=interaction.message.embeds[0].color,
        )
        await interaction.response.send_message(
            embed=summary,
            view=TaskManageView(interaction.message),
            ephemeral=True,
        )


class TaskManageView(discord.ui.View):
    """Ephemeral panel for all task actions: complete, edit, assign, delete."""

    def __init__(self, task_message: discord.Message) -> None:
        super().__init__(timeout=60)
        self.task_message = task_message

    async def _dashboard_channel(self, client: discord.Client) -> discord.TextChannel | None:
        return client.get_channel(config.TASK_DASHBOARD_CHANNEL_ID)

    @discord.ui.button(label="✅ Complete", style=discord.ButtonStyle.success, row=0)
    async def complete(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        embed = self.task_message.embeds[0]
        if is_completed(embed):
            await interaction.response.send_message("Already completed.", ephemeral=True)
            return

        data = parse_task_embed(embed)
        new_embed = build_compact_task_embed(
            title=data["title"],
            description=data["description"],
            creator=data["created_by"],
            assignee=data["assigned_to"],
            deadline=data["deadline"],
            status=STATUS_COMPLETED,
            source_url=data["source_url"] or None,
        )
        await self.task_message.edit(embed=new_embed, view=TaskDashboardView())
        channel = await self._dashboard_channel(interaction.client)
        if channel:
            await rebuild_overview(channel)
        self.stop()
        await interaction.response.edit_message(content="✅ Task marked as completed.", embed=None, view=None)

    @discord.ui.button(label="✏️ Edit", style=discord.ButtonStyle.primary, row=0)
    async def edit(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        from ui.modals import TaskEditModal
        await interaction.response.send_modal(TaskEditModal(self.task_message))

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=0)
    async def delete(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.edit_message(
            content="Are you sure you want to delete this task?",
            embed=None,
            view=DeleteConfirmView(self.task_message),
        )

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        placeholder="Change assignee…",
        min_values=0,
        max_values=1,
        row=1,
    )
    async def assign(
        self, interaction: discord.Interaction, select: discord.ui.UserSelect
    ) -> None:
        embed = self.task_message.embeds[0]
        data = parse_task_embed(embed)
        assignee = select.values[0] if select.values else None

        new_embed = build_compact_task_embed(
            title=data["title"],
            description=data["description"],
            creator=data["created_by"],
            assignee=assignee.mention if assignee else "Unassigned",
            deadline=data["deadline"],
            status=data["status"],
            source_url=data["source_url"] or None,
        )
        await self.task_message.edit(embed=new_embed)
        channel = await self._dashboard_channel(interaction.client)
        if channel:
            await rebuild_overview(channel)
        name = assignee.display_name if assignee else "nobody"
        await interaction.response.send_message(
            f"Assignee updated to **{name}**.", ephemeral=True
        )


class DeleteConfirmView(discord.ui.View):
    """Replaces the manage panel when delete is clicked; asks for confirmation."""

    def __init__(self, task_message: discord.Message) -> None:
        super().__init__(timeout=30)
        self.task_message = task_message

    @discord.ui.button(label="Yes, delete", style=discord.ButtonStyle.danger)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        channel = interaction.client.get_channel(config.TASK_DASHBOARD_CHANNEL_ID)
        await self.task_message.delete()
        if channel:
            await rebuild_overview(channel)
        self.stop()
        await interaction.response.edit_message(content="Task deleted.", view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.stop()
        await interaction.response.edit_message(content="Cancelled.", view=None)
