"""
Heartbeat scheduler — triggers agent runs on randomized schedules.
Runs alongside the main AgentOS server (app.py).

Usage:
    python scheduler.py
"""

import os
import random
from datetime import datetime, timedelta

import httpx
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.date import DateTrigger
from dotenv import load_dotenv
from pymongo import MongoClient
from slack_sdk import WebClient

load_dotenv()

AGNO_BASE_URL = os.getenv("AGNO_BASE_URL", "http://localhost:7777")
slack_client = WebClient(token=os.getenv("SLACK_TOKEN"))

# Slack channel IDs — right-click channel in Slack → "View channel details" → copy ID at bottom
SARGE_CHANNEL = os.getenv("SLACK_SARGE_CHANNEL", "")  # #life-goals channel ID

# MongoDB for snooze check
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "agno_agents")
mongo_client = MongoClient(MONGO_URL)
snooze_collection = mongo_client[MONGO_DB_NAME]["sarge_snooze"]

scheduler = BlockingScheduler()


def is_sarge_snoozed() -> bool:
    """Check if Life Sarge is currently snoozed."""
    snooze = snooze_collection.find_one({"_id": "sarge"})
    if snooze and snooze.get("until") and snooze["until"] > datetime.now():
        print(f"[life-sarge] Snoozed until {snooze['until']} — skipping")
        return True
    return False

# Allowed check-in windows (hour ranges, inclusive)
WEEKDAY_WINDOWS = [(8, 8), (17, 22)]  # 8-9 AM, 5-10 PM
WEEKEND_WINDOWS = [(8, 22)]           # 8 AM - 10 PM

SARGE_CHECKIN_PROMPTS = [
    "Check in on Servio about training. Did he hit the gym? If not, remind him what separates Top Gs from NPCs. If he ghosted the last check-in, open with the roast.",
    "Check in on Servio about meals. Did he eat enough to hit his weight goals? If he's eating garbage, destroy him. Champions don't fuel up on trash.",
    "Check in on Servio about sleep. Is he winding down like a disciplined man or doom-scrolling like a dopamine addict? Call it out.",
    "Mindset check on Servio. Is he locked in or drifting? One focused question. If he's slipping, remind him the matrix wins when he gets comfortable.",
    "Check in on Servio. Did he train today? If not, he better have a damn good reason. If he did, did he push himself hard or just go through the motions like an NPC? Every rep he skips, someone hungrier is doing it.",
    "Check in on Servio. What did he accomplish since last check-in? If nothing — 'Brother, you're moving like a man with no purpose. Fix it.'",
]


def post_to_slack(channel: str, text: str):
    """Send a message to a Slack channel."""
    if not channel:
        print("[slack] No channel ID set, skipping Slack post")
        return
    try:
        slack_client.chat_postMessage(channel=channel, text=text)
        print(f"[slack] Posted to {channel}")
    except Exception as e:
        print(f"[slack] ERROR — {e}")


def trigger_agent(agent_id: str, message: str, slack_channel: str = "", session_id: str | None = None):
    """POST to the AgentOS run endpoint for a given agent, optionally post response to Slack."""
    url = f"{AGNO_BASE_URL}/agents/{agent_id}/runs"
    data = {"message": message, "stream": "false"}
    if session_id:
        data["session_id"] = session_id
    try:
        resp = httpx.post(url, data=data, timeout=300)
        print(f"[{agent_id}] {resp.status_code} — {message[:60]}")
        if slack_channel and resp.status_code == 200:
            try:
                run_data = resp.json()
                content = run_data.get("content", "")
                if content:
                    post_to_slack(slack_channel, content)
                else:
                    print(f"[{agent_id}] No content in response")
            except Exception as e:
                print(f"[{agent_id}] Failed to parse response: {e}")
    except httpx.RequestError as e:
        print(f"[{agent_id}] ERROR — {e}")


def trigger_team(team_id: str, message: str, slack_channel: str = "", session_id: str | None = None):
    """POST to the AgentOS run endpoint for a given team, optionally post response to Slack."""
    url = f"{AGNO_BASE_URL}/teams/{team_id}/runs"
    data = {"message": message, "stream": "false"}
    if session_id:
        data["session_id"] = session_id
    try:
        resp = httpx.post(url, data=data, timeout=300)
        print(f"[{team_id}] {resp.status_code} — {message[:60]}")
        if slack_channel and resp.status_code == 200:
            try:
                run_data = resp.json()
                content = run_data.get("content", "")
                if content:
                    post_to_slack(slack_channel, content)
                else:
                    print(f"[{team_id}] No content in response")
            except Exception as e:
                print(f"[{team_id}] Failed to parse response: {e}")
    except httpx.RequestError as e:
        print(f"[{team_id}] ERROR — {e}")


