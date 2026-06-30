import re

from telegram import Update
from telegram.ext import ContextTypes
from wcbot.agents.data_ingestion import DataIngestionAgent
from wcbot.realtime import RealtimeEngine
from wcbot.utils.teams import normalize_team_name, unknown_team_message
from wcbot.utils.live_tournament import format_completed_match, format_unscheduled_match


async def track_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text[len("/track "):].strip()
    if not text or "vs" not in text:
        await update.message.reply_markdown(
            "Usage: `/track Brazil vs Argentina`\n\n"
            "Starts monitoring a confirmed match for score changes, odds swings, "
            "and model updates."
        )
        return

    parts = re.split(r'\s+vs\s+', text, maxsplit=1)
    if len(parts) != 2:
        return

    raw_home, raw_away = parts[0].strip(), parts[1].strip()
    home = normalize_team_name(raw_home)
    away = normalize_team_name(raw_away)
    if not home:
        await update.message.reply_markdown(unknown_team_message(raw_home))
        return
    if not away:
        await update.message.reply_markdown(unknown_team_message(raw_away))
        return
    if home == away:
        await update.message.reply_markdown("Choose two different teams.")
        return
    ingestion: DataIngestionAgent = context.bot_data["data_ingestion"]
    fixture = await ingestion.find_world_cup_match(home, away)
    if not fixture:
        await update.message.reply_markdown(
            format_unscheduled_match(home, away, await ingestion.fetch_world_cup_events())
        )
        return
    if fixture.get("status") == "completed":
        await update.message.reply_markdown(format_completed_match(fixture))
        return

    home = fixture["home_team"]
    away = fixture["away_team"]
    match_id = fixture["id"]

    realtime: RealtimeEngine = context.bot_data["realtime"]
    realtime.track_match(match_id, home, away)

    await update.message.reply_markdown(
        f"🔴 *Live Tracking Enabled*\n\n"
        f"Now monitoring *{home} vs {away}* in real-time.\n\n"
        f"• Score changes → push alert to subscribers\n"
        f"• Odds swings >15% → alert with details\n"
        f"• Match end → Elo ratings auto-updated\n\n"
        f"Tracking uses the confirmed FIFA World Cup event ID.\n\n"
        f"Use `/subscribe {home}` or `/subscribe {away}` to get alerts."
    )


async def rtstatus_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    realtime: RealtimeEngine = context.bot_data["realtime"]
    stats = realtime.stats
    status = "🟢 Running" if stats["running"] else "🔴 Stopped"

    await update.message.reply_markdown(
        f"📡 *Realtime Engine Status*\n\n"
        f"Status: {status}\n"
        f"Matches tracked: {stats['matches_tracked']}\n"
        f"Currently live: {stats['matches_live']}\n"
        f"Odds monitored: {stats['odds_tracked']}\n"
        f"Lineups watched: {stats['lineups_tracked']}\n\n"
        f"Use `/track <home> vs <away>` to add a match."
    )
