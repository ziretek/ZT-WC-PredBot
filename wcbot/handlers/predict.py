import re

from telegram import Update
from telegram.ext import ContextTypes
from wcbot.agents.prediction_engine import PredictionEngineAgent, MIN_MODELS_AGREEING, MIN_CONFIDENCE_FOR_PREDICTION
from wcbot.agents.state_manager import StateManagerAgent
from wcbot.utils.formatting import format_prediction
from wcbot.utils.teams import normalize_team_name, unknown_team_message
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

    await update.message.reply_markdown(f"🧠 ZT WC PredBot is thinking... analyzing *{home} vs {away}*")

    engine: PredictionEngineAgent = context.bot_data["prediction_engine"]
    state: StateManagerAgent = context.bot_data["state_manager"]
    user = update.effective_user
    await state.create_user(
        chat_id=user.id,
        username=user.username,
        first_name=user.first_name,
        language=user.language_code or "en",
    )

    result = await engine.predict(home, away)

    if result.abstained:
        await update.message.reply_markdown(
            f"🤷 *{home} vs {away}* — too close to call confidently.\n\n"
            f"The ensemble requires ≥{MIN_MODELS_AGREEING} of 4 models agreeing "
            f"at ≥{MIN_CONFIDENCE_FOR_PREDICTION:.0%} confidence to issue a prediction.\n\n"
            f"Try a match with a clearer favourite, or use `/simulate` for tournament odds."
        )
        return

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
