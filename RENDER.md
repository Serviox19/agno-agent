# Deploy options

Choose one: **Render** (cloud) or **Mac Mini** (local server).

---

# Option A: Render

One Web Service (the app) and one Background Worker (the scheduler). The worker calls the app over the public URL.

---

## 1. Repo

- Push this repo to GitHub (or connect Render to your existing repo).

---

## 2. Create the Web Service

- Dashboard → **New** → **Web Service**
- Connect the repo, pick the branch
- **Name:** e.g. `agno-agent`
- **Region:** your choice
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn app:app --host 0.0.0.0 --port $PORT`
- **Instance type:** Free or paid

**Environment (Web Service)** — add every variable from your `.env`:

- `OPENROUTER_API_KEY`, `OLLAMA_API_KEY`, `MONGO_URL`, `MONGO_DB_NAME`
- `SLACK_TOKEN`, `SLACK_SIGNING_SECRET`, `SLACK_SARGE_CHANNEL`
- All X, Firecrawl, etc. Same as local.

Create the service. Note the URL Render gives you (e.g. `https://agno-agent.onrender.com`).

---

## 3. Create the Background Worker

- Dashboard → **New** → **Background Worker**
- Same repo and branch
- **Name:** e.g. `agno-agent-scheduler`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python scheduler.py`

**Environment (Worker)** — same env vars as the web service, plus:

- `AGNO_BASE_URL` = your web service URL, e.g. `https://agno-agent.onrender.com`  
  (no trailing slash; the worker POSTs to `{AGNO_BASE_URL}/agents/...` and `.../teams/...`)

Create the worker.

---

## 4. Slack

- Slack app → **Event Subscriptions** → **Request URL**  
  Set to: `https://YOUR-RENDER-WEB-URL/slack/events`  
  (Replace with your actual Render web URL.) Save and wait for “Verified”.

---

## 5. Free tier note

- Render free web services spin down after ~15 min idle. When a request hits it, it cold-starts (can take 30–60 s). The worker’s POSTs will wake it; Slack may retry. For always-on, use a paid instance.

---

# Option B: Mac Mini M1 (local server)

Run the app and scheduler on your Mac Mini so they’re always on at home. Slack and the scheduler need a stable URL to reach the app — use either a tunnel (ngrok/cloudflared) or your router’s port forward + dynamic DNS.

---

## 1. Setup on the Mac Mini

- Install Python 3.11+ (e.g. `brew install python@3.11`).
- Clone the repo (or copy the project folder) onto the Mac.
- In the project directory:
  ```bash
  python3.11 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  ```
- Copy your `.env` from your dev machine (or recreate it). All the same variables.

---

## 2. Expose the app to the internet

Slack must POST to your app from the internet. Two ways:

**A) Tunnel (easiest)**  
- Install ngrok: `brew install ngrok`, then `ngrok http 7777`.  
- Use the `https://` URL ngrok gives you.  
- Free ngrok URLs change each time you restart ngrok. For a stable URL, use ngrok’s reserved domain (paid) or use Cloudflare Tunnel (free, stable subdomain).

**B) Port forward**  
- Router: forward external port (e.g. 8443) to the Mac Mini’s LAN IP, port 7777.  
- Use HTTPS in front (e.g. Caddy or nginx with Let’s Encrypt) or a reverse proxy; Slack expects HTTPS.  
- Dynamic DNS (e.g. No-IP, DuckDNS) if your home IP changes, so Slack’s Request URL doesn’t break.

For a quick test, ngrok is enough. For 24/7 without changing URLs, use Cloudflare Tunnel or port forward + DNS.

---

## 3. Run the app and scheduler 24/7

You need both processes running all the time and ideally after reboot.

**Option 1: Terminal (simple, not after reboot)**  
- Terminal 1: `source .venv/bin/activate && python app.py`  
- Terminal 2: `source .venv/bin/activate && AGNO_BASE_URL=http://localhost:7777 python scheduler.py`  
- Stops when you close the terminals or SSH session.

**Option 2: launchd (recommended)**  
- Create two plists so macOS runs the app and the scheduler as user agents, restart on crash and after reboot.  
- Example for the **web app** (save as `~/Library/LaunchAgents/com.agno-agent.web.plist`):

  ```xml
  <?xml version="1.0" encoding="UTF-8"?>
  <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
  <plist version="1.0">
  <dict>
    <key>Label</key>
    <string>com.agno-agent.web</string>
    <key>ProgramArguments</key>
    <array>
      <string>/Users/YOUR_USERNAME/path/to/agno-agent/.venv/bin/python</string>
      <string>-m</string>
      <string>uvicorn</string>
      <string>app:app</string>
      <string>--host</string>
      <string>0.0.0.0</string>
      <string>--port</string>
      <string>7777</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/YOUR_USERNAME/path/to/agno-agent</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/agno-web.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/agno-web.err</string>
  </dict>
  </plist>
  ```

- Example for the **scheduler** (save as `~/Library/LaunchAgents/com.agno-agent.scheduler.plist`):

  ```xml
  <?xml version="1.0" encoding="UTF-8"?>
  <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
  <plist version="1.0">
  <dict>
    <key>Label</key>
    <string>com.agno-agent.scheduler</string>
    <key>ProgramArguments</key>
    <array>
      <string>/Users/YOUR_USERNAME/path/to/agno-agent/.venv/bin/python</string>
      <string>scheduler.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/YOUR_USERNAME/path/to/agno-agent</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>EnvironmentVariables</key>
    <dict>
      <key>AGNO_BASE_URL</key>
      <string>http://localhost:7777</string>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/agno-scheduler.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/agno-scheduler.err</string>
  </dict>
  </plist>
  ```

- Replace `YOUR_USERNAME` and `path/to/agno-agent` with the real path.  
- Load and start:  
  `launchctl load ~/Library/LaunchAgents/com.agno-agent.web.plist`  
  `launchctl load ~/Library/LaunchAgents/com.agno-agent.scheduler.plist`  
- To stop: `launchctl unload ~/Library/LaunchAgents/com.agno-agent.web.plist` (and same for scheduler).  
- Logs: `tail -f /tmp/agno-web.log` and `tail -f /tmp/agno-scheduler.log`.

---

## 4. Slack and env on the Mac

- In Slack app → Event Subscriptions → Request URL: set to your Mac’s public URL + `/slack/events`, e.g. `https://your-ngrok-url.ngrok-free.app/slack/events` or `https://your-dynamic-dns.net/slack/events`.
- In the scheduler’s environment (or in `.env` on the Mac), set `AGNO_BASE_URL=http://localhost:7777` so the worker POSTs to the local app. (If you use launchd, the plist above sets this.)
