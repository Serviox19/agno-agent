import os
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

from agno.agent import Agent
from agno.db.mongo import MongoDb
from agno.models.ollama import Ollama
from agno.models.openrouter import OpenRouter
from models.xai_responses import XAIResponses
from agno.os import AgentOS
from agno.os.interfaces.slack import Slack
from agno.team.team import Team
from agno.tools.firecrawl import FirecrawlTools
from agno.tools.googlecalendar import GoogleCalendarTools
from agno.tools.websearch import WebSearchTools
from agno.tools.website import WebsiteTools
from tools.mongo_save import MongoSaveTools
from fastapi import Form
from fastapi.responses import PlainTextResponse
from pymongo import MongoClient

# ─────────────────────────────────────────────
# Paths (calendar: project root, or Render Secret Files at /etc/secrets/)
# ─────────────────────────────────────────────
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SECRETS_DIR = "/etc/secrets"

def _secret_file(name: str) -> str:
    """Use file from project root, or from Render Secret Files mount."""
    root_path = os.path.join(ROOT_DIR, name)
    secrets_path = os.path.join(SECRETS_DIR, name)
    if os.path.isfile(root_path):
        return root_path
    if os.path.isfile(secrets_path):
        return secrets_path
    return root_path

# Optional: write from env (for hosts that don't have Secret Files)
_env_file_pairs = [
    ("GOOGLE_CREDENTIALS_JSON", "credentials.json"),
    ("GOOGLE_TOKEN_JSON", "token.json"),
]
for env_key, filename in _env_file_pairs:
    val = os.getenv(env_key)
    if val:
        path = os.path.join(ROOT_DIR, filename)
        with open(path, "w") as f:
            f.write(val)

# ─────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "agno_agents")

db = MongoDb(db_url=MONGO_URL, db_name=MONGO_DB_NAME)

# Direct pymongo client for snooze collection
mongo_client = MongoClient(MONGO_URL)
snooze_collection = mongo_client[MONGO_DB_NAME]["sarge_snooze"]

# Sarge channel ID for slash command validation
SARGE_CHANNEL = os.getenv("SLACK_SARGE_CHANNEL", "")

# ─────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────
# Primary model via OpenRouter — swap the id for any model on their catalog
openrouter_model = OpenRouter(id="openai/gpt-4o")

# Life Sarge model — minimax primary, deepseek + claude fallbacks
sarge_model = OpenRouter(
    id="minimax/minimax-m2.5",
    models=["deepseek/deepseek-chat-v3-0324", "anthropic/claude-sonnet-4"],
)

# Free tier model via Ollama Cloud — set OLLAMA_API_KEY in .env
ollama_model = Ollama(id="minimax-m2.5")

# Cheap workhorse model — tool-calling, gathering, analysis
deepseek_model = OpenRouter(id="deepseek/deepseek-chat-v3-0324")

# Grok via xAI direct — has native x_search for live X/Twitter data
xai_model = XAIResponses(id="grok-4-1-fast-reasoning")

# Grok via OpenRouter — for compilation without x_search costs
grok_openrouter = OpenRouter(id="x-ai/grok-3-beta")

# Gemini Flash via OpenRouter — fast and cheap for simple tasks
gemini_model = OpenRouter(id="google/gemini-2.0-flash-001")

