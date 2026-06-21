import re
import discord
from datetime import datetime, timezone

COLOR_OPEN = 0x57F287
COLOR_COMPLETED = 0x95A5A6
COLOR_OVERDUE = 0xED4245

STATUS_OPEN = "🟢 Open"
STATUS_COMPLETED = "✅ Completed"

OVERVIEW_TITLE_PREFIX = "📋 Open Tasks"


def _get_color(status: str, deadline: str) -> int:
    if status == STATUS_COMPLETED:
        return COLOR_COMPLETED
    if deadline != "No deadline":
        try:
            due = datetime.strptime(deadline, "%Y-%m-%d").date()
            if due < datetime.now(timezone.utc).date():
                return COLOR_OVERDUE
        except ValueError:
            pass
    return COLOR_OPEN


def build_compact_task_embed(
    title: str,
    description: str,
    creator: str,
    assignee: str = "Unassigned",
    deadline: str = "No deadline",
    status: str = STATUS_OPEN,
    source_url: str | None = None,
) -> discord.Embed:
    desc_parts = []
    if source_url:
        desc_parts.append(f"[↗ View source message]({source_url})")
    if description:
        desc_parts.append(description)

    embed = discord.Embed(
        title=title,
        description="\n".join(desc_parts) if desc_parts else "",
        color=_get_color(status, deadline),
    )
    embed.add_field(name="Created by", value=creator, inline=False)
    embed.add_field(name="Assigned to", value=assignee, inline=True)
    embed.add_field(name="Deadline", value=deadline, inline=True)
    embed.add_field(name="Status", value=status, inline=True)
    return embed


def build_overview_embed(tasks: list[dict]) -> discord.Embed:
    if not tasks:
        description = "_No open tasks._"
    else:
        lines = []
        for t in tasks:
            data, url = t["data"], t["url"]
            line = f"• [{data['title']}]({url})"
            if data["assigned_to"] != "Unassigned":
                line += f" — {data['assigned_to']}"
            if data["deadline"] != "No deadline":
                line += f" — due {data['deadline']}"
            lines.append(line)
        description = "\n".join(lines)

    embed = discord.Embed(
        title=f"{OVERVIEW_TITLE_PREFIX} ({len(tasks)})",
        description=description,
        color=0x5865F2,
    )
    embed.set_footer(text="Right-click any message → Apps → Create Task")
    return embed


def parse_task_embed(embed: discord.Embed) -> dict:
    fields = {f.name: f.value for f in embed.fields}

    # Source URL: was previously a "Source" field, now lives in the description
    source_url = ""
    if embed.description:
        m = re.search(r'\[↗ View source message\]\((.+?)\)', embed.description)
        if m:
            source_url = m.group(1)
    if not source_url:
        # Fallback: old "Source" field format
        raw = fields.get("Source", "")
        m2 = re.search(r'\((.+?)\)', raw)
        if m2:
            source_url = m2.group(1)

    # Description: strip the source link line if present
    raw_desc = embed.description or ""
    task_description = re.sub(r'\[↗ View source message\]\(.+?\)\n?', '', raw_desc).strip()

    return {
        "title": embed.title or "",
        "description": task_description,
        "created_by": fields.get("Created by", ""),
        "assigned_to": fields.get("Assigned to", "Unassigned"),
        "deadline": fields.get("Deadline", "No deadline"),
        "status": fields.get("Status", STATUS_OPEN),
        "source_url": source_url,
    }


def is_completed(embed: discord.Embed) -> bool:
    return parse_task_embed(embed)["status"] == STATUS_COMPLETED


def is_task_embed(embed: discord.Embed) -> bool:
    """True for compact task messages; False for the overview or header embeds."""
    return any(f.name == "Status" for f in embed.fields)
