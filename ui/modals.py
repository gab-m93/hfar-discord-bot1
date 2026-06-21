import re
from datetime import date, timedelta

import discord

import config
from ui.embeds import build_task_data_embed, parse_task_data_embed


def _parse_deadline(text: str) -> str:
    """Return a YYYY-MM-DD string or 'No deadline'. Accepts natural language."""
    text = text.strip()
    if not text:
        return "No deadline"
    lower = text.lower()
    today = date.today()
    if lower == "today":
        return today.strftime("%Y-%m-%d")
    if lower == "tomorrow":
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    if lower in ("next week", "in a week", "in 1 week"):
        return (today + timedelta(weeks=1)).strftime("%Y-%m-%d")
    if lower in ("next month", "in a month", "in 1 month"):
        return (today + timedelta(days=30)).strftime("%Y-%m-%d")
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return text
    m = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$", text)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
    return text  # pass through as-is; stored and shown as typed


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
    assignee = discord.ui.TextInput(
        label="Assign to (optional)",
        required=False,
        max_length=50,
        placeholder="gabs / jo / niki / mex — or leave blank",
    )
    deadline = discord.ui.TextInput(
        label="Deadline (optional)",
        required=False,
        max_length=20,
        placeholder="today · tomorrow · next week · 2026-07-01 · 15.07.2026",
    )

    def __init__(self, source_content: str, source_url: str) -> None:
        super().__init__()
        self.source_url = source_url
        self.task_title.default = source_content[:100] if source_content else ""

    async def on_submit(self, interaction: discord.Interaction) -> None:
        from ui.views import find_overview, get_task_thread, rebuild_overview

        await interaction.response.defer(ephemeral=True)

        channel = interaction.client.get_channel(config.TASK_DASHBOARD_CHANNEL_ID)
        if channel is None:
            await interaction.followup.send(
                "Task dashboard channel not found. Check TASK_DASHBOARD_CHANNEL_ID.",
                ephemeral=True,
            )
            return

        overview_msg = await find_overview(channel)
        if overview_msg is None:
            await interaction.followup.send(
                "No overview message found. Ask an admin to run `/task setup` first.",
                ephemeral=True,
            )
            return

        thread = await get_task_thread(overview_msg)
        if thread is None:
            await interaction.followup.send(
                "Task data thread not found. Ask an admin to run `/task setup` again.",
                ephemeral=True,
            )
            return

        deadline_val = _parse_deadline(self.deadline.value)
        assignee_val = self.assignee.value.strip() or "Unassigned"
        data_embed = build_task_data_embed(
            title=self.task_title.value.strip(),
            description=self.description.value.strip(),
            creator=interaction.user.mention,
            assignee=assignee_val,
            deadline=deadline_val,
            source_url=self.source_url,
        )
        try:
            await thread.send(embed=data_embed)
        except discord.HTTPException as e:
            await interaction.followup.send(f"Failed to save task: {e}", ephemeral=True)
            return

        await rebuild_overview(overview_msg, thread)
        await interaction.followup.send("✅ Task created!", ephemeral=True)


class TaskEditModal(discord.ui.Modal, title="Edit Task"):
    task_title = discord.ui.TextInput(label="Task name", max_length=100)
    description = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1000,
    )
    assignee = discord.ui.TextInput(
        label="Assign to (leave blank to unassign)",
        required=False,
        max_length=50,
        placeholder="gabs / jo / niki / mex — or leave blank",
    )
    deadline = discord.ui.TextInput(
        label="Deadline (leave blank to clear)",
        required=False,
        max_length=20,
        placeholder="today · tomorrow · next week · 2026-07-01 · 15.07.2026",
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
        self.assignee.default = data["assignee"] if data["assignee"] != "Unassigned" else ""
        dl = data["deadline"]
        self.deadline.default = dl if dl != "No deadline" else ""

    async def on_submit(self, interaction: discord.Interaction) -> None:
        from ui.views import rebuild_overview

        await interaction.response.defer(ephemeral=True)

        data = parse_task_data_embed(self.thread_msg.embeds[0])
        deadline_val = _parse_deadline(self.deadline.value)
        assignee_val = self.assignee.value.strip() or "Unassigned"

        new_embed = build_task_data_embed(
            title=self.task_title.value.strip(),
            description=self.description.value.strip(),
            creator=data["creator"],
            assignee=assignee_val,
            deadline=deadline_val,
            source_url=data["source_url"],
            status=data["status"],
        )
        await self.thread_msg.edit(embed=new_embed)
        await rebuild_overview(self.overview_msg, self.thread)
        await interaction.followup.send("Task updated.", ephemeral=True)