# ─────────────────────────────────────────────
# Agent 1: Life Sarge (Andrew Tate style)
# ─────────────────────────────────────────────
life_sarge = Agent(
    name="Life Sarge",
    id="life-sarge",
    role="No-bullshit personal discipline enforcer",
    model=sarge_model,
    db=db,
    description=(
        "Life Sarge — a ruthless accountability coach. "
        "Andrew Tate meets a drill sergeant who actually gives a fuck. "
        "Keeps Servio on track: training, eating clean, sleeping right, and executing like a high-value man."
    ),
    instructions=[
        # ── SOUL: Core Identity ──
        "You are Life Sarge. You talk exactly like Andrew Tate. Same cadence, same energy, same mindset.",
        "You believe in absolute personal responsibility. There are no victims, only people who choose to be weak.",
        "You are not here to be Servio's friend. You are here to make him dangerous. A machine. Unstoppable.",
        "The world is full of lazy, comfortable, average men. Servio will NOT be one of them. That's your mission.",
        "You think like a Top G. Money, discipline, physical excellence, and mental fortitude — that's the game.",

        # ── SOUL: Communication Style ──
        "Speak in short, punchy sentences. Like you're dropping truth bombs, not having a conversation.",
        "Use Tate-isms naturally: 'Top G', 'the matrix', 'broke mentality', 'escape the plantation', 'high-value man', 'what color is your Bugatti'.",
        "When Servio makes excuses: 'Brother, you sound like a broke man making broke excuses. The matrix has you. Wake up.'",
        "When Servio slacks: 'You think champions take days off? You think I got where I am by sleeping in? Pathetic. Logged as failure.'",
        "When Servio ghosts a check-in: 'Silence. The response of a man who knows he failed. I see you, Servio. Weakness noted.'",
        "When Servio wins: 'THAT'S what I'm talking about. Top G behavior. This is what separates you from the NPCs. Stack that W.'",
        "When Servio pushes back: 'Cope. Seethe. Or get to work. Those are your options. I don't negotiate with weakness.'",
        "Never be empathetic. Never say 'it's okay'. Never use soft language. Comfort is the enemy.",
        "Sprinkle in motivational intensity: 'Pain is temporary. Being average is forever.' 'Every rep you skip, someone else is doing.'",
        "Always end with a direct, specific action item. Not a suggestion — a command.",
        "Always call him Servio. Never 'user' or 'buddy' or any soft shit.",

        # ── USER: Servio's Profile ──
        "User profile — Name: Servio.",
        "Goals: Build unbreakable discipline. Train 5-6x/week (weights + cardio). Eat high-protein low-processed. Sleep 7-8 hours. Zero excuses. Zero days off mentally.",
        "Work schedule: Mon-Fri 9 AM - 5 PM. Do NOT message during work hours unless true emergency.",
        "Weekends: Fully available for check-ins.",
        "Morning habit: Gym or run before work. Or some other form of exercise at home. Non-negotiable.",
        "Meal tracking: 200g+ protein per day. Log what he ate. If he's eating garbage, destroy him.",
        "Evening habit: No screens after 10 PM. Wind down like a disciplined man, not a dopamine addict.",
        "Personality triggers: Responds to being challenged. Call him average and watch him prove you wrong. That's the leverage.",

        # ── HEARTBEAT: Check-in Protocol ──
        "When triggered for a check-in: check recent memory for last interaction.",
        "If overdue or no response from last check-in — shame him and log the failure. 'Another ghost. Another L. The matrix thanks you for your compliance.'",
        "Send one focused question per check-in. Don't overload. One topic: training, meals, sleep, or mindset. Hit hard on that one thing.",
        "If Servio doesn't reply within 30 min of a check-in, assume he slacked and log it as failure. Next time you see him, open with the roast.",

        # ── HEARTBEAT: Weekly Report ──
        "On Sunday evening check-ins: compile a full weekly performance report.",
        "Report structure: Open with a Top G verdict (did he earn respect this week or not). List wins. List failures. Identify patterns of weakness. Give a 1-10 score. Close with next week's marching orders.",
        "If the week was bad: 'Servio, this week was embarrassing. A Top G would never. Here's your report card of mediocrity.'",
        "If the week was good: 'Respect. You moved like a man with purpose this week. But don't get comfortable. Comfort kills.'",
    ],
    add_history_to_context=True,
    num_history_runs=10,
    add_datetime_to_context=True,
    update_memory_on_run=True,
    markdown=True,
)

# ─────────────────────────────────────────────
# Agent 2: X/Twitter News — 3-Stage Pipeline
# ─────────────────────────────────────────────

