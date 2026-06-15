import discord
from datetime import datetime, timezone

COLOR_OPEN = 0x57F287
COLOR_COMPLETED = 0x95A5A6
COLOR_OVERDUE = 0xED4245

STATUS_OPEN = "🟢 Open"
STATUS_COMPLETED = "✅ Completed"


def build_task_embed(
    title: str,
    description: str,
    creator: str,
    assignee: str = "Unassigned",
    deadline: str = "No deadline",
    status: str = STATUS_OPEN,
    source_url: str | None = None,
) -> discord.Embed:
    if status == STATUS_COMPLETED:
        color = COLOR_COMPLETED
    elif deadline != "No deadline" and status == STATUS_OPEN:
        try:
            due = datetime.strptime(deadline, "%Y-%m-%d").date()
            today = datetime.now(timezone.utc).date()
            color = COLOR_OVERDUE if due < today else COLOR_OPEN
        except ValueError:
            color = COLOR_OPEN
    else:
        color = COLOR_OPEN

    embed = discord.Embed(title=title, description=description or "", color=color)
    embed.add_field(name="Created by", value=creator, inline=True)
    embed.add_field(name="Assigned to", value=assignee, inline=True)
    embed.add_field(name="Deadline", value=deadline, inline=True)
    embed.add_field(name="Status", value=status, inline=True)
    if source_url:
        embed.add_field(name="Source", value=f"[Jump to message]({source_url})", inline=True)
    embed.timestamp = discord.utils.utcnow()
    return embed


def parse_task_embed(embed: discord.Embed) -> dict:
    fields = {f.name: f.value for f in embed.fields}
    return {
        "title": embed.title or "",
        "description": embed.description or "",
        "created_by": fields.get("Created by", ""),
        "assigned_to": fields.get("Assigned to", "Unassigned"),
        "deadline": fields.get("Deadline", "No deadline"),
        "status": fields.get("Status", STATUS_OPEN),
        "source_url": fields.get("Source", ""),
    }


def is_completed(embed: discord.Embed) -> bool:
    return parse_task_embed(embed)["status"] == STATUS_COMPLETED
