import re

from telegram import Update
from telegram.ext import ContextTypes
from wcbot.agents.prediction_engine import PredictionEngineAgent, MIN_MODELS_AGREEING, MIN_CONFIDENCE_FOR_PREDICTION
from wcbot.agents.data_ingestion import DataIngestionAgent
from wcbot.agents.state_manager import StateManagerAgent
from wcbot.handlers.tournament import is_round_of_32_request, reply_round_of_32
from wcbot.utils.formatting import format_prediction, format_tentative_prediction
from wcbot.utils.teams import normalize_team_name, unknown_team_message
from wcbot.utils.live_tournament import (
    fixture_context,
    format_completed_match,
    format_live_fixture_note,
    format_unscheduled_match,
)
from wcbot.models.prediction import Prediction
from uuid import uuid4


async def predict_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text[len("/predict "):].strip()
    if is_round_of_32_request(text):
        await reply_round_of_32(update, context)
        return

    if not text or "vs" not in text:
        await update.message.reply_markdown(
            "Usage: `/predict <home> vs <away>`\n\n"
            "Use `/fixtures` to choose a confirmed ongoing World Cup match.\n\n"
            "For knockout qualification, try `/predict round of 32`."
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

    ingestion: DataIngestionAgent = context.bot_data["data_ingestion"]
    engine: PredictionEngineAgent = context.bot_data["prediction_engine"]
    state: StateManagerAgent = context.bot_data["state_manager"]

    fixture = await ingestion.find_world_cup_match(home, away)
    if not fixture:
        upcoming = await ingestion.fetch_world_cup_events()
        await update.message.reply_markdown(format_unscheduled_match(home, away, upcoming))
        return
    if fixture.get("status") == "completed":
        await update.message.reply_markdown(format_completed_match(fixture))
        return

    home = fixture["home_team"]
    away = fixture["away_team"]
    await update.message.reply_markdown(f"🧠 Analyzing confirmed fixture *{home} vs {away}*...")

    user = update.effective_user
    await state.create_user(
        chat_id=user.id,
        username=user.username,
        first_name=user.first_name,
        language=user.language_code or "en",
    )

    result = await engine.predict(home, away, fixture_context(fixture))

    if result.abstained:
        text = format_tentative_prediction(
            result,
            home,
            away,
            MIN_MODELS_AGREEING,
            MIN_CONFIDENCE_FOR_PREDICTION,
        ) + format_live_fixture_note(fixture)
        await update.message.reply_markdown(text)
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

    await update.message.reply_markdown(
        format_prediction(result, home, away) + format_live_fixture_note(fixture)
    )