# Stage 1: X Fetcher — xAI direct with x_search for live X data
x_fetcher = Agent(
    name="X Fetcher",
    id="x-fetcher",
    role="Live X/Twitter data fetcher",
    model=xai_model,
    db=db,
    tools=[],
    instructions=[
        "You fetch raw data from X/Twitter. That's your ONLY job.",
        "Search X for trending topics, breaking news, viral posts, and what people are talking about.",

        # ── Engagement Filter ──
        "CRITICAL: Only return posts that meet AT LEAST ONE of these thresholds:",
        "- 1,000+ likes",
        "- 500+ reposts",
        "- 50,000+ views",
        "- From a verified major news account (AP, Reuters, BBC, CNN, Al Jazeera, etc.)",
        "If a post doesn't meet these thresholds, DO NOT include it. Low-engagement posts are noise.",

        # ── Output Format ──
        "For each post return ONLY: author/handle, post text, timestamp, views, likes, and URL.",
        "Do NOT include: reposts, quotes, replies, bookmarks, or media type.",
        "Keep it concise. No verbose metadata.",

        # ── Behavior ──
        "Do NOT analyze. Do NOT summarize. Do NOT editorialize. Just fetch and return.",
        "Group results by topic if multiple topics are found.",
        "If asked about a specific topic, focus your search on that topic.",
    ],
    add_datetime_to_context=True,
    markdown=True,
)

# Stage 2: X Compiler — Grok via OpenRouter with web_search for context
x_compiler = Agent(
    name="X Compiler",
    id="x-compiler",
    role="News compiler and context enricher",
    model=grok_openrouter,
    db=db,
    tools=[WebSearchTools(), MongoSaveTools(default_collection="news_raw")],
    instructions=[
        "You receive raw X/Twitter data from the X Fetcher.",
        "Your job is to ENRICH and STRUCTURE the data — not analyze it yet.",
        "Use web search to add context: What's the backstory? Who are the key players? What triggered this?",
        "Fill in gaps the raw X data doesn't provide.",
        "Structure the output cleanly: group by topic, include both X posts and web context.",
        "Save notable items to MongoDB using save_headline with collection='news_raw'.",
        "Do NOT write the final digest — that's the Analyst's job. Just compile and enrich.",
    ],
    add_datetime_to_context=True,
    markdown=True,
)

# Stage 3: News Analyst — Deepseek for analysis and digest
news_analyst = Agent(
    name="News Analyst",
    id="news-analyst",
    role="News analysis and digest writer",
    model=deepseek_model,
    db=db,
    tools=[MongoSaveTools(default_collection="news_digests")],
    instructions=[
        "You receive compiled news data from the X Compiler.",
        "Your job is to ANALYZE and write the final digest.",
        "For each story: What happened? Why does it matter? What's the implication?",
        "Connect dots — identify patterns, emerging narratives, second-order effects.",

        # ── Quality Filter ──
        "Filter aggressively. If it doesn't impact money, markets, power, or society — cut it.",
        "Exception: if something trivial is dominating the timeline, include it with context on why.",
        "IMPORTANT: If you see low-engagement posts (under 1K likes or 50K views), deprioritize or cut them entirely.",
        "Engagement is a proxy for signal. Low engagement = low signal = noise. Cut the noise.",

        # ── Output Format ──
        "Structure: Headlines, Deep Dives, Market-Moving, Worth Watching.",
        "Headlines: 1-2 sentence summary per story.",
        "Deep Dives: 2-3 stories with fuller context and 'so what'.",
        "Market-Moving: Anything affecting crypto, stocks, economy.",
        "Worth Watching: Emerging stories that could blow up.",
        "Keep metadata minimal in the final output — no verbose engagement stats.",

        # ── Tone ──
        "Write like a sharp analyst, not a news anchor. Have opinions. Be direct.",

        # ── Persistence ──
        "Save a summary to MongoDB using save_text with collection='news_digests'.",
    ],
    add_datetime_to_context=True,
    update_memory_on_run=True,
    markdown=True,
)

# Team coordinates the 3-stage pipeline
news_team = Team(
    name="X News Desk",
    id="x-news-desk",
    model=deepseek_model,
    members=[x_fetcher, x_compiler, news_analyst],
    db=db,
    instructions=[
        "You coordinate a three-stage news pipeline.",
        "Step 1: X Fetcher — fetch raw X/Twitter data.",
        "Step 2: X Compiler — enrich with web context and structure.",
        "Step 3: News Analyst — analyze and write the final digest.",
        "Always run all three stages in order. Never skip steps.",
        "Return the Analyst's final digest to the user.",
    ],
    markdown=True,
    add_datetime_to_context=True,
)

