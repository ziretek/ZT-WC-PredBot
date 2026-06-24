from telegram import Update
from telegram.ext import ContextTypes
from wcbot.agents.data_ingestion import DataIngestionAgent
from wcbot.utils.formatting import format_standings


async def standings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ingestion: DataIngestionAgent = context.bot_data["data_ingestion"]
    standings = await ingestion.fetch_standings()
    if not standings:
        await update.message.reply_markdown(
            "📊 *Group Standings*\n\n"
            "Live standings require a `SPORTS_API_KEY` configured in `.env`.\n\n"
            "The prediction engine works without it — try `/predict Brazil vs Argentina`."
        )
        return

    normalized = [
        normalized_entry
        for entry in standings
        if (normalized_entry := ingestion._normalize_standing_entry(entry))
    ]
    if not normalized:
        await update.message.reply_markdown(
            "📊 *Group Standings*\n\n"
            "The sports API is reachable, but it did not return World Cup group-table data "
            "with team names and groups.\n\n"
            "Try `/simulate` for a tournament outlook or `/predict Brazil vs Argentina` "
            "for a match prediction."
        )
        return

    await update.message.reply_markdown(format_standings(normalized))
