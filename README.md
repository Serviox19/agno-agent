# Agno Agent — Personal Command Center

Multi-agent system with a Life Sarge (accountability coach), X News Desk (news pipeline), Web Scraper, and Crypto Watcher — all routed through a Team coordinator via Slack.

## Setup

```bash
# Create a virtual environment (recommended — keeps deps isolated from other projects)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy env template and fill in your keys
cp .env.example .env
```

Activate the venv with `source venv/bin/activate` each time you open a new terminal before running any commands.

### Required API Keys (`.env`)

| Variable | Source |
|---|---|
| `OPENROUTER_API_KEY` | [openrouter.ai/keys](https://openrouter.ai/keys) |
| `OLLAMA_API_KEY` | [ollama.com](https://ollama.com) |
| `X_BEARER_TOKEN` + X credentials | [developer.x.com](https://developer.x.com/en/portal/dashboard) |
| `FIRECRAWL_API_KEY` | [firecrawl.dev](https://www.firecrawl.dev/) |
| `SLACK_TOKEN` | [api.slack.com/apps](https://api.slack.com/apps) — Bot User OAuth Token (`xoxb-...`) |
| `SLACK_SIGNING_SECRET` | Slack app → Basic Information → App Credentials |
| `MONGO_URL` | Your MongoDB connection string (local or Atlas) |
| `MONGO_DB_NAME` | Database name within your cluster (default: `agno_agents`) |

### Google Calendar Setup (for Calendar Assistant)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Enable **Google Calendar API** (APIs & Services → Enable APIs)
4. Create OAuth credentials: APIs & Services → Credentials → Create Credentials → OAuth client ID → Desktop app
5. Download the JSON and save as `credentials.json` in the project root
6. **Run the app locally once** — a browser opens for OAuth consent. Authorize; tokens save to `token.json`.
7. **For deploy (e.g. Render):** Do not commit these files. In Render (or any host), set env vars with the **entire file contents** (copy-paste the JSON): `GOOGLE_CREDENTIALS_JSON` and `GOOGLE_TOKEN_JSON`. The app writes them to disk at startup so the Calendar tools work. Complete OAuth locally first to get `token.json`, then paste both into env.

## Running Locally

Two processes — the server and the scheduler:

```bash
# Terminal 1: Start the AgentOS server
python app.py

# Terminal 2: Start the scheduler (check-ins, news digests, crypto monitor)
python scheduler.py
```

Server runs on `http://localhost:7777`. The scheduler POSTs to the server on cron schedules.

### Slack app setup (full checklist)

One Slack app can only have one Request URL. Use the main Command Center endpoint (`/slack/events`) so all messages are routed by the coordinator. To use separate endpoints per agent you’d create additional Slack apps and point each to its own URL (e.g. `/slack-sarge/events`).

**1. Create the app**

- Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
- Name it (e.g. “Command Center”) and pick your workspace

**2. Bot token scopes**

- **OAuth & Permissions** (left sidebar) → **Scopes** → **Bot Token Scopes**
- Add these:

| Scope | Purpose |
|-------|--------|
| `chat:write` | Send messages and replies |
| `app_mentions:read` | Receive when the bot is @mentioned |
| `channels:history` | Read messages in channels the bot is in (for @mentions) |
| `channels:read` | See channel list / basic info |
| `im:history` | Read direct messages to the bot |
| `im:read` | See DM channels and basic info |

**3. Event Subscriptions**

- **Event Subscriptions** (left sidebar) → turn **Enable Events** **On**
- **Request URL:**
  - Local: use ngrok (`ngrok http 7777`), then `https://YOUR-NGROK-URL/slack/events`
  - Deployed: `https://YOUR-DOMAIN/slack/events`
- After the URL is verified (see step 5), open **Subscribe to bot events** and add:

| Event | Purpose |
|-------|--------|
| `app_mention` | Bot is @mentioned in a channel |
| `message.im` | Someone DMs the bot |

Save changes.

**4. Get your credentials**

- **Basic Information** (left sidebar) → **App Credentials**
  - Copy **Signing Secret** → put in `.env` as `SLACK_SIGNING_SECRET`
- **OAuth & Permissions** → click **Install to Workspace** (or **Reinstall** if you already did)
  - After installing, copy **Bot User OAuth Token** (`xoxb-...`) → put in `.env` as `SLACK_TOKEN`

**5. Request URL verification**

- With the app server running and reachable at the Request URL (ngrok or deployed), Slack will send a one-time challenge to that URL. The app responds automatically and Slack shows “Verified”.
- If it fails, check: server is running, URL is exactly `https://.../slack/events`, no typo, and `SLACK_SIGNING_SECRET` is set so signature verification passes.

**6. Using the bot**

- **DMs:** Open the app in the Slack sidebar (Apps) and send a message. The bot replies in the thread.
- **Channels:** Invite the bot: in the channel, type `/invite @YourBotName`. Then @mention the bot in a message to trigger a reply.

### Slack not working? Debug checklist

1. **Request URL must be exact**  
   In Event Subscriptions use: `https://YOUR-NGROK-OR-DOMAIN/slack/events`  
   Not `/slack-sarge/events` or anything else. One Slack app = one URL; this one goes to the Command Center.

2. **Ngrok URL changes every time**  
   Free ngrok gives a new URL when you restart it. If you restarted ngrok, update the Request URL in Slack and re-save. Verification must show "Verified" again.

3. **Subscribe to bot events**  
   Under Event Subscriptions → "Subscribe to bot events" add:
   - `message.im` (required for DMs)
   - `app_mention` (for @mentions in channels)  
   Without `message.im`, Slack never sends DM events to your server.

4. **Bot token scopes and reinstall**  
   OAuth & Permissions → Bot Token Scopes must include: `chat:write`, `im:history`, `im:read`, `app_mentions:read`, `channels:history`, `channels:read`.  
   If you added any of these after the first install, click **Reinstall to Workspace**, then put the new Bot User OAuth Token in `.env` as `SLACK_TOKEN` and restart the app.

5. **See if Slack is calling you**  
   Send a DM to the bot, then look at the terminal where `python app.py` is running.  
   - No new log line at all → Slack isn’t sending (wrong URL, or ngrok down, or `message.im` not subscribed).  
   - `403` or "Invalid signature" → wrong `SLACK_SIGNING_SECRET` in `.env`.  
   - `200` but no reply → app is receiving; the run might be erroring (check for tracebacks in the same terminal).

6. **Allow DMs to the app**  
   App Home → turn **on** "Allow users to send Slash commands and messages from the messages tab". Otherwise Slack shows "Sending messages to this app has been turned off" and DMs won't work.

7. **How to open a DM with the bot**  
   In Slack: search (Cmd+J or click search), type your app name, select the app under "Apps" to open its DM. Or add it via the + next to "Direct Messages" and search for the app.

### Slack Endpoints

| Endpoint | Routes to |
|---|---|
| `/slack` | Command Center (auto-routes to the right agent) |
| `/slack-sarge` | Life Sarge directly |
| `/slack-news` | X News Desk team |
| `/slack-scraper` | Web Scraper directly |
| `/slack-crypto` | Crypto Watcher directly |

## Deploying

### What you need

- A server/VPS or container platform (Railway, Render, Fly.io, AWS, etc.)
- MongoDB Atlas (or any accessible MongoDB instance)
- A public URL for Slack webhooks (no more ngrok)

### Steps

1. Push this repo to your hosting platform
2. Set all `.env` variables as environment variables on the platform
3. Run two processes:
   - **Web process:** `python app.py` (or `uvicorn app:app --host 0.0.0.0 --port 7777`)
   - **Worker process:** `python scheduler.py`
4. Update `AGNO_BASE_URL` in the scheduler's env to point to the deployed server (e.g. `https://your-app.railway.app`)
5. Update your Slack app's Event Subscriptions URL to your public server URL + `/slack/events`

### Procfile (if your platform uses one)

```
web: uvicorn app:app --host 0.0.0.0 --port $PORT
worker: python scheduler.py
```

Set `AGNO_BASE_URL=http://localhost:$PORT` for the worker if both processes share the same host, or the full public URL if they're separate.
