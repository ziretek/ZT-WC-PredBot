from telegram import Update
from telegram.ext import ContextTypes
from wcbot.agents.data_ingestion import DataIngestionAgent
from wcbot.utils.formatting import format_standings


async def standings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ingestion: DataIngestionAgent = context.bot_data["data_ingestion"]
    standings = await ingestion.fetch_standings()
    await update.message.reply_markdown(format_standings(standings))
