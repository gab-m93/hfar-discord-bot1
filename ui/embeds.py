import discord
from datetime import datetime, timezone

COLOR_OPEN = 0x57F287
COLOR_COMPLETED = 0x95A5A6
COLOR_OVERDUE = 0xED4245

STATUS_OPEN = "open"
STATUS_COMPLETED = "completed"

OVERVIEW_TITLE_PREFIX = "📋 Open Tasks"


def _get_color(status: str, deadline: str) -> int:
    if status == STATUS_COMPLETED:
        return COLOR_COMPLETED
    if deadline and deadline != "No deadline":
        try:
            due = datetime.strptime(deadline, "%Y-%m-%d").date()
            if due < datetime.now(timezone.utc).date():
                return COLOR_OVERDUE
        except ValueError:
            pass
    return COLOR_OPEN


def build_task_data_embed(
    title: str,
    description: str,
    creator: str,
    assignee: str,
    deadline: str,
    source_url: str,
    status: str = STATUS_OPEN,
) -> discord.Embed:
    """Embed stored in the task data thread. Never shown in the dashboard channel."""
    embed = discord.Embed(title=title, description=description or "")
    embed.add_field(name="source_url", value=source_url or "", inline=False)
    embed.add_field(name="assignee", value=assignee or "Unassigned", inline=False)
    embed.add_field(name="creator", value=creator, inline=False)
    embed.add_field(name="deadline", value=deadline or "No deadline", inline=False)
    embed.add_field(name="status", value=status, inline=False)
    return embed


def parse_task_data_embed(embed: discord.Embed) -> dict:
    fields = {f.name: f.value for f in embed.fields}
    return {
        "title": embed.title or "",
        "description": embed.description or "",
        "source_url": fields.get("source_url", ""),
        "assignee": fields.get("assignee", "Unassigned"),
        "creator": fields.get("creator", ""),
        "deadline": fields.get("deadline", "No deadline"),
        "status": fields.get("status", STATUS_OPEN),
    }


def build_overview_embed(tasks: list[dict], thread_id: int | None = None) -> discord.Embed:
    """Build the pinned overview embed.
    tasks: list of dicts with keys 'data' (parse_task_data_embed result) and 'url' (jump url).
    """
    today = datetime.now(timezone.utc).date()

    if not tasks:
        description = "_No open tasks._"
    else:
        lines = []
        for t in tasks:
            data, url = t["data"], t["url"]
            line = f"• [{data['title']}]({url})"
            if data["assignee"] != "Unassigned":
                line += f" — {data['assignee']}"
            lines.append(line)
            dl = data["deadline"]
            if dl and dl != "No deadline":
                try:
                    due = datetime.strptime(dl, "%Y-%m-%d").date()
                    indicator = "🔴 Overdue:" if due < today else "📅 Due:"
                except ValueError:
                    indicator = "📅 Due:"
                lines.append(f"  {indicator} {dl}")
        description = "\n".join(lines)

    embed = discord.Embed(
        title=f"{OVERVIEW_TITLE_PREFIX} ({len(tasks)})",
        description=description,
        color=0x5865F2,
    )
    footer_parts = []
    if thread_id:
        footer_parts.append(f"thread:{thread_id}")
    footer_parts.append("Right-click any message → Apps → Create Task")
    embed.set_footer(text=" | ".join(footer_parts))
    return embed
