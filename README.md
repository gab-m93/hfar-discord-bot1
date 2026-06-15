# Discord Task Bot

Create tasks from any Discord message via right-click context menu. Tasks appear in a dedicated dashboard channel as embeds with buttons to complete, edit, reassign, or delete them. All state lives inside the Discord embeds — no database required.

---

## Features

- **Right-click any message → Apps → Create Task** — pre-fills the task name from the message text
- Optional deadline (YYYY-MM-DD) and assignee set during creation
- Dashboard channel shows all tasks as embeds with action buttons:
  - ✅ Complete — turns embed gray, disables button
  - ✏️ Edit — update name, description, deadline via modal
  - 👤 Assign — change assignee via user picker
  - 🗑️ Delete — confirm then removes the embed
- `/task list` — ephemeral list of all open tasks with jump links
- `/task setup` — (admin) posts a header embed in the dashboard channel
- Buttons survive bot restarts (persistent views)

---

## 1. Discord Developer Portal

### 1a. Create the application

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications) and click **New Application**.
2. Give it a name (e.g. `Task Bot`) and click **Create**.

### 1b. Create the bot user

1. In the left sidebar click **Bot**.
2. Click **Add Bot** → **Yes, do it!**
3. Under the bot's username click **Reset Token**, confirm, then **copy the token** — this is your `DISCORD_TOKEN`. Store it somewhere safe; you won't see it again.

### 1c. Enable privileged intents and set default permissions

Still on the **Bot** page:

**Privileged Gateway Intents** — turn on:

| Intent | Why |
|---|---|
| **Message Content Intent** | Lets the bot read the text of the message you right-click to pre-fill the task name |

*(Server Members Intent and Presence Intent are **not** needed.)*

**Bot Permissions** (shown below the intents on the same page) — check:

| Permission | Why |
|---|---|
| `View Channels` | See the channels it operates in |
| `Send Messages` | Post task embeds to the dashboard channel |
| `Embed Links` | Required to send Discord embeds |
| `Read Message History` | Used by `/task list` to scan the dashboard for open tasks |

These are the same permissions you'll select again in step 1d when generating the invite URL — setting them here just establishes the defaults.

### 1d. Generate an invite URL

1. In the left sidebar go to **OAuth2 → URL Generator**.
2. Under **Scopes** check:
   - `bot`
   - `applications.commands`
3. Under **Bot Permissions** check:
   - `Send Messages`
   - `Embed Links`
   - `Read Message History`
   - `View Channels`
4. Copy the generated URL at the bottom, open it in a browser, and invite the bot to your server.

---

## 2. First-time server setup

### 2a. Create the dashboard channel

In your Discord server, create a text channel called `#task-dashboard` (or any name you like).

### 2b. Enable Developer Mode and copy the channel ID

Developer Mode makes Discord show internal IDs, which you need for the env variable.

1. Open Discord → click the **gear icon ⚙️** next to your username (bottom left) → **User Settings**
2. In the left sidebar scroll to **Advanced** → turn on **Developer Mode**
3. Close settings, go back to your server
4. Right-click **#task-dashboard** in the channel list → **Copy Channel ID**

That number (e.g. `1234567890123456789`) is your `TASK_DASHBOARD_CHANNEL_ID`.

### 2c. Post the dashboard header

Once the bot is deployed and running, run `/task setup` in any channel (requires Manage Channels permission). This posts an explanatory header embed in the dashboard channel.

---

## 3. Deploy on Railway

### 3a. Create a Railway project

1. Go to [railway.app](https://railway.app) and sign in with GitHub.
2. Click **New Project → Deploy from GitHub repo** and select `hfar-discord-bot1`.
3. Railway will detect `requirements.txt` and install dependencies automatically.

### 3b. Set environment variables

In your Railway project, go to **Variables** and add:

| Variable | Value |
|---|---|
| `DISCORD_TOKEN` | The bot token from step 1b |
| `TASK_DASHBOARD_CHANNEL_ID` | The channel ID from step 2 |

### 3c. Set the start command

Railway reads the `Procfile` in the repo. It already contains:

```
worker: python bot.py
```

Because this is a worker (no HTTP server), make sure Railway is running it as a **Worker** service, not a Web service. If Railway tries to assign a port, open the service settings → **Deploy** tab and confirm the start command is `python bot.py` (no gunicorn or uvicorn wrapper).

### 3d. Deploy

Click **Deploy** (or push a commit — Railway auto-deploys on every push to `main`). Watch the build log; a successful start looks like:

```
INFO root: Logged in as Task Bot (id=123456789)
```

---

## Local development

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Fill in DISCORD_TOKEN and TASK_DASHBOARD_CHANNEL_ID in .env

python bot.py
```

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | Yes | Bot token from the Developer Portal |
| `TASK_DASHBOARD_CHANNEL_ID` | Yes | Numeric ID of your `#task-dashboard` channel |
