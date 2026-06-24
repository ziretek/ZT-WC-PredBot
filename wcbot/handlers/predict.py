import re

from telegram import Update
from telegram.ext import ContextTypes
from wcbot.agents.prediction_engine import PredictionEngineAgent
from wcbot.agents.state_manager import StateManagerAgent
from wcbot.utils.formatting import format_prediction
from wcbot.models.prediction import Prediction
from uuid import uuid4


async def predict_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text[len("/predict "):].strip()
    if not text or "vs" not in text:
        await update.message.reply_markdown(
            "Usage: `/predict Brazil vs Argentina`"
        )
        return

    parts = re.split(r'\s+vs\s+', text, maxsplit=1)
    if len(parts) != 2:
        await update.message.reply_markdown("Format: `/predict <home> vs <away>`")
        return

    home, away = parts[0].strip(), parts[1].strip()

    await update.message.reply_markdown(f"🧠 ZT WC PredBot is thinking... analyzing *{home} vs {away}*")

    engine: PredictionEngineAgent = context.bot_data["prediction_engine"]
    state: StateManagerAgent = context.bot_data["state_manager"]

    result = await engine.predict(home, away)

    pred = Prediction(
        prediction_id=str(uuid4()),
        user_id=update.effective_user.id,
        match_id=f"{home.lower()}-{away.lower()}",
        home_team=home,
        away_team=away,
        predicted_home_score=result.home_score,
        predicted_away_score=result.away_score,
        predicted_winner=result.winner,
        confidence=result.confidence,
        model_version=result.model_version,
    )
    await state.save_prediction(update.effective_user.id, pred.match_id, pred)

    await update.message.reply_markdown(format_prediction(result, home, away))
