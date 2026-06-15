import asyncio
import logging

import discord
from discord.ext import commands

import config
from ui.views import TaskDashboardView

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


intents = discord.Intents.default()
intents.message_content = True  # needed to read message text in context menu target

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    member_cache_flags=discord.MemberCacheFlags.none(),
)


@bot.event
async def on_ready() -> None:
    # Re-register persistent view so old dashboard buttons keep working after restarts
    bot.add_view(TaskDashboardView())
    log.info("Logged in as %s (id=%s)", bot.user, bot.user.id)


async def main() -> None:
    async with bot:
        await bot.load_extension("cogs.tasks")
        await bot.tree.sync()
        await bot.start(config.DISCORD_TOKEN)


asyncio.run(main())
