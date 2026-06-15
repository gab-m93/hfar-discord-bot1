import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
TASK_DASHBOARD_CHANNEL_ID = int(os.environ["TASK_DASHBOARD_CHANNEL_ID"])