def trigger_sarge_checkin(prompt: str):
    """Trigger a Sarge check-in, respecting snooze."""
    if is_sarge_snoozed():
        return
    trigger_agent("life-sarge", prompt, slack_channel=SARGE_CHANNEL)


def random_times_in_windows(windows: list[tuple[int, int]], count: int, base_date: datetime) -> list[datetime]:
    """Pick `count` random datetimes spread across the given hour windows for a specific date."""
    all_minutes = []
    for start_h, end_h in windows:
        for h in range(start_h, end_h + 1):
            for m in range(0, 60):
                all_minutes.append(base_date.replace(hour=h, minute=m, second=0, microsecond=0))

    # Ensure we don't pick times in the past
    now = datetime.now()
    all_minutes = [t for t in all_minutes if t > now + timedelta(minutes=5)]

    if not all_minutes:
        return []

    count = min(count, len(all_minutes))

    # Spread picks apart by at least 90 min to avoid clustering
    picks = []
    candidates = all_minutes[:]
    for _ in range(count):
        if not candidates:
            break
        chosen = random.choice(candidates)
        picks.append(chosen)
        candidates = [t for t in candidates if abs((t - chosen).total_seconds()) > 5400]  # 90 min gap

    return sorted(picks)


def plan_sarge_checkins():
    """Called daily at ~5:50 AM. Picks 1-3 random check-in times for today and schedules them."""
    today = datetime.now().replace(second=0, microsecond=0)
    is_weekend = today.weekday() >= 5

    windows = WEEKEND_WINDOWS if is_weekend else WEEKDAY_WINDOWS
    count = random.randint(1, 3)

    times = random_times_in_windows(windows, count, today)

    # Remove any leftover one-shot sarge check-ins from yesterday
    for job in scheduler.get_jobs():
        if job.id.startswith("sarge-random-"):
            job.remove()

    for i, t in enumerate(times):
        prompt = random.choice(SARGE_CHECKIN_PROMPTS)
        scheduler.add_job(
            trigger_sarge_checkin,
            trigger=DateTrigger(run_date=t),
            args=[prompt],
            id=f"sarge-random-{i}",
            replace_existing=True,
        )

    time_strs = [t.strftime("%I:%M %p") for t in times]
    print(f"[life-sarge] Planned {len(times)} check-in(s) for today: {', '.join(time_strs)}")


# ─────────────────────────────────────────────
# Daily planner — runs at 5:50 AM, schedules
# that day's randomized Life Sarge check-ins
# ─────────────────────────────────────────────
@scheduler.scheduled_job("cron", hour=5, minute=50, id="sarge-daily-planner")
def sarge_daily_planner():
    plan_sarge_checkins()


# ─────────────────────────────────────────────
# Life Sarge: Weekly report — Sunday 8 PM
# (kept fixed — you want this predictably)
# ─────────────────────────────────────────────
@scheduler.scheduled_job("cron", day_of_week="sun", hour=20, minute=0, id="sarge-weekly-report")
def sarge_weekly_report():
    if is_sarge_snoozed():
        return
    trigger_agent("life-sarge", "Compile the full weekly performance report for Servio. Include: wins, failures, patterns, scores, and next week's plan. Be savage. No sugar coating.", slack_channel=SARGE_CHANNEL)


# ─────────────────────────────────────────────
# X News Desk: Morning briefing — 8 AM daily
# ─────────────────────────────────────────────
@scheduler.scheduled_job("cron", hour=8, minute=0, id="news-morning-briefing")
def news_morning_briefing():
    trigger_team("x-news-desk", "Morning news briefing. Fetch the latest from X and the web on business, finance, crypto, tech/AI, politics, and anything dominating the timeline. Full digest.")


# ─────────────────────────────────────────────
# X News Desk: Evening recap — 6 PM daily
# ─────────────────────────────────────────────
@scheduler.scheduled_job("cron", hour=18, minute=0, id="news-evening-recap")
def news_evening_recap():
    trigger_team("x-news-desk", "Evening news recap. What happened today since the morning briefing? Focus on developments, market moves, and anything new that broke. Keep it tight.")


# ─────────────────────────────────────────────
# Crypto Watcher: Market check every 15 min
# ─────────────────────────────────────────────
@scheduler.scheduled_job("cron", minute="*/15", id="crypto-monitor")
def crypto_monitor():
    trigger_agent("crypto-watcher", "Quick check: BTC, ETH, SOL — any move over 5% in 24h? If nothing major, just say 'no major moves'. Keep it brief.")


if __name__ == "__main__":
    # Plan today's check-ins immediately on startup
    plan_sarge_checkins()

    print("\nScheduler started. Persistent jobs:")
    for job in scheduler.get_jobs():
        print(f"  - {job.id}: {job.trigger}")
    scheduler.start()
