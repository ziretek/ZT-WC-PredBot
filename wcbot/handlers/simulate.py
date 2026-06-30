from telegram import Update
from telegram.ext import ContextTypes
from wcbot.agents.prediction_engine import PredictionEngineAgent
from wcbot.agents.data_ingestion import DataIngestionAgent
from wcbot.utils.formatting import format_simulation
from wcbot.utils.live_tournament import format_winner_market


async def simulate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    engine: PredictionEngineAgent = context.bot_data["prediction_engine"]
    ingestion: DataIngestionAgent = context.bot_data["data_ingestion"]

    market = await ingestion.fetch_world_cup_winner_odds()
    if market:
        await update.message.reply_markdown(
            format_winner_market(market, "Ongoing Tournament Forecast")
            + "\n\nA random bracket simulation is disabled while the tournament is active because the feed does not expose stage-labelled bracket slots."
        )
        return

    await update.message.reply_markdown("🎲 Running 10,000 tournament simulations...")

    results = await engine.simulate_tournament(iterations=10000)

    await update.message.reply_markdown(format_simulation(results))