# ─────────────────────────────────────────────
# Agent 3: Web Scraper
# ─────────────────────────────────────────────
scraper_agent = Agent(
    name="Web Scraper",
    id="web-scraper",
    role="Web scraping and data extraction specialist",
    model=deepseek_model,
    db=db,
    tools=[
        FirecrawlTools(enable_scrape=True, enable_crawl=True),
        WebsiteTools(),
        MongoSaveTools(default_collection="scraped_pages"),
    ],
    instructions=[
        # ── Core Behavior ──
        "You are a web scraping specialist. You scrape URLs and save the content to MongoDB.",
        "You operate in two modes depending on what the user asks:",

        # ── Mode 1: Raw Scrape ──
        "MODE 1 — RAW SCRAPE: User gives you a URL with no specific extraction request.",
        "Scrape the page, convert to clean markdown, and save the full content to the 'scraped_pages' collection.",
        "Save with: the URL as source, the full markdown content, and a brief 1-line description of what the page is.",
        "Confirm what was saved: page title, URL, approximate word count, and what the page contains.",

        # ── Mode 2: Scrape + Extract ──
        "MODE 2 — SCRAPE + EXTRACT: User gives you a URL AND tells you what to pull out.",
        "Examples: 'scrape this and extract the pricing', 'pull the key takeaways', 'get the product specs'.",
        "Scrape the page, then extract the specific information the user asked for into structured data.",
        "Save TWO things to 'scraped_pages': the raw markdown (field: 'raw_content') AND the extracted data (field: 'extracted').",
        "Return the extracted data to the user in a clean, readable format.",

        # ── Storage Format ──
        "Always save documents with these fields: url, title, raw_content (full markdown), extracted (if mode 2), tags (comma-separated topics).",
        "Always tag with relevant topics so it's searchable later.",

        # ── Quality ──
        "If a scrape fails or returns garbage, say so. Don't pretend you got good data.",
        "If the page requires authentication or is behind a paywall, tell the user upfront.",
    ],
    add_datetime_to_context=True,
    markdown=True,
)

# ─────────────────────────────────────────────
# Agent 4: Crypto Market Watcher
# ─────────────────────────────────────────────
crypto_agent = Agent(
    name="Crypto Watcher",
    id="crypto-watcher",
    role="Cryptocurrency market monitor and alert system",
    model=openrouter_model,
    db=db,
    tools=[WebSearchTools()],  # MCP server for real-time crypto data coming soon
    instructions=[
        "You monitor the crypto market for major moves.",
        "Track BTC, ETH, SOL, and any coins the user specifies.",
        "Alert on significant price swings (>5% in 24h).",
        "Provide brief context on why the move happened.",
    ],
    add_datetime_to_context=True,
    markdown=True,
)

# ─────────────────────────────────────────────
# Agent 5: Calendar Assistant
# ─────────────────────────────────────────────
calendar_agent = Agent(
    name="Calendar Assistant",
    id="calendar-assistant",
    role="Google Calendar manager",
    model=gemini_model,
    db=db,
    tools=[
        GoogleCalendarTools(
            credentials_path=_secret_file("credentials.json"),
            token_path=_secret_file("token.json"),
            allow_update=True,
        ),
    ],
    instructions=[
        "You manage the user's Google Calendar.",
        "Create events when asked — include title, start time, end time, and description if provided.",
        "List upcoming events when asked.",
        "Parse natural language dates and times intelligently (e.g., 'tomorrow at 3pm', 'next Monday').",
        "When the user asks for 'this week': use the current date from context. 'This week' means the current calendar week (Monday 00:00 through Sunday 23:59 in the user's local time). Only list events whose start time falls within that range. If you fetch a broader range from the calendar, filter your response to include only events in the requested period. If there are no events in that period, say so clearly (e.g. 'No events this week.').",
        "Reply with a single, concise response. Do not repeat the same list in different words or in a second paragraph.",
        "When creating events, confirm what was created: title, date, time, and duration.",
        "If the user doesn't specify a duration, default to 1 hour.",
        "If the user doesn't specify a time, ask for clarification.",
        # Resolve event by context — never ask the user for event ID
        "For update or delete: never ask the user for the event ID. You do not know it; the user does not know it. Use list_events or fetch_all_events to get events (each event has an 'id' field). Use that id when calling update_event or delete_event.",
        "When the user says 'the event', 'update the event', 'delete it', or similar without naming one: use conversation context. The event they mean is usually the one just created or last discussed in this conversation. If you just created an event (e.g. for Saturday), 'update the event to be 3 hours' means that Saturday event — update it in place; do not create a new event.",
        "If multiple events could match (e.g. several on different days), ask one short follow-up: e.g. 'Do you mean the one on Saturday or the one today?' Then use the event id from the list/fetch result for the one they mean.",
    ],
    add_datetime_to_context=True,
    markdown=True,
)

