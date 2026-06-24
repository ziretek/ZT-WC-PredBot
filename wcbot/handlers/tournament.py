from telegram import Update
from telegram.ext import ContextTypes

from wcbot.agents.data_ingestion import DataIngestionAgent
from wcbot.agents.prediction_engine import PredictionEngineAgent
from wcbot.utils.formatting import format_simulation


def is_round_of_32_request(text: str) -> bool:
    lower = text.lower()
    return any(
        phrase in lower
        for phrase in (
            "round of 32",
            "round of thirty two",
            "round of thirty-two",
            "r32",
            "ro32",
            "knockout",
            "next round",
        )
    )


async def round32_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply_round_of_32(update, context)


async def reply_round_of_32(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ingestion: DataIngestionAgent = context.bot_data["data_ingestion"]
    engine: PredictionEngineAgent = context.bot_data["prediction_engine"]

    await update.message.reply_markdown("🏆 Checking Round of 32 picture...")
    advancing = await ingestion.fetch_round_of_32()

    if advancing:
        text = "🏆 *Round of 32 — Advancing Teams*\n\n"
        for entry in advancing:
            text += (
                f"*{entry.get('group', '?')}* — {entry.get('name', 'Unknown')} "
                f"({entry.get('points', 0)}pts, GD {entry.get('goal_diff', 0):+d})\n"
            )
        text += "\nUse `/predict <home> vs <away>` for match predictions."
        await update.message.reply_markdown(text)
        return

    if engine and engine.llm:
        llm_answer = await engine.llm.answer_question(
            "Give a concise Round of 32 outlook for the 2026 World Cup. "
            "If live standings are unavailable, say this is an outlook, not confirmed standings."
        )
        if llm_answer:
            await update.message.reply_markdown(llm_answer)
            return

    await update.message.reply_markdown(
        "I can predict individual matches with `/predict Brazil vs Argentina`, "
        "but Round of 32 standings require live group data from `SPORTS_API_KEY`.\n\n"
        "Try `/winner` for champion odds or `/simulate` for tournament odds."
    )


async def winner_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    engine: PredictionEngineAgent = context.bot_data["prediction_engine"]

    await update.message.reply_markdown("🏆 Forecasting likely World Cup winners...")
    results = await engine.simulate_tournament(iterations=10000)
    champion_pct = results.get("champion_pct", {})

    if not champion_pct:
        await update.message.reply_markdown(
            "I could not generate champion odds right now. Try `/simulate` again in a moment."
        )
        return

    text = "🏆 *World Cup Winner Forecast*\n\n"
    for rank, (team, pct) in enumerate(champion_pct.items(), 1):
        if rank > 8:
            break
        text += f"{rank}. *{team}* — {pct}%\n"

    text += "\nThis is a Monte Carlo forecast from current model ratings, not a guarantee."
    text += "\n\nUse `/simulate` for top-four odds too."
    await update.message.reply_markdown(text)


async def tournament_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    engine: PredictionEngineAgent = context.bot_data["prediction_engine"]
    await update.message.reply_markdown("🎲 Running tournament forecast...")
    results = await engine.simulate_tournament(iterations=10000)
    await update.message.reply_markdown(format_simulation(results))
