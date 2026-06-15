import discord
from ui.embeds import build_task_embed, parse_task_embed, STATUS_OPEN


class TaskCreateModal(discord.ui.Modal, title="Create Task"):
    task_title = discord.ui.TextInput(
        label="Task name",
        max_length=200,
        placeholder="Short summary of what needs to be done",
    )
    description = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1000,
        placeholder="Optional details…",
    )
    deadline = discord.ui.TextInput(
        label="Deadline (optional, YYYY-MM-DD)",
        required=False,
        max_length=10,
        placeholder="e.g. 2026-07-01",
    )

    def __init__(self, source_content: str, source_url: str) -> None:
        super().__init__()
        self.source_url = source_url
        # Pre-fill title from the source message (first 200 chars)
        self.task_title.default = source_content[:200] if source_content else ""

    async def on_submit(self, interaction: discord.Interaction) -> None:
        from ui.views import TaskCreationView

        deadline_val = self.deadline.value.strip() or "No deadline"
        view = TaskCreationView(
            title=self.task_title.value.strip(),
            description=self.description.value.strip(),
            deadline=deadline_val,
            creator=interaction.user,
            source_url=self.source_url,
        )
        await interaction.response.send_message(
            "Optionally assign the task, then click **Create Task**.",
            view=view,
            ephemeral=True,
        )


class TaskEditModal(discord.ui.Modal, title="Edit Task"):
    task_title = discord.ui.TextInput(label="Task name", max_length=200)
    description = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1000,
    )
    deadline = discord.ui.TextInput(
        label="Deadline (YYYY-MM-DD, or leave blank to clear)",
        required=False,
        max_length=10,
    )

    def __init__(self, task_message: discord.Message) -> None:
        super().__init__()
        self.task_message = task_message
        data = parse_task_embed(task_message.embeds[0])
        self.task_title.default = data["title"]
        self.description.default = data["description"]
        dl = data["deadline"]
        self.deadline.default = dl if dl != "No deadline" else ""

    async def on_submit(self, interaction: discord.Interaction) -> None:
        data = parse_task_embed(self.task_message.embeds[0])
        deadline_val = self.deadline.value.strip() or "No deadline"

        # Preserve source URL from old embed fields
        source_url: str | None = None
        for field in self.task_message.embeds[0].fields:
            if field.name == "Source":
                import re
                m = re.search(r'\((.+?)\)', field.value)
                source_url = m.group(1) if m else None
                break

        new_embed = build_task_embed(
            title=self.task_title.value.strip(),
            description=self.description.value.strip(),
            creator=data["created_by"],
            assignee=data["assigned_to"],
            deadline=deadline_val,
            status=data["status"],
            source_url=source_url,
        )
        await self.task_message.edit(embed=new_embed)
        await interaction.response.send_message("Task updated.", ephemeral=True)
