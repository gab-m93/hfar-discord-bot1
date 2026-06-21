import discord
from ui.embeds import build_task_data_embed, parse_task_data_embed


class TaskCreateModal(discord.ui.Modal, title="Create Task"):
    task_title = discord.ui.TextInput(
        label="Task name",
        max_length=100,
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
        self.task_title.default = source_content[:100] if source_content else ""

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
    task_title = discord.ui.TextInput(label="Task name", max_length=100)
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

    def __init__(
        self,
        thread_msg: discord.Message,
        overview_msg: discord.Message,
        thread: discord.Thread,
    ) -> None:
        super().__init__()
        self.thread_msg = thread_msg
        self.overview_msg = overview_msg
        self.thread = thread
        data = parse_task_data_embed(thread_msg.embeds[0])
        self.task_title.default = data["title"]
        self.description.default = data["description"]
        dl = data["deadline"]
        self.deadline.default = dl if dl != "No deadline" else ""

    async def on_submit(self, interaction: discord.Interaction) -> None:
        from ui.views import rebuild_overview

        data = parse_task_data_embed(self.thread_msg.embeds[0])
        deadline_val = self.deadline.value.strip() or "No deadline"

        new_embed = build_task_data_embed(
            title=self.task_title.value.strip(),
            description=self.description.value.strip(),
            creator=data["creator"],
            assignee=data["assignee"],
            deadline=deadline_val,
            source_url=data["source_url"],
            status=data["status"],
        )
        await self.thread_msg.edit(embed=new_embed)
        await rebuild_overview(self.overview_msg, self.thread)
        await interaction.response.send_message("Task updated.", ephemeral=True)
