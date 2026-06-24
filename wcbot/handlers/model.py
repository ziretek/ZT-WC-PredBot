from telegram import Update
from telegram.ext import ContextTypes
from wcbot.agents.prediction_engine import PredictionEngineAgent
from wcbot.utils.formatting import format_model_card


async def model_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    engine: PredictionEngineAgent = context.bot_data["prediction_engine"]
    card = await engine.get_model_card()
    await update.message.reply_markdown(format_model_card(card))
