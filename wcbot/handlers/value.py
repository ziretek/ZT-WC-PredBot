from telegram import Update
from telegram.ext import ContextTypes
from wcbot.agents.prediction_engine import PredictionEngineAgent
from wcbot.agents.data_ingestion import DataIngestionAgent
from wcbot.utils.teams import normalize_team_name, unknown_team_message
from wcbot.utils.live_tournament import (
    fixture_context,
    format_completed_match,
    format_unscheduled_match,
)


async def value_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text[len("/value "):].strip()
    if not text or "vs" not in text:
        await update.message.reply_markdown(
            "Usage: `/value <home> vs <away>`\n\n"
            "Choose a confirmed match from `/fixtures`.\n\n"
            "Compares model confidence vs market odds to find value picks."
        )
        return

    import re
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
    engine: PredictionEngineAgent = context.bot_data["prediction_engine"]
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
    await update.message.reply_markdown(f"🔍 Analyzing *{home} vs {away}* for value...")
    result = await engine.predict(home, away, fixture_context(fixture))
    if result.abstained:
        await update.message.reply_markdown(
            f"🤷 *{home} vs {away}* — too close to call confidently. No value analysis available."
        )
        return

    odds = fixture

    msg = (
        f"💰 *Value Analysis: {home} vs {away}*\n\n"
        f"*Model Prediction:*\n"
        f"• Winner: *{result.winner}* ({result.confidence:.0%} confidence)\n"
        f"• Score: {result.home_score}–{result.away_score}\n\n"
    )

    if odds:
        home_odds = odds.get("home_odds", 0)
        draw_odds = odds.get("draw_odds", 0)
        away_odds = odds.get("away_odds", 0)
        if home_odds:
            implied = 1.0 / home_odds
            msg += f"*Market Odds:*\n"
            msg += f"• {home}: {home_odds:.2f} (implied {implied:.0%})\n"
            msg += f"• Draw: {draw_odds:.2f}\n" if draw_odds else ""
            msg += f"• {away}: {away_odds:.2f}\n" if away_odds else ""
            if result.winner == home and home_odds:
                gap = result.confidence - implied
                if gap > 0.10:
                    msg += f"\n✅ *Value pick!* Model sees {gap:.0%} more probability than market.\n"
                elif gap < -0.10:
                    msg += f"\n⚠️ Market is {abs(gap):.0%} more confident than model.\n"
                else:
                    msg += f"\nModel and market are closely aligned.\n"
        else:
            msg += f"\nOdds data available but couldn't compute comparison.\n"
    else:
        msg += f"*Market Odds:* Not available (requires ODDS_API_KEY).\n"

    msg += f"\nUse `/predict {home} vs {away}` for full prediction details."
    await update.message.reply_markdown(msg)
