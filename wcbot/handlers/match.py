import re

from telegram import Update
from telegram.ext import ContextTypes
from wcbot.agents.data_ingestion import DataIngestionAgent
from wcbot.agents.prediction_engine import PredictionEngineAgent


async def match_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text[len("/match "):].strip()
    if not text or "vs" not in text:
        await update.message.reply_markdown("Usage: `/match Brazil vs Argentina`")
        return

    parts = re.split(r'\s+vs\s+', text, maxsplit=1)
    if len(parts) != 2:
        return

    home, away = parts[0].strip(), parts[1].strip()

    await update.message.reply_markdown(f"📊 Gathering dossier for *{home} vs {away}*...")

    ingestion: DataIngestionAgent = context.bot_data["data_ingestion"]
    engine: PredictionEngineAgent = context.bot_data["prediction_engine"]

    h2h = await ingestion.fetch_head2head(home, away)
    prediction = await engine.predict(home, away)

    msg = (
        f"📊 *{home} vs {away} — Match Dossier*\n\n"
        f"*Head-to-Head:*\n"
        f"• {home}: {h2h.get('team1_wins', 0)} wins\n"
        f"• {away}: {h2h.get('team2_wins', 0)} wins\n"
        f"• Draws: {h2h.get('draws', 0)}\n\n"
        f"*AI Verdict:*\n"
        f"• Winner: *{prediction.winner}*\n"
        f"• Score: {prediction.home_score}-{prediction.away_score}\n"
        f"• Confidence: {prediction.confidence:.0%}\n"
        f"• Model: `{prediction.model_version}`\n\n"
        f"*Analysis:*\n{prediction.reasoning}"
    )

    await update.message.reply_markdown(msg)
