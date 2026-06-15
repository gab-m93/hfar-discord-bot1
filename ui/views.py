import discord
import config
from ui.embeds import (
    build_task_embed,
    parse_task_embed,
    is_completed,
    STATUS_OPEN,
    STATUS_COMPLETED,
)


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
        channel = interaction.client.get_channel(config.TASK_DASHBOARD_CHANNEL_ID)
        if channel is None:
            await interaction.response.send_message(
                "Task dashboard channel not found. Ask an admin to run `/task setup`.",
                ephemeral=True,
            )
            return

        embed = build_task_embed(
            title=self.title,
            description=self.description,
            creator=self.creator.mention,
            assignee=self.assignee.mention if self.assignee else "Unassigned",
            deadline=self.deadline,
            status=STATUS_OPEN,
            source_url=self.source_url or None,
        )
        await channel.send(embed=embed, view=TaskDashboardView())
        self.stop()
        await interaction.response.edit_message(
            content="✅ Task created in the dashboard!", view=None
        )


class TaskDashboardView(discord.ui.View):
    """Persistent view attached to every task embed in the dashboard channel."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="✅ Complete",
        style=discord.ButtonStyle.success,
        custom_id="task_complete",
    )
    async def complete_callback(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        embed = interaction.message.embeds[0]
        if is_completed(embed):
            await interaction.response.send_message(
                "This task is already completed.", ephemeral=True
            )
            return

        data = parse_task_embed(embed)
        source_url = _extract_source_url(embed)
        new_embed = build_task_embed(
            title=data["title"],
            description=data["description"],
            creator=data["created_by"],
            assignee=data["assigned_to"],
            deadline=data["deadline"],
            status=STATUS_COMPLETED,
            source_url=source_url,
        )
        # Disable the Complete button; keep Edit/Assign/Delete
        new_view = TaskDashboardView()
        for child in new_view.children:
            if getattr(child, "custom_id", None) == "task_complete":
                child.disabled = True
        await interaction.message.edit(embed=new_embed, view=new_view)
        await interaction.response.send_message("Task marked as completed.", ephemeral=True)

    @discord.ui.button(
        label="✏️ Edit",
        style=discord.ButtonStyle.primary,
        custom_id="task_edit",
    )
    async def edit_callback(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        from ui.modals import TaskEditModal

        if not interaction.message.embeds:
            await interaction.response.send_message("Could not read task data.", ephemeral=True)
            return
        await interaction.response.send_modal(TaskEditModal(interaction.message))

    @discord.ui.button(
        label="👤 Assign",
        style=discord.ButtonStyle.secondary,
        custom_id="task_assign",
    )
    async def assign_callback(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_message(
            "Select the new assignee:",
            view=TaskAssignView(interaction.message),
            ephemeral=True,
        )

    @discord.ui.button(
        label="🗑️ Delete",
        style=discord.ButtonStyle.danger,
        custom_id="task_delete",
    )
    async def delete_callback(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_message(
            "Are you sure you want to delete this task?",
            view=DeleteConfirmView(interaction.message),
            ephemeral=True,
        )


class TaskAssignView(discord.ui.View):
    """Ephemeral view for changing the assignee of an existing task."""

    def __init__(self, task_message: discord.Message) -> None:
        super().__init__(timeout=120)
        self.task_message = task_message

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        placeholder="Choose new assignee",
        min_values=0,
        max_values=1,
    )
    async def select_assignee(
        self, interaction: discord.Interaction, select: discord.ui.UserSelect
    ) -> None:
        embed = self.task_message.embeds[0]
        data = parse_task_embed(embed)
        source_url = _extract_source_url(embed)
        assignee = select.values[0] if select.values else None

        new_embed = build_task_embed(
            title=data["title"],
            description=data["description"],
            creator=data["created_by"],
            assignee=assignee.mention if assignee else "Unassigned",
            deadline=data["deadline"],
            status=data["status"],
            source_url=source_url,
        )
        await self.task_message.edit(embed=new_embed)
        name = assignee.display_name if assignee else "nobody"
        self.stop()
        await interaction.response.edit_message(
            content=f"Assignee updated to **{name}**.", view=None
        )


class DeleteConfirmView(discord.ui.View):
    """Ephemeral confirm/cancel view for task deletion."""

    def __init__(self, task_message: discord.Message) -> None:
        super().__init__(timeout=60)
        self.task_message = task_message

    @discord.ui.button(label="Yes, delete", style=discord.ButtonStyle.danger)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.task_message.delete()
        self.stop()
        await interaction.response.edit_message(content="Task deleted.", view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.stop()
        await interaction.response.edit_message(content="Cancelled.", view=None)


def _extract_source_url(embed: discord.Embed) -> str | None:
    for field in embed.fields:
        if field.name == "Source":
            import re
            m = re.search(r'\((.+?)\)', field.value)
            return m.group(1) if m else None
    return None
