from telegram import Update
from telegram.ext import ContextTypes
from wcbot.agents.prediction_engine import PredictionEngineAgent
from wcbot.utils.formatting import format_simulation


async def simulate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    engine: PredictionEngineAgent = context.bot_data["prediction_engine"]

    await update.message.reply_markdown("🎲 Running 10,000 tournament simulations...")

    results = await engine.simulate_tournament(iterations=10000)

    await update.message.reply_markdown(format_simulation(results))
