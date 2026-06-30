from telegram import Update
from telegram.ext import ContextTypes

from wcbot.agents.data_ingestion import DataIngestionAgent
from wcbot.agents.prediction_engine import PredictionEngineAgent
from wcbot.utils.live_tournament import format_kickoff, format_winner_market


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

    await update.message.reply_markdown("🏆 Checking Round of 32 picture...")
    fixtures = await ingestion.fetch_world_cup_events()
    recent = [match for match in await ingestion.fetch_world_cup_scores() if match.get("status") == "completed"]

    if fixtures or recent:
        lines = ["🏆 *Current World Cup Knockout Picture*", ""]
        if recent:
            lines.append("*Recent results:*" )
            for match in recent[:6]:
                lines.append(
                    f"• {match['home_team']} {match.get('home_score', '?')}–"
                    f"{match.get('away_score', '?')} {match['away_team']}"
                )
            lines.append("")
        if fixtures:
            lines.append("*Confirmed upcoming fixtures:*")
            for fixture in fixtures[:12]:
                lines.append(
                    f"• {fixture['home_team']} vs {fixture['away_team']} — "
                    f"{format_kickoff(fixture.get('commence_time', ''))}"
                )
        lines.extend([
            "",
            "The provider does not label round stages, so this is the current live knockout feed rather than a guessed bracket.",
            "Use `/fixtures` for the complete upcoming list.",
        ])
        await update.message.reply_markdown("\n".join(lines))
        return

    await update.message.reply_markdown(
        "🏆 *Round of 32*\n\nThe live World Cup fixture feed is unavailable right now.\n\n"
        "Try `/fixtures` again shortly or use `/winner` for the current outright market."
    )


async def winner_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ingestion: DataIngestionAgent = context.bot_data["data_ingestion"]
    engine: PredictionEngineAgent = context.bot_data["prediction_engine"]

    await update.message.reply_markdown("🏆 Loading current World Cup winner market...")
    market = await ingestion.fetch_world_cup_winner_odds()
    if market:
        await update.message.reply_markdown(format_winner_market(market))
        return

    await update.message.reply_markdown("Live winner odds unavailable; running model simulation...")
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
    await winner_handler(update, context)
