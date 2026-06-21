import re
import discord
from ui.embeds import (
    build_task_data_embed,
    build_overview_embed,
    parse_task_data_embed,
    OVERVIEW_TITLE_PREFIX,
    STATUS_OPEN,
    STATUS_COMPLETED,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

async def find_overview(channel: discord.TextChannel) -> discord.Message | None:
    """Find the overview message: check pins first, then oldest channel history."""
    try:
        pins = await channel.pins()
        msg = next(
            (
                p for p in pins
                if p.author == channel.guild.me
                and p.embeds
                and (p.embeds[0].title or "").startswith(OVERVIEW_TITLE_PREFIX)
            ),
            None,
        )
        if msg:
            return msg
    except discord.HTTPException:
        pass

    async for msg in channel.history(limit=50, oldest_first=True):
        if (
            msg.author == channel.guild.me
            and msg.embeds
            and (msg.embeds[0].title or "").startswith(OVERVIEW_TITLE_PREFIX)
        ):
            return msg
    return None


async def get_task_thread(overview_msg: discord.Message) -> discord.Thread | None:
    """Extract thread ID from the overview embed footer and fetch the thread."""
    if not overview_msg.embeds:
        return None
    footer = overview_msg.embeds[0].footer.text or ""
    m = re.search(r'thread:(\d+)', footer)
    if not m:
        return None
    thread_id = int(m.group(1))
    try:
        thread = overview_msg.guild.get_thread(thread_id)
        if thread:
            return thread
        return await overview_msg.guild.fetch_channel(thread_id)
    except (discord.NotFound, discord.HTTPException):
        return None


async def rebuild_overview(
    overview_msg: discord.Message, thread: discord.Thread
) -> None:
    """Read all task messages from the thread and update the overview message."""
    messages: list[discord.Message] = []
    async for msg in thread.history(limit=100):
        if msg.embeds and msg.author == thread.guild.me:
            messages.append(msg)
    messages.reverse()  # oldest first

    open_tasks = []
    for msg in messages:
        data = parse_task_data_embed(msg.embeds[0])
        if data["status"] == STATUS_OPEN:
            open_tasks.append({"data": data, "url": msg.jump_url, "id": str(msg.id)})

    footer = overview_msg.embeds[0].footer.text or ""
    m = re.search(r'thread:(\d+)', footer)
    thread_id = int(m.group(1)) if m else thread.id

    embed = build_overview_embed(open_tasks, thread_id=thread_id)

    if open_tasks:
        options = [
            discord.SelectOption(
                label=t["data"]["title"][:100],
                value=t["id"],
                description=_option_desc(t["data"])[:100],
            )
            for t in open_tasks
        ]
        view = OverviewView(options)
    else:
        view = OverviewView(None)

    await overview_msg.edit(embed=embed, view=view)


def _option_desc(data: dict) -> str:
    parts = []
    if data["assignee"] != "Unassigned":
        parts.append(data["assignee"])
    if data["deadline"] != "No deadline":
        parts.append(f"due {data['deadline']}")
    return " · ".join(parts) if parts else "No deadline · Unassigned"


# ── Views ──────────────────────────────────────────────────────────────────────

class OverviewView(discord.ui.View):
    """Persistent select menu attached to the overview message."""

    def __init__(self, options: list[discord.SelectOption] | None) -> None:
        super().__init__(timeout=None)
        if options:
            self.task_select.options = options
            self.task_select.disabled = False
        else:
            self.task_select.options = [discord.SelectOption(label="—", value="0")]
            self.task_select.disabled = True

    @discord.ui.select(
        custom_id="overview_task_select",
        placeholder="Select a task to manage…",
        min_values=1,
        max_values=1,
        options=[discord.SelectOption(label="—", value="0")],
    )
    async def task_select(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ) -> None:
        task_msg_id = int(select.values[0])
        overview_msg = interaction.message

        thread = await get_task_thread(overview_msg)
        if thread is None:
            await interaction.response.send_message(
                "Could not find the task data thread. Run `/task setup` again.", ephemeral=True
            )
            return

        try:
            task_msg = await thread.fetch_message(task_msg_id)
        except discord.NotFound:
            await interaction.response.send_message(
                "That task no longer exists. Refreshing the overview…", ephemeral=True
            )
            await rebuild_overview(overview_msg, thread)
            return

        data = parse_task_data_embed(task_msg.embeds[0])
        summary = discord.Embed(title=data["title"], color=0x5865F2)
        summary.add_field(name="Assigned to", value=data["assignee"], inline=True)
        summary.add_field(name="Deadline", value=data["deadline"], inline=True)
        summary.add_field(name="Created by", value=data["creator"], inline=True)
        if data["description"]:
            summary.add_field(name="Notes", value=data["description"], inline=False)
        if data["source_url"]:
            summary.add_field(
                name="Source", value=f"[Jump to message]({data['source_url']})", inline=False
            )

        await interaction.response.send_message(
            embed=summary,
            view=TaskManageView(task_msg, overview_msg, thread),
            ephemeral=True,
        )



class TaskManageView(discord.ui.View):
    """Ephemeral panel opened when a task is selected from the overview dropdown."""

    def __init__(
        self,
        thread_msg: discord.Message,
        overview_msg: discord.Message,
        thread: discord.Thread,
    ) -> None:
        super().__init__(timeout=60)
        self.thread_msg = thread_msg
        self.overview_msg = overview_msg
        self.thread = thread

    @discord.ui.button(label="✅ Complete", style=discord.ButtonStyle.success, row=0)
    async def complete(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        data = parse_task_data_embed(self.thread_msg.embeds[0])
        if data["status"] == STATUS_COMPLETED:
            await interaction.response.send_message("Already completed.", ephemeral=True)
            return
        new_embed = build_task_data_embed(
            title=data["title"],
            description=data["description"],
            creator=data["creator"],
            assignee=data["assignee"],
            deadline=data["deadline"],
            source_url=data["source_url"],
            status=STATUS_COMPLETED,
        )
        await self.thread_msg.edit(embed=new_embed)
        await rebuild_overview(self.overview_msg, self.thread)
        self.stop()
        await interaction.response.edit_message(
            content="✅ Task marked as completed.", embed=None, view=None
        )

    @discord.ui.button(label="✏️ Edit", style=discord.ButtonStyle.primary, row=0)
    async def edit(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        from ui.modals import TaskEditModal
        await interaction.response.send_modal(
            TaskEditModal(self.thread_msg, self.overview_msg, self.thread)
        )

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=0)
    async def delete(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.edit_message(
            content="Are you sure you want to delete this task?",
            embed=None,
            view=DeleteConfirmView(self.thread_msg, self.overview_msg, self.thread),
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
        data = parse_task_data_embed(self.thread_msg.embeds[0])
        assignee = select.values[0] if select.values else None
        new_embed = build_task_data_embed(
            title=data["title"],
            description=data["description"],
            creator=data["creator"],
            assignee=assignee.mention if assignee else "Unassigned",
            deadline=data["deadline"],
            source_url=data["source_url"],
            status=data["status"],
        )
        await self.thread_msg.edit(embed=new_embed)
        await rebuild_overview(self.overview_msg, self.thread)
        name = assignee.display_name if assignee else "nobody"
        await interaction.response.send_message(
            f"Assignee updated to **{name}**.", ephemeral=True
        )


class DeleteConfirmView(discord.ui.View):
    def __init__(
        self,
        thread_msg: discord.Message,
        overview_msg: discord.Message,
        thread: discord.Thread,
    ) -> None:
        super().__init__(timeout=30)
        self.thread_msg = thread_msg
        self.overview_msg = overview_msg
        self.thread = thread

    @discord.ui.button(label="Yes, delete", style=discord.ButtonStyle.danger)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.thread_msg.delete()
        await rebuild_overview(self.overview_msg, self.thread)
        self.stop()
        await interaction.response.edit_message(content="Task deleted.", view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.stop()
        await interaction.response.edit_message(content="Cancelled.", view=None)
