from telegram import Update
from telegram.ext import ContextTypes
from wcbot.agents.prediction_engine import PredictionEngineAgent
from wcbot.agents.data_ingestion import DataIngestionAgent


async def value_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text[len("/value "):].strip()
    if not text or "vs" not in text:
        await update.message.reply_markdown(
            "Usage: `/value Brazil vs Argentina`\n\n"
            "Compares model confidence vs market odds to find value picks."
        )
        return

    import re
    parts = re.split(r'\s+vs\s+', text, maxsplit=1)
    if len(parts) != 2:
        return

    home, away = parts[0].strip(), parts[1].strip()
    await update.message.reply_markdown(f"🔍 Analyzing *{home} vs {away}* for value...")

    engine: PredictionEngineAgent = context.bot_data["prediction_engine"]
    ingestion: DataIngestionAgent = context.bot_data["data_ingestion"]

    result = await engine.predict(home, away)
    if result.abstained:
        await update.message.reply_markdown(
            f"🤷 *{home} vs {away}* — too close to call confidently. No value analysis available."
        )
        return

    match_id = f"{home.lower()}-{away.lower()}"
    odds = await ingestion.fetch_odds(match_id)

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