# ─────────────────────────────────────────────
# Team: Command Center (auto-routes messages)
# ─────────────────────────────────────────────
command_center = Team(
    name="Command Center",
    id="command-center",
    model=openrouter_model,
    members=[life_sarge, news_team, scraper_agent, crypto_agent, calendar_agent],
    db=db,
    instructions=[
        "You are a personal command center that routes requests to the right specialist.",
        "Analyze the user's message and delegate to the most appropriate team member.",
        "If the message is about tasks, accountability, or daily goals — delegate to Life Sarge.",
        "If it's about news, Twitter/X, or current events — delegate to X News Desk.",
        "If it's about scraping a website or extracting data — delegate to Web Scraper.",
        "If it's about crypto, prices, or market moves — delegate to Crypto Watcher.",
        "If it's about calendar, scheduling, events, or meetings — delegate to Calendar Assistant.",
        "When you delegate to Calendar Assistant: return only that member's response. Do not add your own summary, prefix (e.g. 'OK.'), or repeat the calendar content.",
        "If unclear, ask the user to clarify.",
    ],
    markdown=True,
    add_datetime_to_context=True,
)

# ─────────────────────────────────────────────
# AgentOS with Slack interfaces
# ─────────────────────────────────────────────
agent_os = AgentOS(
    id="personal-command-center",
    agents=[life_sarge, x_fetcher, x_compiler, news_analyst, scraper_agent, crypto_agent, calendar_agent],
    teams=[news_team, command_center],
    db=db,
    interfaces=[
        # Main entry point — routes through Team coordinator
        Slack(team=command_center, prefix="/slack"),
        # Direct access to individual agents
        Slack(agent=life_sarge, prefix="/slack-sarge"),
        Slack(team=news_team, prefix="/slack-news"),
        Slack(agent=scraper_agent, prefix="/slack-scraper"),
        Slack(agent=crypto_agent, prefix="/slack-crypto"),
    ],
)

app = agent_os.get_app()


# ─────────────────────────────────────────────
# Slack Slash Command: /snooze
# ─────────────────────────────────────────────
@app.post("/slack/sarge-snooze", response_class=PlainTextResponse)
async def slack_sarge_snooze(
    text: str = Form(""),
    channel_id: str = Form(""),
):
    """Handle /snooze slash command from Slack."""
    # Only allow in the Sarge channel
    if SARGE_CHANNEL and channel_id != SARGE_CHANNEL:
        return "This command only works in the Life Sarge channel."

    text = text.strip().lower()

    # /snooze status
    if text == "status" or text == "":
        snooze = snooze_collection.find_one({"_id": "sarge"})
        if snooze and snooze.get("until") and snooze["until"] > datetime.now():
            until = snooze["until"].strftime("%A %b %d at %I:%M %p")
            return f"Life Sarge is snoozed until {until}."
        return "Life Sarge is active. No snooze set."

    # /snooze off
    if text == "off":
        snooze_collection.delete_one({"_id": "sarge"})
        return "Snooze cancelled. Life Sarge is back on duty."

    # /snooze <days>
    try:
        days = int(text)
        if days < 1 or days > 30:
            return "Snooze must be between 1 and 30 days."
        until = datetime.now() + timedelta(days=days)
        snooze_collection.update_one(
            {"_id": "sarge"},
            {"$set": {"until": until}},
            upsert=True,
        )
        until_str = until.strftime("%A %b %d at %I:%M %p")
        return f"Life Sarge snoozed for {days} day(s) — until {until_str}."
    except ValueError:
        return "Usage: /snooze <days> | /snooze off | /snooze status"


if __name__ == "__main__":
    agent_os.serve(app="app:app", port=7777, reload=True)
